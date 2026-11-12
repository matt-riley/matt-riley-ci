"""Execute the opt-in nvim-docs generate-and-commit workflow against real local Git remotes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / '.github/workflows/nvim-docs.yml').read_text())
JOB = WORKFLOW['jobs']['docs']
INPUTS = WORKFLOW['on']['workflow_call']['inputs']


def step(identity):
    return next(s for s in JOB['steps'] if s.get('id', s.get('name')) == identity)


def git(*args, cwd, check=True):
    return subprocess.run(['git', '-c', 'init.defaultBranch=main', *args], cwd=cwd, check=check, text=True, capture_output=True)


class NvimDocs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        git('init', '--bare', str(self.remote), cwd=self.root)
        self.repo = self.root / 'plugin'
        self.repo.mkdir()
        git('init', cwd=self.repo)
        git('config', 'user.name', 'Fixture', cwd=self.repo)
        git('config', 'user.email', 'fixture@example.test', cwd=self.repo)
        (self.repo / 'README.md').write_text('plugin\n')
        git('add', '.', cwd=self.repo)
        git('commit', '-m', 'init', cwd=self.repo)
        git('push', str(self.remote), 'HEAD:refs/heads/main', cwd=self.repo)
        self.output = self.root / 'output'
        self.env = dict(os.environ, GITHUB_OUTPUT=str(self.output), GITHUB_WORKSPACE=str(self.repo), HOME=str(self.root))

    def run_step(self, identity, **env):
        return subprocess.run(['bash', '--noprofile', '--norc', '-eo', 'pipefail', '-c', step(identity)['run']], cwd=self.repo, env={**self.env, **env}, text=True, capture_output=True, timeout=60)

    def generate(self, command='mkdir -p doc && printf "*plugin.txt*\\n" > doc/plugin.txt && mkdir -p build && echo x > build/other.txt'):
        result = self.run_step('generate', DOCS_COMMAND=command, MINI_PATH=str(self.root / 'mini.nvim'))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def detect(self, pattern='.'):
        self.output.write_text('')
        result = self.run_step('detect', FILE_PATTERN=pattern)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return self.output.read_text().strip()

    def publish(self, **env):
        defaults = dict(FILE_PATTERN='.', COMMIT_MESSAGE='chore(docs): regenerate vim help', BRANCH='main', PUSH_TOKEN='unused-for-local-remote', REMOTE_URL=str(self.remote))
        self.output.write_text('')
        return self.run_step('publish', **{**defaults, **env})

    def remote_log(self):
        return git('log', '--format=%an <%ae>|%s', 'main', cwd=self.remote).stdout.strip().splitlines()

    def test_everything_is_opt_in_and_defaults_match_the_consumers(self):
        self.assertEqual('make docs', INPUTS['docs-command']['default'])
        self.assertEqual('chore(docs): regenerate vim help', INPUTS['commit-message']['default'])
        self.assertEqual('.', INPUTS['file-pattern']['default'])
        self.assertEqual(True, INPUTS['commit']['default'])
        self.assertFalse(WORKFLOW['on']['workflow_call']['secrets']['token'].get('required', False))
        self.assertEqual('write', JOB['permissions']['contents'])
        checkout = JOB['steps'][0]
        self.assertIs(False, checkout['with']['persist-credentials'])
        guard = step('publish')['if']
        for needle in ["github.event_name == 'push'", "github.event_name == 'workflow_dispatch'", 'inputs.commit', "github.ref_type == 'branch'"]:
            self.assertIn(needle, guard)

    def test_generate_runs_the_command_with_mini_path_and_no_push_token(self):
        result = self.run_step('generate', DOCS_COMMAND='test -n "$MINI_PATH" && test -z "${PUSH_TOKEN:-}" && echo ok', MINI_PATH='/m')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn('PUSH_TOKEN', str(step('generate').get('env', {})))
        self.assertNotEqual(0, self.run_step('generate', DOCS_COMMAND='   ', MINI_PATH='/m').returncode)
        self.assertNotEqual(0, self.run_step('generate', DOCS_COMMAND='false', MINI_PATH='/m').returncode)

    def test_unchanged_docs_are_not_committed(self):
        self.generate('true')
        self.assertEqual('changed=false', self.detect())
        self.assertEqual(['Fixture <fixture@example.test>|init'], self.remote_log())

    def test_changed_docs_are_committed_as_the_bot_and_pushed(self):
        self.generate()
        self.assertEqual('changed=true', self.detect())
        result = self.publish()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('committed=true', self.output.read_text())
        self.assertEqual(['github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>|chore(docs): regenerate vim help',
                          'Fixture <fixture@example.test>|init'], self.remote_log())
        self.assertEqual('', git('status', '--porcelain', cwd=self.repo).stdout)

    def test_file_pattern_limits_detection_and_the_commit(self):
        self.generate()
        self.assertEqual('changed=false', self.detect('missing/*.txt'))
        self.assertEqual('changed=true', self.detect('doc/*.txt'))
        result = self.publish(FILE_PATTERN='doc/*.txt', COMMIT_MESSAGE='docs: custom message')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        files = git('show', '--name-only', '--format=', 'main', cwd=self.remote).stdout.split()
        self.assertEqual(['doc/plugin.txt'], files)
        self.assertEqual('docs: custom message', git('log', '-1', '--format=%s', 'main', cwd=self.remote).stdout.strip())
        self.assertIn('build/', git('status', '--porcelain', cwd=self.repo).stdout)

    def test_quoted_pathspecs_are_split_without_shell_evaluation(self):
        self.generate('mkdir -p "doc dir" && echo x > "doc dir/a b.txt" && touch ../outside')
        self.assertEqual('changed=true', self.detect("'doc dir/*.txt'"))
        self.assertEqual('changed=false', self.detect('$(touch pwned)'))
        self.assertFalse((self.repo / 'pwned').exists())

    def test_a_rejected_push_fails_and_never_forces(self):
        self.generate()
        other = self.root / 'other'
        git('clone', str(self.remote), str(other), cwd=self.root)
        git('config', 'user.name', 'Other', cwd=other)
        git('config', 'user.email', 'other@example.test', cwd=other)
        (other / 'new.txt').write_text('new\n')
        git('add', '.', cwd=other)
        git('commit', '-m', 'concurrent change', cwd=other)
        git('push', 'origin', 'HEAD:main', cwd=other)
        result = self.publish()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(['Other <other@example.test>|concurrent change', 'Fixture <fixture@example.test>|init'], self.remote_log())
        self.assertNotIn('committed=true', self.output.read_text())

    def test_empty_commit_message_is_rejected(self):
        self.generate()
        self.assertNotEqual(0, self.publish(COMMIT_MESSAGE='  ').returncode)


if __name__ == '__main__':
    unittest.main()
