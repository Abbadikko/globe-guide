"""
ai_guide.py
RelocationGuide and CountryComparator.
Uses raw HTTP requests to Gemini API instead of the google-generativeai
library — keeps the APK small and build time fast.
"""

import re
import requests
from models import Country

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)
PRIMARY_MODEL  = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


class RelocationGuide:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _call(self, prompt: str) -> str:
        """Try primary model, fall back automatically if it fails."""
        for model in (PRIMARY_MODEL, FALLBACK_MODEL):
            try:
                url = GEMINI_URL.format(model=model, key=self.api_key)
                body = {"contents": [{"parts": [{"text": prompt}]}]}
                resp = requests.post(url, json=body, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                return (
                    data["candidates"][0]["content"]["parts"][0]["text"]
                )
            except Exception as e:
                last_error = e
        raise RuntimeError(f"Gemini API error: {last_error}")

    def generate(self, country: Country, purpose: str = "relocation") -> str:
        prompt = f"""
You are an expert relocation and culture consultant.
Write a warm, informative, practical {purpose} guide for {country.name}.

Facts:
- Capital: {country.capital}
- Region: {country.region} / {country.subregion}
- Population: {country.population:,}
- Languages: {', '.join(country.languages) if country.languages else 'N/A'}
- Currencies: {', '.join(country.currencies)}
- Calling code: {country.calling_code}

Write 4 sections:
## Overview & Culture
## Living & Cost of Life
## Practical Info
## Tips for {"Relocating" if purpose == "relocation" else "Visitors"}

3-4 sentences per section. Be specific, not generic.
"""
        return self._call(prompt)

    def generate_checklist(self, country: Country, purpose: str) -> str:
        prompt = f"""
Create a practical Before You Travel checklist for someone {purpose} to {country.name}.

Context: Capital {country.capital}, Region {country.region},
Languages {', '.join(country.languages) if country.languages else 'N/A'},
Currency {', '.join(country.currencies)}.

Group into sections with emoji:
Documents & Visas, Money & Banking, Health & Safety,
Tech & Communication, Packing Essentials, Accommodation.

Be concise and country-specific.
"""
        return self._call(prompt)


class CountryComparator:
    def __init__(self, guide: RelocationGuide):
        self.guide = guide

    def compare(self, a: Country, b: Country) -> dict:
        def tz_offset(tz):
            m = re.match(r"UTC([+-])(\d{1,2})(?::(\d{2}))?", tz)
            if not m:
                return None
            sign = 1 if m.group(1) == "+" else -1
            return sign * (int(m.group(2)) + (int(m.group(3) or 0)) / 60)

        tz_a = a.timezones[0] if a.timezones else "UTC"
        tz_b = b.timezones[0] if b.timezones else "UTC"
        off_a, off_b = tz_offset(tz_a), tz_offset(tz_b)
        tz_diff = abs(off_a - off_b) if off_a is not None and off_b is not None else None

        return {
            "country_a": a.name, "country_b": b.name,
            "capital_a": a.capital, "capital_b": b.capital,
            "population_a": a.population, "population_b": b.population,
            "area_a": a.area, "area_b": b.area,
            "languages_a": a.languages, "languages_b": b.languages,
            "currencies_a": a.currencies, "currencies_b": b.currencies,
            "region_a": a.region, "region_b": b.region,
            "tz_difference_hours": tz_diff,
        }

    def ai_comparison(self, a: Country, b: Country) -> str:
        prompt = f"""
Compare {a.name} and {b.name} for someone deciding where to relocate or travel.

{a.name}: Capital {a.capital}, {a.region}, Pop {a.population:,}, Currency {', '.join(a.currencies[:1])}
{b.name}: Capital {b.capital}, {b.region}, Pop {b.population:,}, Currency {', '.join(b.currencies[:1])}

Cover: Cultural differences, Cost & lifestyle, Work/study suitability, One-sentence verdict.
Use clear sections. Be direct and insightful.
"""
        return self.guide._call(prompt)
