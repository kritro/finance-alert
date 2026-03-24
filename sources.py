"""
sources.py – Henter artikler fra RSS-feeds og Nitter (Twitter via RSS)
"""

import feedparser
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Article:
    url: str
    title: str
    summary: str
    source: str
    published: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# RSS-feeds (ingen API-nøkkel nødvendig)
# ──────────────────────────────────────────────
RSS_FEEDS = {
    # OilPrice.com – dedikert oljefeed (fungerer bra)
    "OilPrice.com": "https://oilprice.com/rss/main",

    # CNBC Energy
    "CNBC Energy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",

    # Al Jazeera (god på Midtøsten/geopolitikk)
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",

    # The Guardian – Energy
    "Guardian Energy": "https://www.theguardian.com/environment/energy/rss",

    # Middle East Eye (geopolitikk som påvirker olje)
    "Middle East Eye": "https://www.middleeasteye.net/rss",

    # CNBC Business
    "CNBC Business": "https://www.cnbc.com/id/100003114/device/rss/rss.html",

    # Yahoo Finance – Energy ETF nyheter
    "Yahoo Energy": "https://finance.yahoo.com/rss/headline?s=XLE",

    # Yahoo Finance – Brent crude nyheter
    "Yahoo Brent": "https://finance.yahoo.com/rss/headline?s=BZ=F",

    # Natural Gas Intelligence
    "NGI": "https://www.naturalgasintel.com/feed/",

    # Hellenic Shipping News (olje-shipping)
    "Hellenic Shipping": "https://www.hellenicshippingnews.com/feed/",

    # Financial Times
    "FT Energy": "https://www.ft.com/rss/home/uk",
}

# ──────────────────────────────────────────────
# Nitter RSS – Twitter/X uten API-nøkkel
# Søker på sentrale hashtags og kontoer
# Prøver flere instanser – den første som svarer brukes
# ──────────────────────────────────────────────
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]

NITTER_SEARCHES = [
    "brent crude",
    "oil price",
    "OPEC production",
    "Iran sanctions oil",
    "Hormuz strait",
    "Trump Iran oil",
    "crude oil barrel",
]

NITTER_ACCOUNTS = [
    "OilPrice_com",      # @OilPrice_com
    "RigzoneNews",       # @RigzoneNews
    "EIAgov",            # @EIAgov
    "OPECSecretariat",   # @OPECSecretariat
]


def _parse_feed(url: str, source_name: str) -> list[Article]:
    """Parser én RSS-feed og returnerer en liste med Article-objekter."""
    articles = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "oil-alert-bot/1.0"})
        if feed.bozo and not feed.entries:
            logger.warning(f"[{source_name}] Ugyldig feed: {url}")
            return []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            # Rens HTML fra summary
            import re
            summary = re.sub(r"<[^>]+>", " ", summary).strip()
            summary = re.sub(r"\s+", " ", summary)[:500]

            # Publiseringstidspunkt
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            if title and link:
                articles.append(Article(
                    url=link,
                    title=title,
                    summary=summary,
                    source=source_name,
                    published=published,
                ))

    except Exception as e:
        logger.error(f"[{source_name}] Feil ved henting av {url}: {e}")

    return articles


def _nitter_search_url(instance: str, query: str) -> str:
    """Bygger Nitter RSS-URL for et søk."""
    import urllib.parse
    q = urllib.parse.quote(query)
    return f"{instance}/search/rss?q={q}&f=tweets"


def _nitter_account_url(instance: str, account: str) -> str:
    """Bygger Nitter RSS-URL for en konto."""
    return f"{instance}/{account}/rss"


def fetch_nitter(timeout_seconds: int = 8) -> list[Article]:
    """
    Henter tweets via Nitter RSS.
    Prøver instanser i rekkefølge – bruker første som svarer.
    """
    import urllib.request
    import urllib.error

    articles = []
    working_instance = None

    # Finn en fungerende Nitter-instans
    for instance in NITTER_INSTANCES:
        try:
            req = urllib.request.Request(
                f"{instance}/search/rss?q=oil+price&f=tweets",
                headers={"User-Agent": "oil-alert-bot/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                if resp.status == 200:
                    working_instance = instance
                    logger.info(f"Nitter: bruker {instance}")
                    break
        except Exception:
            continue

    if not working_instance:
        logger.warning("Nitter: ingen instanser tilgjengelig akkurat nå")
        return []

    # Søk-feeds
    for query in NITTER_SEARCHES:
        url = _nitter_search_url(working_instance, query)
        items = _parse_feed(url, f"Twitter:{query[:20]}")
        articles.extend(items)

    # Konto-feeds
    for account in NITTER_ACCOUNTS:
        url = _nitter_account_url(working_instance, account)
        items = _parse_feed(url, f"@{account}")
        articles.extend(items)

    return articles


def fetch_all_rss() -> list[Article]:
    """Henter alle RSS-feeds parallelt."""
    import concurrent.futures

    all_articles: list[Article] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_parse_feed, url, name): name
            for name, url in RSS_FEEDS.items()
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception as e:
                logger.error(f"RSS-feil: {e}")

    return all_articles


def fetch_all(include_nitter: bool = True) -> list[Article]:
    """
    Henter fra alle kilder (RSS + valgfritt Nitter).
    Returnerer dedupliserte artikler (basert på URL).
    """
    articles = fetch_all_rss()

    if include_nitter:
        articles.extend(fetch_nitter())

    # Dedupliser på URL
    seen_urls: set[str] = set()
    unique: list[Article] = []
    for a in articles:
        if a.url not in seen_urls:
            seen_urls.add(a.url)
            unique.append(a)

    logger.info(f"Hentet {len(unique)} unike artikler fra alle kilder")
    return unique
