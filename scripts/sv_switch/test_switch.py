"""Local tests: auth selection, server eligibility, CLI source validation."""

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from auth import load_auth
from switch import choose_server, parse_args


class ServerSelectionTests(unittest.TestCase):
    def server(self, status=2, **extra):
        return {
            "s_id": "829",
            "area": "800",
            "s_ip": "entry.example",
            "sPort": "19005",
            "s_healthStatus": status,
            **extra,
        }

    def test_normal_server_without_character_and_distinct_area(self):
        target = self.server()
        self.assertEqual(choose_server([target], 829), target)
        self.assertEqual(choose_server([target], 829)["area"], "800")

    def test_full_server_requires_existing_character(self):
        with self.assertRaisesRegex(ValueError, "full"):
            choose_server([self.server(1)], 829)
        self.assertTrue(
            choose_server([self.server(1, playerList={"name": "player"})], 829)
        )

    def test_maintenance_missing_unknown_duplicate(self):
        for servers in (
            [self.server(4)],
            [],
            [self.server(9)],
            [self.server(), self.server()],
        ):
            with self.subTest(servers=servers), self.assertRaises(ValueError):
                choose_server(servers, 829)

    def test_missing_endpoint(self):
        with self.assertRaisesRegex(ValueError, "metadata"):
            choose_server([self.server(sPort="")], 829)


class AuthTests(unittest.TestCase):
    def test_select_account_keeps_metadata_and_source_file(self):
        source = {
            "g_allLoginList": {
                "value": {
                    "a@example.com": {
                        "username": "a@example.com",
                        "access_token": "token-a",
                    },
                    "b@example.com": {
                        "username": "b@example.com",
                        "access_token": "token-b",
                    },
                }
            },
            "g_userLoginData": {"value": {}, "expires": 123},
            "other": "unchanged",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auth.json"
            original = json.dumps(source)
            path.write_text(original)
            selected, key = load_auth(path, "b@example.com")
            self.assertEqual(selected[key]["value"]["access_token"], "token-b")
            self.assertEqual(selected[key]["expires"], 123)
            self.assertEqual(selected["other"], "unchanged")
            self.assertEqual(path.read_text(), original)
            with self.assertRaises(ValueError):
                load_auth(path, "missing@example.com")


class CliTests(unittest.TestCase):
    def test_auth_and_alias(self):
        args = parse_args(
            ["--auth-json", "auth.json", "--acc", "a@example.com", "--sv", "829"]
        )
        self.assertEqual(args.server, 829)

    def test_invalid_sources_and_target(self):
        for argv in (
            ["--server", "829"],
            ["--auth-json", "a.json", "--server", "829"],
            ["--auth-json", "a.json", "--acc", "a", "--server", "0"],
            [
                "--profile",
                "p",
                "--auth-json",
                "a.json",
                "--acc",
                "a",
                "--server",
                "829",
            ],
        ):
            with (
                self.subTest(argv=argv),
                redirect_stderr(StringIO()),
                self.assertRaises(SystemExit),
            ):
                parse_args(argv)


if __name__ == "__main__":
    unittest.main()
