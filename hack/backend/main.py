from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import requests
import json
from datetime import datetime
import os

app = FastAPI(title="AeroPulse AI Backend", description="Medical Air Quality Monitoring API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key for OpenWeatherMap
API_KEY = "8857f7ca2724295e25e5009a3be436f6"

# In-memory storage for user profiles (in production, use a database)
user_profiles: Dict[str, dict] = {}


# ===============================
# MODELS
# ===============================

class AirQualityRequest(BaseModel):
    lat: float
    lon: float


class UserProfile(BaseModel):
    user_id: str
    condition: str
    smoke: bool
    drink: bool
    air_data: Optional[dict] = None


class DiagnosticRequest(BaseModel):
    user_id: str
    air_data: dict
    condition: str
    smoke: bool
    drink: bool


# ===============================
# AIR QUALITY API ENDPOINTS
# ===============================

@app.get("/api/air-quality")
async def get_air_quality(lat: float = Query(...), lon: float = Query(...)):
    """Get current air quality for given coordinates"""
    try:
        url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        response = requests.get(url)
        
        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch air quality data")
        
        data = response.json()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/air-quality/history")
async def get_air_quality_history(lat: float = Query(...), lon: float = Query(...), hours: int = Query(24)):
    """Get air quality history for given coordinates"""
    try:
        end = int(datetime.now().timestamp())
        start = end - (hours * 3600)
        
        url = f"https://api.openweathermap.org/data/2.5/air_pollution/history?lat={lat}&lon={lon}&start={start}&end={end}&appid={API_KEY}"
        response = requests.get(url)
        
        if not response.ok:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch air quality history")
        
        data = response.json()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# USER PROFILE API ENDPOINTS
# ===============================

@app.post("/api/profile/save")
async def save_user_profile(profile: UserProfile):
    """Save user medical profile"""
    try:
        user_profiles[profile.user_id] = {
            "condition": profile.condition,
            "smoke": profile.smoke,
            "drink": profile.drink,
            "air_data": profile.air_data,
            "updated_at": datetime.now().isoformat()
        }
        return {"status": "success", "message": "Profile saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Get user medical profile"""
    if user_id not in user_profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    return user_profiles[user_id]


# ===============================
# DIAGNOSTIC API ENDPOINTS
# ===============================

@app.post("/api/diagnostic/run")
async def run_diagnostic(request: DiagnosticRequest):
    """Run AI diagnostic based on air quality and user profile"""
    try:
        air = request.air_data
        
        # Extract AQI and pollutant values
        aqi = air.get("main", {}).get("aqi", 1)
        components = air.get("components", {})
        
        pm25 = components.get("pm2_5", 0)
        no2 = components.get("no2", 0)
        so2 = components.get("so2", 0)
        co = components.get("co", 0)
        
        # Calculate base score based on condition
        condition_multipliers = {
            "Healthy": 1.0,
            "Asthma": 2.5,
            "COPD": 4.0
        }
        
        multiplier = condition_multipliers.get(request.condition, 1.0)
        score = aqi * multiplier
        
        # Add lifestyle factors
        if request.smoke:
            score += 80
        if request.drink:
            score += 20
        
        # Determine risk level
        if score < 50:
            risk_level = "Low"
            recommendation = "Air quality is good. Maintain your healthy lifestyle."
        elif score < 100:
            risk_level = "Moderate"
            recommendation = "Air quality is moderate. Consider limiting outdoor activities if you have respiratory issues."
        elif score < 150:
            risk_level = "High"
            recommendation = "Air quality is unhealthy. Limit outdoor exposure and use protective measures."
        elif score < 200:
            risk_level = "Very High"
            recommendation = "Air quality is very unhealthy. Avoid outdoor activities."
        else:
            risk_level = "Hazardous"
            recommendation = "Air quality is hazardous. Stay indoors and use air purification."
        
        # Add condition-specific advice
        if request.condition == "Asthma":
            recommendation += " Keep your inhaler accessible."
        elif request.condition == "COPD":
            recommendation += " Monitor your oxygen levels closely."
        
        if request.smoke:
            recommendation += " Smoking significantly degrades your alveolar capacity."
        
        return {
            "score": round(score),
            "risk_level": risk_level,
            "recommendation": recommendation,
            "air_quality": {
                "aqi": aqi,
                "pm25": pm25,
                "no2": no2,
                "so2": so2,
                "co": co
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# FRONTEND SERVING
# ===============================

@app.get("/")
async def serve_index():
    """Serve the main dashboard page"""
    index_path = os.path.join(os.path.dirname(__file__), "..", "index.html.html")
    return FileResponse(index_path)


@app.get("/page2")
async def serve_page2():
    """Serve the medical profile page"""
    page2_path = os.path.join(os.path.dirname(__file__), "..", "page2.html.html")
    return FileResponse(page2_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
