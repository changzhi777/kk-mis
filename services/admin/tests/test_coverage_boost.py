"""覆盖率提升测试（2026-07-16 批次5）

集中覆盖低覆盖纯函数/mock 模块：
- weather.py（19% → 90%）：_geo_lookup/get_weather/get_forecast + fail-open 各分支
- approval_engine（72% → 95%）：_parse_nodes 校验 + _check_approver_authority
- notifier（改后）：无 URL 跳过 / 成功 / 失败日志
"""
import pytest


# ── 共用 fake httpx ────────────────────────────────────────
class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeClient:
    """假 httpx.AsyncClient：按 URL 返回不同 payload（context manager + get）。"""

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        if "geo" in url:
            return _FakeResp({"code": "200", "location": [{"lon": "116.4", "lat": "39.9"}]})
        if "/now" in url:
            return _FakeResp({"now": {"text": "晴", "temp": "25", "feelsLike": "26",
                                       "humidity": "50", "icon": "100",
                                       "windDir": "东", "windScale": "2"}})
        if url.endswith("d"):  # /v7/weather/3d 或 7d
            return _FakeResp({"daily": [{"fxDate": "2026-07-16", "textDay": "晴"}]})
        return _FakeResp({})


# ── weather ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_weather_no_key_stub(monkeypatch):
    """无 QWEATHER_KEY → fail-open 返回 stub，forecast 返回空。"""
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "")
    w = await weather.get_weather("北京")
    assert w["text"] == "天气服务未配置"
    f = await weather.get_forecast("北京")
    assert f == []


@pytest.mark.asyncio
async def test_weather_geo_not_found_stub(monkeypatch):
    """有 KEY 但 geo 查不到（code != 200）→ stub。"""
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "fake")
    monkeypatch.setattr(weather, "_HEADERS", {"X-QW-Api-Key": "fake"})

    class _NoLocClient(_FakeClient):
        async def get(self, url, **kw):
            if "geo" in url:
                return _FakeResp({"code": "404"})  # 查不到城市
            return await super().get(url, **kw)

    monkeypatch.setattr(weather.httpx, "AsyncClient", _NoLocClient)
    w = await weather.get_weather("未知城市")
    assert w["text"] == "天气服务未配置"


@pytest.mark.asyncio
async def test_weather_success(monkeypatch):
    """geo 成功 + now 成功 → 返回实时天气字段。"""
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "fake")
    monkeypatch.setattr(weather, "_HEADERS", {"X-QW-Api-Key": "fake"})
    monkeypatch.setattr(weather.httpx, "AsyncClient", _FakeClient)
    w = await weather.get_weather("北京")
    assert w["text"] == "晴"
    assert w["temperature"] == "25"
    assert w["humidity"] == "50"


@pytest.mark.asyncio
async def test_forecast_success(monkeypatch):
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "fake")
    monkeypatch.setattr(weather, "_HEADERS", {"X-QW-Api-Key": "fake"})
    monkeypatch.setattr(weather.httpx, "AsyncClient", _FakeClient)
    daily = await weather.get_forecast("北京", days=3)
    assert len(daily) == 1
    assert daily[0]["fxDate"] == "2026-07-16"


@pytest.mark.asyncio
async def test_weather_api_error_fail_open(monkeypatch):
    """weather API 抛异常 → fail-open 返回'获取失败'（不阻塞）。"""
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "fake")
    monkeypatch.setattr(weather, "_HEADERS", {"X-QW-Api-Key": "fake"})

    class _ErrClient(_FakeClient):
        async def get(self, url, **kw):
            if "/now" in url:
                raise Exception("network error")
            return await super().get(url, **kw)

    monkeypatch.setattr(weather.httpx, "AsyncClient", _ErrClient)
    w = await weather.get_weather("北京")
    assert w["text"] == "获取失败"


@pytest.mark.asyncio
async def test_forecast_error_fail_open(monkeypatch):
    from app.services import weather
    monkeypatch.setattr(weather, "QWEATHER_KEY", "fake")
    monkeypatch.setattr(weather, "_HEADERS", {"X-QW-Api-Key": "fake"})

    class _ErrClient(_FakeClient):
        async def get(self, url, **kw):
            if url.endswith("d"):
                raise Exception("timeout")
            return await super().get(url, **kw)

    monkeypatch.setattr(weather.httpx, "AsyncClient", _ErrClient)
    assert await weather.get_forecast("北京") == []


