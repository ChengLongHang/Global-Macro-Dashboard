"""
Single source of truth for:
  1. Which countries we cover (G20, minus the EU bloc -- it isn't a single
     lat/lng point for the globe UI; add it separately as a bloc-level
     dashboard if/when needed).
  2. Which indicators exist and their display metadata.
  3. For each country, which adapters to try, IN ORDER, per indicator type.
     The ingestion pipeline walks this list and uses the first adapter that
     returns data -- central bank first where we have a real integration,
     falling back to World Bank then IMF, so every country/indicator
     combination degrades gracefully instead of returning nothing.

This is intentionally just data (no logic) so adding a country or swapping a
source priority is a config change, not a code change.
"""

INDICATOR_TYPES = ["IR", "LTY", "CPI", "GDP", "UNEMP", "FX", "STOCK"]

INDICATOR_DISPLAY = {
    "IR": {"name": "Short-Term Policy/Yield Rate", "category": "Interest Rates"},
    "LTY": {"name": "Long-Term Yield (10Y benchmark)", "category": "Interest Rates"},
    "CPI": {"name": "Consumer Price Index / Inflation Rate", "category": "Inflation"},
    "GDP": {"name": "Real GDP Growth Rate", "category": "Economic Growth"},
    "UNEMP": {"name": "Unemployment Rate", "category": "Labor Data"},
    "FX": {"name": "Exchange Rate (vs USD)", "category": "Exchange Rates"},
    "STOCK": {"name": "Stock Market Index", "category": "Stock Market"},
}

# lat/lng are rough country centroids for the globe marker.
COUNTRIES = [
    {"id": "USA", "name": "United States", "lat": 37.09, "lng": -95.71},
    {"id": "GBR", "name": "United Kingdom", "lat": 55.37, "lng": -3.43},
    {"id": "DEU", "name": "Germany", "lat": 51.16, "lng": 10.45},
    {"id": "JPN", "name": "Japan", "lat": 36.20, "lng": 138.25},
    {"id": "CHN", "name": "China", "lat": 35.86, "lng": 104.19},
    {"id": "IND", "name": "India", "lat": 20.59, "lng": 78.96},
    {"id": "BRA", "name": "Brazil", "lat": -14.23, "lng": -51.92},
    {"id": "CAN", "name": "Canada", "lat": 56.13, "lng": -106.34},
    {"id": "AUS", "name": "Australia", "lat": -25.27, "lng": 133.77},
    {"id": "FRA", "name": "France", "lat": 46.60, "lng": 2.21},
    {"id": "ITA", "name": "Italy", "lat": 41.87, "lng": 12.57},
    {"id": "ESP", "name": "Spain", "lat": 40.46, "lng": -3.75},  # not G20, kept from original build
    {"id": "MEX", "name": "Mexico", "lat": 23.63, "lng": -102.55},
    {"id": "KOR", "name": "South Korea", "lat": 35.90, "lng": 127.77},
    {"id": "RUS", "name": "Russia", "lat": 61.52, "lng": 105.32},
    {"id": "SAU", "name": "Saudi Arabia", "lat": 23.89, "lng": 45.08},
    {"id": "ZAF", "name": "South Africa", "lat": -30.56, "lng": 22.94},
    {"id": "TUR", "name": "Turkey", "lat": 38.96, "lng": 35.24},
    {"id": "IDN", "name": "Indonesia", "lat": -0.79, "lng": 113.92},
    {"id": "ARG", "name": "Argentina", "lat": -38.42, "lng": -63.62},
]

COUNTRY_IDS = {c["id"] for c in COUNTRIES}

# Default chain used for any country/indicator not explicitly overridden
# below. World Bank first (annual, but the widest, most reliable coverage
# across all 20 countries with no key), IMF second (adds monthly CPI where
# World Bank is annual-only).
_DEFAULT_MACRO_CHAIN = ["worldbank", "imf"]

