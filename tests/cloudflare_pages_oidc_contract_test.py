import pathlib
import unittest

import yaml

WORKFLOW = pathlib.Path(".github/workflows/cloudflare-pages-deploy.yml")


class CloudflarePagesOidcContractTest(unittest.TestCase):
    def setUp(self):
        data = yaml.safe_load(WORKFLOW.read_text())
        # PyYAML reads the bare key "on" as boolean True under YAML 1.1.
        self.call = data.get("on", data.get(True))["workflow_call"]
        self.job = data["jobs"]["deploy"]
        self.steps = self.job["steps"]

    def _step(self, name):
        for step in self.steps:
            if step.get("name") == name:
                return step
        self.fail(f"Missing workflow step: {name}")

    def test_job_can_mint_an_oidc_token(self):
        self.assertEqual(self.job["permissions"]["id-token"], "write")

    # The whole point of the migration: a caller can deploy without holding a
    # long-lived Cloudflare token.
    def test_api_token_secret_is_optional(self):
        self.assertFalse(self.call["secrets"]["CLOUDFLARE_API_TOKEN"]["required"])

    # OIDC swaps the credential, not the account selector.
    def test_account_id_stays_required(self):
        self.assertTrue(self.call["secrets"]["CLOUDFLARE_ACCOUNT_ID"]["required"])

    def test_deploy_consumes_the_resolved_token_not_the_secret(self):
        deploy = self._step("Deploy to Cloudflare Pages")

        self.assertEqual(
            deploy["with"]["apiToken"], "${{ steps.cloudflare-auth.outputs.token }}"
        )
        self.assertEqual(
            deploy["with"]["accountId"], "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}"
        )

    def test_secret_path_short_circuits_before_the_exchange(self):
        resolve = self._step("Resolve Cloudflare API token")["run"]

        self.assertIn('if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]', resolve)
        self.assertIn('mode=secret', resolve)
        # The fallback returns before any network call is made.
        self.assertLess(resolve.index("exit 0"), resolve.index("oauth/token"))

    def test_exchange_uses_the_token_exchange_grant(self):
        resolve = self._step("Resolve Cloudflare API token")["run"]

        self.assertIn("ACTIONS_ID_TOKEN_REQUEST_TOKEN", resolve)
        self.assertIn(
            "urn:ietf:params:oauth:grant-type:token-exchange",
            resolve,
        )
        self.assertIn("https://api.cloudflare.com/client/v4/oauth/token", resolve)
        self.assertIn(".result.access_token", resolve)

    # Both branches produce a credential that must never reach the log.
    def test_both_credentials_are_masked(self):
        resolve = self._step("Resolve Cloudflare API token")["run"]

        self.assertEqual(resolve.count("::add-mask::"), 2)

    def test_missing_credential_fails_with_actionable_guidance(self):
        resolve = self._step("Resolve Cloudflare API token")["run"]

        self.assertIn('if [ -z "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]', resolve)
        self.assertIn("id-token: write", resolve)

    def test_audience_defaults_to_the_repository_owner(self):
        resolve = self._step("Resolve Cloudflare API token")["run"]

        self.assertEqual(self.call["inputs"]["oidc-audience"]["default"], "")
        self.assertIn('https://github.com/${GITHUB_REPOSITORY_OWNER}', resolve)

    def test_readme_documents_the_breaking_permission(self):
        readme = pathlib.Path("README.md").read_text()

        self.assertIn("Breaking in v3", readme)
        self.assertIn("id-token: write", readme)


if __name__ == "__main__":
    unittest.main()
