from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import hashlib
import json
from pathlib import Path

# Try to import imfp
try:
    import imfp
    IMF_AVAILABLE = True
    print("✅ imfp package loaded successfully")
except ImportError:
    IMF_AVAILABLE = False
    print("⚠️ imfp package not available - please install: pip install imfp")

# Try to import joblib for persistent caching
try:
    import joblib
    JOBLIB_AVAILABLE = True
    print("✅ joblib package loaded successfully")
except ImportError:
    JOBLIB_AVAILABLE = False
    print("⚠️ joblib package not available - please install: pip install joblib")

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Macro Globe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRED_API_KEY = os.getenv("FRED_API_KEY")

# ============================================
# PERSISTENT CACHE CONFIGURATION
# ============================================

# Create cache directory if it doesn't exist
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Cache expiration time (in seconds)
CACHE_EXPIRY = {
    "fred": 86400 * 7,      # 7 days for FRED data
    "imf": 86400 * 7,       # 7 days for IMF data
    "imfp": 86400 * 7,      # 7 days for imfp data
    "yfinance": 86400,      # 1 day for stock data
    "fx": 86400,            # 1 day for FX data
}

class PersistentCache:
    """Persistent cache using joblib for disk-based storage"""
    
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.memory_cache = {}  # In-memory cache for super-fast access
    
    def _get_cache_key(self, prefix, *args, **kwargs):
        """Generate a unique cache key based on the arguments"""
        # Create a string representation of all arguments
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        key_parts.extend([f"{k}_{v}" for k, v in sorted(kwargs.items())])
        key_string = "_".join(key_parts)
        # Create a hash for the filename
        hash_obj = hashlib.md5(key_string.encode())
        return hash_obj.hexdigest()
    
    def _get_cache_path(self, cache_key):
        """Get the file path for a cache key"""
        return self.cache_dir / f"{cache_key}.joblib"
    
    def get(self, prefix, *args, **kwargs):
        """Get data from cache"""
        cache_key = self._get_cache_key(prefix, *args, **kwargs)
        
        # Check memory cache first
        if cache_key in self.memory_cache:
            logger.info(f"Cache: Memory hit for {prefix}")
            return self.memory_cache[cache_key]
        
        # Check disk cache
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                # Check if cache is expired
                expiry_file = cache_path.with_suffix('.expiry')
                if expiry_file.exists():
                    with open(expiry_file, 'r') as f:
                        expiry_time = float(f.read())
                    if datetime.now().timestamp() < expiry_time:
                        data = joblib.load(cache_path)
                        # Store in memory cache for faster access
                        self.memory_cache[cache_key] = data
                        logger.info(f"Cache: Disk hit for {prefix}")
                        return data
                    else:
                        logger.info(f"Cache: Expired for {prefix}")
                        return None
                else:
                    # No expiry file, treat as expired
                    logger.info(f"Cache: No expiry file for {prefix}")
                    return None
            except Exception as e:
                logger.error(f"Cache: Error loading {prefix}: {str(e)}")
                return None
        
        logger.info(f"Cache: Miss for {prefix}")
        return None
    
    def set(self, prefix, data, expiry_seconds, *args, **kwargs):
        """Store data in cache"""
        cache_key = self._get_cache_key(prefix, *args, **kwargs)
        
        try:
            # Store in memory cache
            self.memory_cache[cache_key] = data
            
            # Store on disk
            cache_path = self._get_cache_path(cache_key)
            joblib.dump(data, cache_path)
            
            # Store expiry time
            expiry_file = cache_path.with_suffix('.expiry')
            expiry_time = datetime.now().timestamp() + expiry_seconds
            with open(expiry_file, 'w') as f:
                f.write(str(expiry_time))
            
            logger.info(f"Cache: Stored {prefix} ({len(data)} items)")
            return True
        except Exception as e:
            logger.error(f"Cache: Error storing {prefix}: {str(e)}")
            return False
    
    def clear(self, prefix=None):
        """Clear cache entries"""
        if prefix:
            # Clear specific prefix
            for file in self.cache_dir.glob(f"{prefix}*"):
                file.unlink()
            # Clear from memory cache
            keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                del self.memory_cache[k]
            logger.info(f"Cache: Cleared {prefix}")
        else:
            # Clear all
            for file in self.cache_dir.glob("*"):
                file.unlink()
            self.memory_cache.clear()
            logger.info("Cache: Cleared all")
    
    def get_stats(self):
        """Get cache statistics"""
        files = list(self.cache_dir.glob("*.joblib"))
        expiry_files = list(self.cache_dir.glob("*.expiry"))
        return {
            "total_files": len(files),
            "total_expiry_files": len(expiry_files),
            "memory_cache_size": len(self.memory_cache),
            "cache_dir": str(self.cache_dir)
        }

