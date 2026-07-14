"""和风天气服务（复用 QM-WX 的和风 API 模式）

城市名 → 经纬度（geo lookup）→ 实时天气 + 3d 预报。
凭据从 .env QWEATHER_KEY / QWEATHER_API_HOST（复用 QM-WX 凭据）。
无 KEY 时走 stub 兜底（旅游产品参考用，不阻塞）。
"""
import os

import httpx

QWEATHER_KEY = os.getenv("QWEATHER_KEY", "")
QWEATHER_HOST = os.getenv("QWEATHER_API_HOST", "nf5b5vtkcp.re.qweatherapi.com")
_HEADERS = {"X-QW-Api-Key": QWEATHER_KEY} if QWEATHER_KEY else {}


async def _geo_lookup(city: str) -> tuple[str, str] | None:
    """城市名 → (lon, lat)；无 KEY 或查不到返回 None"""
    if not QWEATHER_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(
                f"https://{QWEATHER_HOST}/geo/v2/city/lookup",
                params={"location": city},
                headers=_HEADERS,
            )
        data = r.json()
        if data.get("code") == "200" and data.get("location"):
            loc = data["location"][0]
            return loc["lon"], loc["lat"]
    except Exception:
        pass
    return None


async def get_weather(city: str) -> dict:
    """实时天气（城市名）"""
    ll = await _geo_lookup(city)
    if not ll:
        return {"city": city, "text": "天气服务未配置", "temperature": "", "icon": "999"}
    lon, lat = ll
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(
                f"https://{QWEATHER_HOST}/v7/weather/now",
                params={"location": f"{lon},{lat}"},
                headers=_HEADERS,
            )
        now = r.json().get("now", {})
        return {
            "city": city,
            "text": now.get("text", ""),
            "temperature": now.get("temp", ""),
            "feelsLike": now.get("feelsLike", ""),
            "humidity": now.get("humidity", ""),
            "icon": now.get("icon", "999"),
            "windDir": now.get("windDir", ""),
            "windScale": now.get("windScale", ""),
        }
    except Exception:
        return {"city": city, "text": "获取失败", "temperature": "", "icon": "999"}


async def get_forecast(city: str, days: int = 3) -> list:
    """3d/7d 预报（城市名）"""
    ll = await _geo_lookup(city)
    if not ll:
        return []
    lon, lat = ll
    endpoint = f"/v7/weather/{days}d"
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(
                f"https://{QWEATHER_HOST}{endpoint}",
                params={"location": f"{lon},{lat}"},
                headers=_HEADERS,
            )
        return r.json().get("daily", [])
    except Exception:
        return []
