"""Regression tests for owner-linked admission, using the production guard."""
import importlib.util
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace as NS
import unittest


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    sys.modules[name] = m
    s.loader.exec_module(m)
    return m


request = load('owner_request', 'gateway/telegram_owner_request.py')
guard = load('loop_guard', 'gateway/bot_loop_guard.py')
NOW = float(int(request.PROCESS_STARTED) + 2)


def event(payload='test42', original=None):
    original = original or '@Instinctbig_bot @Hermes_render_bot ' + payload
    human = NS(from_user=NS(id=request.OWNER_ID, is_bot=False), chat=NS(id=request.CHAT_ID), text=original, message_id=71,
               date=datetime.fromtimestamp(NOW, timezone.utc), edit_date=None)
    raw = NS(from_user=NS(id=request.RELAY_ID, is_bot=True), chat=NS(id=request.CHAT_ID), text='@Hermes_render_bot ' + payload, reply_to_message=human)
    return NS(source=NS(platform=NS(value='telegram'), chat_id=request.CHAT_ID, is_bot=True, user_id=request.RELAY_ID), raw_message=raw)


class OwnerRelayTests(unittest.TestCase):
    def test_fresh_verified_and_once(self):
        key = request.owner_request_key(event(), now=NOW)
        self.assertTrue(key)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'used.sqlite'
            self.assertTrue(request.consume_request(key, p))
            self.assertFalse(request.consume_request(key, p))

    def test_wrong_context_rejected(self):
        changes = [
            lambda e: setattr(e.raw_message.from_user, 'id', 123),
            lambda e: setattr(e.raw_message.reply_to_message.from_user, 'id', 123),
            lambda e: setattr(e.raw_message.reply_to_message.from_user, 'is_bot', True),
            lambda e: setattr(e.raw_message.chat, 'id', -99),
            lambda e: setattr(e.raw_message.reply_to_message, 'date', datetime.fromtimestamp(NOW - 500, timezone.utc)),
            lambda e: setattr(e.raw_message.reply_to_message, 'edit_date', True),
            lambda e: setattr(e.raw_message, 'reply_to_message', None),
            lambda e: setattr(e.raw_message, 'text', '@Hermes_render_bot /start different payload'),
            lambda e: setattr(e.raw_message.reply_to_message, 'text', '@Hermes_render_bot test42'),
        ]
        for mutate in changes:
            e = event(); mutate(e)
            self.assertIsNone(request.owner_request_key(e, now=NOW))

    def test_only_reply_barrier_bypassed(self):
        g = guard.BotLoopGuard(settings=lambda: guard.BotLoopGuardSettings(max_hops=3), clock=lambda:1000.)
        self.assertTrue(g.admit('chat')[0])
        self.assertEqual(g.chain_admit('chat', 'peer', 'first', is_bot=True), (True, 'ok'))
        g.note_reply('chat', 'peer')
        self.assertEqual(g.chain_admit('chat', 'peer', 'second', is_bot=True), (False, 'reply_to_reply'))
        self.assertEqual(g.chain_admit('chat', 'peer', 'second', is_bot=True, owner_request_claim=lambda:True), (True, 'ok'))
        self.assertEqual(g.chain_admit('chat', 'peer', 'second', is_bot=True, owner_request_claim=lambda:True), (False, 'duplicate'))
        self.assertEqual(g.chain_admit('chat', 'peer', 'third', is_bot=True, owner_request_claim=lambda:False), (False, 'owner_request_used'))
        self.assertEqual(g.chain_admit('chat', 'peer', 'third', is_bot=True, owner_request_claim=lambda:True), (True, 'ok'))
        self.assertEqual(g.chain_admit('chat', 'peer', 'fourth', is_bot=True, owner_request_claim=lambda:True), (False, 'max_hops'))

    def test_shared_payload_examples(self):
        self.assertEqual(request.payload("@Instinctbig_bot @Hermes_render_bot a selam soyle"), 'selam')
        self.assertEqual(request.payload("@Instinctbig_bot @Hermes1_instinct1_bot ve @Hermes_render_bot'a merhaba de"), 'merhaba')
        self.assertEqual(request.payload("@Instinctbig_bot @Hermes_render_bot _bot a test42 der misin"), 'test42')

    def test_rate_budget_unchanged(self):
        g = guard.BotLoopGuard(settings=lambda:guard.BotLoopGuardSettings(max_events=1), clock=lambda:1000.)
        self.assertEqual(g.admit('chat'), (True, 'ok'))
        self.assertEqual(g.admit('chat'), (False, 'tripped'))
        self.assertEqual(g.admit('chat'), (False, 'cooldown'))


if __name__ == '__main__':
    unittest.main()
