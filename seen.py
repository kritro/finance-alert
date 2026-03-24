"""
seen.py – Holder styr på artikler som allerede er sendt som varsel.

Bruker en JSON-fil for persistens (fungerer lokalt og på Railway med volum).
Hvis ingen persistens er tilgjengelig, faller den tilbake til in-memory (nullstilles ved restart).
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Konfigurasjon
# ──────────────────────────────────────────────

# Fil for å lagre sette URL-er
# Railway: mount et volum på /data og sett DATA_DIR=/data
# Lokalt: bruker ./data/seen.json
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
SEEN_FILE = DATA_DIR / "seen.json"

# Hvor lenge vi husker en artikkel (standard: 7 dager)
# Forhindrer at gamle, irrelevante artikler fyller opp filen
RETENTION_DAYS = int(os.getenv("SEEN_RETENTION_DAYS", "7"))


class SeenStore:
    """
    Lagrer URL-hasher for allerede-sendte artikler.
    Støtter persistent lagring (JSON-fil) og in-memory fallback.
    """

    def __init__(self, filepath: Optional[Path] = None):
        self._filepath = filepath or SEEN_FILE
        # Format: { url_hash: iso_timestamp_string }
        self._store: dict[str, str] = {}
        self._persistent = False
        self._load()

    def _load(self) -> None:
        """Laster seen-data fra fil."""
        try:
            self._filepath.parent.mkdir(parents=True, exist_ok=True)
            if self._filepath.exists():
                with open(self._filepath, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
                logger.info(
                    f"SeenStore: lastet {len(self._store)} oppføringer fra {self._filepath}"
                )
            self._persistent = True
        except PermissionError:
            logger.warning(
                f"SeenStore: ingen skrivetilgang til {self._filepath} – "
                f"bruker in-memory (nullstilles ved restart)"
            )
            self._store = {}
            self._persistent = False
        except json.JSONDecodeError:
            logger.warning(f"SeenStore: korrupt fil {self._filepath} – starter fra scratch")
            self._store = {}
            self._persistent = True

    def _save(self) -> None:
        """Lagrer seen-data til fil."""
        if not self._persistent:
            return
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._store, f, indent=2)
        except Exception as e:
            logger.error(f"SeenStore: klarte ikke lagre til {self._filepath}: {e}")

    @staticmethod
    def _hash(url: str) -> str:
        """Lager en kort, deterministisk nøkkel fra URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    def has_seen(self, url: str) -> bool:
        """Returnerer True hvis denne URL-en allerede er sendt."""
        return self._hash(url) in self._store

    def mark_seen(self, url: str) -> None:
        """Markerer en URL som sett (lagrer tidsstempel)."""
        key = self._hash(url)
        self._store[key] = datetime.utcnow().isoformat()
        self._save()

    def mark_seen_batch(self, urls: list[str]) -> None:
        """Markerer flere URL-er som sett i én operasjon."""
        now = datetime.utcnow().isoformat()
        for url in urls:
            self._store[self._hash(url)] = now
        self._save()

    def prune_old(self, days: int = RETENTION_DAYS) -> int:
        """
        Fjerner oppføringer eldre enn `days` dager.
        Returnerer antall fjernede oppføringer.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        to_remove = []

        for key, ts_str in self._store.items():
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    to_remove.append(key)
            except (ValueError, TypeError):
                to_remove.append(key)  # Korrupt tidsstempel – fjern

        for key in to_remove:
            del self._store[key]

        if to_remove:
            logger.info(f"SeenStore: fjernet {len(to_remove)} gamle oppføringer")
            self._save()

        return len(to_remove)

    def stats(self) -> dict:
        """Returnerer statistikk om lageret."""
        return {
            "total": len(self._store),
            "persistent": self._persistent,
            "filepath": str(self._filepath),
        }

    def filter_new(self, urls: list[str]) -> list[str]:
        """Returnerer kun URL-er som ikke er sett før."""
        return [url for url in urls if not self.has_seen(url)]


# Singleton – deles av hele applikasjonen
_store_instance: Optional[SeenStore] = None


def get_store() -> SeenStore:
    """Returnerer den globale SeenStore-instansen (lager den ved første kall)."""
    global _store_instance
    if _store_instance is None:
        _store_instance = SeenStore()
    return _store_instance


def reset_store() -> None:
    """Nullstiller den globale instansen (nyttig i tester)."""
    global _store_instance
    _store_instance = None
