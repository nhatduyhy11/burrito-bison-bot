"""Passive battle + roster capture. The user plays normally; no automation or game requests.

uv run python scripts/capture/battle.py --profile .tmp/pmain
uv run python scripts/capture/battle.py --profile .tmp/pcn --cn   # GAT
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VN_TZ = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh, no DST; zoneinfo needs tzdata on Windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--url', help='Override the URL selected by --cn.')
    parser.add_argument('--cn', action='store_true',
                        help='GAT server; events go to .tmp/battle_sim_gat/ where the GAT sandbox reads them.')
    args = parser.parse_args()
    args.url = args.url or ('https://hauntheroesweb.acenetgame.com/' if args.cn else 'https://hauntedroomvnh5.joynetgame.com/')
    stamp = datetime.now(VN_TZ).strftime('%Y%m%d-%H%M%S')
    out_dir = ROOT / ('.tmp/battle_sim_gat' if args.cn else '.tmp/battle_research')
    target = args.output or out_dir / f'events-{args.profile.name}-{stamp}.jsonl'
    target.parent.mkdir(parents=True, exist_ok=True)
    hook = Path(__file__).with_name('battle-hook.js').read_text()

    def private_open(path, flags):
        return os.open(path, flags, 0o600)

    with open(target, 'x', buffering=1, encoding='utf-8', opener=private_open) as output, sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(args.profile.resolve()), channel='chrome', headless=False,
            no_viewport=True, ignore_default_args=['--enable-automation'],
        )

        def record(source, payload):
            if not source['frame'].url.startswith(args.url):
                return
            event = json.loads(payload)
            output.write(payload + '\n')
            msg, obj = event['data']['msg'], event['data']['obj']
            if msg == 'HeroRosterSnapshot':
                print(f"ROSTER {obj['heros']['_length']} heroes (lobby cache; missing per-hero artifact/relic)", flush=True)
            elif msg == 'HeroRosterSnapshotError':
                print(f"ROSTER SNAPSHOT FAILED: {obj.get('reason')}", flush=True)
            elif 'refreshMemberInfosR' in msg:
                members = obj.get('members') or {}
                print(f"TEAM ROSTER {members.get('_length', 0)} members (complete, has artifact/relic)", flush=True)
            elif msg.startswith('StartGameP'):
                print(f"START type={obj.get('battleType')} level={obj.get('level')} uuid={obj.get('uuid')}", flush=True)
            elif 'GetRelicInfoR(' in msg or 'GetArtifactInfoR(' in msg:
                kind = 'RELIC' if 'GetRelicInfoR(' in msg else 'ARTIFACT'
                print(f"{kind} wearList captured ({(obj.get('wearList') or {}).get('_length', 0)} worn; fills solo roster gear)", flush=True)
            elif msg.startswith('QuitRoom'):
                print('QUIT captured', flush=True)

        context.expose_binding('__recordBattle', record)
        context.add_init_script('setInterval(() => { try { ' + hook + ' } catch {} }, 150)')
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.url, wait_until='domcontentloaded')
        page.bring_to_front()
        page.wait_for_function('window.__battleCaptureReady', timeout=120_000)
        print(f'READY {target}', flush=True)
        context.wait_for_event('close', timeout=0)


if __name__ == '__main__':
    main()
