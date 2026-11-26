"""Tests for scripts/check_infra.py (AC10): no pull_request_target, no public IAM members."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_infra  # noqa: E402


class CheckInfra(unittest.TestCase):
    def run_check(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel, text in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return check_infra.find_errors(root)

    def test_clean_repo_passes(self):
        errors = self.run_check({
            ".github/workflows/ci.yml": "on:\n  pull_request:\n",
            "infra/app/run.tf": 'member = "serviceAccount:x@y.iam.gserviceaccount.com"\n',
        })
        self.assertEqual(errors, [])

    def test_pull_request_target_fails(self):
        errors = self.run_check({".github/workflows/x.yml": "on:\n  pull_request_target:\n"})
        self.assertEqual(len(errors), 1)
        self.assertIn("pull_request_target", errors[0])

    def test_pull_request_target_in_comment_passes(self):
        errors = self.run_check({".github/workflows/x.yml": "# never use pull_request_target\non: push\n"})
        self.assertEqual(errors, [])

    def test_all_users_fails(self):
        errors = self.run_check({"infra/app/run.tf": 'member = "allUsers"\n'})
        self.assertEqual(len(errors), 1)
        self.assertIn("allUsers", errors[0])

    def test_all_authenticated_users_fails(self):
        errors = self.run_check({"infra/platform/x.tf": 'member = "allAuthenticatedUsers"\n'})
        self.assertEqual(len(errors), 1)

    def test_all_users_in_comment_passes(self):
        errors = self.run_check({"infra/app/run.tf": '# never grant allUsers here\n'})
        self.assertEqual(errors, [])

    def test_yaml_extension_is_checked(self):
        errors = self.run_check({".github/workflows/x.yaml": "on: pull_request_target\n"})
        self.assertEqual(len(errors), 1)

    def test_terraform_version_mismatch_fails(self):
        errors = self.run_check({
            "infra/.terraform-version": "1.17.2\n",
            ".devcontainer/Dockerfile": "ARG TERRAFORM_VERSION=1.9.8\n",
        })
        self.assertEqual(len(errors), 1)
        self.assertIn("1.9.8", errors[0])

    def test_terraform_version_match_passes(self):
        errors = self.run_check({
            "infra/.terraform-version": "1.17.2\n",
            ".devcontainer/Dockerfile": "ARG TERRAFORM_VERSION=1.17.2\n",
        })
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
