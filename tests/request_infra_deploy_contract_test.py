import pathlib
import unittest

import yaml


class RequestInfraDeployContractTest(unittest.TestCase):
    def setUp(self):
        data = yaml.safe_load(
            pathlib.Path(".github/workflows/request-infra-deploy.yml").read_text()
        )
        self.workflow = data.get("on", data.get(True))
        self.call = self.workflow["workflow_call"]
        self.run_scripts = "\n".join(
            step.get("run", "")
            for job in data["jobs"].values()
            for step in job.get("steps", [])
        )

    def test_artifact_inputs_are_typed_and_optional(self):
        inputs = self.call["inputs"]
        self.assertEqual(inputs["artifact-run-id"]["type"], "number")
        self.assertEqual(inputs["artifact-run-id"]["default"], 0)
        self.assertEqual(inputs["artifact-name"]["type"], "string")
        self.assertEqual(inputs["artifact-name"]["default"], "")
        self.assertEqual(inputs["artifact-digest"]["type"], "string")
        self.assertEqual(inputs["artifact-digest"]["default"], "")

    def test_payload_validates_and_forwards_artifact_metadata(self):
        self.assertIn("ARTIFACT_RUN_ID", self.run_scripts)
        self.assertIn("ARTIFACT_NAME", self.run_scripts)
        self.assertIn("ARTIFACT_DIGEST", self.run_scripts)
        self.assertIn("artifact_run_id", self.run_scripts)
        self.assertIn("artifact_name", self.run_scripts)
        self.assertIn("artifact_digest", self.run_scripts)


if __name__ == "__main__":
    unittest.main()