# ── approval_engine ────────────────────────────────────────
class _FakeFlow:
    def __init__(self, fid, nodes_json):
        self.id = fid
        self.nodes_config = nodes_json


def test_parse_nodes_valid():
    from app.services.approval_engine import _parse_nodes
    nodes = _parse_nodes(_FakeFlow(1, '[{"approver_type":"user","approver_id":5},{"approver_type":"leader"}]'))
    assert len(nodes) == 2


def test_parse_nodes_invalid_json():
    from app.services.approval_engine import _parse_nodes
    with pytest.raises(ValueError, match="非法 JSON"):
        _parse_nodes(_FakeFlow(1, 'not-json'))


def test_parse_nodes_not_list():
    from app.services.approval_engine import _parse_nodes
    with pytest.raises(ValueError, match="非空 list"):
        _parse_nodes(_FakeFlow(1, '{"a":1}'))


def test_parse_nodes_empty_list():
    from app.services.approval_engine import _parse_nodes
    with pytest.raises(ValueError, match="非空 list"):
        _parse_nodes(_FakeFlow(1, '[]'))


def test_parse_nodes_bad_approver_type():
    from app.services.approval_engine import _parse_nodes
    with pytest.raises(ValueError, match="approver_type 非法"):
        _parse_nodes(_FakeFlow(1, '[{"approver_type":"robot"}]'))


def test_parse_nodes_node_not_dict():
    from app.services.approval_engine import _parse_nodes
    with pytest.raises(ValueError, match="非 dict"):
        _parse_nodes(_FakeFlow(1, '["str"]'))


def test_check_authority_none_node():
    from app.services.approval_engine import _check_approver_authority
    assert _check_approver_authority(None, 1) is not None  # 拒绝


def test_check_authority_unknown_type():
    from app.services.approval_engine import _check_approver_authority
    err = _check_approver_authority({"approver_type": "robot"}, 1)
    assert err is not None and "robot" in err


def test_check_authority_user_mismatch():
    from app.services.approval_engine import _check_approver_authority
    assert _check_approver_authority({"approver_type": "user", "approver_id": 5}, 9) is not None


def test_check_authority_user_match():
    from app.services.approval_engine import _check_approver_authority
    assert _check_approver_authority({"approver_type": "user", "approver_id": 5}, 5) is None


def test_check_authority_leader_pass():
    from app.services.approval_engine import _check_approver_authority
    assert _check_approver_authority({"approver_type": "leader"}, 1) is None


# ── notifier ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_notify_no_url_skips(monkeypatch):
    from app.services import notifier
    monkeypatch.setattr(notifier, "_webhook_url", lambda: "")
    await notifier.notify("test", {"a": 1})  # 无 URL 静默跳过，不抛


@pytest.mark.asyncio
async def test_notify_success(monkeypatch):
    from app.services import notifier
    monkeypatch.setattr(notifier, "_webhook_url", lambda: "http://fake/wh")

    class _OKClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kw):
            return _FakeResp({}, status=200)

    monkeypatch.setattr(notifier.httpx, "AsyncClient", _OKClient)
    await notifier.notify("evt", {"x": 1})  # 200 不抛


@pytest.mark.asyncio
async def test_notify_failure_logged(monkeypatch):
    """5xx → raise_for_status 抛 → 捕获记日志（不向上抛）。"""
    from app.services import notifier
    monkeypatch.setattr(notifier, "_webhook_url", lambda: "http://fake/wh")

    class _FailClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kw):
            return _FakeResp({}, status=500)

    monkeypatch.setattr(notifier.httpx, "AsyncClient", _FailClient)
    await notifier.notify("evt", {"x": 1})  # 失败被捕获，不抛


@pytest.mark.asyncio
async def test_notify_close_client_noop_when_none():
    """未初始化 client 时 close_client 安全（不抛）。"""
    from app.services import notifier
    notifier._CLIENT = None  # 重置
    await notifier.close_client()
