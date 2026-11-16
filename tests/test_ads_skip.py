import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from ads_skip import CN_URL, VN_URL, parse_args


def test_parse_args_uses_vn_url_and_pmain_profile_by_default():
    args = parse_args([])

    assert args.url == VN_URL
    assert args.profile == ".tmp/pmain"
    assert args.out == ".tmp/ads_skip"


def test_parse_args_uses_cn_url_with_cn_flag():
    args = parse_args(["--cn"])

    assert args.url == CN_URL


def test_parse_args_url_overrides_server_flags():
    args = parse_args(["--cn", "--url", "http://example.test/game"])

    assert args.url == "http://example.test/game"
