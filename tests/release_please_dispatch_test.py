"""Execute the opt-in release-please-dispatch follow-on with real shells and a stubbed gh."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/release-please-dispatch.yml').read_text())
JOB = WORKFLOW['jobs']['dispatch']
INPUTS = WORKFLOW['on']['workflow_call']['inputs']
SPEC = importlib.util.spec_from_file_location('check', ROOT / 'scripts/check.py')
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


def step(identity):
    return next(s for s in JOB['steps'] if s.get('id', s.get('name')) == identity)


class ReleasePleaseDispatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_text('#!/usr/bin/env python3\nimport json, os, sys\nopen(os.environ["RUNNER_TEMP"] + "/gh-calls", "a").write(json.dumps(sys.argv[1:]) + "\\n")\n'
                      'sys.exit(int(os.environ.get("GH_EXIT", "0")))\n')
        gh.chmod(0o755)
        self.output = self.root / 'output'
        self.calls = self.root / 'gh-calls'
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], RUNNER_TEMP=str(self.root), GITHUB_OUTPUT=str(self.output),
                        GITHUB_REPOSITORY='owner/project', GH_TOKEN='token')

    def dispatch(self, **env):
        defaults = dict(RELEASE_CREATED='true', TAG='v1.2.3', WORKFLOW_FILE='goreleaser.yml', RELEASE_TOKEN_AVAILABLE='false')
        self.output.write_text('')
        self.calls.unlink(missing_ok=True)
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step('dispatch')['run']], cwd=self.root, env={**self.env, **defaults, **env}, text=True, capture_output=True, timeout=30)

    def gh_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_inputs_defaults_and_permissions(self):
        self.assertTrue(INPUTS['release-created']['required'] and INPUTS['tag']['required'])
        self.assertEqual('goreleaser.yml', INPUTS['workflow']['default'])
        self.assertFalse(WORKFLOW['on']['workflow_call']['secrets']['release-token'].get('required', False))
        self.assertEqual({'contents': 'read', 'actions': 'write'}, JOB['permissions'])

    def test_release_please_itself_is_untouched_and_needs_no_new_permission(self):
        callee = yaml.safe_load((ROOT / '.github/workflows/release-please.yml').read_text())
        for job in callee['jobs'].values():
            self.assertNotIn('actions', job['permissions'])
        self.assertEqual({'config-file', 'runner', 'manifest-file', 'component-output-key', 'target-branch', 'environment'}, set(callee['on']['workflow_call']['inputs']))

    def test_callers_must_grant_actions_write(self):
        directory = self.root / 'workflows'
        directory.mkdir()
        shutil.copy(ROOT / '.github/workflows/release-please-dispatch.yml', directory)
        with_inputs = {'release-created': 'true', 'tag': 'v1.0.0'}
        for permissions, valid in [({'contents': 'read', 'actions': 'write'}, True), ({'contents': 'read'}, False), ({'contents': 'write', 'issues': 'write', 'pull-requests': 'write'}, False)]:
            caller = {'on': 'push', 'jobs': {'follow-on': {'needs': 'x', 'permissions': permissions, 'uses': './.github/workflows/release-please-dispatch.yml', 'with': with_inputs}}}
            caller['jobs']['x'] = {'runs-on': 'ubuntu-latest', 'timeout-minutes': 5, 'permissions': {'contents': 'read'}, 'steps': [{'run': 'true'}]}
            (directory / 'caller.yml').write_text(yaml.safe_dump(caller))
            errors = [e for e in CHECKS.validate(directory) if 'caller.yml' in e]
            self.assertEqual(valid, not errors, (permissions, errors))

    def test_dispatches_the_workflow_at_the_release_tag(self):
        result = self.dispatch()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([['workflow', 'run', 'goreleaser.yml', '--repo', 'owner/project', '--ref', 'v1.2.3']], self.gh_calls())
        self.assertIn('dispatched=true', self.output.read_text())

    def test_other_publishers_and_component_tags(self):
        for workflow_file, tag in [('homebrew.yml', 'v0.4.0'), ('docker-publish.yaml', 'v2.0.0-rc.1'), ('goreleaser.yml', 'clients/typescript-v1.0.0')]:
            self.assertEqual(0, self.dispatch(WORKFLOW_FILE=workflow_file, TAG=tag).returncode)
            self.assertEqual([['workflow', 'run', workflow_file, '--repo', 'owner/project', '--ref', tag]], self.gh_calls())

    def test_no_release_means_no_dispatch(self):
        for created in ['false', '']:
            result = self.dispatch(RELEASE_CREATED=created, TAG='')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([], self.gh_calls())
            self.assertIn('dispatched=false', self.output.read_text())

    def test_release_token_means_the_tag_push_starts_the_publisher(self):
        result = self.dispatch(RELEASE_TOKEN_AVAILABLE='true')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], self.gh_calls())
        self.assertIn('dispatched=false', self.output.read_text())
        self.assertIn('secrets.release-token', step('dispatch')['env']['RELEASE_TOKEN_AVAILABLE'])

    def test_invalid_inputs_never_reach_gh(self):
        for bad in [dict(WORKFLOW_FILE='../goreleaser.yml'), dict(WORKFLOW_FILE='goreleaser'), dict(WORKFLOW_FILE='--help.yml'), dict(WORKFLOW_FILE='a b.yml'),
                    dict(TAG='-v1'), dict(TAG='v1 --ref main'), dict(TAG='$(id)'), dict(TAG='')]:
            with self.subTest(bad=bad):
                self.assertNotEqual(0, self.dispatch(**bad).returncode)
                self.assertEqual([], self.gh_calls())

    def test_a_failed_dispatch_fails_the_job(self):
        result = self.dispatch(GH_EXIT='1')
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('dispatched=true', self.output.read_text())


if __name__ == '__main__':
    unittest.main()
