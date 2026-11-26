"""Tests for scripts/check_infra.py (AC10): no pull_request_target, no public IAM members."""
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_infra  # noqa: E402


class CheckInfra(unittest.TestCase):
    def run_check(self, files, ci=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel, text in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return check_infra.find_errors(root, ci=ci)

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
        errors = self.run_check(self.terraform_files(dockerfile_version="1.9.8"))
        self.assertEqual(len(errors), 1)
        self.assertIn("1.9.8", errors[0])

    GOOD_HASH = "a" * 64
    OTHER_HASH = "b" * 64

    def terraform_files(self, version="1.17.2", amd64=None, arm64=None, dockerfile_version=None, dockerfile_amd64=None):
        amd64 = amd64 or self.GOOD_HASH
        arm64 = arm64 or self.OTHER_HASH
        return {
            "infra/.terraform-version": f"{version}\n",
            "infra/.terraform-sha256": (
                f"{amd64}  terraform_{version}_linux_amd64.zip\n"
                f"{arm64}  terraform_{version}_linux_arm64.zip\n"
            ),
            ".devcontainer/Dockerfile": (
                f"ARG TERRAFORM_VERSION={dockerfile_version or version}\n"
                f"ARG TERRAFORM_SHA256_AMD64={dockerfile_amd64 or amd64}\n"
                f"ARG TERRAFORM_SHA256_ARM64={arm64}\n"
            ),
        }

    def test_terraform_version_match_passes(self):
        self.assertEqual(self.run_check(self.terraform_files()), [])

    def test_dockerfile_hash_mismatch_fails(self):
        errors = self.run_check(self.terraform_files(dockerfile_amd64="c" * 64))
        self.assertEqual(len(errors), 1)
        self.assertIn("TERRAFORM_SHA256_AMD64", errors[0])

    def test_hash_for_other_version_fails(self):
        files = self.terraform_files()
        files["infra/.terraform-sha256"] = files["infra/.terraform-sha256"].replace("1.17.2", "1.9.8")
        errors = self.run_check(files)
        self.assertTrue(any("terraform_1.17.2_linux_amd64.zip" in e for e in errors))
        self.assertTrue(any("terraform_1.17.2_linux_arm64.zip" in e for e in errors))

    def test_missing_hash_file_fails(self):
        files = self.terraform_files()
        del files["infra/.terraform-sha256"]
        errors = self.run_check(files)
        self.assertEqual(len(errors), 1)
        self.assertIn(".terraform-sha256", errors[0])

    def test_malformed_hash_fails(self):
        errors = self.run_check(self.terraform_files(amd64="not-a-hash"))
        self.assertEqual(len(errors), 1)
        self.assertIn("amd64", errors[0])

    def test_placeholder_is_a_warning_locally(self):
        files = self.terraform_files(amd64=check_infra.PLACEHOLDER)
        self.assertEqual(self.run_check(files, ci=False), [])

    def test_placeholder_fails_in_ci(self):
        files = self.terraform_files(amd64=check_infra.PLACEHOLDER)
        errors = self.run_check(files, ci=True)
        self.assertEqual(len(errors), 1)
        self.assertIn("placeholder", errors[0])


if __name__ == "__main__":
    unittest.main()
