"""Execute the optional go-ci coverage-threshold gate with real shells."""
import json
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


def step(identity):
    return next(s for s in STEPS if s.get('id', s.get('name')) == identity)


class GoCoverageThreshold(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.project = self.root / 'nested project'
        self.project.mkdir()
        self.summary = self.root / 'summary'
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'], GITHUB_STEP_SUMMARY=str(self.summary))

    def stub_go(self, total):
        """Print the final line `go tool cover -func` emits for a profile."""
        path = self.bin / 'go'
        path.write_text('#!/usr/bin/env python3\nimport sys\nassert sys.argv[1:3] == ["tool", "cover"], sys.argv\n'
                        'assert sys.argv[3].startswith("-func="), sys.argv\n'
                        'print("example.test/pkg/a.go:3:\\tf\\t100.0%")\nprint("total:\\t\\t\\t(statements)\\t' + total + '")\n')
        path.chmod(0o755)

    def run_step(self, identity, **env):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(identity)['run']], cwd=self.project, env={**self.env, **env}, text=True, capture_output=True, timeout=45)

    def enforce(self, total, threshold, profile='coverage.out'):
        self.stub_go(total)
        (self.project / 'coverage.out').write_text('mode: set\n')
        return self.run_step('coverage-threshold', THRESHOLD=threshold, COVERAGE_PATH=profile)

    def test_default_is_off_and_backward_compatible(self):
        inputs = WORKFLOW['on']['workflow_call']['inputs']
        self.assertEqual(0, inputs['coverage-threshold']['default'])
        self.assertEqual('number', inputs['coverage-threshold']['type'])
        self.assertFalse(inputs['coverage-threshold'].get('required', False))
        for identity in ['coverage-threshold-inputs', 'coverage-threshold']:
            self.assertEqual('${{ inputs.coverage-threshold != 0 }}', step(identity)['if'])

    def test_every_existing_input_and_check_is_unchanged_in_shape(self):
        names = [s.get('id', s.get('name')) for s in STEPS]
        for required in ['build', 'test', 'vet', 'fmt', 'coverage', 'Validate coverage inputs', 'Summary']:
            self.assertIn(required, names)
        self.assertLess(names.index('test'), names.index('coverage-threshold'))
        self.assertLess(names.index('coverage-threshold-inputs'), names.index('build'))
        self.assertLess(names.index('coverage-threshold'), names.index('coverage'))

    def test_gate_passes_at_or_above_threshold(self):
        for total, threshold in [('71.0%', '71'), ('71.3%', '71'), ('100.0%', '100'), ('70.9%', '70.9'), ('0.5%', '0.5')]:
            with self.subTest(total=total, threshold=threshold):
                result = self.enforce(total, threshold)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn('Coverage threshold met.', result.stdout)
        self.assertIn('- threshold: 0.5%', self.summary.read_text())

    def test_gate_fails_below_threshold_with_the_numbers(self):
        for total, threshold in [('70.9%', '71'), ('59.9%', '60'), ('0.0%', '1'), ('99.9%', '100')]:
            with self.subTest(total=total, threshold=threshold):
                result = self.enforce(total, threshold)
                self.assertNotEqual(0, result.returncode)
                self.assertIn('is below threshold ' + threshold + '%', result.stdout)

    def test_missing_empty_or_unparseable_profiles_fail_closed(self):
        self.stub_go('50.0%')
        self.assertNotEqual(0, self.run_step('coverage-threshold', THRESHOLD='10', COVERAGE_PATH='absent.out').returncode)
        (self.project / 'empty.out').touch()
        self.assertNotEqual(0, self.run_step('coverage-threshold', THRESHOLD='10', COVERAGE_PATH='empty.out').returncode)
        self.assertNotEqual(0, self.enforce('n/a', '10').returncode)

    def test_inputs_are_validated_before_any_check_runs(self):
        good = dict(THRESHOLD='71', COVERAGE_PATH='coverage.out', RUN_TEST='true')
        self.assertEqual(0, self.run_step('coverage-threshold-inputs', **good).returncode)
        self.assertEqual(0, self.run_step('coverage-threshold-inputs', **{**good, 'THRESHOLD': '99.5'}).returncode)
        for override in [dict(THRESHOLD='-1'), dict(THRESHOLD='101'), dict(THRESHOLD='abc'), dict(THRESHOLD='1e2'), dict(THRESHOLD=''),
                         dict(RUN_TEST='false'), dict(COVERAGE_PATH=''), dict(COVERAGE_PATH='  \n'), dict(COVERAGE_PATH='a.out\nb.out'),
                         dict(COVERAGE_PATH='*.out'), dict(COVERAGE_PATH='!private.out'), dict(COVERAGE_PATH='cov[1].out')]:
            with self.subTest(override=override):
                result = self.run_step('coverage-threshold-inputs', **{**good, **override})
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertIn('::error', result.stdout)

    @unittest.skipUnless(shutil.which('go'), 'go toolchain not installed')
    def test_matches_the_total_line_real_go_prints(self):
        shutil.copytree(ROOT / 'fixtures/go', self.project, dirs_exist_ok=True)
        real = dict(os.environ, GOFLAGS='-mod=mod')
        subprocess.run(['go', 'test', '-coverprofile=coverage.out', './...'], cwd=self.project, env=real, check=True, capture_output=True)
        # The fixture covers 1 of 2 statements; compare with Go's own figure rather than a literal.
        out = subprocess.run(['go', 'tool', 'cover', '-func=coverage.out'], cwd=self.project, env=real, check=True, capture_output=True, text=True).stdout
        total = float(out.strip().splitlines()[-1].split()[-1].rstrip('%'))
        self.env = dict(real, GITHUB_STEP_SUMMARY=str(self.summary))
        result = self.run_step("coverage-threshold", THRESHOLD=str(total), COVERAGE_PATH="coverage.out")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotEqual(0, self.run_step('coverage-threshold', THRESHOLD=str(min(total + 0.5, 100)), COVERAGE_PATH='coverage.out').returncode)


if __name__ == '__main__':
    unittest.main()
