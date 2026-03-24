"""
filter.py – Nøkkelordbasert relevansscoring for oljeprissensitive nyheter.

Score 0–100. Varsel sendes hvis score >= THRESHOLD (standard: 40).
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from sources import Article

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Terskelverdi – juster etter behov
# ──────────────────────────────────────────────
THRESHOLD = 40


# ──────────────────────────────────────────────
# Nøkkelord med vekter (høyere = mer relevant)
# ──────────────────────────────────────────────

# Kjerneord: direkte koblet til oljepris
CORE_OIL = {
    "brent": 25,
    "wti": 25,
    "crude oil": 25,
    "crude": 15,
    "oil price": 25,
    "barrel": 15,
    "$/b": 20,
    "per barrel": 20,
    "oil market": 20,
    "petroleum": 15,
    "gasoline": 10,
    "fuel": 8,
    "refinery": 10,
    "refining": 10,
    "downstream": 10,
    "upstream": 10,
}

# OPEC og produksjon
OPEC_SUPPLY = {
    "opec": 20,
    "opec+": 25,
    "production cut": 25,
    "output cut": 25,
    "production quota": 20,
    "oil output": 20,
    "oil supply": 20,
    "oil production": 20,
    "spare capacity": 20,
    "oil stockpile": 15,
    "oil inventory": 15,
    "strategic reserve": 15,
    "spr": 15,
    "drawdown": 12,
    "oversupply": 20,
    "undersupply": 20,
    "glut": 15,
}

# Geopolitiske triggere
GEOPOLITICAL = {
    "iran": 15,
    "iranian": 15,
    "tehran": 12,
    "hormuz": 25,
    "strait of hormuz": 30,
    "persian gulf": 20,
    "gulf": 8,
    "saudi": 15,
    "saudi arabia": 18,
    "riyadh": 12,
    "iraq": 12,
    "kuwait": 12,
    "uae": 10,
    "abu dhabi": 10,
    "venezuela": 12,
    "russia": 12,
    "russian oil": 20,
    "libya": 12,
    "nigeria": 10,
    "conflict": 10,
    "war": 12,
    "airstrike": 15,
    "bombing": 15,
    "attack": 8,
    "tanker": 18,
    "pipeline": 15,
    "infrastructure attack": 20,
}

# Politikk og sanksjoner
POLICY_SANCTIONS = {
    "sanction": 20,
    "sanctions": 20,
    "embargo": 22,
    "export ban": 20,
    "nuclear deal": 22,
    "nuclear agreement": 22,
    "jcpoa": 22,
    "trump": 10,
    "biden": 8,
    "executive order": 10,
    "tariff": 8,
    "trade war": 10,
    "ceasefire": 15,
    "peace deal": 12,
    "deal": 6,
}

# Markedsuttrykk
MARKET_TERMS = {
    "rally": 10,
    "surge": 12,
    "spike": 12,
    "slump": 12,
    "plunge": 12,
    "drop": 8,
    "rise": 6,
    "fall": 6,
    "volatility": 10,
    "futures": 12,
    "hedge": 8,
    "commodities": 8,
    "energy sector": 10,
    "energy market": 12,
}

ALL_KEYWORD_GROUPS = [
    CORE_OIL,
    OPEC_SUPPLY,
    GEOPOLITICAL,
    POLICY_SANCTIONS,
    MARKET_TERMS,
]

# Negativt filter – unngå irrelevante treff på "oil" i andre sammenhenger
NEGATIVE_KEYWORDS = {
    "cooking oil": -30,
    "olive oil": -30,
    "palm oil": -10,
    "essential oil": -30,
    "hair oil": -30,
    "sunflower oil": -20,
    "vegetable oil": -15,
    "motor oil": -5,    # kan faktisk være relevant (refining), lav straff
}


@dataclass
class ScoredArticle:
    article: "Article"
    score: int
    matched_keywords: list[str]

    def is_relevant(self, threshold: int = THRESHOLD) -> bool:
        return self.score >= threshold


def _normalize(text: str) -> str:
    """Lowercase og fjern overflødig whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def score_article(article: "Article", threshold: int = THRESHOLD) -> ScoredArticle:
    """
    Beregner relevansscoren for én artikkel.
    Tittel teller dobbelt (mer signal per ord).
    """
    title_text = _normalize(article.title)
    summary_text = _normalize(article.summary)

    # Kombiner, men gi tittel dobbel vekt ved å legge den til to ganger
    combined = f"{title_text} {title_text} {summary_text}"

    total_score = 0
    matched: list[str] = []

    for group in ALL_KEYWORD_GROUPS:
        for keyword, weight in group.items():
            if keyword in combined:
                total_score += weight
                matched.append(keyword)

    # Negative justeringer
    for keyword, penalty in NEGATIVE_KEYWORDS.items():
        if keyword in combined:
            total_score += penalty  # penalty er negativ

    # Cap ved 100
    total_score = max(0, min(100, total_score))

    return ScoredArticle(
        article=article,
        score=total_score,
        matched_keywords=matched,
    )


def filter_articles(
    articles: list["Article"],
    threshold: int = THRESHOLD,
) -> list[ScoredArticle]:
    """
    Scorer og filtrerer en liste artikler.
    Returnerer kun de med score >= threshold, sortert etter score (høyest først).
    """
    scored = [score_article(a, threshold) for a in articles]
    relevant = [s for s in scored if s.is_relevant(threshold)]
    relevant.sort(key=lambda s: s.score, reverse=True)

    logger.info(
        f"Filter: {len(relevant)}/{len(articles)} artikler passerte terskelen {threshold}"
    )
    return relevant


def explain_score(scored: ScoredArticle) -> str:
    """Returnerer en menneskelig forklaring på scoren (nyttig for debugging)."""
    kw = ", ".join(scored.matched_keywords[:10])
    return (
        f"Score: {scored.score}/100 | "
        f"Nøkkelord: {kw or 'ingen'} | "
        f"Tittel: {scored.article.title[:80]}"
    )