# Per-country override of source priority, by indicator type. Only listed
# where a direct central-bank (or FRED-for-US) integration exists; anything
# not listed here falls through to _DEFAULT_MACRO_CHAIN, and FX/STOCK always
# resolve via yfinance regardless of country.
SOURCE_CHAINS: dict[str, dict[str, list[str]]] = {
    "USA": {"IR": ["fred"], "LTY": ["fred"], "CPI": ["fred"], "GDP": ["fred"], "UNEMP": ["fred"]},
    "DEU": {"IR": ["ecb"], "LTY": ["ecb"], "CPI": ["ecb", "worldbank", "imf"], "GDP": ["ecb", "worldbank", "imf"], "UNEMP": ["ecb", "worldbank", "imf"]},
    "FRA": {"IR": ["ecb"], "LTY": ["ecb"], "CPI": ["ecb", "worldbank", "imf"], "GDP": ["ecb", "worldbank", "imf"], "UNEMP": ["ecb", "worldbank", "imf"]},
    "ITA": {"IR": ["ecb"], "LTY": ["ecb"], "CPI": ["ecb", "worldbank", "imf"], "GDP": ["ecb", "worldbank", "imf"], "UNEMP": ["ecb", "worldbank", "imf"]},
    "ESP": {"IR": ["ecb"], "LTY": ["ecb"], "CPI": ["ecb", "worldbank", "imf"], "GDP": ["ecb", "worldbank", "imf"], "UNEMP": ["ecb", "worldbank", "imf"]},
    "CAN": {"IR": ["boc"], "LTY": ["boc"], "CPI": ["boc", "worldbank", "imf"]},
    "BRA": {"IR": ["bcb"], "LTY": ["bcb", "worldbank", "imf"], "CPI": ["bcb", "worldbank", "imf"], "GDP": ["bcb", "worldbank", "imf"], "UNEMP": ["bcb", "worldbank", "imf"]},
    "MEX": {"IR": ["banxico"], "CPI": ["banxico", "worldbank", "imf"]},
    "KOR": {"IR": ["ecos"], "CPI": ["ecos", "worldbank", "imf"], "UNEMP": ["ecos", "worldbank", "imf"], "GDP": ["ecos", "worldbank", "imf"]},
    "TUR": {"IR": ["evds"], "CPI": ["evds", "worldbank", "imf"], "UNEMP": ["evds", "worldbank", "imf"]},
    # GBR, JPN, AUS, ZAF: no clean modern REST API for the central bank in
    # this build (BoE/BoJ/RBA/SARB publish CSV/XLS or no public API at all).
    # They intentionally fall through to World Bank/IMF for now; a scraper
    # adapter per bank would be the next step if this coverage isn't enough.
    # CHN, IND, IDN, RUS, SAU, ARG: no reliable public central-bank API;
    # World Bank/IMF is the realistic ceiling for these without scraping.
}


def get_source_chain(country_id: str, indicator_type: str) -> list[str]:
    if indicator_type in ("FX", "STOCK"):
        return ["yfinance"]
    return SOURCE_CHAINS.get(country_id, {}).get(indicator_type, _DEFAULT_MACRO_CHAIN)


def series_key(country_id: str, indicator_type: str) -> str:
    return f"{indicator_type}_{country_id}"


def all_series() -> list[dict]:
    """Every (country, indicator) combination we track, with display metadata."""
    out = []
    for country in COUNTRIES:
        for indicator_type in INDICATOR_TYPES:
            display = INDICATOR_DISPLAY[indicator_type]
            out.append(
                {
                    "series_key": series_key(country["id"], indicator_type),
                    "country_id": country["id"],
                    "indicator_type": indicator_type,
                    "name": display["name"],
                    "category": display["category"],
                }
            )
    return out


def get_indicators_for_country(country_id: str) -> list[dict]:
    return [
        {
            "id": s["series_key"],
            "name": s["name"],
            "category": s["category"],
            "source": "/".join(get_source_chain(country_id, s["indicator_type"])),
        }
        for s in all_series()
        if s["country_id"] == country_id
    ]
