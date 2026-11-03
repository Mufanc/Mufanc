import importlib.util
import unittest
import json
import base64
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
from datetime import date
from pathlib import Path
from codex_usage import panel, N

spec = importlib.util.spec_from_file_location('sync', Path(__file__).with_name('sync-codex-usage.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
export = sync.export


class UsageChecks(unittest.TestCase):
    def test_export_and_weekly_render(self):
        source = {'is_self': True, 'page': {'activity_graph': {'daily_usage_buckets': [
            {'start_date': '2026-10-04', 'tokens': 100, 'chat_turns': 9},
            {'start_date': '2026-10-05', 'tokens': 30},
            {'start_date': '2026-10-08', 'tokens': 20},
        ]}}}
        data = export(source, date(2026, 10, 8))
        self.assertEqual(set(data), {'version', 'as_of', 'daily'})
        self.assertEqual(sum(data['daily'].values()), 150)  # Do not add cached tokens twice.
        for dark in (False, True):
            svg = panel(data, dark)
            self.assertEqual(len(svg.findall(N + 'rect')), 365)
            numbers = [t.text for t in svg.findall(N + 'text')]
            self.assertIn('150', numbers)
            self.assertIn('50', numbers)  # Monday onward; Sunday belongs to last week.
        source['page']['activity_graph']['daily_usage_buckets'].append({'start_date': '2026-10-08', 'tokens': 20})
        with self.assertRaises(ValueError):
            export(source, date(2026, 10, 8))

    def test_reject_invalid_profile(self):
        for payload in [
            {'is_self': False},
            {'is_self': True, 'page': {'activity_graph': {'daily_usage_buckets': []}}},
            {'is_self': True, 'page': {'activity_graph': {'daily_usage_buckets': [{'start_date': '2026-10-08', 'tokens': -1}]}}},
        ]:
            with self.assertRaises(ValueError):
                export(payload, date(2026, 10, 8))

    def test_zero_and_missing_are_distinct(self):
        data = {'version': 1, 'as_of': '2026-10-08', 'daily': {'2026-10-08': 0}}
        cells = panel(data, False).findall(N + 'rect')
        self.assertEqual(len({c.get('fill') for c in cells}), 2)

    def test_bot_upload_stays_off_main(self):
        today = sync.datetime.now(sync.TZ).date().isoformat()
        raw = {'is_self': True, 'page': {'activity_graph': {'daily_usage_buckets': [{'start_date': today, 'tokens': 10}]}}}
        remote = {'sha': 'previous-blob', 'content': base64.b64encode(json.dumps({'daily': {}}).encode()).decode()}
        replies = [SimpleNamespace(stdout=json.dumps(remote)), SimpleNamespace(stdout='{}'), SimpleNamespace(stdout='')]
        with TemporaryDirectory() as temp, patch.object(sync.subprocess, 'run', side_effect=replies) as run, patch.object(sync, 'fetch_usage', return_value=raw):
            with patch('sys.argv', ['sync', '--publish', '--state', str(Path(temp) / 'state.json')]):
                sync.main()
            self.assertIn('?ref=usage-data', run.call_args_list[0].args[0][-1])
            body = json.loads(run.call_args_list[1].kwargs['input'])
            self.assertEqual(body['branch'], 'usage-data')
            self.assertEqual(body['author'], sync.BOT)
            self.assertEqual(body['committer'], sync.BOT)
            self.assertEqual(run.call_args_list[2].args[0][-2:], ['--ref', 'main'])
            self.assertIn('workflow', run.call_args_list[2].args[0])
            state = json.loads((Path(temp) / 'state.json').read_text())
            self.assertEqual(state['pushes'], 1)
            self.assertFalse(state['pending_dispatch'])

    def test_persistent_rate_limits(self):
        now = 100000
        self.assertTrue(sync.eligible({}, now, '2026-10-08'))
        self.assertFalse(sync.eligible({'last_success': now - 21599}, now, '2026-10-08'))
        self.assertFalse(sync.eligible({'last_attempt': now - 599}, now, '2026-10-08'))
        self.assertFalse(sync.eligible({'day': '2026-10-08', 'pushes': 4}, now, '2026-10-08'))
        self.assertTrue(sync.eligible({'day': '2026-10-07', 'pushes': 4}, now, '2026-10-08'))


if __name__ == '__main__':
    unittest.main()
