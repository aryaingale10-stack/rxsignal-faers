"""Client for the free NLM RxNav REST API, with rate limiting, retries and an on-disk cache.

Layer 2 (exact):        /rxcui.json?name=...&search=2      (normalized string match)
Layer 3 (approximate):  /approximateTerm.json?term=...      (fuzzy match, then checked by us)
Both are mapped to the active ingredient(s) via /rxcui/{id}/properties and /related.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from urllib.parse import quote

import requests
from rapidfuzz import fuzz

from .config import APPROX_MIN_SIMILARITY, DATA_DIR, RXNAV_BASE, RXNAV_MAX_RPS

INGREDIENT_TTYS = {"IN", "MIN"}


class RateLimiter:
    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self.lock = threading.Lock()
        self.next_time = time.monotonic()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_time:
                time.sleep(self.next_time - now)
            self.next_time = max(now, self.next_time) + self.interval


class RxNormClient:
    def __init__(self, cache_path=DATA_DIR / "rxnav_cache.db"):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "rxsignal-faers (student portfolio project)"
        self.limiter = RateLimiter(RXNAV_MAX_RPS)
        self.cache = sqlite3.connect(cache_path, check_same_thread=False)
        self.cache.execute("CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, body TEXT)")
        self.cache_lock = threading.Lock()
        self.calls = 0

    # ---- low-level -------------------------------------------------------------------
    def get(self, path: str) -> dict:
        url = f"{RXNAV_BASE}{path}"
        with self.cache_lock:
            row = self.cache.execute("SELECT body FROM cache WHERE url = ?", (url,)).fetchone()
        if row:
            return json.loads(row[0])
        for attempt in range(5):
            self.limiter.wait()
            try:
                r = self.session.get(url, timeout=30)
                self.calls += 1
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                body = r.text or "{}"
                with self.cache_lock:
                    self.cache.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (url, body))
                    self.cache.commit()
                return json.loads(body)
            except (requests.RequestException, ValueError):
                time.sleep(2 ** attempt)
        return {}

    # ---- concept helpers ---------------------------------------------------------------
    def properties(self, rxcui: str) -> dict:
        return self.get(f"/rxcui/{rxcui}/properties.json").get("properties") or {}

    def ingredients(self, rxcui: str) -> list[str]:
        """Active ingredient name(s) for any RxNorm concept (brand, clinical drug, ...)."""
        props = self.properties(rxcui)
        tty = props.get("tty")
        if tty in INGREDIENT_TTYS:
            return [props.get("name", "").lower()]
        if tty == "PIN":  # precise ingredient, e.g. 'metformin hydrochloride' -> 'metformin'
            types = "IN"
        else:
            types = "MIN+IN"
        data = self.get(f"/rxcui/{rxcui}/related.json?tty={types}")
        groups = (data.get("relatedGroup") or {}).get("conceptGroup") or []
        by_tty = {g.get("tty"): g.get("conceptProperties") or [] for g in groups}
        if by_tty.get("MIN"):
            return [by_tty["MIN"][0]["name"].lower()]
        names = sorted({c["name"].lower() for c in by_tty.get("IN", [])})
        return names

    # ---- matching layers ---------------------------------------------------------------
    def exact(self, name: str) -> dict | None:
        data = self.get(f"/rxcui.json?name={quote(name)}&search=2")
        ids = (data.get("idGroup") or {}).get("rxnormId") or []
        for rxcui in ids:
            ings = self.ingredients(rxcui)
            if ings:
                return {"rxcui": rxcui, "ingredient": " / ".join(ings),
                        "matched_name": self.properties(rxcui).get("name", name)}
        return None

    def approximate(self, name: str) -> dict | None:
        data = self.get(f"/approximateTerm.json?term={quote(name)}&maxEntries=5")
        cands = (data.get("approximateGroup") or {}).get("candidate") or []
        seen = set()
        for c in cands:
            rxcui = c.get("rxcui")
            if not rxcui or rxcui in seen:
                continue
            seen.add(rxcui)
            props = self.properties(rxcui)
            cand_name = (c.get("name") or props.get("name") or "").lower()
            ings = self.ingredients(rxcui)
            if not ings:
                continue
            ingredient = " / ".join(ings)
            # The API always returns *something*; only accept it if it really resembles the input.
            similarity = max(
                fuzz.token_set_ratio(name, cand_name) if cand_name else 0,
                fuzz.token_set_ratio(name, ingredient),
                fuzz.ratio(name, cand_name) if cand_name else 0,
            )
            if similarity >= APPROX_MIN_SIMILARITY:
                return {"rxcui": rxcui, "ingredient": ingredient,
                        "matched_name": cand_name or ingredient, "similarity": round(similarity, 1)}
        return None
