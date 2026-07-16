"""tripgen 集成测试（Step 7）

覆盖：
- pipeline 生成冒烟（HTML 4件套）
- config.trip_from_dict（JSON → Trip）
- routes /api/v1/tripgen/* 端点
- CLI 入口（init/build/html）
"""
import json
import os
import tempfile

import pytest


# ── pipeline 冒烟 ─────────────────────────────────────────────

@pytest.fixture
def sample_trip_data():
    """最小行程数据（够生成 HTML）。"""
    return {
        "title": "测试行程",
        "subtitle": "自动化测试",
        "origin": "长沙",
        "party": "一大一小",
        "dates": "7/30-8/2",
        "days": [
            {"label": "Day1", "text": "<b>出发</b>到目的地"},
            {"label": "Day2", "text": "景点游览"},
        ],
        "attractions": [{"name": "测试景点", "desc": "测试描述", "icon": "spot"}],
        "foods": [{"name": "测试美食", "desc": "推荐店", "price": "¥50", "icon": "bowl"}],
        "lodging": [{"place": "测试酒店", "rec": "推荐", "price": "¥300"}],
        "budget": [{"item": "交通", "amount": "¥500"}],
        "budget_total": "¥1000",
        "warnings": ["注意天气"],
    }


def test_trip_from_dict(sample_trip_data):
    """JSON → Trip dataclass。"""
    from app.services.tripgen.config import trip_from_dict
    trip = trip_from_dict(sample_trip_data)
    assert trip.title == "测试行程"
    assert len(trip.days) == 2
    assert trip.days[0].text == "<b>出发</b>到目的地"
    assert trip.attractions[0].name == "测试景点"
    assert trip.foods[0].icon == "bowl"


def test_pipeline_html_generation(sample_trip_data):
    """pipeline HTML 生成冒烟。"""
    from app.services.tripgen.config import trip_from_dict
    from app.services.tripgen import pipeline
    trip = trip_from_dict(sample_trip_data)
    out_dir = tempfile.mkdtemp(prefix="tripgen_test_")
    files = pipeline.generate(trip, out_dir)
    # HTML 一定有
    html_files = [f for f in files if f.endswith(".html")]
    assert len(html_files) >= 1
    assert os.path.getsize(html_files[0]) > 500  # 至少 500 bytes
    # 正文 PDF 可能有（取决于字体是否装）
    pdf_files = [f for f in files if f.endswith(".pdf")]
    # PDF 可选（无字体时跳过），不强制 assert


def test_html_render(sample_trip_data):
    """html_guide.render_html 返回 HTML 字符串。"""
    from app.services.tripgen.config import trip_from_dict
    from app.services.tripgen import html_guide
    trip = trip_from_dict(sample_trip_data)
    html = html_guide.render_html(trip)
    assert "<html" in html or "<div" in html
    assert "测试行程" in html


def test_example_config():
    """CLI EXAMPLE 常量是有效 YAML。"""
    from app.services.tripgen.cli import EXAMPLE
    import yaml
    data = yaml.safe_load(EXAMPLE)
    assert data.get("title")
    assert "days" in data


# ── API 端点 ──────────────────────────────────────────────────

def test_api_example_endpoint(client, auth_header):
    """GET /admin/api/v1/tripgen/example 返回示例 JSON。"""
    r = client.get("/admin/api/v1/tripgen/example", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "title" in data or "trip" in str(data)


def test_api_preview_endpoint(client, auth_header, sample_trip_data):
    """POST /admin/api/v1/tripgen/preview 返回 HTML。"""
    r = client.post(
        "/admin/api/v1/tripgen/preview",
        json=sample_trip_data,
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.text
    assert "测试行程" in body


def test_api_generate_endpoint(client, auth_header, sample_trip_data):
    """POST /admin/api/v1/tripgen/generate 返回文件列表。"""
    r = client.post(
        "/admin/api/v1/tripgen/generate",
        json=sample_trip_data,
        headers=auth_header,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert len(data["files"]) >= 1


def test_api_preview_no_title(client, auth_header):
    """POST preview 缺 title → 400。"""
    r = client.post(
        "/admin/api/v1/tripgen/preview",
        json={"subtitle": "无标题"},
        headers=auth_header,
    )
    assert r.status_code == 400


# ── CLI 冒烟 ──────────────────────────────────────────────────

def test_cli_init(tmp_path):
    """CLI init 写示例配置。"""
    import subprocess, sys
    config_path = str(tmp_path / "test_trip.yaml")
    result = subprocess.run(
        [sys.executable, "-m", "app.cli.tripgen", "init", config_path],
        capture_output=True, text=True,
        cwd="/Users/mac/Documents/Claude/Projects/szdhts-a/mis-system/services/admin",
        env={**os.environ, "PYTHONPATH": "."},
    )
    assert result.returncode == 0
    assert os.path.exists(config_path)
    content = open(config_path).read()
    assert "title:" in content
