"""office/engine + tripgen config 覆盖率补充（2026-07-16 批次5）

- office/engine（11% → 50%+）：data_to_excel 真跑（openpyxl 已装）+ 错误路径 + batch copy
- tripgen config（38% → 80%+）：build_trip（json/yaml）+ route_map 映射
依赖缺失的函数（weasyprint/pptx）自动 skip。
"""
import json

import pytest


# ── office/engine ──────────────────────────────────────────
def test_data_to_excel_dict_rows(tmp_path):
    """list[dict] → xlsx（openpyxl 已装）。"""
    from app.services.office.engine import data_to_excel
    out = tmp_path / "dict.xlsx"
    data_to_excel([{"name": "张三", "age": 30}, {"name": "李四", "age": 25}], str(out))
    assert out.exists() and out.stat().st_size > 0


def test_data_to_excel_list_rows_with_headers(tmp_path):
    """list[list] + headers → xlsx。"""
    from app.services.office.engine import data_to_excel
    out = tmp_path / "list.xlsx"
    data_to_excel([["张三", 30], ["李四", 25]], str(out), headers=["姓名", "年龄"])
    assert out.exists()


def test_html_to_pdf_or_skip(tmp_path):
    """html_to_pdf（weasyprint 未装则 skip，不报错）。"""
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        pytest.skip("weasyprint 未装")
    from app.services.office.engine import html_to_pdf
    out = tmp_path / "t.pdf"
    html_to_pdf("<h1>标题</h1><p>内容</p>", str(out))
    assert out.exists()


def test_docx_to_pdf_missing_file(tmp_path):
    """docx_to_pdf 文件不存在 → OfficeEngineError。"""
    from app.services.office.engine import OfficeEngineError, docx_to_pdf
    with pytest.raises(OfficeEngineError, match="文件不存在"):
        docx_to_pdf(tmp_path / "nope.docx")


def test_fill_form_missing_template(tmp_path):
    """fill_form 模板不存在 → OfficeEngineError（docxtpl 未装则 skip）。"""
    try:
        import docxtpl  # noqa: F401
    except ImportError:
        pytest.skip("docxtpl 未装")
    from app.services.office.engine import OfficeEngineError, fill_form
    with pytest.raises(OfficeEngineError, match="模板不存在"):
        fill_form(tmp_path / "nope.docx", {"a": 1})


@pytest.mark.asyncio
async def test_batch_process_copy(tmp_path):
    """batch_process copy 操作（shutil，不依赖 office 库）。"""
    from app.services.office.engine import batch_process
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.txt").write_text("y")
    results = await batch_process(str(tmp_path), "copy", str(tmp_path / "out"))
    assert len(results) == 2
    assert (tmp_path / "out" / "a.txt").exists()


@pytest.mark.asyncio
async def test_batch_process_unknown_op_skipped(tmp_path):
    """batch_process 未知操作 → 文件被 except 跳过（不崩，results 空）。"""
    from app.services.office.engine import batch_process
    (tmp_path / "a.txt").write_text("x")
    results = await batch_process(str(tmp_path), "unknown_op")
    assert results == []


@pytest.mark.asyncio
async def test_batch_process_pdf_skips_non_docx(tmp_path):
    """batch_process pdf 操作跳过非 docx 文件。"""
    from app.services.office.engine import batch_process
    (tmp_path / "a.txt").write_text("x")
    results = await batch_process(str(tmp_path), "pdf", str(tmp_path / "out"))
    assert results == []  # txt 不转


# ── tripgen config ────────────────────────────────────────
def test_build_trip_from_json(tmp_path):
    from app.services.tripgen.config import build_trip
    cfg = tmp_path / "t.json"
    cfg.write_text(json.dumps({"title": "JSON行程", "party": "一大一小"}, ensure_ascii=False))
    trip = build_trip(str(cfg), assume_yes=True)
    assert trip.title == "JSON行程"
    assert trip.party == "一大一小"


def test_build_trip_from_yaml(tmp_path):
    try:
        import yaml
    except ImportError:
        pytest.skip("pyyaml 未装")
    from app.services.tripgen.config import build_trip
    cfg = tmp_path / "t.yaml"
    cfg.write_text(yaml.dump(
        {"title": "YAML行程", "days": [{"label": "D1", "text": "出发"}]},
        allow_unicode=True,
    ))
    trip = build_trip(str(cfg), assume_yes=True)
    assert trip.title == "YAML行程"
    assert len(trip.days) == 1


def test_trip_from_dict_with_route_map():
    """含 route_map → RouteMap + MapNode 构造（覆盖 _map 分支）。"""
    from app.services.tripgen.config import trip_from_dict
    trip = trip_from_dict({
        "title": "T",
        "route_map": {
            "title": "线路图",
            "nodes": [{"name": "长沙", "x": 0.1, "y": 0.2, "kind": "city"}],
            "legend": "图例",
        },
    })
    assert trip.route_map is not None
    assert trip.route_map.nodes[0].name == "长沙"
    assert trip.route_map.title == "线路图"


def test_trip_from_dict_no_route_map():
    """无 route_map → route_map=None。"""
    from app.services.tripgen.config import trip_from_dict
    trip = trip_from_dict({"title": "T"})
    assert trip.route_map is None
