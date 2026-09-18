"""
models.py
Country dataclass shared across all modules.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class Country:
    name: str
    official_name: str
    capital: str
    region: str
    subregion: str
    population: int
    languages: list
    currencies: list
    timezones: list
    flag_url: str
    flag_emoji: str
    area: float
    calling_code: str
    tld: list
    iso2: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_cnow(cls, base: dict, extra: dict = None) -> "Country":
        extra = extra or {}
        name = base.get("name", "Unknown")
        capital = base.get("capital", "N/A") or "N/A"
        region = base.get("region", "N/A") or "N/A"
        iso2 = base.get("iso2", "")

        curr_raw = base.get("currency", None)
        if isinstance(curr_raw, dict):
            curr_name = curr_raw.get("name", "") or ""
            curr_symbol = curr_raw.get("symbol", "") or ""
            currencies = [f"{curr_name} ({curr_symbol})".strip()] if curr_name else ["N/A"]
        elif isinstance(curr_raw, str) and curr_raw:
            currencies = [curr_raw]
        else:
            currencies = ["N/A"]

        flag_emoji = base.get("unicodeFlag", "🏳") or "🏳"
        dial = base.get("dialCode", "") or ""
        calling_code = dial if dial.startswith("+") else ("+" + dial if dial else "N/A")

        population = extra.get("population", 0)
        timezones = extra.get("timezones", [])
        flag_url = extra.get("flag_url", "")
        languages = extra.get("languages", [])
        area = extra.get("area", 0.0)
        subregion = extra.get("subregion", "")
        tld = extra.get("tld", [f".{iso2.lower()}"] if iso2 else [])

        return cls(
            name=name, official_name=name, capital=capital,
            region=region, subregion=subregion, population=population,
            languages=languages, currencies=currencies, timezones=timezones,
            flag_url=flag_url, flag_emoji=flag_emoji, area=area,
            calling_code=calling_code, tld=tld, iso2=iso2, raw=base
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d
