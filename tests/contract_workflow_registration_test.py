from pathlib import Path
import unittest


class ContractWorkflowRegistrationTest(unittest.TestCase):
    def test_contract_workflow_runs_infra_deploy_contracts(self):
        workflow = Path(".github/workflows/contract-tests.yml").read_text()

        self.assertIn("tests/request_infra_deploy_contract_test.py", workflow)
        self.assertIn("tests/contract_workflow_registration_test.py", workflow)


if __name__ == "__main__":
    unittest.main()