# Initialize persistent cache
persistent_cache = PersistentCache()

# ============================================
# COUNTRY CONFIGURATION
# ============================================

COUNTRIES = [
    {"id": "USA", "name": "United States", "lat": 37.09, "lng": -95.71, "iso3": "USA", "yfinance": "^GSPC"},
    {"id": "GBR", "name": "United Kingdom", "lat": 55.37, "lng": -3.43, "iso3": "GBR", "yfinance": "^FTSE"},
    {"id": "DEU", "name": "Germany", "lat": 51.16, "lng": 10.45, "iso3": "DEU", "yfinance": "^GDAXI"},
    {"id": "JPN", "name": "Japan", "lat": 36.20, "lng": 138.25, "iso3": "JPN", "yfinance": "^N225"},
    {"id": "CHN", "name": "China", "lat": 35.86, "lng": 104.19, "iso3": "CHN", "yfinance": "000001.SS"},
    {"id": "IND", "name": "India", "lat": 20.59, "lng": 78.96, "iso3": "IND", "yfinance": "^BSESN"},
    {"id": "BRA", "name": "Brazil", "lat": -14.23, "lng": -51.92, "iso3": "BRA", "yfinance": "^BVSP"},
    {"id": "CAN", "name": "Canada", "lat": 56.13, "lng": -106.34, "iso3": "CAN", "yfinance": "^GSPTSE"},
    {"id": "AUS", "name": "Australia", "lat": -25.27, "lng": 133.77, "iso3": "AUS", "yfinance": "^AXJO"},
    {"id": "FRA", "name": "France", "lat": 46.60, "lng": 2.21, "iso3": "FRA", "yfinance": "^FCHI"},
    {"id": "ITA", "name": "Italy", "lat": 41.87, "lng": 12.57, "iso3": "ITA", "yfinance": "FTMIB.MI"},
    {"id": "ESP", "name": "Spain", "lat": 40.46, "lng": -3.75, "iso3": "ESP", "yfinance": "^IBEX"},
    {"id": "MEX", "name": "Mexico", "lat": 23.63, "lng": -102.55, "iso3": "MEX", "yfinance": "^MXX"},
    {"id": "KOR", "name": "South Korea", "lat": 35.90, "lng": 127.77, "iso3": "KOR", "yfinance": "^KS11"},
]

# ============================================
# INDICATOR DEFINITIONS
# ============================================

