"""Shared strict validation for short model-written relay questions."""
import re
import unicodedata

STOP = {'bir','ve','ile','a','e','ya','ye','tan','ten','dan','den','de','diye','lutfen','mi','mu','misin','musun','misiniz','musunuz','sana','ona','bana','bunu','sunu','su','bu','hangi','kac'}
WRAPPERS = {'soyle','soylermisin','soyler','soylemesini','sor','sorarmisin','sorar','sormasini','de','dermisin','der','istermisin','ister','istemek','istiyorum','istiyorum','istemi','misin'}

def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s.lower().replace('ı','i')) if not unicodedata.combining(c))


def content_words(s):
    words = re.findall(r'[a-z0-9]+', fold(s))
    return {w[:5] for w in words if w not in STOP and w not in WRAPPERS}


def valid_rewrite(source, candidate):
    if not isinstance(candidate, str) or not 2 <= len(candidate) <= 220:
        return False
    if any(c in candidate for c in '@/\\\n\r<>`:=') or re.search(r'(?i)https?|www\.|\b(?:com|net|org)\b|[\w-]+\.[a-z]{2,}', candidate):
        return False
    if len(re.findall(r'[.!?]',candidate)) > 1 or re.search(r'[.!?].+\S', candidate):
        return False
    if candidate.lstrip().startswith(('-', '!', '$', '#')):
        return False
    # Vocabulary may change when the model preserves the owner's intent.
    # This filter enforces shape and hard invariants, not semantic equivalence.
    if not re.search(r'[A-Za-zÇĞİÖŞÜçğıöşü]', candidate):
        return False
    if re.findall(r'\d+', source) != re.findall(r'\d+', candidate):
        return False
    # Keep explicit negation. Ambiguous inflected requests fail closed.
    for word in ('degil','hayir','yapma','etme','gonderme','silme'):
        if (word in fold(source).split()) != (word in fold(candidate).split()):
            return False
    return True
