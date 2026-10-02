"""Execute workflow scripts with real shells and isolated consumer repositories."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


def step(name, identity):
    return next(s for job in workflow(name)['jobs'].values() for s in job.get('steps', []) if s.get('id', s.get('name')) == identity)


class Scripts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'nested project'
        self.project.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'], GITHUB_WORKSPACE=str(self.root), RUNNER_TEMP=str(self.root), RUNNER_OS='Linux', RUNNER_ARCH='X64', GITHUB_EVENT_NAME='push', GITHUB_REF='refs/heads/main', GITHUB_REF_NAME='main', GITHUB_REPOSITORY='owner/project', GITHUB_OUTPUT=str(self.root / 'outputs'), GITHUB_STEP_SUMMARY=str(self.root / 'summary'), GITHUB_PATH=str(self.root / 'path'))

    def stub(self, name, source):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\n' + source)
        path.chmod(0o755)

    def run_step(self, name, identity, **env):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(name, identity)['run']], cwd=self.project, env=dict(self.env, **env), text=True, capture_output=True, timeout=45)

    def okay(self, result):
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_all_embedded_python_compiles_and_shells_parse(self):
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            for job in yaml.safe_load(path.read_text())['jobs'].values():
                for script in job.get('steps', []):
                    if 'run' not in script:
                        continue
                    with self.subTest(workflow=path.name, step=script.get('name')):
                        parsed = subprocess.run(['bash', '-n'], input=script['run'], text=True, capture_output=True)
                        self.okay(parsed)
                        for block in re.findall(r"<<'PY'[^\n]*\n(.*?)\nPY(?:\n|$)", script['run'], re.S):
                            compile(block, path.name, 'exec')

    def task_env(self, **changes):
        defaults = dict(DEFAULT_TASK='ci', TASK_PREFIX='', TASK_ENV='', TASK_JOBS='4', PHASE_INSTALL='false', PHASE_LINT='false', PHASE_BUILD='false', PHASE_TEST='false', PHASE_VET='false', PHASE_FMT='false')
        return dict(defaults, **changes)

    def test_tasks_use_one_process_and_separators_without_shell_evaluation(self):
        self.stub('mise', 'import json, sys\nprint(json.dumps(sys.argv[1:]))\n')
        result = self.run_step('ci.yml', 'tasks', **self.task_env(PHASE_INSTALL='true', PHASE_TEST='true', TASK_ENV='VALUE=a "quoted" $(touch injected)\n'))
        self.okay(result)
        args = json.loads(result.stdout)
        self.assertEqual(['run', '--skip-tools', '--jobs', '4', 'install', ':::', 'test'], args)
        self.assertFalse((self.project / 'injected').exists())
        for change in [dict(TASK_ENV='PATH=bad'), dict(DEFAULT_TASK=''), dict(DEFAULT_TASK='ci;echo injected'), dict(TASK_JOBS='0'), dict(TASK_ENV='bad line')]:
            with self.subTest(change=change):
                self.assertNotEqual(0, self.run_step('ci.yml', 'tasks', **self.task_env(**change)).returncode)

    def test_real_mise_graph_installs_shared_dependency_once(self):
        mise = shutil.which('mise')
        if not mise:
            self.fail('mise must be installed to verify task graph behavior')
        (self.bin / 'mise').symlink_to(mise)
        (self.project / 'mise.toml').write_text('''[tasks.install]
run = "echo install >> count"
[tasks.build]
depends = ["install"]
run = "test -f count"
[tasks.test]
depends = ["install"]
run = "test -f count"
''')
        result = self.run_step('ci.yml', 'tasks', **self.task_env(PHASE_INSTALL='true', PHASE_BUILD='true', PHASE_TEST='true'), MISE_TRUSTED_CONFIG_PATHS=str(self.root), MISE_YES='1')
        self.okay(result)
        self.assertEqual('install\n', (self.project / 'count').read_text())
        self.assertNotEqual(0, self.run_step('ci.yml', 'tasks', **self.task_env(DEFAULT_TASK='missing'), MISE_TRUSTED_CONFIG_PATHS=str(self.root)).returncode)

    def test_artifact_paths_apply_directory_to_every_line_and_reject_escape(self):
        self.okay(self.run_step('ci.yml', 'paths', BUILD_PATHS='dist\ncoverage/out\n!dist/private\n', FAILURE_PATHS='logs'))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        for suffix in ['dist', 'coverage/out', 'dist/private', 'logs']:
            self.assertIn(str(self.project / suffix), output)
        self.assertNotEqual(0, self.run_step('ci.yml', 'paths', BUILD_PATHS='../../outside', FAILURE_PATHS='').returncode)

    def test_adapter_artifact_paths_apply_nested_directory_to_every_line(self):
        for name in ['go-ci.yml', 'aube-ci.yml']:
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step(name, 'paths', COVERAGE_PATHS='coverage.out\nreports/*.xml\n!reports/private', FAILURE_PATHS='logs\nerrors'))
            output = Path(self.env['GITHUB_OUTPUT']).read_text()
            for path in ['coverage.out', 'reports/*.xml', 'reports/private', 'logs', 'errors']:
                self.assertIn(str(self.project / path), output)
            self.assertNotEqual(0, self.run_step(name, 'paths', COVERAGE_PATHS='../../outside', FAILURE_PATHS='').returncode)

    def test_cache_metadata_uses_project_and_runtime_and_browser_opt_in(self):
        (self.project / 'package-lock.json').write_text('{}')
        self.stub('npm', "print('/tmp/npm-store')\n")
        self.stub('node', "print('v24.0.0')\n")
        self.okay(self.run_step('ci.yml', 'cache-metadata', EXTRA_PATHS='', PLAYWRIGHT_CACHE='false'))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        self.assertIn('/tmp/npm-store', output)
        self.assertNotIn('ms-playwright', output)
        first_scope = re.search(r'scope=(.*)', output).group(1)
        self.project = self.root / 'another project'
        self.project.mkdir()
        self.okay(self.run_step('ci.yml', 'cache-metadata', EXTRA_PATHS='', PLAYWRIGHT_CACHE='true'))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        self.assertIn('ms-playwright', output)
        self.assertNotEqual(first_scope, re.findall(r'scope=(.*)', output)[-1])

    def test_installed_tool_paths_expose_selected_runtime_without_shims(self):
        selected = self.root / 'selected runtime' / 'bin'
        selected.mkdir(parents=True)
        (selected / 'node').write_text('#!/bin/sh\necho v24.0.0\n')
        (selected / 'node').chmod(0o755)
        self.stub('mise', 'print(' + repr(str(selected) + '\n' + str(self.root / 'missing')) + ')\n')
        self.stub('node', "print('v22.0.0')\n")
        for name in ['ci.yml', 'contract-tests.yml']:
            self.okay(self.run_step(name, 'Expose installed tool binaries'))
        paths = Path(self.env['GITHUB_PATH']).read_text().splitlines()
        self.assertEqual([str(selected), str(selected)], paths)
        selected_env = dict(self.env, PATH=paths[0] + os.pathsep + self.env['PATH'])
        result = subprocess.run(['node', '--version'], env=selected_env, text=True, capture_output=True)
        self.okay(result)
        self.assertEqual('v24.0.0', result.stdout.strip())

    def test_documented_callers_match_required_inputs_secrets_and_permissions(self):
        examples = (ROOT / 'docs/examples.md').read_text()
        documented = set()
        for block in re.findall(r'```yaml\n(.*?)\n```', examples, re.S):
            caller = yaml.safe_load(block)
            for job in caller.get('jobs', {}).values():
                use = job.get('uses', '')
                if not use.startswith('matt-riley/matt-riley-ci/.github/workflows/'):
                    continue
                name = use.split('/')[-1].split('@')[0]
                documented.add(name)
                target = workflow(name)
                contract = target.get('on', target.get(True))['workflow_call']
                for kind, supplied in [('inputs', job.get('with', {})), ('secrets', job.get('secrets', {}))]:
                    for key, spec in contract.get(kind, {}).items():
                        if spec.get('required'):
                            self.assertIn(key, supplied, name + ': missing ' + key)
                    self.assertFalse(set(supplied) - set(contract.get(kind, {})), name + ': unknown ' + kind)
                permissions = job.get('permissions', caller.get('permissions', {}))
                rank = {'none': 0, 'read': 1, 'write': 2}
                for callee in target['jobs'].values():
                    for key, level in callee.get('permissions', target.get('permissions', {})).items():
                        self.assertGreaterEqual(rank[permissions.get(key, 'none')], rank[level], name + ': ' + key)
        expected = {p.name for p in (ROOT / '.github/workflows').glob('*.yml') if p.name != 'contract-tests.yml' and isinstance(workflow(p.name).get('on', workflow(p.name).get(True)), dict) and 'workflow_call' in workflow(p.name).get('on', workflow(p.name).get(True))}
        self.assertEqual(expected, documented)

    def test_luacheck_checks_asset_bytes_before_exposing_or_executing(self):
        import hashlib
        payload = b'fixed asset'
        digest = hashlib.sha256(payload).hexdigest()
        self.stub('gh', "import pathlib, sys\na=sys.argv\npathlib.Path(a[a.index('--dir')+1], 'luacheck').write_bytes(b'fixed asset')\n")
        args = dict(VERSION='v1.2.0', EXPECTED_SHA256='0' * 64)
        result = self.run_step('nvim-lint.yml', 'Install luacheck', **args)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('checksum mismatch', result.stderr)
        asset = self.root / 'luacheck-bin' / 'luacheck'
        self.assertFalse(asset.stat().st_mode & 0o111)
        self.assertFalse(Path(self.env['GITHUB_PATH']).exists())
        self.okay(self.run_step('nvim-lint.yml', 'Install luacheck', **dict(args, EXPECTED_SHA256=digest)))
        self.assertTrue(asset.stat().st_mode & 0o111)
        self.assertIn(str(asset.parent), Path(self.env['GITHUB_PATH']).read_text())
        Path(self.env['GITHUB_PATH']).unlink()
        self.assertNotEqual(0, self.run_step('nvim-lint.yml', 'Install luacheck', **dict(args, EXPECTED_SHA256='invalid')).returncode)
        self.assertFalse(Path(self.env['GITHUB_PATH']).exists())

    def test_validation_runner_jobs_have_read_only_permissions(self):
        suite = workflow('contract-tests.yml')
        for name, job in suite['jobs'].items():
            if 'runs-on' in job:
                self.assertNotIn('write', job.get('permissions', suite['permissions']).values(), name)
        active = {
            'ci.yml': 'ci', 'go-ci.yml': 'test', 'go-lint.yml': 'lint',
            'go-security.yml': 'govulncheck', 'aube-ci.yml': 'ci',
            'nvim-format.yml': 'stylua', 'nvim-lint.yml': 'luacheck',
            'nvim-tests.yml': 'tests', 'docker-ghcr-publish.yml': 'build',
            'go-goreleaser.yml': 'snapshot',
        }
        for name, job_id in active.items():
            self.assertNotIn('write', workflow(name)['jobs'][job_id]['permissions'].values(), name)
        release = workflow('go-goreleaser.yml')['jobs']
        self.assertEqual('${{ inputs.snapshot }}', release['snapshot']['if'])
        self.assertNotIn('environment', release['snapshot'])
        self.assertNotIn('concurrency', release['snapshot'])
        self.assertEqual('${{ !inputs.snapshot }}', release['goreleaser']['if'])
        self.assertEqual('write', release['goreleaser']['permissions']['contents'])
        docker = workflow('docker-ghcr-publish.yml')['jobs']
        self.assertEqual('${{ !inputs.push }}', docker['build']['if'])
        self.assertEqual('${{ inputs.push }}', docker['publish']['if'])
        self.assertTrue(suite['jobs']['go-snapshot']['with']['snapshot'])
        self.assertFalse(suite['jobs']['docker']['with']['push'])
        gate = workflow('repository-release-please.yml')['on']
        self.assertNotIn('pull_request', gate)
        self.assertEqual(['main'], gate['push']['branches'])

    def test_goreleaser_snapshot_and_publish_arguments_fail_closed(self):
        env = dict(SNAPSHOT='true', ARGS='release --clean', TAP_TOKEN='', APP_TOKEN='', TAP_OWNER='owner', TAP_REPO='tap', TAP_FAIL_IF_MISSING='true')
        self.okay(self.run_step('go-goreleaser.yml', 'Validate release authority', **env))
        self.okay(self.run_step('go-goreleaser.yml', 'goreleaser-args', **env))
        self.assertIn('value=release --clean --snapshot --skip=publish', Path(self.env['GITHUB_OUTPUT']).read_text())
        self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'Validate release authority', **dict(env, SNAPSHOT='false', GITHUB_EVENT_NAME='pull_request')).returncode)
        self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'goreleaser-args', **dict(env, ARGS='release\nvalue=bad')).returncode)

    def test_scanner_cache_only_reuses_exact_pinned_versions(self):
        for version, cacheable in [('v1.1.4', 'true'), ('latest', 'false'), ('main', 'false')]:
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step('go-security.yml', 'scanner', VERSION=version))
            self.assertIn('cacheable=' + cacheable, Path(self.env['GITHUB_OUTPUT']).read_text())
        self.assertIn(str(self.root / 'govulncheck-bin'), Path(self.env['GITHUB_PATH']).read_text())
        restore = step('go-security.yml', 'scanner-cache')
        for dimension in ['runner.os', 'runner.arch', 'go-cache-metadata.outputs.version', 'inputs.govulncheck-version']:
            self.assertIn(dimension, restore['with']['key'])
        save = step('go-security.yml', 'Save pinned scanner binary')
        self.assertIn('inputs.save-cache', save['if'])
        self.assertIn('github.event.repository.default_branch', save['if'])

    def test_go_quoted_commands_and_arguments_are_preserved(self):
        self.stub('go', 'import json, sys\nprint(json.dumps(sys.argv[1:]))\n')
        result = self.run_step('go-ci.yml', 'build', BUILD_COMMAND='go build -ldflags "-s -w" ./...')
        self.okay(result)
        self.assertEqual(['build', '-ldflags', '-s -w', './...'], json.loads(result.stdout))
        result = self.run_step('go-ci.yml', 'test', TEST_COMMAND='', TEST_ARGS='-run "Test With Space" -count=1', RUN_RACE='true')
        self.okay(result)
        self.assertEqual(['test', '-race', '-run', 'Test With Space', '-count=1', './...'], json.loads(result.stdout))

    def test_aube_requested_scripts_and_lockfiles_fail_closed(self):
        args = dict(LOCKFILE_PATH='', REQUIRE_LOCKFILE='false', VERIFY_LOCKFILE='false', RUN_LINT='true', RUN_BUILD='false', RUN_TEST='false', TEST_SCRIPT='test')
        package = self.project / 'package.json'
        package.write_text('{')
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)
        package.write_text('{"scripts":{"test":"echo test"}}')
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)
        args['RUN_LINT'] = 'false'
        args['RUN_TEST'] = 'true'
        self.okay(self.run_step('aube-ci.yml', 'lockfile', **args))
        args['REQUIRE_LOCKFILE'] = 'true'
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)
        (self.project / 'package-lock.json').write_text('{}')
        subprocess.run(['git', 'init', '-q'], cwd=self.project, check=True)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)
        subprocess.run(['git', 'add', 'package-lock.json'], cwd=self.project, check=True)
        self.okay(self.run_step('aube-ci.yml', 'lockfile', **args))
        (self.project / 'yarn.lock').write_text('')
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)

    def test_aube_build_env_cannot_change_workflow_control(self):
        self.stub('aube', 'import os\nprint(os.environ.get("URL"))\n')
        self.okay(self.run_step('aube-ci.yml', 'build', SCRIPT_NAME='build', BUILD_ENV='URL=https://example.test?a=b\n'))
        for value in ['SCRIPT_NAME=test', 'PATH=bad', 'GITHUB_TOKEN=bad', 'no equals']:
            self.assertNotEqual(0, self.run_step('aube-ci.yml', 'build', SCRIPT_NAME='build', BUILD_ENV=value).returncode)

    def docker_env(self, **changes):
        defaults = dict(IMAGE_NAME='', CONTEXT='.', DOCKERFILE='', PLATFORMS='linux/amd64', CACHE_SCOPE='', TAG='', PUSH='false', LOAD='false', DEFAULT_BRANCH='main')
        return dict(defaults, **changes)

    def test_docker_prereleases_do_not_tag_latest_or_install_unneeded_qemu(self):
        self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG='v2.1.0-rc.1')))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        self.assertIn('stable=false', output)
        self.assertIn('emulate=false', output)
        self.okay(self.run_step('docker-ghcr-publish.yml', 'rules', CUSTOM_TAGS='', TAG='v2.1.0-rc.1', STABLE='false'))
        self.assertIn('value=latest,enable=false', Path(self.env['GITHUB_OUTPUT']).read_text())
        for changes in [dict(GITHUB_EVENT_NAME='pull_request', PUSH='true'), dict(PLATFORMS='linux/amd64,linux/arm64', LOAD='true'), dict(TAG='injected,enable=true')]:
            self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(**changes)).returncode)
        jobs = workflow('docker-ghcr-publish.yml')['jobs']
        self.assertEqual({'contents': 'read'}, jobs['build']['permissions'])
        self.assertEqual('write', jobs['publish']['permissions']['packages'])

    def test_pages_rejects_untrusted_source_and_command_injection(self):
        args = dict(PROJECT='site', DIRECTORY='.', BRANCH='', DEFAULT_BRANCH='main')
        self.okay(self.run_step('cloudflare-pages-deploy.yml', 'source', **args))
        for changes in [dict(PROJECT='site;id'), dict(DIRECTORY='../escape'), dict(BRANCH='main --extra'), dict(GITHUB_EVENT_NAME='pull_request')]:
            self.assertNotEqual(0, self.run_step('cloudflare-pages-deploy.yml', 'source', **dict(args, **changes)).returncode)
        job = workflow('cloudflare-pages-deploy.yml')['jobs']['deploy']
        self.assertEqual({'contents': 'read'}, job['permissions'])
        self.assertFalse(any(s.get('name') in ['Build', 'Install dependencies'] for s in job['steps']))

    def test_homebrew_quotes_ruby_and_accepts_one_platform(self):
        self.stub('gh', "import pathlib, sys\na=sys.argv\npathlib.Path(a[a.index('--dir')+1], a[a.index('--pattern')+1]).write_bytes(b'asset')\n")
        env = dict(SOURCE_REPO='owner/project', TAP_REPO='owner/tap', TAG='v1.2.3', FORMULA_NAME='tool', CLASS_NAME='Tool', DESC='Say "hello" #{raise "boom"} and it\'s fine', HOMEPAGE='https://example.test', LICENSE='MIT', BINARY='tool', TEST_ARGS='--version "quoted arg"', ARCHIVE_X86_64_MACOS='tool.tar.gz', ARCHIVE_AARCH64_MACOS='', ARCHIVE_X86_64_LINUX='', ARCHIVE_AARCH64_LINUX='', GITHUB_REF='refs/tags/v1.2.3')
        self.okay(self.run_step('homebrew-formula.yml', 'formula', **env))
        formula = (self.root / 'tool.rb').read_text()
        self.assertIn('on_intel do', formula)
        self.assertNotIn('on_linux do', formula)
        self.assertIn("'--version', 'quoted arg'", formula)
        self.assertIn("it\\'s fine", formula)
        self.okay(self.run_step('homebrew-formula.yml', 'formula', **dict(env, BINARY='dist/tool')))
        nested_formula = (self.root / 'tool.rb').read_text()
        self.assertIn("bin.install 'dist/tool'", nested_formula)
        self.assertIn("system bin/'tool'", nested_formula)
        self.assertNotIn("system bin/'dist/tool'", nested_formula)
        self.assertNotEqual(0, self.run_step('homebrew-formula.yml', 'formula', **dict(env, CLASS_NAME='Tool;raise')).returncode)

    def test_tailscale_explicit_apply_cannot_bypass_default_branch_guard(self):
        (self.project / 'policy.hujson').write_text('{}')
        env = dict(REQUESTED='apply', EVENT_NAME='pull_request', REF='refs/pull/1/merge', DEFAULT_BRANCH='main', POLICY_FILE='policy.hujson')
        self.assertNotEqual(0, self.run_step('tailscale-acl.yml', 'resolve', **env).returncode)
        self.okay(self.run_step('tailscale-acl.yml', 'resolve', **dict(env, EVENT_NAME='push', REF='refs/heads/main')))

    def test_no_broad_install_or_implicit_browser_setup_in_library(self):
        mise = step('ci.yml', 'Install mise')['with']
        self.assertEqual('${{ inputs.install-tools }}', mise['install_args'])
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            self.assertNotIn('apt-get', path.read_text())
        self.assertNotIn('playwright install', (ROOT / 'mise.toml').read_text())

    def test_major_tag_publication_handles_annotated_refs_and_rejects_wrong_sha(self):
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        commands = [
            ['init', '-q'], ['config', 'user.name', 'Test'], ['config', 'user.email', 'test@example.test'],
            ['config', 'commit.gpgsign', 'false'], ['config', 'tag.gpgsign', 'false'],
            ['commit', '--allow-empty', '-qm', 'one'], ['tag', 'v1.0.0'], ['tag', '-a', 'v1', '-m', 'old major'],
            ['commit', '--allow-empty', '-qm', 'two'], ['tag', 'v1.1.0'], ['remote', 'add', 'origin', str(remote)], ['push', '-q', '--tags', 'origin'],
        ]
        for command in commands:
            subprocess.run(['git'] + command, cwd=self.project, check=True)
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.project, text=True).strip()
        env = dict(TAG_NAME='v1.1.0', TESTED_SHA='0' * 40, PUSH_TOKEN='', HAS_TAG_TOKEN='true')
        self.assertNotEqual(0, self.run_step('repository-release-please.yml', 'move', **env).returncode)
        env['TESTED_SHA'] = sha
        self.okay(self.run_step('repository-release-please.yml', 'move', **env))
        self.okay(self.run_step('repository-release-please.yml', 'move', **env))
        published = subprocess.check_output(['git', '--git-dir', str(remote), 'rev-parse', 'refs/tags/v1'], text=True).strip()
        self.assertEqual(sha, published)
        old_sha = subprocess.check_output(['git', 'rev-parse', 'v1.0.0'], cwd=self.project, text=True).strip()
        self.assertNotEqual(0, self.run_step('repository-release-please.yml', 'move', **dict(env, TAG_NAME='v1.0.0', TESTED_SHA=old_sha)).returncode)


class Policy(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('checks', ROOT / 'scripts/check.py')
        self.checks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checks)

    def test_policy_rejects_empty_duplicate_yaml_and_unpinned_job_or_docker_uses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(self.checks.validate(root))
            file = root / 'test.yaml'
            for text in ['', 'name: one\nname: two\n', 'on: push\njobs:\n  test:\n    uses: owner/repo/.github/workflows/test.yml@v1\n', 'on: push\njobs:\n  test:\n    timeout-minutes: 5\n    permissions: {contents: read}\n    steps:\n      - uses: docker://image:latest\n']:
                file.write_text(text)
                self.assertTrue(self.checks.validate(root), text)

    def test_local_calls_reject_missing_permission_and_missing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            callee = root / 'callee.yml'
            callee.write_text('on: {workflow_call: {}}\njobs:\n  run:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    permissions: {contents: read, packages: read}\n    steps: [{run: echo okay}]\n')
            caller = root / 'caller.yml'
            text = 'on: push\npermissions: {contents: read}\njobs:\n  run:\n    uses: ./.github/workflows/callee.yml\n'
            caller.write_text(text)
            self.assertTrue(self.checks.validate(root))
            caller.write_text(text.replace('contents: read}', 'contents: read, packages: read}'))
            self.assertEqual([], self.checks.validate(root))
            callee.unlink()
            self.assertTrue(self.checks.validate(root))

    def test_registration_and_release_gate_cover_all_checks_and_merge_queue(self):
        tests = workflow('contract-tests.yml')
        self.assertIn('merge_group', tests['on'])
        self.assertNotIn('paths', tests['on']['pull_request'] or {})
        required = set(tests['jobs']['checks']['needs'])
        self.assertEqual(set(tests['jobs']) - {'checks'}, required)
        self.assertIn('scripts/check.py', tests['jobs']['validate']['steps'][-1]['run'])
        release = workflow('repository-release-please.yml')
        self.assertEqual('validate', release['jobs']['release']['needs'])
        run = step('repository-release-please.yml', 'move')['run']
        self.assertIn('test "$target_sha" = "$TESTED_SHA"', run)
        self.assertIn('test "$published_sha" = "$target_sha"', run)
        self.assertIn('--force-with-lease', run)


if __name__ == '__main__':
    unittest.main()
