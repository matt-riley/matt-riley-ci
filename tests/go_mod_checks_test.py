"""Execute the optional go-ci module checks (go mod verify / go mod tidy) with real shells."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/go-ci.yml').read_text())
STEPS = WORKFLOW['jobs']['test']['steps']
BOGUS_SUM = 'example.invalid/unused v1.0.0 h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n'


def step(identity):
    return next(s for s in STEPS if s.get('id', s.get('name')) == identity)


class GoModChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'nested project'
        self.project.mkdir()
        (self.project / 'go.mod').write_text('module example.test/m\n\ngo 1.21\n')
        (self.project / 'main.go').write_text('package main\n\nfunc main() {}\n')
        self.env = dict(os.environ, GOFLAGS='-mod=mod', GOTOOLCHAIN='local')

    def run_step(self, identity):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(identity)['run']], cwd=self.project, env=self.env, text=True, capture_output=True, timeout=120)

    def stub_go(self, source):
        bin_dir = self.root / 'bin'
        bin_dir.mkdir(exist_ok=True)
        path = bin_dir / 'go'
        path.write_text('#!/usr/bin/env python3\n' + source)
        path.chmod(0o755)
        self.env['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']

    def test_both_checks_are_opt_in_booleans(self):
        inputs = WORKFLOW['on']['workflow_call']['inputs']
        for name in ['run-verify', 'run-tidy']:
            self.assertEqual(False, inputs[name]['default'])
            self.assertEqual('boolean', inputs[name]['type'])
            self.assertFalse(inputs[name].get('required', False))
        self.assertEqual('${{ inputs.run-verify }}', step('verify')['if'])
        self.assertEqual('${{ inputs.run-tidy }}', step('tidy')['if'])
        names = [s.get('id', s.get('name')) for s in STEPS]
        for before in ['verify', 'tidy']:
            self.assertLess(names.index(before), names.index('test'))

    @unittest.skipUnless(shutil.which('go'), 'go toolchain not installed')
    def test_verify_passes_for_a_consistent_module(self):
        result = self.run_step('verify')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('all modules verified', result.stdout)

    def test_verify_failure_fails_the_step(self):
        self.stub_go('import sys\nprint("example.test/dep v1.0.0: dir has been modified", file=sys.stderr)\nsys.exit(1)\n')
        self.assertNotEqual(0, self.run_step('verify').returncode)

    @unittest.skipUnless(shutil.which('go'), 'go toolchain not installed')
    def test_tidy_passes_and_leaves_the_files_alone(self):
        (self.project / 'go.sum').write_text('')
        before = {name: (self.project / name).read_text() for name in ['go.mod', 'go.sum']}
        result = self.run_step('tidy')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('are tidy', result.stdout)
        self.assertEqual(before, {name: (self.project / name).read_text() for name in ['go.mod', 'go.sum']})

    @unittest.skipUnless(shutil.which('go'), 'go toolchain not installed')
    def test_tidy_without_go_sum_passes_and_does_not_create_one(self):
        result = self.run_step('tidy')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertFalse((self.project / 'go.sum').exists())

    @unittest.skipUnless(shutil.which('go'), 'go toolchain not installed')
    def test_untidy_go_sum_fails_with_a_diff_and_is_restored(self):
        (self.project / 'go.sum').write_text(BOGUS_SUM)
        result = self.run_step('tidy')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('-example.invalid/unused', result.stdout)
        self.assertIn('go mod tidy would change files', result.stdout)
        self.assertEqual(BOGUS_SUM, (self.project / 'go.sum').read_text())

    def test_tidy_command_failure_still_restores_the_files(self):
        self.stub_go('import sys\nfrom pathlib import Path\nPath("go.mod").write_text("changed")\nsys.exit(1)\n')
        original = (self.project / 'go.mod').read_text()
        self.assertNotEqual(0, self.run_step('tidy').returncode)
        self.assertEqual(original, (self.project / 'go.mod').read_text())
        self.assertFalse((self.project / 'go.sum').exists())


if __name__ == '__main__':
    unittest.main()
