"""Execute the opt-in nvim-typecheck (LuaLS) workflow steps with real shells and stubbed tools."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/nvim-typecheck.yml').read_text())
JOB = WORKFLOW['jobs']['typecheck']
INPUTS = WORKFLOW['on']['workflow_call']['inputs']
TESTS = yaml.safe_load((ROOT / '.github/workflows/nvim-tests.yml').read_text())


def step(identity, steps=JOB['steps']):
    return next(s for s in steps if s.get('id', s.get('name')) == identity)


class NvimTypecheck(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.project = self.root / 'nested project'
        self.project.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'], RUNNER_TEMP=str(self.root), RUNNER_OS='Linux', RUNNER_ARCH='X64',
                        GITHUB_WORKSPACE=str(self.root), GITHUB_PATH=str(self.root / 'path'), GITHUB_OUTPUT=str(self.root / 'output'))

    def stub(self, name, source):
        path = self.bin / name
        path.write_text('#!/usr/bin/env python3\n' + source)
        path.chmod(0o755)

    def run_step(self, identity, **env):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(identity)['run']], cwd=self.project, env={**self.env, **env}, text=True, capture_output=True, timeout=60)

    def test_opt_in_workflow_with_the_consumers_settings_as_defaults(self):
        self.assertEqual('3.13.6', INPUTS['luals-version']['default'])
        self.assertEqual('Warning', INPUTS['checklevel']['default'])
        self.assertEqual('.', INPUTS['check-path']['default'])
        for name, spec in INPUTS.items():
            self.assertFalse(spec.get('required', False), name)
        self.assertEqual('read', JOB['permissions']['contents'])
        self.assertIs(False, JOB['steps'][0]['with']['persist-credentials'])
        self.assertIn('--check_format=json', step('check')['run'])
        self.assertIn('--checklevel="$CHECKLEVEL"', step('check')['run'])

    def test_neovim_installer_is_identical_to_the_nvim_tests_installer(self):
        self.assertEqual(step('Install Neovim', TESTS['jobs']['tests']['steps']), step('Install Neovim'))
        for key in ['neovim-version', 'neovim-sha256']:
            self.assertEqual(TESTS['on']['workflow_call']['inputs'][key]['default'], INPUTS[key]['default'])

    def test_luals_archive_is_verified_before_extraction(self):
        digest = hashlib.sha256(b'luals archive').hexdigest()
        self.stub('gh', "import pathlib, sys\na = sys.argv\nassert a[1:3] == ['release', 'download'] and a[a.index('--repo') + 1] == 'LuaLS/lua-language-server', a\n"
                        "pathlib.Path(a[a.index('--dir') + 1], a[a.index('--pattern') + 1]).write_bytes(b'luals archive')\n")
        self.stub('tar', "import os, pathlib\npathlib.Path(os.environ['RUNNER_TEMP'], 'extracted').touch()\n")
        args = dict(VERSION='3.13.6', EXPECTED_SHA256=digest, GH_TOKEN='x')
        result = self.run_step('Install LuaLS', **args)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue((self.root / 'extracted').exists())
        self.assertIn(str(self.root / 'luals' / 'bin'), Path(self.env['GITHUB_PATH']).read_text())
        for bad in [dict(EXPECTED_SHA256='0' * 64), dict(EXPECTED_SHA256='invalid'), dict(VERSION='v3.13.6'), dict(VERSION='3.13'), dict(VERSION='3.13.6/../x')]:
            with self.subTest(bad=bad):
                (self.root / 'extracted').unlink(missing_ok=True)
                Path(self.env['GITHUB_PATH']).unlink(missing_ok=True)
                self.assertNotEqual(0, self.run_step('Install LuaLS', **{**args, **bad}).returncode)
                self.assertFalse((self.root / 'extracted').exists())
                self.assertFalse(Path(self.env['GITHUB_PATH']).exists())
        for system in [dict(RUNNER_OS='macOS'), dict(RUNNER_ARCH='ARM64')]:
            self.assertNotEqual(0, self.run_step('Install LuaLS', **{**args, **system}).returncode)

    def stub_luals(self, diagnostics, status=0):
        runtime = self.root / 'runtime'
        runtime.mkdir(exist_ok=True)
        self.stub('nvim', 'import sys\nsys.stdout.write(' + repr(str(runtime)) + ')\n')
        body = 'import json, os, pathlib, sys\na = sys.argv[1:]\nlog = [x.split("=", 1)[1] for x in a if x.startswith("--logpath=")][0]\n' \
               'open(os.environ["RUNNER_TEMP"] + "/luals-args.json", "w").write(json.dumps({"args": a, "vimruntime": os.environ.get("VIMRUNTIME"), "cwd": os.getcwd()}))\n'
        if diagnostics is not None:
            body += 'pathlib.Path(log, "check.json").write_text(' + repr(diagnostics) + ')\n'
        self.stub('lua-language-server', body + 'sys.exit(' + str(status) + ')\n')

    def check(self, **env):
        return self.run_step('check', CHECK_PATH='.', CHECKLEVEL='Warning', **env)

    def test_clean_run_passes_with_the_expected_luals_arguments(self):
        for clean in ['[]', '{}', '']:
            self.stub_luals(clean)
            result = self.check()
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn('LuaLS diagnostics: none', result.stdout)
        recorded = json.loads((self.root / 'luals-args.json').read_text())
        self.assertEqual(['--check=.', '--checklevel=Warning', '--check_format=json', '--logpath=' + str(self.root / 'luals-log')], recorded['args'])
        self.assertEqual(str(self.root / 'runtime'), recorded['vimruntime'])

    def test_diagnostics_fail_and_are_printed(self):
        diagnostics = json.dumps({'file:///p/lua/bad.lua': [{'code': 'undefined-global', 'message': 'Undefined global `x`.'}]})
        for status in [0, 1]:
            self.stub_luals(diagnostics, status)
            result = self.check()
            self.assertNotEqual(0, result.returncode)
            self.assertIn('undefined-global', result.stdout)

    def test_missing_results_or_a_crash_fail_closed(self):
        self.stub_luals(None)
        result = self.check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('wrote no check.json', result.stderr)
        self.stub_luals('[]', 3)
        self.assertNotEqual(0, self.check().returncode)

    def test_stale_results_from_an_earlier_run_are_not_trusted(self):
        (self.root / 'luals-log').mkdir()
        (self.root / 'luals-log' / 'check.json').write_text('[]')
        self.stub_luals(None)
        self.assertNotEqual(0, self.check().returncode)

    def test_inputs_are_validated(self):
        self.stub_luals('[]')
        for bad in [dict(CHECKLEVEL='Fatal'), dict(CHECKLEVEL=''), dict(CHECK_PATH='--help'), dict(CHECK_PATH='  ')]:
            with self.subTest(bad=bad):
                self.assertNotEqual(0, self.run_step('check', **{'CHECK_PATH': '.', 'CHECKLEVEL': 'Warning', **bad}).returncode)
        self.assertEqual(0, self.run_step('check', CHECK_PATH='lua', CHECKLEVEL='Error').returncode)
        self.stub('nvim', 'import sys\nsys.stdout.write("/does/not/exist")\n')
        self.assertNotEqual(0, self.check().returncode)


if __name__ == '__main__':
    unittest.main()
