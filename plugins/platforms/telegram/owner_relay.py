"""Owner-only deterministic bot relay for the Test group. No model chooses recipients."""
import re
import logging
from gateway.telegram_owner_request import OWNER_ID, CHAT_ID, PROCESS_STARTED, consume_request
import time

logger = logging.getLogger(__name__)
SELF = 'hermes_render_bot'
TARGETS = ('hermes1_instinct1_bot', 'instinctbig_bot')
HANDLE = re.compile(r'(?<![A-Za-z0-9_])@([A-Za-z0-9_]+)', re.I)
ENDING = re.compile(r'(?i)\s+(?:der\s*misin|de|s[oö]yler\s*misin|s[oö]yle|sorar\s*m[ıi]s[ıi]n|sor)\s*[?.!]*$')


def relay_plan(message):
    sender = getattr(message, 'from_user', None)
    if not sender or sender.id != OWNER_ID or getattr(sender, 'is_bot', False) or getattr(message.chat, 'id', None) != CHAT_ID:
        return None
    if getattr(message, 'edit_date', None):
        return None
    stamp = getattr(message, 'date', None)
    if stamp is None or not PROCESS_STARTED <= stamp.timestamp() <= time.time() or time.time() - stamp.timestamp() > 120:
        return None
    text = str(getattr(message, 'text', '') or '')
    if any(str(getattr(e, 'type', '')).split('.')[-1].lower() in {'code','pre','url','text_link'} for e in (getattr(message, 'entities', None) or [])):
        return None
    from plugins.platforms.telegram.first_bot_priority import first_bot_handle
    if first_bot_handle(message) != SELF:
        return None
    handles = [m.group(1).lower() for m in HANDLE.finditer(text)]
    if not handles or handles[0] != SELF or any(h not in {SELF, *TARGETS} for h in handles):
        return None
    targets = list(dict.fromkeys(h for h in handles[1:] if h in TARGETS))
    if not targets or not ENDING.search(text):
        return None
    # Only the addressing prefix is stripped. Remaining @ signs fail closed.
    prefix = re.match(r"(?i)^\s*@hermes_render_bot\b\s*((?:(?:@(?:hermes1_instinct1_bot|instinctbig_bot)\b(?:['’](?:ya|ye|a|e)|\s+(?:ya|ye|a|e)\b)?|ve\b|ile\b)[\s,]*)+)", text)
    if not prefix:
        return None
    body = ENDING.sub('', ' ' + text[prefix.end():]).strip()
    if not body or '@' in body or len(body) > 1000:
        return None
    # Only an explicit final indirect-verb allowlist is converted to an imperative.
    verbs = {'anlatmasını': 'anlat', 'anlatmasini': 'anlat',
             'söylemesini': 'söyle', 'soylemesini': 'söyle',
             'sormasını': 'sor', 'sormasini': 'sor'}
    body = re.sub(r'(?i)\b(anlatmasını|anlatmasini|söylemesini|soylemesini|sormasını|sormasini)$',
                  lambda m: verbs.get(m.group(1).lower(), m.group(1)), body)
    # A request to ask the time becomes a fixed question, never a locally answered clock query.
    if re.fullmatch(r'(?i)(?:saati|saat[ıi])', body):
        body = 'Saat kaç?'
    return [(target, '@' + target + ' ' + body) for target in targets]


async def handle_owner_relay(adapter, message):
    plan = relay_plan(message)
    if plan is None:
        return False
    runner = getattr(adapter, 'gateway_runner', None) or getattr(getattr(adapter, '_message_handler', None), '__self__', None)
    if runner is None or not hasattr(runner, '_bot_loop_guard_instance'):
        logger.warning('Owner relay unavailable: no gateway guard')
        return True
    source = adapter._source_from_message_for_auth(message)
    guard = runner._bot_loop_guard_instance()
    conversation = runner._bot_loop_guard_conversation(source)
    for target, text in plan:
        key = f'out:{CHAT_ID}:{OWNER_ID}:{message.message_id}:{target}'
        # Claim before any send to prevent duplicates on update replay or uncertain send result.
        if not consume_request(key):
            logger.info('Owner relay suppressed: already claimed original=%s target=@%s', message.message_id, target)
            continue
        from gateway.relay_model_rewrite import rewrite_request
        source_payload = text.split(' ', 1)[1]
        rewritten = await rewrite_request(source_payload)
        if rewritten is None:
            logger.warning('Owner relay suppressed: rewrite validation failed original=%s target=@%s', message.message_id, target)
            await adapter.send(str(CHAT_ID), 'İsteği güvenli biçimde yeniden yazamadım. Lütfen tek ve kısa bir istek yazın.', reply_to=str(message.message_id))
            continue
        text = '@' + target + ' ' + rewritten
        def admit():
            ok, reason = guard.admit(conversation)
            if ok:
                ok, reason = guard.chain_admit(conversation, SELF, text, is_bot=True)
            return ok, reason
        allowed, reason = runner._under_authorization_profile(source, admit)
        if not allowed:
            logger.info('Owner relay suppressed: guard=%s original=%s target=@%s', reason, message.message_id, target)
            continue
        result = await adapter.send(str(CHAT_ID), text, reply_to=str(message.message_id))
        logger.info('Owner relay send result: original=%s target=@%s success=%s message_id=%s', message.message_id, target, result.success, result.message_id)
    return True