def get_indicators_for_country(country_id):
    indicators = []

    if country_id == "USA":
        indicators.extend([
            {"id": "IR_USA", "name": "Short-Term Yield (2Y Treasury)", "category": "Interest Rates", "source": "FRED"},
            {"id": "LTY_USA", "name": "Long-Term Yield (10Y Treasury)", "category": "Interest Rates", "source": "FRED"},
            {"id": "CPI_USA", "name": "Consumer Price Index (CPI)", "category": "Inflation", "source": "FRED"},
            {"id": "GDP_USA", "name": "Real Gross Domestic Product", "category": "Economic Growth", "source": "FRED"},
            {"id": "UNEMP_USA", "name": "Unemployment Rate", "category": "Labor Data", "source": "FRED"},
            {"id": "FX_USA", "name": "Exchange Rate (USD/EUR)", "category": "Exchange Rates", "source": "YFinance"},
        ])
    else:
        indicators.extend([
            {"id": f"IR_{country_id}", "name": "Short-Term Yield (2Y Treasury)", "category": "Interest Rates", "source": "FRED"},
            {"id": f"LTY_{country_id}", "name": "Long-Term Yield (10Y Treasury)", "category": "Interest Rates", "source": "FRED"},
            {"id": f"CPI_{country_id}", "name": "Consumer Price Index (CPI)", "category": "Inflation", "source": "IMF"},
            {"id": f"GDP_{country_id}", "name": "Real GDP Growth Rate", "category": "Economic Growth", "source": "IMF"},
            {"id": f"UNEMP_{country_id}", "name": "Unemployment Rate", "category": "Labor Data", "source": "IMF"},
            {"id": f"FX_{country_id}", "name": "Exchange Rate (vs USD)", "category": "Exchange Rates", "source": "YFinance"},
        ])

    country = next((c for c in COUNTRIES if c["id"] == country_id), None)
    if country and country.get("yfinance"):
        indicators.append({
            "id": f"STOCK_{country_id}",
            "name": "Stock Market Index",
            "category": "Stock Market",
            "source": "YFinance"
        })

    return indicators

# ============================================
# FX TICKER MAPPING (for YFinance)
# ============================================

def get_fx_ticker(country_id):
    """Get Yahoo Finance ticker for exchange rates"""
    fx_map = {
        "USA": "EURUSD=X",
        "GBR": "GBPUSD=X",
        "DEU": "EURUSD=X",
        "FRA": "EURUSD=X",
        "ITA": "EURUSD=X",
        "ESP": "EURUSD=X",
        "MEX": "MXNUSD=X",
        "CAN": "CADUSD=X",
        "AUS": "AUDUSD=X",
        "JPN": "JPY=X",
        "CHN": "CNY=X",
        "IND": "INRUSD=X",
        "BRA": "BRLUSD=X",
        "KOR": "KRW=X",
    }
    return fx_map.get(country_id)

# ============================================
# DATA FETCHING FUNCTIONS
# ============================================

# ---------- FRED API (USA) ----------
def fetch_fred_data(series_id, start_date, end_date):
    """Fetch data from FRED API with persistent caching"""
    
    # Check cache first
    cached_data = persistent_cache.get("fred", series_id, start_date, end_date)
    if cached_data is not None:
        return cached_data
    
    if not series_id:
        return []

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
        "sort_order": "asc",
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        df = pd.DataFrame(obs)
        if df.empty:
            return []

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
        df = df.dropna(subset=["date", "value"]).sort_values("date")

        result = [
            {"date": row.date.strftime("%Y-%m-%d"), "value": float(row.value)} 
            for row in df.itertuples(index=False)
        ]
        
        # Store in cache
        persistent_cache.set("fred", result, CACHE_EXPIRY["fred"], series_id, start_date, end_date)
        
        logger.info(f"FRED: Retrieved {len(result)} data points for {series_id}")
        return result

    except Exception as e:
        logger.error(f"FRED Error for {series_id}: {str(e)}")
        return []

