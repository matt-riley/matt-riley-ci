from pathlib import Path
import unittest

import yaml


class UniversalCiCacheContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load(
            Path(".github/workflows/ci.yml").read_text()
        )
        cls.job = cls.workflow["jobs"]["ci"]
        cls.steps = cls.job["steps"]
        cls.steps_by_name = {
            step["name"]: step for step in cls.steps if "name" in step
        }

    def test_cache_writes_require_explicit_opt_in(self):
        trigger = self.workflow.get("on", self.workflow.get(True))
        inputs = trigger["workflow_call"]["inputs"]
        self.assertIn("save-cache", inputs)
        save_cache = inputs["save-cache"]

        self.assertEqual(
            save_cache,
            {
                "description": "Save dependency and build caches after a successful run",
                "required": False,
                "default": False,
                "type": "boolean",
            },
        )
        self.assertEqual(
            self.steps_by_name["Install mise"]["with"]["cache_save"],
            "${{ inputs.save-cache && (github.event_name == 'push' || github.event_name == 'workflow_dispatch') && github.ref == format('refs/heads/{0}', github.event.repository.default_branch) }}",
        )

        save_steps = (
            "Save pnpm store",
            "Save npm cache",
            "Save Go module cache",
            "Save Go build cache",
            "Save Playwright browser binaries",
        )
        for name in save_steps:
            condition = self.steps_by_name[name]["if"]
            self.assertIn("success()", condition)
            self.assertIn("inputs.save-cache", condition)
            self.assertIn("github.event_name == 'push'", condition)
            self.assertIn("github.event_name == 'workflow_dispatch'", condition)
            self.assertNotIn("github.event_name != 'pull_request'", condition)
            self.assertIn("github.event.repository.default_branch", condition)
            self.assertIn("cache-hit != 'true'", condition)

        for step in self.steps:
            self.assertNotEqual(
                step.get("uses"),
                "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
            )

        for name in ("Save Go module cache", "Save Go build cache"):
            self.assertIn(
                "hashFiles('go.mod') != ''",
                self.steps_by_name[name]["if"],
            )

    def test_go_modules_and_build_outputs_use_separate_cache_lifecycles(self):
        self.assertIn("Restore Go module cache", self.steps_by_name)
        self.assertIn("Restore Go build cache", self.steps_by_name)
        module_restore = self.steps_by_name["Restore Go module cache"]
        build_restore = self.steps_by_name["Restore Go build cache"]

        self.assertEqual(
            module_restore["uses"],
            "actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
        )
        self.assertEqual(
            build_restore["uses"],
            "actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
        )

        module_key = module_restore["with"]["key"]
        build_key = build_restore["with"]["key"]
        self.assertIn("go-mod-v2-", module_key)
        self.assertIn("runner.arch", module_key)
        self.assertIn("steps.go-cache-metadata.outputs.version", module_key)
        self.assertIn("hashFiles('go.mod', 'go.sum')", module_key)
        self.assertNotIn("github.sha", module_key)

        self.assertIn("go-build-v2-", build_key)
        self.assertIn("runner.arch", build_key)
        self.assertIn("steps.go-cache-metadata.outputs.version", build_key)
        self.assertIn("hashFiles('go.mod', 'go.sum')", build_key)
        self.assertIn("github.sha", build_key)

        self.assertEqual(
            module_restore["with"]["path"],
            "${{ steps.go-cache-metadata.outputs.module_cache }}",
        )
        self.assertEqual(
            build_restore["with"]["path"],
            "${{ steps.go-cache-metadata.outputs.build_cache }}",
        )

    def test_specialized_go_workflows_restore_without_implicit_go_writes(self):
        for path, job_name in (
            (".github/workflows/go-lint.yml", "lint"),
            (".github/workflows/go-security.yml", "govulncheck"),
        ):
            workflow = yaml.safe_load(Path(path).read_text())
            steps = workflow["jobs"][job_name]["steps"]
            steps_by_name = {
                step["name"]: step for step in steps if "name" in step
            }

            self.assertIs(
                steps_by_name["Set up Go"]["with"]["cache"],
                False,
            )
            for name in ("Restore Go module cache", "Restore Go build cache"):
                self.assertIn(name, steps_by_name)
                self.assertEqual(
                    steps_by_name[name]["uses"],
                    "actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
                )

        lint = yaml.safe_load(
            Path(".github/workflows/go-lint.yml").read_text()
        )
        lint_steps = {
            step["name"]: step
            for step in lint["jobs"]["lint"]["steps"]
            if "name" in step
        }
        skip_save = lint_steps["Run golangci-lint"]["with"]["skip-save-cache"]
        self.assertIn("github.event_name == 'push'", skip_save)
        self.assertIn("github.event_name == 'workflow_dispatch'", skip_save)
        self.assertIn("github.event.repository.default_branch", skip_save)


if __name__ == "__main__":
    unittest.main()
