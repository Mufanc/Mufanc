"""CodexBar hook. Defaults to export-only; --publish explicitly enables GitHub writes."""
import argparse
from contextlib import ExitStack
import base64
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

BOT = {'name': 'github-actions[bot]', 'email': '41898282+github-actions[bot]@users.noreply.github.com'}


def export(payload, today=None):
    today = today or datetime.now(TZ).date()
    records = [p for p in payload if p.get('provider') == 'codex']
    if len(records) != 1 or records[0].get('source') != 'local':
        raise ValueError('Expected one local Codex usage report')
    daily = {}
    for row in records[0]['daily']:
        day, tokens = date.fromisoformat(row['date']), row['totalTokens']
        if type(tokens) is not int or tokens < 0 or day.isoformat() in daily:
            raise ValueError('Invalid or duplicate daily usage')
        if today - timedelta(days=364) <= day <= today:
            daily[day.isoformat()] = tokens
    if not daily:
        raise ValueError('No daily records; refusing to replace published data')
    return {'version': 1, 'as_of': today.isoformat(), 'daily': dict(sorted(daily.items()))}


def eligible(state, now, day):
    return (now - state.get('last_success', 0) >= 21600
            and now - state.get('last_attempt', 0) >= 600
            and (state.get('day') != day or state.get('pushes', 0) < 4))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--codexbar', default='/opt/homebrew/bin/codexbar')
    parser.add_argument('--gh', default='/opt/homebrew/bin/gh')
    parser.add_argument('--output', type=Path, help='Write sanitized export locally')
    parser.add_argument('--state', type=Path, default=Path.home() / '.cache/mufanc-profile/usage-sync.json')
    args = parser.parse_args()
    with ExitStack() as cleanup:
        state = {}
        now, day = time.time(), datetime.now(TZ).date().isoformat()

        def save():
            temp = args.state.with_suffix('.tmp')
            temp.write_text(json.dumps(state))
            os.replace(temp, args.state)

        if args.publish:
            args.state.parent.mkdir(parents=True, exist_ok=True)
            lock = cleanup.enter_context(args.state.with_suffix('.lock').open('a'))
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            if args.state.exists():
                state = json.loads(args.state.read_text())
            if not eligible(state, now, day):
                print('Skip: publication rate limit')
                return
            state['last_attempt'] = now
            save()

        raw = subprocess.run([args.codexbar, 'cost', '--provider', 'codex', '--days', '365', '--format', 'json', '--refresh'], check=True, capture_output=True, text=True, timeout=120)
        data = export(json.loads(raw.stdout))
        content = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        if args.output:
            args.output.write_text(content)
        if not args.publish:
            print(f'Export only: {len(data["daily"])} days; no GitHub writes')
            return

        endpoint = 'repos/Mufanc/Mufanc/contents/data/codex-usage.json'
        response = subprocess.run([args.gh, 'api', endpoint + '?ref=usage-data'], check=True, capture_output=True, text=True, timeout=45)
        remote = json.loads(response.stdout)
        previous = json.loads(base64.b64decode(remote['content']))
        if previous != data:
            body = {'message': 'Update daily Codex token usage', 'branch': 'usage-data', 'author': BOT, 'committer': BOT, 'sha': remote['sha'], 'content': base64.b64encode(content.encode()).decode()}
            state['pending_dispatch'] = True
            save()
            subprocess.run([args.gh, 'api', '--method', 'PUT', endpoint, '--input', '-'], input=json.dumps(body), check=True, capture_output=True, text=True, timeout=45)
            state['pushes'] = (state.get('pushes', 0) if state.get('day') == day else 0) + 1
            state['day'] = day
            save()
            print('Published daily token aggregates to usage-data')
        else:
            print('Skip: daily data unchanged')
        if state.get('pending_dispatch'):
            subprocess.run([args.gh, 'workflow', 'run', 'snake.yml', '--repo', 'Mufanc/Mufanc', '--ref', 'main'], check=True, capture_output=True, text=True, timeout=30)
            state['pending_dispatch'] = False
        state['last_success'] = time.time()
        save()


if __name__ == '__main__':
    main()
