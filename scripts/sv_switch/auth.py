"""Standalone SDK localStorage auth; no crawler dependencies."""

import copy
import json
from pathlib import Path

SDK_URL = "https://h5sdk.joynetgame.com/"


def load_auth(path: Path, account: str) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("Auth JSON must be a localStorage object")
    keys = [k for k in data if k.endswith("_allLoginList")]
    if len(keys) != 1:
        raise ValueError("Expected one _allLoginList key")
    key = keys[0]
    wrapper = data[key]
    accounts = wrapper.get("value", {}) if isinstance(wrapper, dict) else {}
    selected = accounts.get(account) if isinstance(accounts, dict) else None
    if not isinstance(selected, dict) or selected.get("username") != account:
        raise ValueError("Account missing from allLoginList.value")
    if not selected.get("access_token"):
        raise ValueError("Account has no access_token")
    login_key = key.removesuffix("_allLoginList") + "_userLoginData"
    if not isinstance(data.get(login_key), dict):
        raise TypeError("Missing userLoginData wrapper")
    data = copy.deepcopy(data)
    data[login_key]["value"] = copy.deepcopy(selected)
    return data, login_key


async def restore_auth(context, data: dict, login_key: str, account: str):
    page = await context.new_page()
    await page.goto(SDK_URL, wait_until="domcontentloaded", timeout=60000)
    if page.url.rstrip("/") != SDK_URL.rstrip("/"):
        raise ValueError("Unexpected SDK origin")
    await page.evaluate(
        """data => {
      for (const [k,v] of Object.entries(data))
        localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v));
    }""",
        data,
    )
    actual = await page.evaluate(
        "k => JSON.parse(localStorage.getItem(k))?.value?.username", login_key
    )
    if actual != account:
        raise ValueError("SDK account readback mismatch")
    return page
