"""
api_client.py
Handles all CountriesNow API requests with validation and error handling.
"""

import re
import requests
from models import Country

CNOW_BASE = "https://countriesnow.space/api/v0.1/countries"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

_cache = []  # in-memory cache for all countries


def load_all_countries() -> list:
    global _cache
    if _cache:
        return _cache
    try:
        r = requests.get(
            f"{CNOW_BASE}/info?returns=name,capital,currency,unicodeFlag,dialCode,region,iso2,iso3",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if data.get("error") is False:
            _cache = data.get("data", [])
            return _cache
        return []
    except Exception as e:
        raise ConnectionError(f"Could not load country database: {e}")


class CountryAPIClient:

    def _validate_name(self, name: str) -> str:
        name = name.strip()
        if not re.match(r"^[A-Za-z\s'\-\.]{2,60}$", name):
            raise ValueError(f"'{name}' is not a valid country name.")
        return name

    def search(self, query: str, all_countries: list) -> list:
        query = self._validate_name(query)
        q = query.lower().strip()
        matches = [c for c in all_countries if q in c.get("name", "").lower()]
        if not matches:
            raise ValueError(f"No country found for '{query}'. Check spelling.")
        results = []
        for base in matches[:5]:
            extra = self._enrich(base.get("name", ""))
            results.append(Country.from_cnow(base, extra))
        return results

    def _enrich(self, country_name: str) -> dict:
        extra = {}
        try:
            r = requests.post(
                f"{CNOW_BASE}/population",
                json={"country": country_name},
                headers=HEADERS, timeout=6
            )
            if r.ok:
                counts = r.json().get("data", {}).get("populationCounts", [])
                if counts:
                    extra["population"] = counts[-1].get("value", 0)

            r2 = requests.post(
                f"{CNOW_BASE}/flag/images",
                json={"country": country_name},
                headers=HEADERS, timeout=6
            )
            if r2.ok:
                extra["flag_url"] = r2.json().get("data", {}).get("flag", "")
        except Exception:
            pass
        return extra
