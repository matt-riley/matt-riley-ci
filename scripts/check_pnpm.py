#!/usr/bin/env python3
"""Exercise actual lockfile scripts and the hosted artifact handoff without live publication."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
BEFORE = "lockfileVersion: '9.0'\nimporters:\n  .: {}\n"
AFTER = BEFORE + '# updated in isolated generation\n'


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.STDOUT)


def fixture(root):
    root.mkdir(parents=True, exist_ok=True)
    project = root / 'nested project'
    project.mkdir()
    (project / 'pnpm-lock.yaml').write_text(BEFORE)
    (project / 'package.json').write_text('{"name":"handoff-fixture","private":true}\n')
    (project / 'unrelated.txt').write_text('original\n')
    git(root, 'init', '-q', '-b', 'main')
    for key, value in [('user.name', 'Fixture'), ('user.email', 'fixture@example.test'), ('commit.gpgsign', 'false')]:
        git(root, 'config', key, value)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'original source')
    return project


def invoke(identity, cwd, env):
    document = yaml.safe_load((ROOT / '.github/workflows/pnpm-lockfile-sync.yml').read_text())
    script = next(s['run'] for job in document['jobs'].values() for s in job['steps'] if s.get('id', s.get('name')) == identity)
    with tempfile.TemporaryDirectory(prefix='pnpm-step-') as temporary:
        output = Path(temporary) / 'outputs'
        result = subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', script], cwd=cwd,
            env=dict(env, GITHUB_OUTPUT=str(output)), text=True, capture_output=True, timeout=45)
        if result.returncode:
            raise RuntimeError(f'{identity}: {result.stdout}{result.stderr}')
        return dict(line.split('=', 1) for line in output.read_text().splitlines()) if output.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['export', 'publish'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--import-directory', type=Path)
    args = parser.parse_args()
    if args.mode == 'publish' and not args.import_directory:
        parser.error('publish requires --import-directory')
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GITHUB_WORKSPACE=str(directory), RUNNER_TEMP=str(directory), LOCKFILE='pnpm-lock.yaml')
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env['PATH']
    if args.mode == 'export':
        env.pop('PUSH_TOKEN', None)
        project = fixture(directory / 'generation')
        original = invoke('snapshot', project, env)['sha256']
        # Model a consumer install hook that changes local Git state. Only the
        # resulting lockfile bytes may cross to the separate publication runner.
        hook_script = '#!/bin/sh\nexit 91\n'
        payload = '\n'.join([
            'import pathlib, subprocess',
            f'pathlib.Path("pnpm-lock.yaml").write_text({AFTER!r})',
            'pathlib.Path("unrelated.txt").write_text("changed by install\\n")',
            f'hooks = pathlib.Path({str(project.parent / ".git/hooks")!r})',
            'hooks.mkdir(parents=True, exist_ok=True)',
            f'hook = hooks / "pre-commit"; hook.write_text({hook_script!r}); hook.chmod(0o755)',
            'subprocess.run(["git", "config", "core.hooksPath", str(hooks)], check=True)',
        ])
        invoke('Update lockfile', project, dict(env, INSTALL_COMMAND=shlex.join([sys.executable, '-c', payload])))
        exported = invoke('export', project, dict(env, ORIGINAL_SHA=original))
        if exported['changed'] != 'true': raise RuntimeError('Changed fixture was not exported')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('path=' + exported['path'] + '\nname=' + exported['name'] + '\n')
        print('Actual generation scripts exported only the changed lockfile.')
    else:
        fresh = directory / invoke('workspace', directory, env)['path']
        project = fixture(fresh)
        remote = directory / 'publication.git'
        git(directory, 'init', '--bare', '-q', str(remote))
        git(fresh, 'remote', 'add', 'origin', str(remote))
        published = invoke('push', fresh, dict(env, WORKING_DIR=project.name, IMPORT_DIR=str(args.import_directory.resolve()),
            HEAD_REF='release-please--fixture', COMMIT_MESSAGE='fixture lockfile update', PUSH_TOKEN='fixture-only-token'))
        if published.get('status') != 'pushed': raise RuntimeError('Fixture publication did not report pushed')
        changed = git(fresh, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').strip()
        if changed != project.name + '/pnpm-lock.yaml': raise RuntimeError('Publication changed unexpected paths: ' + changed)
        if (project / 'unrelated.txt').read_text() != 'original\n': raise RuntimeError('Generator state crossed the handoff')
        received = git(directory, '--git-dir', str(remote), 'show', 'refs/heads/release-please--fixture:' + changed)
        if received != AFTER: raise RuntimeError('Published bytes differ from the generated artifact')
        print('Actual publication script committed only artifact bytes from a fresh checkout; local remote verified.')


if __name__ == '__main__':
    main()
