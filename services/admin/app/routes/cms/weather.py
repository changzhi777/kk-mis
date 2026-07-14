"""CMS 天气路由（公开，旅游产品/行程设计参考）

- GET /weather?city= 实时天气
- GET /weather/forecast?city=&days=3 预报
"""
from fastapi import APIRouter

from ...services.weather import get_forecast, get_weather

router = APIRouter(prefix="/api/v1/cms/weather", tags=["cms-weather"])


@router.get("")
async def current_weather(city: str):
    """实时天气（城市名，公开无需登录）"""
    return await get_weather(city)


@router.get("/forecast")
async def weather_forecast(city: str, days: int = 3):
    """3d/7d 预报（城市名，公开）"""
    return {"city": city, "daily": await get_forecast(city, days)}
