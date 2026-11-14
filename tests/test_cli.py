import sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.cli import CN_URL, VN_URL, YGKKSY_URL, prepare_runner


def test_prepare_runner_uses_vn_url_by_default(tmp_path):
    profile = tmp_path / "profile"

    with patch.object(sys, "argv", ["hauntedroom", "--profile", str(profile)]):
        args, _ = prepare_runner()

    assert args.url == VN_URL


def test_prepare_runner_uses_cn_url_with_cn_flag(tmp_path):
    profile = tmp_path / "profile"

    with patch.object(
        sys,
        "argv",
        ["hauntedroom", "--profile", str(profile), "--cn"],
    ):
        args, _ = prepare_runner()

    assert args.url == CN_URL


def test_prepare_runner_uses_ygkksy_url_and_separate_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YGKKSY_PASS", "a+b&c")
    monkeypatch.setenv("YGKKSY_ACCOUNT", "1234")
    monkeypatch.setenv("YGKKSY_TOKEN", "token/=")
    monkeypatch.setenv("YGKKSY_TIMESTAMP", "0012345678")

    with patch.object(sys, "argv", ["hauntedroom", "--ygkksy"]):
        args, profile = prepare_runner()

    entry, query = args.url.split("?", 1)
    assert entry == YGKKSY_URL
    assert parse_qs(query) == {
        "pass": ["a+b&c"],
        "account": ["1234"],
        "token": ["token/="],
        "timestamp": ["0012345678"],
    }
    assert profile == Path(".tmp/ygkksy-profile")
    assert profile.is_dir()


def test_prepare_runner_requires_ygkksy_timestamp(monkeypatch, capsys):
    monkeypatch.setenv("YGKKSY_PASS", "secret")
    monkeypatch.setenv("YGKKSY_ACCOUNT", "1234")
    monkeypatch.setenv("YGKKSY_TOKEN", "secret")
    monkeypatch.delenv("YGKKSY_TIMESTAMP", raising=False)

    with patch.object(sys, "argv", ["hauntedroom", "--ygkksy"]), pytest.raises(SystemExit):
        prepare_runner()

    error = capsys.readouterr().err
    assert "requires environment variables: YGKKSY_TIMESTAMP" in error
    assert "secret" not in error


def test_prepare_runner_keeps_explicit_url_override(tmp_path):
    profile = tmp_path / "profile"
    custom_url = "https://example.test/"

    with patch.object(
        sys,
        "argv",
        ["hauntedroom", "--profile", str(profile), "--cn", "--url", custom_url],
    ):
        args, _ = prepare_runner()

    assert args.url == custom_url
