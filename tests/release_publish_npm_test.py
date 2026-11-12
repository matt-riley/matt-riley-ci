"""Execute the opt-in publish-npm workflow steps with real shells and a stubbed npm."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/release-publish-npm.yml').read_text())
JOB = WORKFLOW['jobs']['publish']
INPUTS = WORKFLOW['on']['workflow_call']['inputs']


def step(identity):
    return next(s for s in JOB['steps'] if s.get('id', s.get('name')) == identity)


class ReleasePublishNpm(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'nested package'
        self.project.mkdir()
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        npm = bin_dir / 'npm'
        npm.write_text('#!/usr/bin/env python3\nimport json, os, sys\nopen(os.environ["RUNNER_TEMP"] + "/npm-calls", "a").write(json.dumps({"args": sys.argv[1:], "token": os.environ.get("NODE_AUTH_TOKEN")}) + "\\n")\n'
                       'sys.exit(int(os.environ.get("NPM_EXIT", "0")))\n')
        npm.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'], RUNNER_TEMP=str(self.root))
        self.write_package({'name': '@owner/pkg', 'version': '1.2.3'})

    def write_package(self, data):
        (self.project / 'package.json').write_text(json.dumps(data))

    def run_step(self, identity, **env):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(identity)['run']], cwd=self.project, env={**self.env, **env}, text=True, capture_output=True, timeout=30)

    def verify(self, **env):
        defaults = dict(REF='v1.2.3', VERIFY_VERSION='true', ACCESS='', DIST_TAG='', REGISTRY_URL='https://npm.pkg.github.com')
        return self.run_step('verify', **{**defaults, **env})

    def publish(self, **env):
        (self.root / 'npm-calls').unlink(missing_ok=True)
        defaults = dict(NODE_AUTH_TOKEN='the-token', ACCESS='', DIST_TAG='', DRY_RUN='false')
        return self.run_step('publish', **{**defaults, **env})

    def calls(self):
        path = self.root / 'npm-calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_defaults_permissions_and_auth_match_the_two_consumers(self):
        self.assertEqual('https://npm.pkg.github.com', INPUTS['registry-url']['default'])
        self.assertEqual('24', INPUTS['node-version']['default'])
        for name, spec in INPUTS.items():
            self.assertFalse(spec.get('required', False), name)
        self.assertEqual({'contents': 'read', 'packages': 'write'}, JOB['permissions'])
        self.assertEqual('${{ secrets.token || github.token }}', step('publish')['env']['NODE_AUTH_TOKEN'])
        self.assertFalse(WORKFLOW['on']['workflow_call']['secrets']['token'].get('required', False))
        self.assertIs(False, JOB['steps'][0]['with']['persist-credentials'])

    def test_the_publish_token_is_only_exposed_to_the_publish_step(self):
        for item in JOB['steps']:
            if item.get('id') == 'publish':
                continue
            self.assertNotIn('secrets.', json.dumps(item), item.get('name'))
            self.assertNotIn('github.token', json.dumps(item), item.get('name'))
            self.assertNotIn('NODE_AUTH_TOKEN', json.dumps(item.get('env', {})), item.get('name'))

    def test_version_must_match_the_ref_when_verifying(self):
        for ref, ok in [('v1.2.3', True), ('typescript-client-v1.2.3', True), ('1.2.3', True), ('', True), ('v1.2.4', False), ('v1.2.3-rc.1', False)]:
            with self.subTest(ref=ref):
                self.assertEqual(ok, self.verify(REF=ref).returncode == 0)
        self.assertEqual(0, self.verify(REF='v9.9.9', VERIFY_VERSION='false').returncode)

    def test_unpublishable_packages_and_bad_options_fail_before_publishing(self):
        for data in [{'name': 'x'}, {'name': 'x', 'version': ''}, {'name': 'x', 'version': '1.2.3', 'private': True}]:
            self.write_package(data)
            self.assertNotEqual(0, self.verify().returncode, data)
        self.write_package({'name': '@owner/pkg', 'version': '1.2.3'})
        for bad in [dict(ACCESS='internal'), dict(DIST_TAG='-x'), dict(DIST_TAG='a b'), dict(REGISTRY_URL='http://registry.test'), dict(REGISTRY_URL='file:///x'), dict(REGISTRY_URL='')]:
            with self.subTest(bad=bad):
                self.assertNotEqual(0, self.verify(**bad).returncode)
        (self.project / 'package.json').unlink()
        self.assertNotEqual(0, self.verify().returncode)

    def test_publish_runs_npm_publish_with_the_token_and_requested_flags(self):
        self.assertEqual(0, self.publish().returncode)
        self.assertEqual([{'args': ['publish'], 'token': 'the-token'}], self.calls())
        self.assertEqual(0, self.publish(ACCESS='public', DIST_TAG='next', DRY_RUN='true').returncode)
        self.assertEqual(['publish', '--access', 'public', '--tag', 'next', '--dry-run'], self.calls()[0]['args'])

    def test_a_failed_publish_fails_the_job(self):
        self.assertNotEqual(0, self.publish(NPM_EXIT='1').returncode)

    def test_install_and_build_commands_keep_their_quoting(self):
        for identity, variable in [('Install dependencies', 'INSTALL_COMMAND'), ('Build', 'BUILD_COMMAND')]:
            result = self.run_step(identity, **{variable: 'printf "%s|" "a b" c'})
            self.assertEqual('a b|c|', result.stdout)
            self.assertNotEqual(0, self.run_step(identity, **{variable: 'false; true && exit 3'}).returncode)
        self.assertEqual("${{ inputs.install-command != '' }}", step('Install dependencies')['if'])
        self.assertEqual("${{ inputs.build-command != '' }}", step('Build')['if'])


if __name__ == '__main__':
    unittest.main()
