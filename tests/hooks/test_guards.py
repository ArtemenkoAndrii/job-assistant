"""Tests for the Claude Code guard hooks in .claude/hooks/.

Fake secrets are assembled at run time so that this file itself never contains one
(gitleaks scans the repo).
"""
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

import guard_bash  # noqa: E402
import guard_write  # noqa: E402


def fake(prefix, body_len, alphabet="a1B2c3D4e5"):
    return prefix + (alphabet * (body_len // len(alphabet) + 1))[:body_len]


class GuardBash(unittest.TestCase):
    def blocked(self, cmd, branch="13-ci-guardrails"):
        return guard_bash.check(cmd, branch=branch) is not None

    def test_blocks_push_to_main(self):
        for cmd in ["git push origin main", "git push origin HEAD:main",
                    "git push -u origin main", "git push origin refs/heads/main",
                    "cd x && git push origin main"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(self.blocked(cmd))

    def test_blocks_bare_push_on_main(self):
        self.assertTrue(self.blocked("git push", branch="main"))

    def test_blocks_force_push(self):
        for cmd in ["git push --force origin 13-x", "git push -f",
                    "git push --force-with-lease", "git push origin +13-x"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(self.blocked(cmd))

    def test_blocks_bypasses(self):
        for cmd in ["git commit --no-verify -m x", "git config core.hooksPath /dev/null",
                    "gh repo delete ArtemenkoAndrii/job-assistant", "gh repo edit --visibility private",
                    "gh api repos/o/r/rulesets/1 -X PUT", "gh api -X DELETE repos/o/r/issues/1",
                    "gh auth token", "cat ~/.config/gh/hosts.yml", "cat .env", "cat ./.env.local", "source .env",
                    "ls config/secrets/"]:
            with self.subTest(cmd=cmd):
                self.assertTrue(self.blocked(cmd))

    def test_allows_normal_work(self):
        for cmd in ["git push -u origin 13-ci-guardrails", "git push origin 12-fix-main-page",
                    "git push origin main-docs", "git merge main", "git pull origin main",
                    "git commit -m 'fix -f flag docs'", "git push --follow-tags",
                    "cp .env.example /tmp/x", "gh pr create", "gh api repos/o/r/pulls", "gh issue view 14", "gh auth status",
                    "node -e 'console.log(process.env.HOME)'", "scripts/lint.sh"]:
            with self.subTest(cmd=cmd):
                self.assertFalse(self.blocked(cmd))

    def test_hook_protocol(self):
        payload = json.dumps({"tool_name": "Bash", "cwd": str(ROOT),
                              "tool_input": {"command": "git push origin main"}})
        out = subprocess.run([sys.executable, str(HOOKS / "guard_bash.py")], input=payload,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("ADR-0003", out.stderr)


class GuardWrite(unittest.TestCase):
    def blocked(self, tool_input):
        return guard_write.check(tool_input) is not None

    def test_blocks_secret_files(self):
        for path in [".env", "app/.env.production", "infra/secrets/db.txt", "certs/server.pem",
                     "C:\\repo\\.env"]:
            with self.subTest(path=path):
                self.assertTrue(self.blocked({"file_path": path, "content": "x"}))

    def test_allows_env_example(self):
        self.assertFalse(self.blocked({"file_path": ".env.example", "content": "OPENAI_API_KEY="}))

    def test_blocks_secrets_in_content(self):
        secrets = [
            fake("gh" + "p_", 36),
            fake("github" + "_pat_", 60),
            fake("sk-" + "ant-api03-", 40),
            fake("sk-" + "proj-", 48),
            "AK" + "IA" + "ABCDEFGHIJKLMNOP",
            "-----BEGIN " + "RSA PRIVATE KEY-----",
            "CF-Access-Client-" + "Secret: " + "0123456789abcdef" * 4,
        ]
        for secret in secrets:
            with self.subTest(secret=secret[:12]):
                self.assertTrue(self.blocked({"file_path": "notes.md", "content": f"x {secret} y"}))

    def test_checks_edit_and_multiedit(self):
        token = fake("gh" + "p_", 36)
        self.assertTrue(self.blocked({"file_path": "a.py", "old_string": "a", "new_string": token}))
        self.assertTrue(self.blocked({"file_path": "a.py",
                                      "edits": [{"old_string": "a", "new_string": "b"},
                                                {"old_string": "c", "new_string": token}]}))

    def test_allows_placeholders(self):
        for text in ["OPENAI_API_KEY=${OPENAI_API_KEY}", "CF-Access-Client-Secret: <from secret manager>",
                     "sk-...", "token: ghp_xxx"]:
            with self.subTest(text=text):
                self.assertFalse(self.blocked({"file_path": "docs/x.md", "content": text}))

    def test_hook_protocol(self):
        payload = json.dumps({"tool_name": "Write",
                              "tool_input": {"file_path": ".env", "content": "A=1"}})
        out = subprocess.run([sys.executable, str(HOOKS / "guard_write.py")], input=payload,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


if __name__ == "__main__":
    unittest.main()
