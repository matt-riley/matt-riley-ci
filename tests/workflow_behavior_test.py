"""Execute workflow scripts with real shells and isolated consumer repositories."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / name).read_text())


def step(name, identity):
    return next(s for job in workflow(name)['jobs'].values() for s in job.get('steps', []) if s.get('id', s.get('name')) == identity)


def expression(value, event='push', ref='refs/heads/main', source='owner/project', steps_context=None, **inputs):
    """Evaluate the simple boolean/string GitHub expressions used by these guards."""
    github = SimpleNamespace(repository='owner/project', event_name=event, ref=ref,
        event=SimpleNamespace(repository=SimpleNamespace(default_branch='main'),
            pull_request=SimpleNamespace(head=SimpleNamespace(repo=SimpleNamespace(full_name=source)))))
    def evaluate(match):
        code = match.group(1).replace('&&', 'and').replace('||', 'or')
        code = re.sub(r'!(?!=)', 'not ', code)
        code = re.sub(r'\binputs\.([A-Za-z0-9_-]+)', lambda item: "inputs[" + repr(item.group(1)) + "]", code)
        code = code.replace('steps.cache-metadata', 'steps.cache_metadata')
        steps = steps_context or SimpleNamespace(cache_metadata=SimpleNamespace(outputs=SimpleNamespace(paths='/cache/dependencies', build_cache='/cache/build')))
        return str(eval(code, {'__builtins__': {}}, {'github': github, 'inputs': inputs, 'steps': steps, 'true': True, 'false': False, 'format': lambda text, *args: text.format(*args)}))
    return re.sub(r'\$\{\{\s*(.*?)\s*\}\}', evaluate, value)


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
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(name, identity)['run']], cwd=self.project, env={**self.env, 'COVERAGE_NAME': 'test-coverage', **env}, text=True, capture_output=True, timeout=45)

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

    def test_artifact_retention_respects_the_actual_repository_cap(self):
        for retention, limit, okay in [('7', '14', True), ('15', '14', False), ('100', '90', False), ('100', '400', True), ('0', '90', False)]:
            result = self.run_step('ci.yml', 'Validate CI inputs', ARTIFACT_PATH='', ARTIFACT_NAME='', RETENTION=retention, GITHUB_RETENTION_DAYS=limit)
            self.assertEqual(okay, result.returncode == 0, result.stdout + result.stderr)

    def test_artifact_names_fail_before_build_for_backend_forbidden_characters(self):
        for name in ['packages/server', 'back\\slash', 'a:b', 'a"b', 'a<b', 'a>b', 'a|b', 'a*b', 'a?b', 'a\rb', 'a\nb', 'coverage server-α']:
            valid = name == 'coverage server-α'
            cases = [('ci.yml', 'Validate CI inputs', dict(ARTIFACT_PATH='dist', ARTIFACT_NAME=name, RETENTION='7'))]
            cases += [(workflow_name, 'paths', dict(COVERAGE_PATHS='coverage.out', COVERAGE_NAME=name, FAILURE_PATHS='')) for workflow_name in ['go-ci.yml', 'aube-ci.yml']]
            cases += [('ci.yml', 'Validate CI inputs', dict(ARTIFACT_PATH='', ARTIFACT_NAME='', FAILURE_NAME=name, RETENTION='7')), ('go-ci.yml', 'paths', dict(COVERAGE_PATHS='', FAILURE_PATHS='logs', FAILURE_NAME=name))]
            for workflow_name, identity, env in cases:
                with self.subTest(workflow=workflow_name, name=name, env=env):
                    result = self.run_step(workflow_name, identity, **env)
                    self.assertEqual(valid, result.returncode == 0, result.stdout + result.stderr)

    def test_adapter_artifact_paths_apply_nested_directory_to_every_line(self):
        for name in ['go-ci.yml', 'aube-ci.yml']:
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step(name, 'paths', COVERAGE_PATHS='coverage.out\nreports/*.xml\n!reports/private', FAILURE_PATHS='logs\nerrors'))
            output = Path(self.env['GITHUB_OUTPUT']).read_text()
            for path in ['coverage.out', 'reports/*.xml', 'reports/private', 'logs', 'errors']:
                self.assertIn(str(self.project / path), output)
            self.assertNotEqual(0, self.run_step(name, 'paths', COVERAGE_PATHS='../../outside', FAILURE_PATHS='').returncode)
        self.project = self.root
        for name, variables in [('go-ci.yml', dict(COVERAGE_PATHS='.', FAILURE_PATHS='')), ('aube-ci.yml', dict(COVERAGE_PATHS='.', FAILURE_PATHS='')), ('ci.yml', dict(BUILD_PATHS='.', FAILURE_PATHS=''))]:
            self.assertNotEqual(0, self.run_step(name, 'paths', **variables).returncode)

    def test_yarn_cache_metadata_registers_classic_and_modern_stores(self):
        (self.project / 'yarn.lock').write_text('')
        for modern in [True, False]:
            self.stub('yarn', "import sys\na=sys.argv[1:]\nprint('4.0.0' if a == ['--version'] else " + repr('/tmp/modern-yarn' if modern else 'undefined') + " if a == ['config', 'get', 'cacheFolder'] else '/tmp/classic-yarn')\n")
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step('ci.yml', 'cache-metadata', EXTRA_PATHS='', PLAYWRIGHT_CACHE='false'))
            self.assertIn('/tmp/modern-yarn' if modern else '/tmp/classic-yarn', Path(self.env['GITHUB_OUTPUT']).read_text())

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

    def test_extra_cache_paths_resolve_from_the_consumer_project(self):
        self.okay(self.run_step('ci.yml', 'cache-metadata', EXTRA_PATHS='.cache/compiler\n~/.cache/global\n/tmp/absolute-cache\n!.cache/private', PLAYWRIGHT_CACHE='false'))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        self.assertIn(str(self.project / '.cache/compiler'), output)
        self.assertIn(str(Path.home() / '.cache/global'), output)
        self.assertIn('/tmp/absolute-cache', output)
        self.assertIn('!' + str(self.project.resolve() / '.cache/private'), output)

    def test_dependency_cache_fallback_cannot_match_a_build_cache(self):
        dependencies = step('ci.yml', 'dependencies')['with']
        build = step('ci.yml', 'go-build-cache')['with']
        normalize = lambda text: re.sub(r'\s+', '', text)
        self.assertFalse(normalize(build['key']).startswith(normalize(dependencies['restore-keys'])))

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

    def test_neovim_and_stylua_verify_archives_before_extracting(self):
        import hashlib
        digest = hashlib.sha256(b'fixture asset').hexdigest()
        self.stub('gh', '''import json, pathlib, sys
a = sys.argv
if a[1:3] == ['release', 'view']:
    print(json.dumps({'assets': [{'name':'nvim-linux-x86_64.tar.gz', 'digest':'sha256:''' + digest + ''''}]}))
else: pathlib.Path(a[a.index('--dir')+1], a[a.index('--pattern')+1]).write_bytes(b'fixture asset')
''')
        for command in ['tar', 'unzip']:
            self.stub(command, "import os, pathlib\np=pathlib.Path(os.environ['RUNNER_TEMP']); (p/'extracted').touch(); (p/'stylua-bin').mkdir(exist_ok=True); (p/'stylua-bin/stylua').touch()\n")
        for name, identity, pinned in [('nvim-tests.yml', 'Install Neovim', 'v0.12.5'), ('nvim-format.yml', 'Install stylua', 'v2.4.0')]:
            with self.subTest(workflow=name):
                for version, expected in [(pinned, ''), ('v9.9.9', ''), ('v9.9.9', '0' * 64)]:
                    (self.root / 'extracted').unlink(missing_ok=True)
                    Path(self.env['GITHUB_PATH']).unlink(missing_ok=True)
                    result = self.run_step(name, identity, VERSION=version, EXPECTED_SHA256=expected)
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse((self.root / 'extracted').exists())
                    self.assertFalse(Path(self.env['GITHUB_PATH']).exists())
                self.okay(self.run_step(name, identity, VERSION='v9.9.9', EXPECTED_SHA256=digest))
                self.assertTrue((self.root / 'extracted').exists())
                (self.root / 'extracted').unlink()
        self.okay(self.run_step('nvim-tests.yml', 'Install Neovim', VERSION='nightly', EXPECTED_SHA256=''))

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
        release_gate = workflow('repository-release-please.yml')['jobs']
        self.assertEqual('release', release_gate['release']['with']['environment'])
        self.assertEqual('release', release_gate['move-major-tag']['environment'])

    def test_goreleaser_snapshot_and_publish_arguments_fail_closed(self):
        env = dict(SNAPSHOT='true', ARGS='release --clean', TAP_TOKEN='', APP_TOKEN='', TAP_OWNER='owner', TAP_REPO='tap', TAP_FAIL_IF_MISSING='true')
        self.okay(self.run_step('go-goreleaser.yml', 'Validate release authority', **env))
        self.okay(self.run_step('go-goreleaser.yml', 'goreleaser-args', **env))
        self.assertIn('value=release --clean --snapshot --skip=publish', Path(self.env['GITHUB_OUTPUT']).read_text())
        self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'Validate release authority', **dict(env, SNAPSHOT='false', GITHUB_EVENT_NAME='pull_request')).returncode)
        self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'goreleaser-args', **dict(env, ARGS='release\nvalue=bad')).returncode)
        trusted = dict(env, SNAPSHOT='false', GITHUB_REF='refs/tags/v1.2.3')
        for args in ['release --snapshot', 'release --snapshot=true', 'release --auto-snapshot', 'release --skip=publish', 'release --skip homebrew,publish', 'release --skip=homebrew --skip=publish', 'release --skip=\'"publish",homebrew\'', 'release --help']:
            self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'Validate release authority', **dict(trusted, ARGS=args)).returncode, args)
        for args in ['release --clean', 'release --skip=homebrew', 'release --skip homebrew', 'release --snapshot=false --auto-snapshot=false', 'release --release-notes "--snapshot"']:
            self.okay(self.run_step('go-goreleaser.yml', 'Validate release authority', **dict(trusted, ARGS=args)))
        app = step('go-goreleaser.yml', 'app-token')
        self.assertTrue(app['continue-on-error'])
        self.okay(self.run_step('go-goreleaser.yml', 'goreleaser-args', **dict(trusted, TAP_TOKEN='fake-fallback-pat', APP_TOKEN='')))
        self.assertIn('tap_source=pat', Path(self.env['GITHUB_OUTPUT']).read_text())
        self.assertNotEqual(0, self.run_step('go-goreleaser.yml', 'goreleaser-args', **trusted).returncode)
        self.okay(self.run_step('go-goreleaser.yml', 'goreleaser-args', **dict(trusted, TAP_FAIL_IF_MISSING='false')))
        self.assertIn('--skip=homebrew', Path(self.env['GITHUB_OUTPUT']).read_text())

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
        subprocess.run(['git', 'add', 'package.json'], cwd=self.project, check=True)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **dict(args, LOCKFILE_PATH='package.json')).returncode)
        for lockfile in [str(self.project / 'package-lock.json'), '../package-lock.json']:
            self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **dict(args, LOCKFILE_PATH=lockfile)).returncode)
        link = self.project / 'linked-lock.json'
        link.symlink_to(self.project / 'package-lock.json')
        subprocess.run(['git', 'add', 'linked-lock.json'], cwd=self.project, check=True)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **dict(args, LOCKFILE_PATH='linked-lock.json')).returncode)
        (self.project / 'yarn.lock').write_text('')
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **args).returncode)
        (self.project / 'yarn.lock').unlink()
        (self.project / 'package.json').write_text('{"scripts":{"--help":"echo skipped"}}')
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'lockfile', **dict(args, TEST_SCRIPT='--help')).returncode)

    def test_aube_lockfile_check_detects_committed_or_index_hidden_changes(self):
        import hashlib
        lockfile = self.project / 'package-lock.json'
        lockfile.write_text('{}')
        def git(*args):
            return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', '-c', 'commit.gpgsign=false', *args], cwd=self.project, check=True, capture_output=True)
        git('init', '-q')
        git('add', 'package-lock.json')
        git('commit', '-qm', 'baseline')
        args = dict(LOCKFILE='package-lock.json', EXPECTED_SHA256=hashlib.sha256(b'{}').hexdigest(), EXPECTED_EXECUTABLE='false')
        self.okay(self.run_step('aube-ci.yml', 'Verify lockfile is unchanged', **args))
        original_mode = lockfile.stat().st_mode
        lockfile.chmod(original_mode | 0o100)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'Verify lockfile is unchanged', **args).returncode)
        lockfile.chmod(original_mode)
        lockfile.write_text('{"changed":true}')
        git('add', 'package-lock.json')
        git('commit', '-qm', 'installation changed HEAD')
        self.assertEqual(b'', git('status', '--porcelain').stdout)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'Verify lockfile is unchanged', **args).returncode)
        for flag in ['--assume-unchanged', '--skip-worktree']:
            git('update-index', flag, 'package-lock.json')
            lockfile.write_text('{"hidden":true}')
            self.assertEqual(b'', git('status', '--porcelain').stdout)
            self.assertNotEqual(0, self.run_step('aube-ci.yml', 'Verify lockfile is unchanged', **args).returncode)
        lockfile.unlink()
        target = self.project / 'outside-lock.json'
        target.write_text('{}')
        lockfile.symlink_to(target)
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'Verify lockfile is unchanged', **args).returncode)

    def test_aube_coverage_requires_unique_name_and_can_upload_build_output(self):
        self.assertNotEqual(0, self.run_step('aube-ci.yml', 'paths', COVERAGE_PATHS='coverage.out', FAILURE_PATHS='', COVERAGE_NAME='').returncode)
        self.okay(self.run_step('aube-ci.yml', 'paths', COVERAGE_PATHS='coverage.out', FAILURE_PATHS='', COVERAGE_NAME='package-a-coverage'))
        upload = step('aube-ci.yml', 'Upload coverage')
        self.assertIn("steps.install.outcome == 'success'", upload['if'])
        self.assertNotIn('steps.test.outcome', upload['if'])
        self.assertEqual('', workflow('aube-ci.yml')['on']['workflow_call']['inputs']['coverage-artifact-name']['default'])

    def test_go_rejects_whitespace_only_check_overrides(self):
        args = dict(RUN_TEST='false', RUN_VET='false', RUN_FMT='false')
        for command in ['', '   ', '\t\n']:
            self.assertNotEqual(0, self.run_step('go-ci.yml', 'Require a Go check', BUILD_COMMAND=command, **args).returncode)
        self.okay(self.run_step('go-ci.yml', 'Require a Go check', BUILD_COMMAND='go build ./...', **args))
        self.assertNotEqual(0, self.run_step('go-ci.yml', 'test', TEST_COMMAND=' \t\n', TEST_ARGS='', RUN_RACE='false').returncode)

    def test_aube_build_env_cannot_change_workflow_control(self):
        self.stub('aube', 'import os\nprint(os.environ.get("URL"))\n')
        self.okay(self.run_step('aube-ci.yml', 'build', SCRIPT_NAME='build', BUILD_ENV='URL=https://example.test?a=b\n'))
        for value in ['SCRIPT_NAME=test', 'PATH=bad', 'GITHUB_TOKEN=bad', 'NODE_AUTH_TOKEN=bad', 'no equals']:
            self.assertNotEqual(0, self.run_step('aube-ci.yml', 'build', SCRIPT_NAME='build', BUILD_ENV=value).returncode)

    def test_aube_authentication_reaches_every_requested_command(self):
        self.stub('aube', 'import json, os, sys\nprint(json.dumps([sys.argv[1:], os.environ.get("NODE_AUTH_TOKEN")]))\n')
        for identity, args in [('install', ['ci']), ('lint', ['run', 'lint']), ('build', ['run', 'build']), ('test', ['run', 'custom-test'])]:
            with self.subTest(step=identity):
                config = step('aube-ci.yml', identity)
                self.assertEqual('${{ secrets.node_auth_token || github.token }}', config['env'].get('NODE_AUTH_TOKEN'))
                for token in ['fake-github-token', 'fake-registry-token']:
                    result = self.run_step('aube-ci.yml', identity, SCRIPT_NAME='custom-test' if identity == 'test' else identity, BUILD_ENV='', INSTALL_COMMAND='', NODE_AUTH_TOKEN=token)
                    self.okay(result)
                    self.assertEqual([args, token], json.loads(result.stdout))

    def test_infra_repository_resolution_never_normalizes_an_invalid_target(self):
        for target, expected in [('infra', 'default-owner/infra'), ('owner/repo-name', 'owner/repo-name')]:
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step('request-infra-deploy.yml', 'resolve', DEFAULT_OWNER='default-owner', INPUT_INFRA_REPO=target))
            self.assertIn('infra_full_name=' + expected + '\n', Path(self.env['GITHUB_OUTPUT']).read_text())
        for target in ['owner/middle/name', 'owner//name', '/name', 'owner/', '', 'owner/repo name']:
            with self.subTest(target=target):
                Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
                result = self.run_step('request-infra-deploy.yml', 'resolve', DEFAULT_OWNER='default-owner', INPUT_INFRA_REPO=target)
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(Path(self.env['GITHUB_OUTPUT']).exists())

    def docker_env(self, **changes):
        defaults = dict(IMAGE_NAME='', CONTEXT='.', DOCKERFILE='', PLATFORMS='linux/amd64', CACHE_SCOPE='', TAG='', PUSH='false', LOAD='false', OUTPUTS='', DEFAULT_BRANCH='main')
        return dict(defaults, **changes)

    def test_docker_cache_restores_and_writes_respect_trust_and_opt_out(self):
        build = step('docker-ghcr-publish.yml', 'build')['with']
        context = SimpleNamespace(image=SimpleNamespace(outputs=SimpleNamespace(scope='fixture')))
        for event, ref, source, cache, save, push, restore, write in [
            ('pull_request', 'refs/pull/1/merge', 'fork/project', True, True, False, False, False),
            ('pull_request_target', 'refs/heads/main', 'fork/project', True, True, False, False, False),
            ('pull_request', 'refs/pull/1/merge', 'owner/project', True, True, False, True, False),
            ('push', 'refs/heads/main', 'owner/project', True, False, False, True, False),
            ('push', 'refs/heads/main', 'owner/project', True, True, False, True, True),
            ('workflow_dispatch', 'refs/heads/main', 'owner/project', True, True, False, True, True),
            ('push', 'refs/heads/feature', 'owner/project', True, True, False, True, False),
            ('push', 'refs/tags/v1.0.0', 'owner/project', True, False, True, True, True),
            ('push', 'refs/heads/main', 'owner/project', False, True, True, False, False),
        ]:
            with self.subTest(event=event, ref=ref, cache=cache, save=save, push=push):
                inputs = {'cache': cache, 'save-cache': save, 'push': push}
                for key, expected in [('cache-from', restore), ('cache-to', write)]:
                    result = expression(build[key], event=event, ref=ref, source=source, steps_context=context, **inputs)
                    self.assertEqual('type=gha,' in result, expected, result)
        self.assertFalse(workflow('contract-tests.yml')['jobs']['docker-export']['with']['cache'])

    def test_docker_prereleases_do_not_tag_latest_or_install_unneeded_qemu(self):
        self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG='v2.1.0', PUSH='true', GITHUB_REF='refs/tags/v2.1.0')))
        for ref in ['refs/tags/v9.9.9', 'refs/heads/main']:
            self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG='v2.1.0', PUSH='true', GITHUB_REF=ref)).returncode)
        self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG='v2.1.0-rc.1')))
        output = Path(self.env['GITHUB_OUTPUT']).read_text()
        self.assertIn('stable=false', output)
        self.assertIn('emulate=false', output)
        self.okay(self.run_step('docker-ghcr-publish.yml', 'rules', CUSTOM_TAGS='', TAG='v2.1.0-rc.1', STABLE='false'))
        self.assertIn('value=latest,enable=false', Path(self.env['GITHUB_OUTPUT']).read_text())
        for changes in [dict(GITHUB_EVENT_NAME='pull_request', PUSH='true'), dict(PLATFORMS='linux/amd64,linux/arm64', LOAD='true'), dict(TAG='injected,enable=true')]:
            self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(**changes)).returncode)
        for image in ['ghcr.io/owner//image', 'ghcr.io/owner/image/', 'ghcr.io/image', 'ghcr.io/-owner/image', 'ghcr.io/owner/image-', 'ghcr.io/owner/im..age']:
            with self.subTest(image=image):
                self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(IMAGE_NAME=image)).returncode)
        for image in ['ghcr.io/owner/image', 'ghcr.io/owner/nested/image', 'ghcr.io/owner/image__name']:
            self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(IMAGE_NAME=image)))
        for tag in ['v01.2.3', 'v1.02.3', 'v1.2.03', 'v1.2.3-01', 'v1.2.3-rc..1', 'v1.2.3+build..id']:
            self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG=tag)).returncode, tag)
        for tag in ['v0.0.0', '1.2.3-0', 'v1.2.3-rc.1+build.00', 'v1.2.3-01a']:
            self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(TAG=tag)))
        jobs = workflow('docker-ghcr-publish.yml')['jobs']
        self.assertEqual({'contents': 'read'}, jobs['build']['permissions'])
        self.assertEqual('write', jobs['publish']['permissions']['packages'])
        self.assertEqual('max', jobs['publish']['concurrency']['queue'])
        self.assertFalse(jobs['publish']['concurrency']['cancel-in-progress'])
        build = step('docker-ghcr-publish.yml', 'build')['with']
        self.assertEqual("${{ !inputs.load && steps.image.outputs.docker_exporter != 'true' && inputs.provenance }}", build['provenance'])
        self.assertEqual("${{ !inputs.load && steps.image.outputs.docker_exporter != 'true' && inputs.sbom }}", build['sbom'])
        for outputs, docker in [('', False), ('type=oci,dest=image.tar', False), ('type=docker,dest=image.tar', True), ('type=local,dest=out\ntype=docker,dest="image,archive.tar"', True)]:
            Path(self.env['GITHUB_OUTPUT']).unlink(missing_ok=True)
            self.okay(self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(OUTPUTS=outputs)))
            self.assertIn('docker_exporter=' + str(docker).lower(), Path(self.env['GITHUB_OUTPUT']).read_text())
        self.assertNotEqual(0, self.run_step('docker-ghcr-publish.yml', 'image', **self.docker_env(OUTPUTS='type=docker,dest=image.tar', PLATFORMS='linux/amd64,linux/arm64')).returncode)
        contract = workflow('docker-ghcr-publish.yml')['on']['workflow_call']['inputs']
        self.assertTrue(contract['provenance']['default'])
        self.assertTrue(contract['sbom']['default'])
        self.assertNotIn('provenance', workflow('contract-tests.yml')['jobs']['docker']['with'])
        self.assertNotIn('sbom', workflow('contract-tests.yml')['jobs']['docker']['with'])

    def test_infra_dispatch_passes_generated_payload_to_curl(self):
        self.stub('curl', "import json, os, pathlib, sys\na=sys.argv\nbody=a[a.index('--data-binary')+1]\nassert body.startswith('@')\npathlib.Path(os.environ['RUNNER_TEMP'], 'sent-payload.json').write_text(pathlib.Path(body[1:]).read_text())\npathlib.Path(os.environ['RUNNER_TEMP'], 'request.json').write_text(json.dumps(a))\n")
        for run in ['0', '12345678901234567890']:
            self.okay(self.run_step('request-infra-deploy.yml', 'dispatch', APP_NAME='test-app', GH_TOKEN='test-token', INFRA_NAME='infra', INFRA_OWNER='owner', SOURCE_REF='refs/heads/main', SOURCE_REPO='owner/project', SOURCE_SHA='a' * 40, ARTIFACT_RUN_ID=run, ARTIFACT_NAME='build' if run != '0' else '', ARTIFACT_DIGEST='b' * 64 if run != '0' else ''))
            body = json.loads((self.root / 'sent-payload.json').read_text())
            self.assertEqual('deploy-app', body['event_type'])
            payload = body['client_payload']
            self.assertEqual('test-app', payload['app'])
            self.assertEqual('a' * 40, payload['source_sha'])
            if run == '0':
                self.assertNotIn('artifact_run_id', payload)
            else:
                self.assertEqual(run, payload['artifact_run_id'])
                self.assertEqual('build', payload['artifact_name'])
                self.assertEqual('b' * 64, payload['artifact_digest'])
            request = json.loads((self.root / 'request.json').read_text())
            self.assertIn('https://api.github.com/repos/owner/infra/dispatches', request)

    def test_pages_rejects_untrusted_source_and_command_injection(self):
        args = dict(PROJECT='site', DIRECTORY='.', BRANCH='', DEFAULT_BRANCH='main')
        self.okay(self.run_step('cloudflare-pages-deploy.yml', 'source', **args))
        for changes in [dict(PROJECT='site;id'), dict(DIRECTORY='../escape'), dict(DIRECTORY='--help'), dict(BRANCH='main --extra'), dict(GITHUB_EVENT_NAME='pull_request')]:
            self.assertNotEqual(0, self.run_step('cloudflare-pages-deploy.yml', 'source', **dict(args, **changes)).returncode)
        job = workflow('cloudflare-pages-deploy.yml')['jobs']['deploy']
        self.assertEqual({'contents': 'read'}, job['permissions'])
        self.assertFalse(any(s.get('name') in ['Build', 'Install dependencies'] for s in job['steps']))
        self.assertNotIn('inputs.environment', job['concurrency']['group'])

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
        for change in [dict(GITHUB_REF='refs/tags/v9.9.9'), dict(BINARY='.'), dict(BINARY='./')]:
            self.assertNotEqual(0, self.run_step('homebrew-formula.yml', 'formula', **dict(env, **change)).returncode)

    def test_homebrew_optional_credentials_skip_before_asset_download(self):
        self.okay(self.run_step('homebrew-formula.yml', 'auth', HAS_TOKEN='false', REQUIRED='false'))
        self.assertIn('status=skipped', Path(self.env['GITHUB_OUTPUT']).read_text())
        steps = workflow('homebrew-formula.yml')['jobs']['update-formula']['steps']
        ids = [item.get('id') for item in steps]
        self.assertLess(ids.index('auth'), ids.index('formula'))
        self.assertEqual("${{ steps.auth.outputs.status == 'ready' }}", step('homebrew-formula.yml', 'formula')['if'])
        self.assertNotEqual(0, self.run_step('homebrew-formula.yml', 'auth', HAS_TOKEN='false', REQUIRED='true').returncode)
        output = workflow('homebrew-formula.yml')['jobs']['update-formula']['outputs']['status']
        for auth, published, expected in [('skipped', '', 'skipped'), ('ready', '', 'failed'), ('', '', 'failed'), ('ready', 'published', 'published'), ('ready', 'unchanged', 'unchanged')]:
            context = SimpleNamespace(auth=SimpleNamespace(outputs=SimpleNamespace(status=auth)), publish=SimpleNamespace(outputs=SimpleNamespace(status=published)))
            self.assertEqual(expected, expression(output, steps_context=context))

    def test_fork_pull_requests_never_restore_dependency_or_build_caches(self):
        for name in ['ci.yml', 'go-ci.yml', 'go-lint.yml', 'go-security.yml', 'go-goreleaser.yml']:
            for item in (item for job in workflow(name)['jobs'].values() for item in job['steps']):
                if not item.get('name', '').startswith(('Restore dependencies', 'Restore Go module cache', 'Restore Go build cache')):
                    continue
                for event, source, allowed in [('push', '', True), ('pull_request', 'owner/project', True), ('pull_request', 'fork/project', False), ('pull_request_target', 'fork/project', False)]:
                    with self.subTest(workflow=name, step=item['name'], event=event, source=source):
                        result = expression(item.get('if', '${{ true }}'), event=event, source=source, cache=True)
                        # Cache path existence is independent of the source-authority guard.
                        self.assertEqual(str(allowed), result)
                        self.assertEqual('False', expression(item['if'], event=event, source=source, cache=False))
                self.assertTrue(workflow(name)['on']['workflow_call']['inputs']['cache']['default'])
            for job in workflow(name)['jobs'].values():
                for item in job['steps']:
                    if item.get('uses', '').startswith('actions/cache/save@'):
                        self.assertIn('inputs.cache && inputs.save-cache', item['if'])
        for name, identity, setting, disabled in [('ci.yml', 'Install mise', 'cache', 'False'), ('go-lint.yml', 'lint', 'skip-cache', 'True')]:
            self.assertEqual(disabled, expression(step(name, identity)['with'][setting], event='pull_request', source='fork/project', cache=True))
            self.assertEqual(disabled, expression(step(name, identity)['with'][setting], cache=False))

    def test_equivalent_release_targets_and_acl_actions_share_the_correct_queues(self):
        release = workflow('release-please.yml')['jobs']['release-please']['concurrency']['group']
        self.assertEqual(expression(release, **{'target-branch': ''}), expression(release, **{'target-branch': 'main'}))
        acl = workflow('tailscale-acl.yml')['jobs']['acl']['concurrency']['group']
        auto_apply = expression(acl, action='', tailnet='example')
        explicit_apply = expression(acl, action='apply', tailnet='example')
        pr_test = expression(acl, event='pull_request', ref='refs/pull/1/merge', action='', tailnet='example')
        explicit_test = expression(acl, action='test', tailnet='example')
        self.assertEqual(auto_apply, explicit_apply)
        self.assertEqual(pr_test, explicit_test)
        self.assertNotEqual(auto_apply, pr_test)
        environment = workflow('tailscale-acl.yml')['jobs']['acl']['environment']
        for event, ref, action, protected in [('push', 'refs/heads/main', '', 'production'), ('workflow_dispatch', 'refs/heads/main', 'apply', 'production'), ('pull_request', 'refs/pull/1/merge', '', ''), ('push', 'refs/heads/main', 'test', '')]:
            self.assertEqual(protected, expression(environment, event=event, ref=ref, action=action, environment='production'))

    def test_lockfile_sync_rejects_directories_and_commits_only_the_lockfile(self):
        for lockfile in ['.', '..', 'dir/name', '']:
            self.assertNotEqual(0, self.run_step('pnpm-lockfile-sync.yml', 'Validate sync inputs', PREFIX='release-please--', LOCKFILE=lockfile).returncode)
            self.assertNotEqual(0, self.run_step('pnpm-lockfile-sync.yml', 'push', HEAD_REF='release-please--main', COMMIT_MESSAGE='sync', LOCKFILE=lockfile, PUSH_TOKEN='').returncode)
        (self.project / 'directory').mkdir()
        self.assertNotEqual(0, self.run_step('pnpm-lockfile-sync.yml', 'push', HEAD_REF='release-please--main', COMMIT_MESSAGE='sync', LOCKFILE='directory', PUSH_TOKEN='').returncode)
        remote = self.root / 'lockfile-remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        (self.project / 'pnpm-lock.yaml').write_text('before')
        (self.project / 'unrelated.txt').write_text('before')
        for command in [['init', '-q'], ['config', 'user.name', 'Test'], ['config', 'user.email', 'test@example.test'], ['config', 'commit.gpgsign', 'false'], ['add', '.'], ['commit', '-qm', 'initial'], ['remote', 'add', 'origin', str(remote)]]:
            subprocess.run(['git'] + command, cwd=self.project, check=True)
        (self.project / 'pnpm-lock.yaml').write_text('after')
        (self.project / 'unrelated.txt').write_text('after')
        args = dict(HEAD_REF='release-please--main', COMMIT_MESSAGE='sync', LOCKFILE='pnpm-lock.yaml', PUSH_TOKEN='')
        self.okay(self.run_step('pnpm-lockfile-sync.yml', 'push', **args))
        changed = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'], cwd=self.project, text=True)
        self.assertEqual('pnpm-lock.yaml\n', changed)
        self.okay(self.run_step('pnpm-lockfile-sync.yml', 'push', **args))
        self.assertIn('status=unchanged', Path(self.env['GITHUB_OUTPUT']).read_text())

    def test_major_tag_remote_reads_are_authenticated_and_share_one_snapshot(self):
        self.stub('git', '''import json, os, pathlib, sys
args = sys.argv[1:]
log = pathlib.Path(os.environ['RUNNER_TEMP']) / 'git-calls.jsonl'
with log.open('a') as out: out.write(json.dumps(args) + '\\n')
if 'rev-list' in args: print('a' * 40)
if 'ls-remote' in args:
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    count = sum('ls-remote' in call for call in calls)
    if count == 1:
        print('c' * 40 + '\\trefs/tags/v1')
        print('b' * 40 + '\\trefs/tags/v1^{}')
    else: print('a' * 40 + '\\trefs/tags/v1')
''')
        self.okay(self.run_step('repository-release-please.yml', 'move', TAG_NAME='v1.2.3', TESTED_SHA='a' * 40, PUSH_TOKEN='fake-token', HAS_TAG_TOKEN='true'))
        calls = [json.loads(line) for line in (self.root / 'git-calls.jsonl').read_text().splitlines()]
        remote_calls = [call for call in calls if any(command in call for command in ['fetch', 'ls-remote', 'push'])]
        for call in remote_calls:
            self.assertIn('credential.helper=', call)
            self.assertTrue(any(arg.startswith('credential.helper=!') for arg in call))
        self.assertEqual(2, sum('ls-remote' in call for call in calls))
        push = next(call for call in calls if 'push' in call)
        self.assertIn('--force-with-lease=refs/tags/v1:' + 'c' * 40, push)

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
            for shorthand in ['read-all', 'write-all']:
                caller.write_text(text.replace('{contents: read}', shorthand))
                self.assertTrue(any('scoped permission mappings' in error for error in self.checks.validate(root)))
            callee.unlink()
            self.assertTrue(self.checks.validate(root))
            (root / 'leaf.yml').write_text('on: {workflow_call: {}}\njobs:\n  run:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    permissions: {packages: write}\n    steps: [{run: echo okay}]\n')
            callee.write_text('on: {workflow_call: {}}\npermissions: {contents: read}\njobs:\n  run:\n    uses: ./.github/workflows/leaf.yml\n')
            caller.write_text(text.replace('contents: read}', 'contents: read, packages: write}'))
            self.assertTrue(any('callee.yml' in error and 'caller must grant packages' in error for error in self.checks.validate(root)))

    def test_registration_and_release_gate_cover_all_checks_and_merge_queue(self):
        tests = workflow('contract-tests.yml')
        self.assertIn('merge_group', tests['on'])
        self.assertNotIn('paths', tests['on']['pull_request'] or {})
        required = set(tests['jobs']['checks']['needs'])
        self.assertEqual(set(tests['jobs']) - {'checks'}, required)
        runs = [step.get('run', '') for step in tests['jobs']['validate']['steps']]
        self.assertTrue(any('scripts/check.py' in run for run in runs))
        self.assertTrue(any('scripts/check_nvim.py --prepare' in run for run in runs))
        self.assertEqual('max', tests['jobs']['queue-proof']['concurrency']['queue'])
        self.assertEqual(3, len(tests['jobs']['queue-proof']['strategy']['matrix']['item']))
        bootstrap = step('contract-tests.yml', 'Install actionlint')
        self.assertTrue(bootstrap['uses'].startswith('jdx/mise-action@'))
        self.assertEqual('2026.9.18', str(bootstrap['with']['version']))
        release = workflow('repository-release-please.yml')
        self.assertEqual('validate', release['jobs']['release']['needs'])
        run = step('repository-release-please.yml', 'move')['run']
        self.assertIn('test "$target_sha" = "$TESTED_SHA"', run)
        self.assertIn('test "$published_sha" = "$target_sha"', run)
        self.assertIn('--force-with-lease', run)

    def test_reusable_call_schema_and_literal_input_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'callee.yml').write_text('on: {workflow_call: {inputs: {environment: {type: string, required: true}, snapshot: {type: boolean}}}}\njobs:\n  run:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    permissions: {contents: read}\n    steps: [{run: echo okay}]\n')
            base = {'on': 'push', 'permissions': {'contents': 'read'}, 'jobs': {'run': {'uses': './.github/workflows/callee.yml', 'with': {'environment': 'release', 'snapshot': True}}}}
            caller = root / 'caller.yml'
            caller.write_text(yaml.safe_dump(base))
            self.assertEqual([], self.checks.validate(root))
            supported = dict(base, jobs={'run': dict(base['jobs']['run'], **{'cache-mode': 'read'})})
            caller.write_text(yaml.safe_dump(supported))
            self.assertEqual([], self.checks.validate(root))
            for extra in [{'environment': 'release'}, {'runs-on': 'ubuntu-latest'}, {'with': {'snapshot': True}}, {'with': {'environment': 'release', 'snapshot': 'true'}}, {'with': {'environment': 'release', 'unknown': True}}]:
                invalid = dict(base, jobs={'run': dict(base['jobs']['run'], **extra)})
                caller.write_text(yaml.safe_dump(invalid))
                self.assertTrue(self.checks.validate(root), extra)
        release = workflow('repository-release-please.yml')['jobs']['release']
        self.assertNotIn('environment', release)
        self.assertEqual('release', release['with']['environment'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = 'on: push\njobs:\n  first: &defaults\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    permissions: {contents: read}\n    steps: [{run: echo okay}]\n  second: *defaults\n'
            path = root / 'anchors.yml'
            path.write_text(source)
            self.assertEqual([], self.checks.validate(root))
            path.write_text(source.replace('second: *defaults', 'second:\n    <<: *defaults'))
            self.assertTrue(any('YAML merge keys' in error for error in self.checks.validate(root)))
            for where in ['workflow', 'job']:
                for queue, cancel, accepted in [('max', False, True), ('single', True, True), ('max', True, False), ('invalid', False, False)]:
                    document = yaml.safe_load(source)
                    target = document if where == 'workflow' else document['jobs']['first']
                    target['concurrency'] = {'group': 'fixture', 'queue': queue, 'cancel-in-progress': cancel}
                    path.write_text(yaml.safe_dump(document))
                    self.assertEqual(accepted, not self.checks.validate(root), (where, queue, cancel))


if __name__ == '__main__':
    unittest.main()