# ---------- IMF API using imfp ----------
def fetch_imf_data_imfp(indicator_type, country_id, start_date, end_date):
    """
    Fetch IMF data using the imfp package with persistent caching.
    Supports: CPI, GDP (Real GDP Growth Rate), UNEMP (Unemployment Rate)
    """
    
    # Check cache first
    cached_data = persistent_cache.get("imfp", indicator_type, country_id, start_date, end_date)
    if cached_data is not None:
        return cached_data

    if not IMF_AVAILABLE:
        logger.error("imfp package not available")
        return []

    # Get country ISO3 code
    country = next((c for c in COUNTRIES if c["id"] == country_id), None)
    if not country:
        logger.warning(f"Country not found: {country_id}")
        return []
    
    iso3 = country["iso3"]
    
    # Map indicator_type to imfp parameters based on your verified test code
    indicator_map = {
        "CPI": {
            "database_id": "CPI",
            "index_type": ["CPI"],
            "coicop_1999": ["_T"],
            "type_of_transformation": ["IX"],
            "frequency": ["M"],
        },
        "GDP": {
            "database_id": "WEO",
            "indicator": ["NGDP_RPCH"],  # Real GDP Growth Rate
            "frequency": ["A"],          # Annual frequency
        },
        "UNEMP": {
            "database_id": "LS",
            "indicator": ["U"],          # Unemployment rate
            "type_of_transformation": ["PT"],
            "frequency": ["M"],
        }
    }
    
    params = indicator_map.get(indicator_type)
    if not params:
        logger.warning(f"Unknown indicator type: {indicator_type}")
        return []
    
    try:
        # Prepare query parameters
        query_params = {
            "country": [iso3],
            "start_year": int(start_date[:4]),
        }
        
        # Add indicator-specific parameters
        query_params.update(params)
        
        logger.info(f"IMF imfp: Fetching {indicator_type} for {iso3}")
        
        # Make the request using imfp
        df = imfp.imf_dataset(**query_params)
        
        if df is None or df.empty:
            logger.warning(f"IMF imfp: No data returned for {indicator_type} in {iso3}")
            return []
        
        # Process the DataFrame
        if 'time_period' not in df.columns or 'obs_value' not in df.columns:
            logger.warning(f"IMF imfp: Unexpected columns: {df.columns.tolist()}")
            return []
        
        # Convert time_period to datetime
        df['time_period'] = df['time_period'].astype(str)
        df['time_period'] = df['time_period'].str.replace('-M', '-')
        df['time_period'] = pd.to_datetime(df['time_period'], errors='coerce')
        
        # Drop rows with invalid dates
        df = df.dropna(subset=['time_period'])
        
        # Convert obs_value to numeric
        df['obs_value'] = pd.to_numeric(df['obs_value'], errors='coerce')
        df = df.dropna(subset=['obs_value'])
        
        # Filter by date range
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df['time_period'] >= start_dt) & (df['time_period'] <= end_dt)]
        
        # Sort by date
        df = df.sort_values('time_period')
        
        # Convert to required format
        result = [
            {"date": row['time_period'].strftime("%Y-%m-%d"), "value": float(row['obs_value'])}
            for _, row in df.iterrows()
        ]
        
        if result:
            # Store in cache
            persistent_cache.set("imfp", result, CACHE_EXPIRY["imfp"], indicator_type, country_id, start_date, end_date)
            logger.info(f"IMF imfp: Retrieved {len(result)} data points for {indicator_type} in {iso3}")
        else:
            logger.warning(f"IMF imfp: No data after filtering for {indicator_type} in {iso3}")
        
        return result
        
    except Exception as e:
        logger.error(f"IMF imfp Error for {indicator_type} ({iso3}): {str(e)}")
        return []

