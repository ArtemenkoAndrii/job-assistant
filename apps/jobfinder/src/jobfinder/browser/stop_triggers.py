"""Stop triggers (ADR-0011 §6, NFR-B7): is this page a reason to stop at once?

Pure text rules over the URL, title and body of a tool result, English and Spanish. The page text
is data: it is matched against fixed patterns and never interpreted.
"""

import re
from urllib.parse import urlsplit

from jobfinder.domain.runs import Reason

LOGIN_PATHS = ("/login", "/uas/login", "/checkpoint", "/authwall", "/signup")
LOGIN_TEXT = re.compile(
    r"sign in to (?:view|linkedin|see)|join linkedin|join now to see|authwall"
    r"|inicia(?:r)? sesi[oó]n para|[uú]nete a linkedin",
    re.IGNORECASE,
)
CHALLENGE_TEXT = re.compile(
    r"just a moment|verify you are human|challenges\.cloudflare\.com|captcha"
    r"|quick security check|unusual activity|temporarily restricted"
    r"|verifica que eres humano|un momento|actividad inusual|comprobaci[oó]n de seguridad",
    re.IGNORECASE,
)
BLOCK_TITLE = re.compile(r"\b(?:403|429)\b|access denied|too many requests", re.IGNORECASE)


def evaluate(url: str, title: str, text: str, status: int | None = None) -> Reason | None:
    """The reason to stop, or None if the page looks normal."""
    if status in (403, 429):
        return Reason.CHALLENGE
    path = urlsplit(url).path.lower()
    if any(path.startswith(p) for p in LOGIN_PATHS):
        return Reason.LOGIN_WALL
    if CHALLENGE_TEXT.search(title) or CHALLENGE_TEXT.search(text):
        return Reason.CHALLENGE
    if BLOCK_TITLE.search(title):
        return Reason.CHALLENGE
    if LOGIN_TEXT.search(title) or LOGIN_TEXT.search(text):
        return Reason.LOGIN_WALL
    return None
