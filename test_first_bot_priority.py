"""Dependency-free regression tests of the production routing methods."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import logging
import unittest
import sys
from types import ModuleType
package = ModuleType('plugins.platforms.telegram')
package.__path__ = [str(Path('plugins/platforms/telegram').resolve())]
sys.modules['plugins.platforms.telegram'] = package
from plugins.platforms.telegram.first_bot_priority import first_bot_handle, TEST_GROUP_ID

# Execute exact production methods with only unrelated platform state stubbed.
tree = ast.parse(Path('plugins/platforms/telegram/adapter.py').read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TelegramAdapter')
names = {'_explicit_bot_mentions_exclude_self', '_should_process_message', '_message_mentions_bot'}
body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
mini = ast.Module(body=[ast.ClassDef(name='Gate', bases=[], keywords=[], body=body, decorator_list=[])], type_ignores=[])
namespace = dict(Message=object, logger=logging.getLogger('first-bot-test'), refresh_telegram_gates=lambda s: None)
exec(compile(ast.fix_missing_locations(mini), '<production-gates>', 'exec'), namespace)
Gate = namespace['Gate']


def message(text, entities=None, caption=None, reply=False):
    return NS(text=text, entities=entities or [], caption=caption, caption_entities=[], message_id=42,
              chat=NS(id=int(TEST_GROUP_ID)), reply=reply)


def gate():
    a = Gate()
    a._bot = NS(id=999)
    a.name = 'Hermes2'
    a._current_bot_username = lambda: 'hermes_render_bot'
    a._chat_id_str = lambda m: str(m.chat.id)
    a._observe_bot_identity_from_message = lambda m: None
    a._is_own_message = lambda m: False
    a._is_group_chat = lambda m: m.chat.id < 0
    a._effective_message_thread_id = lambda m: None
    a._topic_gates_pass = lambda *args, **kw: True
    a._telegram_exclusive_bot_mentions = lambda: True
    a._is_guest_mention = lambda m: False
    a._telegram_allowed_chats = lambda: []
    a._bot_sender_suppressed = lambda m: False
    a._telegram_free_response_chats = lambda: []
    a._telegram_is_free_response_topic = lambda m: False
    a._telegram_require_mention = lambda: True
    a._is_reply_to_bot = lambda m: m.reply
    a._message_matches_mention_patterns = lambda m: False
    return a


class FirstBotTests(unittest.TestCase):
    def test_production_gates(self):
        cases = [
            ('@Instinctbig_bot @Hermes_render_bot selam', False),
            ('@Hermes_render_bot @Instinctbig_bot selam', True),
            ('Selam @Instinctbig_bot sonra @Hermes_render_bot', False),
            ('Selam @Hermes_render_bot sonra @Instinctbig_bot', True),
            ('@Hermes1_instinct1_bot @Hermes_render_bot', False),
            ('@Hermes_render_bot selam', True),
            ('@Instinctbig_bot @Hermes_render_bot_bot\'a selam', False),
            ('@Hermes_render_bot_bot\'a @Instinctbig_bot selam', True),
            ('@Hermes_render_bot _bot a @Instinctbig_bot selam', True),
            ('@Instinctbig_bot_bot\'a @Hermes_render_bot selam', False),
            ('@alice @Hermes_render_bot selam', True),
            ('@HERMES_RENDER_BOT @INSTINCTBIG_BOT selam', True),
        ]
        for text, expected in cases:
            for reply in (False, True):
                with self.subTest(text=text, reply=reply):
                    self.assertEqual(gate()._should_process_message(message(text, reply=reply)), expected)

    def test_utf16_and_entity_order(self):
        text = '\U0001f44b @Instinctbig_bot @Hermes_render_bot selam'
        ents = [NS(type='mention', offset=len(text[:text.index(h)].encode('utf-16-le')) // 2, length=len(h)) for h in ('@Hermes_render_bot', '@Instinctbig_bot')]
        self.assertFalse(gate()._should_process_message(message(text, ents)))

    def test_code_ignored(self):
        text = '@Instinctbig_bot @Hermes_render_bot'
        ents = [NS(type='code', offset=0, length=16), NS(type='mention', offset=17, length=18)]
        self.assertEqual(first_bot_handle(message(text, ents)), 'hermes_render_bot')

    def test_plain_reply_unchanged(self):
        a = gate()
        a._entity_sources = lambda m: []
        a._extract_bot_mention_usernames = lambda *args: set()
        self.assertTrue(a._should_process_message(message('selam', reply=True)))
        self.assertFalse(a._should_process_message(message('selam')))

    def test_caption(self):
        self.assertFalse(gate()._should_process_message(message(None, caption='@Instinctbig_bot @Hermes_render_bot selam')))


if __name__ == '__main__':
    unittest.main()
