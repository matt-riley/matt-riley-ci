#!/usr/bin/env python3
"""Exercise the actual reusable Neovim command with isolated positive/negative consumers."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]


def shell(source, cwd, env):
    process = subprocess.Popen(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', source], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise RuntimeError('Neovim workflow command hung') from None
    return process.returncode, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true', help='Download the workflow default Neovim and mini.nvim using the actual installation steps')
    parser.add_argument('--nvim', type=Path, help='Existing Neovim executable, paired with --mini')
    parser.add_argument('--mini', type=Path, help='Existing pinned mini.nvim checkout')
    args = parser.parse_args()
    if args.prepare == bool(args.nvim or args.mini) or (not args.prepare and not (args.nvim and args.mini)):
        parser.error('Use --prepare or both --nvim and --mini')
    workflow = yaml.safe_load((ROOT / '.github/workflows/nvim-tests.yml').read_text())
    steps = workflow['jobs']['tests']['steps']
    inputs = workflow['on']['workflow_call']['inputs']
    run = next(step['run'] for step in steps if step.get('id') == 'tests')
    with tempfile.TemporaryDirectory(prefix='nvim-contracts-') as temporary:
        root = Path(temporary)
        env = dict(os.environ, RUNNER_TEMP=str(root), GITHUB_PATH=str(root / 'paths'), EXPECTED_SHA256='')
        nvim, mini = args.nvim, args.mini
        if args.prepare:
            for name, overrides in [('Install Neovim', {'VERSION': inputs['neovim-version']['default']}), ('Fetch pinned mini.nvim', {'MINI_SHA': inputs['mini-version']['default']})]:
                code, output = shell(next(step['run'] for step in steps if step.get('name') == name), ROOT, dict(env, **overrides))
                if code: raise RuntimeError(name + '\n' + output)
            nvim = Path((root / 'paths').read_text().splitlines()[-1]) / 'nvim'
            mini = root / 'mini.nvim'
        nvim, mini = nvim.resolve(), mini.resolve()
        setup = 'require("mini.test").setup()'
        cases = [
            ('passing', setup, 'MiniTest.expect.equality(42, 42)', 0),
            ('assertion failure', setup, 'MiniTest.expect.equality(42, 99)', 1),
            ('runtime error', setup, 'error("intentional error")', 1),
            ('empty set', setup, None, 1),
            ('collection error', setup, 'collection-error', 1),
            ('init error', 'error("broken init")', None, 1),
            ('custom nonquitting reporter', 'require("mini.test").setup({execute={reporter={}}})', 'MiniTest.expect.equality(42, 99)', 1),
        ]
        for index, (name, init, body, expected) in enumerate(cases):
            project = root / str(index)
            (project / 'tests').mkdir(parents=True)
            (project / 'tests/minimal_init.lua').write_text('vim.opt.rtp:append(os.getenv("MINI_PATH"))\n' + init + '\n')
            test = 'return MiniTest.new_set()' if body is None else 'local T = MiniTest.new_set()\nT["case"] = function() ' + body + ' end\nreturn T'
            if body == 'collection-error': test = 'error("broken collection")'
            (project / 'tests/test_case.lua').write_text(test + '\n')
            case_env = dict(env, PATH=str(nvim.parent) + os.pathsep + env['PATH'], MINI_PATH=str(mini), MINIMAL_INIT='tests/minimal_init.lua', TEST_DIRECTORY='tests', NVIM_LOG_FILE=str(project / 'nvim.log'))
            for kind in ['CONFIG', 'DATA', 'STATE', 'CACHE']:
                case_env['XDG_' + kind + '_HOME'] = str(project / kind.lower())
            code, output = shell(run, project, case_env)
            if code != expected: raise RuntimeError(f'{name}: expected exit {expected}, got {code}\n{output}')
            print(f'{name}: exit {code}', flush=True)
        print('All 7 real Neovim exit-status contracts passed.')


if __name__ == '__main__':
    main()
