"""
Pure sentiment scoring utilities.
No network calls, no DB.

Keyword-driven sentiment for financial headlines in English AND German.
TextBlob polarity is used as a minor input (it only works for English),
while keyword matching carries most of the weight — especially for
German-language headlines from Yahoo Finance DE RSS feeds.
"""
import re
from textblob import TextBlob

# ── Financial keyword lists (English + German) ──────────
_BULLISH = [
    # English
    r"\bbeat(?:s|ing)?\b", r"\bsurpass", r"\bupgrade[ds]?\b",
    r"\brais(?:e[ds]?|ing)\b", r"\brecord high", r"\bstrong results",
    r"\bblowout", r"\boutperform", r"\bgrowth\b", r"\boptimis",
    r"\bbullish", r"\bexpansion", r"\bdividend hike", r"\bbuyback",
    r"\bpositive guidance", r"\brally", r"\bsurge[ds]?\b",
    r"\bsoar(?:s|ed|ing)?\b", r"\bacceler",
    # German
    r"\bkaufen\b", r"\bkaufempfehlung", r"\b[üu]bergewicht(?:en|ung)?\b",
    r"\bkursplus\b", r"\bkursziel\s*(?:angehoben|erhöht|rauf)",
    r"\bgefragt\b", r"\bauftrieb\b", r"\bwachstum",
    r"\bgewinnplus\b", r"\brekord(?:hoch|gewinn|umsatz)",
    r"\bstarke[sn]?\s+(?:ergebnis|zahlen|quartal)",
    r"\boptimist", r"\bkursrall[yi]e?\b",
    r"\bangehoben\b", r"\berhöh(?:t|ung)\b",
    r"\bpositiv(?:e[rsnm]?)?\b", r"\bzulegen\b", r"\bzugelegt\b",
    r"\bexponiert\b", r"\bchance[n]?\b",
    r"\bvertrag\s*verl[äa]ngert", r"\bverlängert\b",
]
_BEARISH = [
    # English
    r"\bmiss(?:es|ed|ing)?\b", r"\bdowngrade[ds]?\b",
    r"\bcut(?:s|ting)?\b", r"\bwarn(?:s|ed|ing)?\b",
    r"\brecession", r"\bloss(?:es)?\b", r"\bplunge[ds]?\b",
    r"\bcrash(?:es|ed)?\b", r"\bslump", r"\bbearish", r"\bdefault",
    r"\blawsuit", r"\bregulat(?:ory|ion)\s+(?:risk|probe|fine)",
    r"\bprofit warning", r"\bnegative guidance",
    r"\btumble[ds]?\b", r"\bsink(?:s|ing)?\b",
    # German
    r"\bverkaufen\b", r"\bverkaufsempfehlung",
    r"\buntergewicht(?:en|ung)?\b",
    r"\bentt[äa]usch(?:t|end|ung)\b",
    r"\bkursverlust", r"\bkursminus\b",
    r"\bkursziel\s*(?:gesenkt|reduziert|runter)",
    r"\bgesenkt\b", r"\breduziert\b",
    r"\bverl(?:ust|ieren|iert|or)\b",
    r"\bdreijahrestief\b", r"\b(?:all)?zeittief\b",
    r"\bjahrestief\b", r"\btief(?:stand|punkt|st)\b",
    r"\bf[äa]llt\b", r"\babsturz\b", r"\beinbruch\b",
    r"\bschwach(?:e[rsnm]?)?\b", r"\bwarnung\b",
    r"\brisikoreich\b", r"\brisik(?:o|en)\b",
    r"\bnegativ(?:e[rsnm]?)?\b", r"\bbelast(?:et|ung)\b",
    r"\bgewinnwarnung\b", r"\bprognosesenkung\b",
    r"\bkorrektur\b", r"\babverkauf\b",
]

_BULL_RE = re.compile("|".join(_BULLISH), re.IGNORECASE)
_BEAR_RE = re.compile("|".join(_BEARISH), re.IGNORECASE)

# Keyword weight — high because TextBlob is near-useless on German text
_KEYWORD_BOOST = 0.12
# How much weight TextBlob base polarity gets (low for German-heavy feeds)
_TEXTBLOB_WEIGHT = 0.3


def analyze_text(text: str) -> float:
    """Return a sentiment polarity in [-1.0, 1.0].

    Primarily keyword-driven (works for both English and German).
    TextBlob polarity is blended in as a minor factor since it
    only understands English.
    """
    if not text:
        return 0.0

    # TextBlob base — useful for English, near-zero for German
    try:
        base = float(TextBlob(text).sentiment.polarity)
    except Exception:
        base = 0.0

    # Keyword matching — the main signal for German headlines
    bull_hits = len(_BULL_RE.findall(text))
    bear_hits = len(_BEAR_RE.findall(text))
    keyword_score = (bull_hits - bear_hits) * _KEYWORD_BOOST

    # Blend: keywords dominate, TextBlob is secondary
    combined = keyword_score + (base * _TEXTBLOB_WEIGHT)

    return max(-1.0, min(1.0, combined))


def score_label(score: float) -> str:
    if score > 0.3:
        return "VERY POSITIVE"
    elif score > 0.1:
        return "POSITIVE"
    elif score > -0.1:
        return "NEUTRAL"
    elif score > -0.3:
        return "NEGATIVE"
    else:
        return "VERY NEGATIVE"