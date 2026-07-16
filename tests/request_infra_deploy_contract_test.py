import pathlib
import re
import unittest

import yaml


class RequestInfraDeployContractTest(unittest.TestCase):
    def setUp(self):
        data = yaml.safe_load(
            pathlib.Path(".github/workflows/request-infra-deploy.yml").read_text()
        )
        self.workflow = data.get("on", data.get(True))
        self.call = self.workflow["workflow_call"]
        self.dispatch_run = next(
            step.get("run", "")
            for job in data["jobs"].values()
            for step in job.get("steps", [])
            if step.get("name") == "Dispatch infra deploy request"
        )
        match = re.search(r"python - <<'PY' \| curl.*?\n(.*?)\n\s*PY\n?", self.dispatch_run, re.S)
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

        self.assertEqual(
            {name for name in artifact_inputs if name in inputs},
            set(artifact_inputs),
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
