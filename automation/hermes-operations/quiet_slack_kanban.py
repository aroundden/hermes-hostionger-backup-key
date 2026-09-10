#!/usr/bin/env python3
"""Set existing Slack board subscriptions to native wake-only mode.
No task state, cursor, artifacts, profile configuration or Slack history changes.
New linked tasks inherit their creator/parent subscription mode.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

HOME = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
sys.path.insert(0, str(HOME / 'hermes-agent'))
from hermes_cli import kanban_db_connect as kbc
from hermes_cli import kanban_db_notify as kbn
from gateway.kanban_watchers_notifier import _KanbanNotification, _WAKE_KINDS


def verify_delivery(sub):
    task = SimpleNamespace(title='검증만 완료; 실제 적용 전', assignee='den', result='', session_id='test-origin')
    ev = SimpleNamespace(kind='completed', id=1, payload={'summary': '검증 완료. 실제 적용 없음.', 'artifacts': ['/tmp/internal-ax.json']})
    runner = SimpleNamespace(_deliver_kanban_artifacts=AsyncMock())
    n = _KanbanNotification(runner, {'sub': sub, 'task': task, 'board': 'default', 'events': [ev]}, platform_cls=None, sub_fail_counts={})
    n.adapter = SimpleNamespace(send=AsyncMock())
    assert n.wake_agent and not n.send_passive
    assert asyncio.run(n._send_pings())
    n.adapter.send.assert_not_awaited()
    runner._deliver_kanban_artifacts.assert_not_awaited()
    n.build_wake_text()
    assert n.wake_kinds == {'completed'}
    assert '검증 완료. 실제 적용 없음.' in n.synth
    assert {'blocked', 'review_requested', 'changes_requested', 'gave_up'} <= set(_WAKE_KINDS)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    conn = kbc.connect(board='default')
    try:
        rows = kbn.list_notify_subs(conn)
        targets = [r for r in rows if r['platform'].lower() == 'slack' and r.get('notifier_profile') in ('den', 'default', '', None)]
        changes = [r for r in targets if r.get('delivery_mode') != 'wake']
        for r in targets:
            verify_delivery({**r, 'delivery_mode': 'wake'})
        print(json.dumps({'slack_subscriptions': len(targets), 'mode_changes': len(changes), 'delivery_test': 'PASS: no raw ping or artifact upload; completion handoff and blocker wake retained'}, ensure_ascii=False))
        if not args.apply:
            return
        folder = HOME / 'cache' / 'slack-notification-policy'
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        receipt = folder / f'{stamp}.json'
        receipt.write_text(json.dumps({'before': targets}, ensure_ascii=False, indent=2))
        receipt.chmod(0o600)
        for r in changes:
            kbn.add_notify_sub(conn, task_id=r['task_id'], platform=r['platform'], chat_id=r['chat_id'], thread_id=r.get('thread_id'), delivery_mode='wake')
        after = kbn.list_notify_subs(conn)
        key = lambda r: (r['task_id'], r['platform'], r['chat_id'], r['thread_id'])
        after_by_key = {key(r): r for r in after}
        target_keys = {key(r) for r in targets}
        assert len(rows) == len(after)
        for r in rows:
            observed = after_by_key[key(r)]
            expected = {**r, 'delivery_mode': 'wake'} if key(r) in target_keys else r
            assert observed == expected, f'Unexpected subscription change: {key(r)}'
        receipt.write_text(json.dumps({'before': targets, 'after': [after_by_key[key(r)] for r in targets], 'verified': True}, ensure_ascii=False, indent=2))
        print(json.dumps({'applied': len(changes), 'readback_verified': True, 'only_delivery_mode_changed': True, 'receipt': str(receipt)}, ensure_ascii=False))
    finally:
        conn.close()

if __name__ == '__main__':
    main()
