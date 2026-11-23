"""Regression tests, fake events only, no Telegram traffic."""
import ast
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from gateway.telegram_bot_answer import answer_only, prepare_bot_answer, sanitize_bot_answer


def source(**kw):
    return NS(**dict(dict(platform=NS(value='telegram'), chat_id='-1002498879871', is_bot=True), **kw))


class BotAnswerTests(unittest.TestCase):
    def test_scope(self):
        self.assertTrue(answer_only(source()))
        for s in [source(is_bot=False), source(chat_id='other'), source(platform=NS(value='discord'))]:
            self.assertFalse(answer_only(s))

    def test_prepare_keeps_auth_and_reply_anchor(self):
        e=NS(source=source(),reply_to_text='outer owner relay request',reply_to_message_id='6589',channel_prompt='existing')
        s=e.source
        prepare_bot_answer(e)
        self.assertIsNone(e.reply_to_text)
        self.assertEqual(e.reply_to_message_id,'6589')
        self.assertIs(e.source,s)
        self.assertIn('Answer its underlying question yourself',e.channel_prompt)
        self.assertTrue(e.channel_prompt.startswith('existing'))

    def test_human_and_other_groups_unchanged(self):
        for s in [source(is_bot=False),source(chat_id='other')]:
            e=NS(source=s,reply_to_text='keep',reply_to_message_id='1',channel_prompt='keep')
            prepare_bot_answer(e)
            self.assertEqual(e.reply_to_text,'keep')
            self.assertEqual(e.channel_prompt,'keep')
            self.assertEqual(sanitize_bot_answer(s,'@Instinctbig_bot hello'),'@Instinctbig_bot hello')

    def test_no_bot_mentions_escape(self):
        for t in ['@Instinctbig_bot soru?', '@Hermes1_instinct1_bot cevap', '@\u200bInstinctbig_bot', 'email@example.com']:
            self.assertNotIn('@',sanitize_bot_answer(source(),t))
        self.assertEqual(sanitize_bot_answer(source(),'Nil Nehri.'),'Nil Nehri.')

    def test_stream_disabled_for_test_bot_before_other_setup(self):
        tree=ast.parse(Path('gateway/run_turn_runner.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_setup_stream_consumer')
        space={}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'real-method','exec'),space)
        self.assertEqual(space['_setup_stream_consumer'](NS(_ctx=NS(mute_notification_reply=False,source=source())), 'telegram'),(None,None,None,False))

    def test_actual_adapter_prepare_path(self):
        tree=ast.parse(Path('plugins/platforms/telegram/adapter.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.AsyncFunctionDef) and n.name=='_build_triggered_event')
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='prepare_bot_answer' for n in ast.walk(method)))
        persistence=Path('gateway/run_turn_persistence.py').read_text()
        self.assertIn('response = sanitize_bot_answer(source, response)',persistence)


if __name__=='__main__':unittest.main()
