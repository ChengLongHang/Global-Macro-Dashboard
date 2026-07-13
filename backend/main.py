from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import json

load_dotenv()

app = FastAPI(title="Macro Globe API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRED_API_KEY = os.getenv("FRED_API_KEY")
CACHE = {}

@app.get("/")
def root():
    return {"message": "Macro Globe API is running!"}

@app.get("/api/countries")
def get_countries():
    countries = [
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
        {"id": "ESP", "name": "Spain", "lat": 40.46, "lng": -3.75},
        {"id": "MEX", "name": "Mexico", "lat": 23.63, "lng": -102.55},
        {"id": "KOR", "name": "South Korea", "lat": 35.90, "lng": 127.77},
    ]
    return countries

@app.get("/api/indicators")
def get_indicators():
    indicators = [
        {"id": "FEDFUNDS", "name": "Interest Rate (Fed Funds)", "category": "Interest Rates"},
        {"id": "DGS10", "name": "10-Year Treasury Yield", "category": "Interest Rates"},
        {"id": "DGS2", "name": "2-Year Treasury Yield", "category": "Interest Rates"},
        {"id": "PAYEMS", "name": "Total Nonfarm Employment", "category": "Labor Data"},
        {"id": "UNRATE", "name": "Unemployment Rate", "category": "Labor Data"},
        {"id": "AHEMAN", "name": "Average Hourly Earnings", "category": "Labor Data"},
        {"id": "SP500", "name": "S&P 500 Index", "category": "Stock Market"},
        {"id": "GDPC1", "name": "Real Gross Domestic Product", "category": "Economic Growth"},  # ← CHANGED from "GDP"
        {"id": "CPIAUCSL", "name": "Consumer Price Index (CPI)", "category": "Inflation"},
        {"id": "GS10", "name": "10-Year Treasury Constant Maturity", "category": "Interest Rates"},
        {"id": "PPIACO", "name": "Producer Price Index", "category": "Inflation"},
        {"id": "HOUST", "name": "Housing Starts", "category": "Housing"},
        {"id": "EXUSEU", "name": "USD/EUR Exchange Rate", "category": "Exchange Rates"},
    ]
    return indicators

@app.get("/api/theme_indicators")
def get_theme_indicators(theme: str):
    theme_map = {
        "Labor Data": ["PAYEMS", "UNRATE", "AHEMAN"],
        "Interest Rates": ["FEDFUNDS", "DGS10", "DGS2"],
        "Stock Market": ["SP500"],
        "Inflation": ["CPIAUCSL", "PPIACO"],
        "Economic Growth": ["GDPC1"],  # ← CHANGED from "GDP"
        "Housing": ["HOUST"],
        "Exchange Rates": ["EXUSEU"]
    }
    return theme_map.get(theme, [])

@app.get("/api/data")
def fetch_fred_data(
    series_id: str = Query(..., description="FRED series ID"),
    start_date: str = Query("2019-01-01", description="Start date YYYY-MM-DD"),
    end_date: str = Query(None, description="End date YYYY-MM-DD"),
):
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    cache_key = f"{series_id}_{start_date}_{end_date}"
    if cache_key in CACHE:
        return CACHE[cache_key]
    
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date,
        "frequency": "m",
        "sort_order": "asc"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Check if there's an error message from FRED
        if "error" in data:
            return JSONResponse(
                status_code=400,
                content={"error": data["error"]["message"]}
            )
        
        observations = data.get("observations", [])
        
        if not observations:
            return []
        
        df = pd.DataFrame(observations)
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        df = df.sort_values("date")
        
        if df.empty:
            return []
        
        result = df[["date", "value"]].to_dict(orient="records")
        
        for item in result:
            item["date"] = item["date"].strftime("%Y-%m-%d")
        
        CACHE[cache_key] = result
        return result
    
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Network error: {str(e)}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"}
        )

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)