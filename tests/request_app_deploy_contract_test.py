import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


class RequestAppDeployContractTest(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(Path('.github/workflows/request-app-deploy.yml').read_text())
        self.job = self.workflow['jobs']['request']
        self.script = self.job['steps'][1]['run']

    def test_permissions_and_explicit_credentials(self):
        token = self.job['steps'][0]['with']
        self.assertEqual('infra', token['repositories'])
        self.assertEqual('matt-riley', token['owner'])
        self.assertEqual('write', token['permission-contents'])
        self.assertEqual('${{ inputs.dispatch-app-id }}', token['app-id'])
        self.assertEqual('${{ secrets.INFRA_DISPATCH_PRIVATE_KEY }}', token['private-key'])
        self.assertEqual({'contents': 'read'}, self.workflow['permissions'])
        self.assertIn("github.ref == format('refs/heads/{0}', inputs.production-branch)", self.job['if'])
        self.assertEqual('main', self.workflow['on']['workflow_call']['inputs']['production-branch']['default'])

    def test_only_push_or_explicit_dispatch_on_production_branch_can_request(self):
        self.assertEqual(
            "(github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == format('refs/heads/{0}', inputs.production-branch)",
            self.job['if'],
        )

    def run_dispatch(self, **overrides):
        with tempfile.TemporaryDirectory() as directory:
            gh = Path(directory, 'gh')
            gh.write_text('#!/bin/sh\ncat\n')
            gh.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ['PATH'], APP='waffle', SOURCE_REPO='matt-riley/waffle', SOURCE_SHA='a' * 40, SOURCE_REF='refs/heads/main', RUN_ID='', ARTIFACT_NAME='', ARTIFACT_DIGEST='')
            env['GITHUB_OUTPUT'] = str(Path(directory, 'outputs'))
            env.update(overrides)
            return subprocess.run(['bash', '-c', self.script], env=env, text=True, capture_output=True)

    def test_source_dispatch_keeps_exact_source_identity(self):
        result = self.run_dispatch()
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)['client_payload']
        self.assertEqual(payload['app'], payload['app_id'])
        self.assertEqual('waffle', payload['app_id'])
        self.assertEqual('a' * 40, payload['source_sha'])
        self.assertEqual('matt-riley/waffle', payload['source_repo'])
        self.assertNotIn('artifact_run_id', payload)

    def test_binary_dispatch_requires_complete_immutable_artifact(self):
        result = self.run_dispatch(RUN_ID='123', ARTIFACT_NAME='waffle-linux-amd64', ARTIFACT_DIGEST='b' * 64)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)['client_payload']
        self.assertEqual(123, payload['artifact_run_id'])
        self.assertEqual('b' * 64, payload['artifact_digest'])
        for invalid in ({'RUN_ID': '123'}, {'ARTIFACT_NAME': 'only-name'}, {'SOURCE_SHA': 'main'}, {'APP': '../infra'}, {'RUN_ID': '0', 'ARTIFACT_NAME': 'binary', 'ARTIFACT_DIGEST': 'b' * 64}):
            with self.subTest(invalid=invalid):
                self.assertNotEqual(0, self.run_dispatch(**invalid).returncode)


if __name__ == '__main__':
    unittest.main()
