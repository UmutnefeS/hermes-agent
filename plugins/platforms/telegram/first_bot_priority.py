"""First bot mentioned owns messages in Mustafa's Test group."""
import re
from plugins.platforms.telegram.telegram_entities import addressing_sources

TEST_GROUP_ID = "-1002498879871"
KNOWN_BOTS = frozenset({"hermes_render_bot", "hermes1_instinct1_bot", "instinctbig_bot", "instinctbasic_bot"})
_HANDLE = re.compile(r"(?<![A-Za-z0-9_`])@([A-Za-z0-9_]{2,64})\b", re.I)


def _canonical(handle):
    handle = handle.lower().lstrip("@")
    for bot in KNOWN_BOTS:
        if handle == bot or (handle.startswith(bot) and re.fullmatch(r"(?:_bot)+", handle[len(bot):])):
            return bot
    return handle if handle.endswith("bot") else None


def first_bot_handle(message):
    """Read mentions in order, respecting Telegram code/link entities and UTF-16 offsets.

    Repeated autocomplete _bot suffixes on known bots keep their original identity.
    When Telegram provides no entities, use a bounded raw handle fallback.
    """
    for text, entities in addressing_sources(message):
        candidates = []
        if entities:
            encoded = text.encode("utf-16-le")
            for entity in entities:
                kind = str(getattr(entity, "type", "")).split(".")[-1].lower()
                if kind not in {"mention", "bot_command"}:
                    continue
                start, size = getattr(entity, "offset", -1), getattr(entity, "length", 0)
                if start < 0 or size <= 0:
                    continue
                try:
                    span = encoded[start * 2:(start + size) * 2].decode("utf-16-le")
                except UnicodeDecodeError:
                    continue
                if "@" in span:
                    candidates.append((start, span.split("@", 1)[1]))
        else:
            candidates = [(m.start(), m.group(1)) for m in _HANDLE.finditer(text)]
        for _, handle in sorted(candidates):
            bot = _canonical(handle)
            if bot:
                return bot
    return None
