import pathlib
import re
import unittest

import yaml

WORKFLOW = pathlib.Path(".github/workflows/tailscale-acl.yml")


class TailscaleAclContractTest(unittest.TestCase):
    def setUp(self):
        data = yaml.safe_load(WORKFLOW.read_text())
        self.data = data
        # PyYAML reads the bare key "on" as boolean True under YAML 1.1.
        self.call = data.get("on", data.get(True))["workflow_call"]
        self.inputs = self.call["inputs"]
        self.job = data["jobs"]["acl"]
        self.steps = self.job["steps"]

    def _step(self, name_fragment):
        for step in self.steps:
            if name_fragment in step.get("name", ""):
                return step
        self.fail(f"Missing workflow step containing: {name_fragment}")

    # Workload identity federation is the entire reason this workflow can take
    # no secrets. A secrets block reappearing means someone reintroduced a
    # long-lived credential.
    def test_takes_no_secrets(self):
        self.assertNotIn("secrets", self.call)
        self.assertNotIn("secrets.", WORKFLOW.read_text())

    def test_credentials_are_plain_inputs(self):
        for name in ("oauth-client-id", "audience"):
            with self.subTest(name=name):
                self.assertIn(name, self.inputs)
                self.assertTrue(self.inputs[name]["required"])
                self.assertEqual(self.inputs[name]["type"], "string")

        acl_step = self._step("Run Tailscale ACL")
        self.assertEqual(
            acl_step["with"]["oauth-client-id"], "${{ inputs.oauth-client-id }}"
        )
        self.assertEqual(acl_step["with"]["audience"], "${{ inputs.audience }}")
        self.assertNotIn("oauth-secret", acl_step["with"])
        self.assertNotIn("api-key", acl_step["with"])

    def test_job_can_mint_an_oidc_token(self):
        self.assertEqual(self.job["permissions"]["id-token"], "write")
        self.assertEqual(self.job["permissions"]["contents"], "read")

    def test_third_party_actions_are_sha_pinned(self):
        for step in self.steps:
            uses = step.get("uses")
            if not uses or uses.startswith("./"):
                continue
            with self.subTest(uses=uses):
                self.assertRegex(uses, r"^[^@]+@[0-9a-f]{40}$")

    def test_policy_file_defaults_to_the_documented_name(self):
        self.assertEqual(self.inputs["policy-file"]["default"], "policy.hujson")
        self.assertFalse(self.inputs["policy-file"]["required"])

    def test_action_input_defaults_to_automatic_selection(self):
        self.assertEqual(self.inputs["action"]["default"], "")
        self.assertFalse(self.inputs["action"]["required"])

    # Auto-selection must never apply from anywhere but a default-branch push,
    # or a pull request could mutate the tailnet before review.
    def test_apply_is_reachable_only_from_a_default_branch_push(self):
        resolve = self._step("Resolve action")["run"]

        self.assertIn('if [ "$EVENT_NAME" = "push" ]', resolve)
        self.assertIn('[ "$REF" = "refs/heads/$DEFAULT_BRANCH" ]', resolve)
        # The apply assignment sits inside that guard, and the fallback is test.
        guard = re.search(
            r'if \[ "\$EVENT_NAME" = "push" \].*?\n(.*?)\n\s*fi', resolve, re.S
        )
        self.assertIsNotNone(guard, "expected the push/default-branch guard")
        self.assertIn('resolved="apply"', guard.group(1))
        self.assertIn('resolved="test"', guard.group(1))

    def test_invalid_action_fails_the_run(self):
        resolve = self._step("Resolve action")["run"]

        self.assertIn("case \"$REQUESTED\" in", resolve)
        self.assertIn("test|apply)", resolve)
        self.assertIn("Invalid action", resolve)

    def test_missing_policy_file_fails_before_calling_tailscale(self):
        resolve = self._step("Resolve action")["run"]

        self.assertIn('if [ ! -f "$POLICY_FILE" ]', resolve)
        names = [step.get("name", "") for step in self.steps]
        self.assertLess(
            names.index("Resolve action"),
            next(i for i, n in enumerate(names) if n.startswith("Run Tailscale ACL")),
        )

    def test_is_documented_in_the_readme(self):
        readme = pathlib.Path("README.md").read_text()

        self.assertIn("tailscale-acl.yml", readme)
        self.assertIn("### Tailscale ACL", readme)


if __name__ == "__main__":
    unittest.main()
