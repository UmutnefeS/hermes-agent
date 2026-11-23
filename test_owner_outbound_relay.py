"""Owner relay parser and send-path tests. Fake sender only, no Telegram traffic."""
import ast
import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
import unittest
from datetime import datetime, timezone

package=ModuleType('plugins.platforms.telegram'); package.__path__=[str(Path('plugins/platforms/telegram').resolve())]
sys.modules['plugins.platforms.telegram']=package
from plugins.platforms.telegram import owner_relay as relay
from gateway.bot_loop_guard import BotLoopGuard, BotLoopGuardSettings


def msg(text):
    return NS(text=text, entities=[], chat=NS(id=relay.CHAT_ID), from_user=NS(id=relay.OWNER_ID,is_bot=False), message_id=123, edit_date=None, date=datetime.now(timezone.utc))


class RelayTests(unittest.TestCase):
    def test_time_and_two_targets(self):
        self.assertEqual(relay.relay_plan(msg('@Hermes_render_bot @Hermes1_instinct1_bot a saati sorarmisin')), [('hermes1_instinct1_bot','@hermes1_instinct1_bot Saat kaç?')])
        self.assertEqual(relay.relay_plan(msg("@Hermes_render_bot @Hermes1_instinct1_bot ve @Instinctbig_bot'a merhaba de")), [('hermes1_instinct1_bot','@hermes1_instinct1_bot merhaba'),('instinctbig_bot','@instinctbig_bot merhaba')])

    def test_only_named_final_verbs_normalized(self):
        for indirect, imperative in [('anlatmasını','anlat'),('anlatmasini','anlat'),('söylemesini','söyle'),('soylemesini','söyle'),('sormasını','sor'),('sormasini','sor')]:
            result = relay.relay_plan(msg('@Hermes_render_bot @Instinctbig_bot a bir fikra ' + indirect + ' soylermisin'))
            self.assertEqual(result, [('instinctbig_bot','@instinctbig_bot bir fikra ' + imperative)])
        self.assertEqual(relay.relay_plan(msg('@Hermes_render_bot @Instinctbig_bot a bunu yazmasini soylermisin')), [('instinctbig_bot','@instinctbig_bot bunu yazmasini')])
        self.assertEqual(relay.relay_plan(msg('@Hermes_render_bot @Instinctbig_bot a anlatmasini tekrar soylermisin')), [('instinctbig_bot','@instinctbig_bot anlatmasini tekrar')])

    def test_reject_ambiguous_and_wrong_sender(self):
        for text in ['@Instinctbig_bot @Hermes_render_bot selam de', '@Hermes_render_bot @Other_bot selam de', '@Hermes_render_bot @Hermes1_instinct1_bot test', '@Hermes_render_bot @Hermes1_instinct1_bot selam @Other_bot de']:
            self.assertIsNone(relay.relay_plan(msg(text)))
        for field,value in [('id',123),('is_bot',True)]:
            m=msg('@Hermes_render_bot @Instinctbig_bot selam de');setattr(m.from_user,field,value)
            self.assertIsNone(relay.relay_plan(m))

    def test_fake_send_is_reply_bound_and_once(self):
        async def run():
            g=BotLoopGuard(settings=lambda:BotLoopGuardSettings(),clock=lambda:1000.)
            r=NS(_bot_loop_guard_instance=lambda:g,_bot_loop_guard_conversation=lambda s:'chat',_under_authorization_profile=lambda s,f:f())
            a=NS(gateway_runner=r,_source_from_message_for_auth=lambda m:NS(),send=AsyncMock(return_value=NS(success=True,message_id='124')))
            with tempfile.TemporaryDirectory() as d:
                from gateway.telegram_owner_request import consume_request
                saved=relay.consume_request
                relay.consume_request=lambda k:consume_request(k,Path(d)/'used.sqlite')
                try:
                    m=msg('@Hermes_render_bot @Instinctbig_bot merhaba de')
                    with patch('gateway.relay_model_rewrite.rewrite_request', new=AsyncMock(return_value='merhaba')):
                        self.assertTrue(await relay.handle_owner_relay(a,m))
                        self.assertTrue(await relay.handle_owner_relay(a,m))
                    a.send.assert_awaited_once_with(str(relay.CHAT_ID),'@instinctbig_bot merhaba',reply_to='123')
                finally:relay.consume_request=saved
        asyncio.run(run())

    def test_duplicate_hops_and_budget_unchanged(self):
        g=BotLoopGuard(settings=lambda:BotLoopGuardSettings(max_hops=1),clock=lambda:1000.)
        self.assertEqual(g.chain_admit('c','hermes_render_bot','x',is_bot=True),(True,'ok'))
        self.assertEqual(g.chain_admit('c','hermes_render_bot','x',is_bot=True),(False,'duplicate'))
        self.assertEqual(g.chain_admit('c','hermes_render_bot','y',is_bot=True),(False,'max_hops'))


if __name__=='__main__':unittest.main()
