"""Strict, single-use owner-linked Telegram relay admission for the Test group."""
import re
import sqlite3
import time
from pathlib import Path

OWNER_ID = 5080185444
RELAY_ID = 9115171687
CHAT_ID = -1002498879871
TARGET = 'hermes_render_bot'
ORIGIN = 'instinctbig_bot'
PROCESS_STARTED = time.time()
HANDLE = re.compile(r'(?<![A-Za-z0-9_])@([A-Za-z0-9_]+)', re.I)
KNOWN = {TARGET, ORIGIN, 'hermes1_instinct1_bot', 'instinctbasic_bot'}


def canonical(handle):
    h = handle.lower()
    for bot in KNOWN:
        if h == bot or (h.startswith(bot) and re.fullmatch(r'(?:_bot)+', h[len(bot):])):
            return bot
    return h


def payload(text):
    # Match the owner's deterministic relay grammar, not a model paraphrase.
    text = re.sub(r"(?i)@([A-Za-z0-9_]+)(?:\s+(?:_bot\s*)?(?:ya|ye|a|e)\b|['’](?:ya|ye|a|e)\b)?", ' ', str(text or ''))
    text = re.sub(r"(?i)(?:_bot)*(?:['’](?:ya|ye|a|e)|\b_bot\s+(?:ya|ye|a|e)\b)", ' ', text)
    text = re.sub(r'(?i)\b(?:ve|ile)\b', ' ', text)
    text = re.sub(r'(?i)\s+(?:der\s*misin|de|s[oö]yler\s*misin|s[oö]yle)\s*[?.!]*$', '', text)
    return ' '.join(text.split()).strip(' ,:;')


def owner_request_key(event, now=None):
    """Return a key only from SDK-supplied sender/reply fields, never a text claim."""
    source = event.source
    if getattr(getattr(source, 'platform', None), 'value', '') != 'telegram' or str(source.chat_id) != str(CHAT_ID):
        return None
    if not getattr(source, 'is_bot', False) or str(getattr(source, 'user_id', '')) != str(RELAY_ID):
        return None
    raw = getattr(event, 'raw_message', None)
    sender = getattr(raw, 'from_user', None)
    original = getattr(raw, 'reply_to_message', None)
    owner = getattr(original, 'from_user', None)
    if not (sender and sender.id == RELAY_ID and sender.is_bot and original and owner and owner.id == OWNER_ID and not owner.is_bot):
        return None
    if any(getattr(getattr(m, 'chat', None), 'id', None) != CHAT_ID for m in (raw, original)):
        return None
    if getattr(original, 'edit_date', None):
        return None
    stamp = getattr(original, 'date', None)
    age = (time.time() if now is None else now) - stamp.timestamp() if stamp else -1
    if not 0 <= age <= 120 or stamp.timestamp() < PROCESS_STARTED:
        return None
    original_text = str(getattr(original, 'text', '') or '')
    relay_text = str(getattr(raw, 'text', '') or '')
    if not original_text.lstrip().lower().startswith('@' + ORIGIN):
        return None
    if any(str(getattr(e, 'type', '')).split('.')[-1].lower() in {'code', 'pre'} for e in (getattr(original, 'entities', None) or [])):
        return None
    bots = [canonical(m.group(1)) for m in HANDLE.finditer(original_text)]
    relays = [canonical(m.group(1)) for m in HANDLE.finditer(relay_text)]
    if not bots or bots[0] != ORIGIN or TARGET not in bots or relays != [TARGET] or not relay_text.lstrip().lower().startswith('@' + TARGET):
        return None
    original_payload = payload(original_text)
    first_handle = HANDLE.search(relay_text)
    relay_payload = relay_text[first_handle.end():].strip() if first_handle else ''
    from gateway.relay_rewrite_validation import valid_rewrite
    if not original_payload or not valid_rewrite(original_payload, relay_payload):
        return None
    mid = getattr(original, 'message_id', None)
    return f'{CHAT_ID}:{OWNER_ID}:{mid}:{TARGET}' if isinstance(mid, int) and mid > 0 else None


def consume_request(key, path=None):
    """Atomically claim a one-use request across restarts; I/O errors fail closed."""
    if path is None:
        from hermes_constants import get_hermes_home
        path = get_hermes_home() / 'telegram-owner-requests.sqlite'
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(path), timeout=2) as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (request_key TEXT PRIMARY KEY, used_at REAL NOT NULL)')
            changed = db.execute('INSERT OR IGNORE INTO requests VALUES (?, ?)', (key, time.time())).rowcount
            return changed == 1
    except (OSError, sqlite3.Error):
        return False
