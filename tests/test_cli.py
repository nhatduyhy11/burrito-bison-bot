import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from hauntedroom.core.cli import CN_URL, VN_URL, prepare_runner


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
