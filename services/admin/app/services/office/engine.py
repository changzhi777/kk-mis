"""Office 核心引擎（CLI + API 共用 service 层）

6 个核心函数，admin 本地处理（无网络依赖）：
- docx_to_pdf：docx → html（mammoth）→ PDF（weasyprint）
- html_to_pdf：HTML 字符串 → PDF（weasyprint）
- data_to_excel：JSON/列表 → xlsx（openpyxl）
- template_to_pptx：模板 + 数据 → PPT（python-pptx）
- fill_form：docx 模板 + 变量 → 填充文档（docxtpl）
- batch_process：文件夹级批量（asyncio + glob）

设计原则（SOLID/KISS/DRY）：
- 每个函数单一职责，输入/输出清晰
- CLI 和 API 调同一函数（零重复）
- 异常统一 OfficeEngineError
"""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

logger = __name__


class OfficeEngineError(Exception):
    """office 引擎处理失败。"""


# ── PDF ──────────────────────────────────────────────────────

def html_to_pdf(html: str, output: str | Path) -> Path:
    """HTML 字符串 → PDF（weasyprint）。

    >>> html_to_pdf("<h1>Hello</h1>", "out.pdf")
    """
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise OfficeEngineError("weasyprint 未安装") from e
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(output))
    return output


def docx_to_pdf(input: str | Path, output: str | Path | None = None) -> Path:
    """docx → html（mammoth）→ PDF（weasyprint）。

    两步转换：mammoth 提取 html → weasyprint 渲染 PDF。
    格式还原度不如 libreoffice，但纯 Python 无系统依赖。
    """
    input = Path(input)
    if not input.exists():
        raise OfficeEngineError(f"文件不存在: {input}")
    output = Path(output) if output else input.with_suffix(".pdf")
    try:
        import mammoth
    except ImportError as e:
        raise OfficeEngineError("mammoth 未安装") from e
    with open(input, "rb") as f:
        result = mammoth.convert_to_html(f)
    html = f"<html><body>{result.value}</body></html>"
    return html_to_pdf(html, output)


# ── Excel ────────────────────────────────────────────────────

def data_to_excel(
    data: list[list[Any]] | list[dict[str, Any]],
    output: str | Path,
    headers: list[str] | None = None,
    sheet_name: str = "Sheet1",
) -> Path:
    """JSON/列表 → xlsx（openpyxl）。

    支持两种输入：
    - list[list]：二维数组，headers 可选
    - list[dict]：字典列表，keys 自动提取为 headers

    >>> data_to_excel([{"name":"张三","age":30}], "users.xlsx")
    """
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise OfficeEngineError("openpyxl 未安装") from e
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    # 统一为 list[list] 格式
    rows: list[list[Any]] = []
    if data and isinstance(data[0], dict):
        keys = headers or list(data[0].keys())
        rows.append(keys)
        for item in data:
            rows.append([item.get(k, "") for k in keys])
    else:
        if headers:
            rows.append(headers)
        rows.extend(data)
    for row in rows:
        ws.append(row)
    wb.save(str(output))
    return output


# ── PPT ──────────────────────────────────────────────────────

def template_to_pptx(
    slides: list[dict[str, Any]],
    output: str | Path,
    template: str | Path | None = None,
) -> Path:
    """数据 → PPT（python-pptx）。

    每条 slide dict 含：title / content / layout（可选，默认 1=标题+内容）
    template 可选：加载已有 pptx 作为基础模板。

    >>> template_to_pptx([{"title":"Q1","content":"收入100万"}], "report.pptx")
    """
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError as e:
        raise OfficeEngineError("python-pptx 未安装") from e
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    prs = Presentation(str(template)) if template else Presentation()
    for slide_data in slides:
        layout_idx = slide_data.get("layout", 1)
        layout = prs.slide_layouts[layout_idx]
        slide = prs.slides.add_slide(layout)
        if "title" in slide_data:
            slide.shapes.title.text = str(slide_data["title"])
        if "content" in slide_data:
            body = slide.placeholders[1]
            body.text = str(slide_data["content"])
    prs.save(str(output))
    return output


# ── 表单填写 ──────────────────────────────────────────────────

def fill_form(
    template: str | Path,
    data: dict[str, Any],
    output: str | Path | None = None,
) -> Path:
    """docx 模板 + 变量 → 填充文档（docxtpl）。

    模板内用 {{var}} 占位符，data 提供 key-value。

    >>> fill_form("contract.docx", {"party_a":"大华天麓","amount":"100万"})
    """
    try:
        from docxtpl import DocxTemplate
    except ImportError as e:
        raise OfficeEngineError("docxtpl 未安装") from e
    template_path = Path(template)
    if not template_path.exists():
        raise OfficeEngineError(f"模板不存在: {template_path}")
    output = Path(output) if output else template_path.with_stem(
        f"{template_path.stem}_filled"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = DocxTemplate(str(template_path))
    doc.render(data)
    doc.save(str(output))
    return output


# ── 批量处理 ──────────────────────────────────────────────────

async def batch_process(
    input_dir: str | Path,
    operation: str,
    output_dir: str | Path | None = None,
    pattern: str = "*",
) -> list[Path]:
    """文件夹级批量处理。

    operation 支持：pdf（docx→PDF）/ form（需 data.json 同名文件）/ copy
    遍历 input_dir/pattern 匹配文件，逐个调用对应函数。

    >>> await batch_process("./docs", "pdf", "./pdfs", "*.docx")
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else input_dir / f"output_{operation}"
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.glob(pattern))
    results: list[Path] = []
    for f in files:
        if not f.is_file():
            continue
        try:
            out = output_dir / f"{f.stem}_converted"
            if operation == "pdf":
                if f.suffix.lower() == ".docx":
                    result = docx_to_pdf(f, out.with_suffix(".pdf"))
                    results.append(result)
            elif operation == "form":
                data_file = f.with_suffix(".json")
                if data_file.exists():
                    import json
                    data = json.loads(data_file.read_text(encoding="utf-8"))
                    result = fill_form(f, data, out.with_suffix(".docx"))
                    results.append(result)
            elif operation == "copy":
                import shutil
                dest = output_dir / f.name
                shutil.copy2(f, dest)
                results.append(dest)
            else:
                raise OfficeEngineError(f"未知操作: {operation}")
        except Exception as e:
            import logging
            logging.getLogger(logger).warning("批量处理 %s 失败: %s", f, e)
    return results