# ---------- Fallback: IMF Direct API ----------
def fetch_imf_data_direct(indicator_type, country_id, start_date, end_date):
    """Fallback: Direct IMF API call using REST with persistent caching"""
    
    # Check cache first
    cached_data = persistent_cache.get("imf_direct", indicator_type, country_id, start_date, end_date)
    if cached_data is not None:
        return cached_data

    country = next((c for c in COUNTRIES if c["id"] == country_id), None)
    if not country:
        return []

    iso3 = country["iso3"]

    # Use the same mappings as before for fallback
    imf_map = {
        "CPI": {"dataset": "CPI", "series": f"{iso3}.PCPI_IX"},
        "GDP": {"dataset": "WEO", "series": f"{iso3}.NGDP_RPCH"},
        "UNEMP": {"dataset": "LS", "series": f"{iso3}.LUR"},
    }

    mapping = imf_map.get(indicator_type)
    if not mapping:
        return []

    base_url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData"
    url = f"{base_url}/{mapping['dataset']}/{mapping['series']}"
    params = {"startPeriod": start_date, "endPeriod": end_date}
    
    try:
        logger.info(f"IMF Direct: Fetching from {url}")
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        # Parse the response
        result = []
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        compact = data.get("CompactData", {})
        dataset = compact.get("DataSet", {})
        series = dataset.get("Series", [])

        if isinstance(series, dict):
            series = [series]

        for s in series:
            obs = s.get("Obs", [])
            if isinstance(obs, dict):
                obs = [obs]

            for o in obs:
                time = o.get("TIME_PERIOD")
                value = o.get("OBS_VALUE")
                if time is None or value is None:
                    continue
                dt = pd.to_datetime(time, errors="coerce")
                val = pd.to_numeric(value, errors="coerce")
                if pd.notna(dt) and pd.notna(val) and start_dt <= dt <= end_dt:
                    result.append({"date": dt.strftime("%Y-%m-%d"), "value": float(val)})
        
        if result:
            # Store in cache
            persistent_cache.set("imf_direct", result, CACHE_EXPIRY["imf"], indicator_type, country_id, start_date, end_date)
            logger.info(f"IMF Direct: Retrieved {len(result)} data points for {indicator_type} in {iso3}")
        return result
        
    except Exception as e:
        logger.error(f"IMF Direct Error for {indicator_type} ({iso3}): {str(e)}")
        return []

def fetch_imf_data(indicator_type, country_id, start_date, end_date):
    """
    Main IMF data fetcher - tries imfp first, falls back to direct API
    """
    # Try imfp first
    result = fetch_imf_data_imfp(indicator_type, country_id, start_date, end_date)
    
    # If imfp returns data, use it
    if result and len(result) > 0:
        return result
    
    # Otherwise try direct API
    logger.info(f"IMF: imfp returned no data, trying direct API for {indicator_type} in {country_id}")
    return fetch_imf_data_direct(indicator_type, country_id, start_date, end_date)

# ---------- YAHOO FINANCE ----------
def fetch_yfinance_data(ticker, start_date, end_date):
    """Fetch stock market or FX data from Yahoo Finance with persistent caching"""
    
    # Check cache first
    cached_data = persistent_cache.get("yfinance", ticker, start_date, end_date)
    if cached_data is not None:
        return cached_data

    if not ticker:
        return []

    try:
        df = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=False,
        )

        if df is None or df.empty:
            return []

        if isinstance(df.columns, pd.MultiIndex):
            if ("Close", ticker) in df.columns:
                close = df[("Close", ticker)]
            elif "Close" in df.columns.get_level_values(0):
                close = df.xs("Close", axis=1, level=0)
                close = close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
            else:
                return []
        else:
            if "Close" not in df.columns:
                return []
            close = df["Close"]

        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        close = pd.to_numeric(close, errors="coerce").dropna()
        result = [
            {"date": idx.strftime("%Y-%m-%d"), "value": float(val)} 
            for idx, val in close.items() 
            if pd.notna(val)
        ]
        
        # Determine expiry based on ticker type
        if "=X" in ticker:
            expiry = CACHE_EXPIRY["fx"]
        else:
            expiry = CACHE_EXPIRY["yfinance"]
        
        # Store in cache
        persistent_cache.set("yfinance", result, expiry, ticker, start_date, end_date)
        
        logger.info(f"YFinance: Retrieved {len(result)} data points for {ticker}")
        return result

    except Exception as e:
        logger.error(f"YFinance Error for {ticker}: {str(e)}")
        return []

# ============================================
# MAIN ROUTER FUNCTION
# ============================================

