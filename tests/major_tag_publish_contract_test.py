import pathlib
import unittest

import yaml

WORKFLOW = pathlib.Path(".github/workflows/repository-release-please.yml")


class MajorTagPublishContractTest(unittest.TestCase):
    def setUp(self):
        data = yaml.safe_load(WORKFLOW.read_text())
        self.job = data["jobs"]["move-major-tag"]
        self.steps = self.job["steps"]

    def _step(self, name):
        for step in self.steps:
            if step.get("name") == name:
                return step
        self.fail(f"Missing workflow step: {name}")

    # The default GITHUB_TOKEN is a GitHub App token, which GitHub refuses to
    # let create or update a ref carrying .github/workflows content. Every tag
    # in this repository carries exactly that, so the checkout has to be able to
    # pick up a token that holds `workflows`.
    def test_checkout_prefers_the_release_tag_token(self):
        checkout = self._step("Checkout")

        self.assertEqual(
            checkout["with"]["token"],
            "${{ secrets.RELEASE_TAG_TOKEN || github.token }}",
        )
        self.assertEqual(checkout["with"]["persist-credentials"], True)
        self.assertEqual(checkout["with"]["fetch-depth"], 0)

    # `workflows` is not a grantable scope, so nobody should "fix" a future
    # failure by adding it here and assuming it works.
    def test_permissions_do_not_pretend_to_grant_workflows(self):
        self.assertNotIn("workflows", self.job.get("permissions", {}))

    def test_push_failure_is_reported_not_swallowed(self):
        run = self._step("Move major tag")["run"]

        self.assertIn("if git push origin", run)
        self.assertIn("::error title=Cannot publish", run)
        self.assertIn("RELEASE_TAG_TOKEN", run)
        # A rejected push must fail the job; a missing floating tag silently
        # breaks every caller pinning @vN.
        self.assertIn("exit 1", run)

    # ls-remote emits a second "^{}" line for annotated tags. Two SHAs reaching
    # the equality check would make it never match and force-push every time.
    def test_idempotence_check_handles_annotated_tags(self):
        run = self._step("Move major tag")["run"]

        self.assertIn('"refs/tags/$major_tag^{}"', run)
        self.assertIn("tail -n 1", run)

    def test_summary_reports_what_was_actually_published(self):
        run = self._step("Summary")["run"]

        self.assertIn("git ls-remote --exit-code --tags origin", run)
        self.assertIn("published:", run)

    def test_readme_documents_the_secret(self):
        readme = pathlib.Path("README.md").read_text()

        self.assertIn("RELEASE_TAG_TOKEN", readme)
        self.assertIn("workflows: write", readme)


if __name__ == "__main__":
    unittest.main()
