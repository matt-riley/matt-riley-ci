import pathlib
import re
import unittest

import yaml


class RequestInfraDeployContractTest(unittest.TestCase):
    def _get_step(self, data, step_name):
        for job in data["jobs"].values():
            for step in job.get("steps", []):
                if step.get("name") == step_name:
                    return step
        self.fail(f"Missing workflow step: {step_name}")

    def setUp(self):
        data = yaml.safe_load(
            pathlib.Path(".github/workflows/request-infra-deploy.yml").read_text()
        )
        self.workflow = data.get("on", data.get(True))
        self.call = self.workflow["workflow_call"]
        self.dispatch_run = self._get_step(data, "Dispatch infra deploy request").get(
            "run", ""
        )
        self.validation_run = self._get_step(
            data, "Validate artifact configuration"
        ).get("run", "")
        match = re.search(
            r"python - <<'PY' \| curl.*?\n(.*?)\n\s*PY\n?",
            self.dispatch_run,
            re.S,
        )
        self.dispatch_python = match.group(1) if match else ""

    def test_artifact_inputs_are_optional_and_all_or_none(self):
        inputs = self.call["inputs"]
        artifact_inputs = {
            "artifact-run-id": ("number", 0),
            "artifact-name": ("string", ""),
            "artifact-digest": ("string", ""),
        }

        for name, (input_type, default_value) in artifact_inputs.items():
            with self.subTest(name=name):
                self.assertIn(name, inputs)
                self.assertFalse(inputs[name]["required"])
                self.assertEqual(inputs[name]["type"], input_type)
                self.assertEqual(inputs[name]["default"], default_value)

    def test_validation_step_enforces_artifact_configuration(self):
        self.assertIn('if [ "$ARTIFACT_RUN_ID" = "0" ]; then', self.validation_run)
        self.assertIn(
            'if [ -n "$ARTIFACT_NAME" ] || [ -n "$ARTIFACT_DIGEST" ]; then',
            self.validation_run,
        )
        self.assertIn(
            'if ! [[ "$ARTIFACT_RUN_ID" =~ ^[1-9][0-9]*$ ]]; then',
            self.validation_run,
        )
        self.assertIn(
            'if ! [[ "$ARTIFACT_DIGEST" =~ ^[0-9a-f]{64}$ ]]; then',
            self.validation_run,
        )
        self.assertIn("ARTIFACT_RUN_ID", self.dispatch_python)
        self.assertIn("ARTIFACT_NAME", self.dispatch_python)
        self.assertIn("ARTIFACT_DIGEST", self.dispatch_python)
        self.assertIn("artifact_run_id", self.dispatch_python)
        self.assertIn("artifact_name", self.dispatch_python)
        self.assertIn("artifact_digest", self.dispatch_python)
        self.assertIn("json.dumps(payload)", self.dispatch_python)


if __name__ == "__main__":
    unittest.main()