def fetch_data_from_source(country_id, indicator_type, start_date, end_date):
    """
    Main router function that directs data requests to the appropriate source
    """
    logger.info(f"ROUTER: Fetching {indicator_type} for {country_id} from {start_date} to {end_date}")

    # ---------- Interest Rates (USA only via FRED) ----------
    if indicator_type == "IR":
        return fetch_fred_data("DGS2", start_date, end_date)

    if indicator_type == "LTY":
        return fetch_fred_data("DGS10", start_date, end_date)

    # ---------- Exchange Rates (YFinance for all countries) ----------
    if indicator_type == "FX":
        ticker = get_fx_ticker(country_id)
        if ticker:
            return fetch_yfinance_data(ticker, start_date, end_date)
        return []

    # ---------- USA - FRED ----------
    if country_id == "USA":
        fred_map = {
            "CPI": "CPIAUCSL",
            "GDP": "GDPC1",
            "UNEMP": "UNRATE",
        }
        series_id = fred_map.get(indicator_type)
        if series_id:
            return fetch_fred_data(series_id, start_date, end_date)
        return []

    # ---------- Non-USA - IMF ----------
    return fetch_imf_data(indicator_type, country_id, start_date, end_date)

# ============================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================

@app.get("/api/cache/stats")
def get_cache_stats():
    """Get cache statistics"""
    stats = persistent_cache.get_stats()
    return {
        "status": "success",
        "cache_stats": stats,
        "expiry_settings": CACHE_EXPIRY
    }

@app.delete("/api/cache/clear")
def clear_cache(prefix: str = Query(None, description="Optional prefix to clear (fred, imfp, yfinance, etc.)")):
    """Clear cache entries"""
    if prefix:
        persistent_cache.clear(prefix)
        return {"status": "success", "message": f"Cache cleared for prefix: {prefix}"}
    else:
        persistent_cache.clear()
        return {"status": "success", "message": "All cache cleared"}

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
def root():
    return {"message": "Macro Globe API is running!"}

@app.get("/api/countries")
def get_countries():
    return COUNTRIES

@app.get("/api/indicators/{country_id}")
def get_country_indicators(country_id: str):
    return get_indicators_for_country(country_id)

@app.get("/api/theme_indicators/{country_id}")
def get_theme_indicators(country_id: str, theme: str):
    all_indicators = get_indicators_for_country(country_id)
    return [ind for ind in all_indicators if ind["category"] == theme]

@app.get("/api/data")
def fetch_data(
    series_id: str = Query(..., description="Indicator series ID"),
    country_id: str = Query(..., description="Country ID"),
    start_date: str = Query("2019-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query(None, description="End date YYYY-MM-DD"),
):
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"API Request: series_id={series_id}, country_id={country_id}")

    # ---------- Stock Market Data (YFinance) ----------
    if series_id.startswith("STOCK_"):
        country = next((c for c in COUNTRIES if c["id"] == country_id), None)
        if country and country.get("yfinance"):
            result = fetch_yfinance_data(country["yfinance"], start_date, end_date)
            if result:
                return result
        return JSONResponse(
            status_code=404,
            content={"error": f"No stock data available for {country_id}"}
        )

    # ---------- Parse Indicator Type ----------
    parts = series_id.split("_")
    if len(parts) == 2:
        indicator_type = parts[0]

        # Handle special cases
        if indicator_type == "IR":
            result = fetch_fred_data("DGS2", start_date, end_date)
        elif indicator_type == "LTY":
            result = fetch_fred_data("DGS10", start_date, end_date)
        elif indicator_type == "FX":
            ticker = get_fx_ticker(country_id)
            result = fetch_yfinance_data(ticker, start_date, end_date) if ticker else []
        elif country_id == "USA":
            fred_map = {
                "CPI": "CPIAUCSL",
                "GDP": "GDPC1",
                "UNEMP": "UNRATE",
            }
            series = fred_map.get(indicator_type)
            result = fetch_fred_data(series, start_date, end_date) if series else []
        else:
            result = fetch_imf_data(indicator_type, country_id, start_date, end_date)

        if result and len(result) > 0:
            logger.info(f"API: Returning {len(result)} data points")
            return result

        return JSONResponse(
            status_code=404,
            content={"error": f"No data available for {indicator_type} in {country_id}"}
        )

    return JSONResponse(
        status_code=400,
        content={"error": f"Invalid series ID format: {series_id}"}
    )

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)