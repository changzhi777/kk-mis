"""Office engine CLI — 直接调用 app.services.office.engine 的 6 个函数。

设计原则（与 routes/office.py 共用同一 engine，零业务重复）：

    python -m app.cli.office pdf --input report.docx --output report.pdf
    python -m app.cli.office excel --data '[{"name":"张三","age":30}]' --output users.xlsx
    python -m app.cli.office pptx --slides '[{"title":"Q1","content":"100万"}]' --output report.pptx
    python -m app.cli.office form --template contract.docx --data '{"party_a":"大华天麓"}'
    python -m app.cli.office batch --input ./docs --op pdf --output ./pdfs --pattern "*.docx"

适用场景：
- CI/CD 脚本批量转 PDF（如报表归档）
- 运维在服务器上无浏览器时直接跑 engine
- 调试 engine 本身（不需要起 FastAPI）

不适用：
- 对外服务（那是 routes/office.py 的职责）
- 需要鉴权/审计的场景（CLI 无 RBAC）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from ..services.office.engine import (
    OfficeEngineError,
    batch_process,
    data_to_excel,
    docx_to_pdf,
    fill_form,
    html_to_pdf,
    template_to_pptx,
)


def _parse_json(arg: str, *, expect: type) -> Any:
    """解析 CLI 传入的 JSON 字符串，类型不符直接 sys.exit(2)。"""
    try:
        value = json.loads(arg)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 解析失败 ({exc.msg} at pos {exc.pos}): {arg!r}") from exc
    if not isinstance(value, expect):
        kind = "list" if expect is list else "dict"
        raise SystemExit(f"参数必须是 JSON {kind}，实际是 {type(value).__name__}")
    return value


def _cmd_pdf(args: argparse.Namespace) -> int:
    src = Path(args.input)
    out = Path(args.output) if args.output else src.with_suffix(".pdf")
    suffix = src.suffix.lower()
    try:
        if suffix in {".html", ".htm"}:
            html = src.read_text(encoding="utf-8")
            html_to_pdf(html, out)
        else:
            # 默认当 docx 处理（与 routes/office.py 行为一致）
            docx_to_pdf(src, out)
    except OfficeEngineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"OK -> {out}")
    return 0


def _cmd_excel(args: argparse.Namespace) -> int:
    data = _parse_json(args.data, expect=list)
    out = Path(args.output)
    headers = _parse_json(args.headers, expect=list) if args.headers else None
    try:
        data_to_excel(data, out, headers=headers, sheet_name=args.sheet_name)
    except OfficeEngineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"OK -> {out}")
    return 0


def _cmd_pptx(args: argparse.Namespace) -> int:
    slides = _parse_json(args.slides, expect=list)
    out = Path(args.output)
    template = args.template or None
    try:
        template_to_pptx(slides, out, template=template)
    except OfficeEngineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"OK -> {out}")
    return 0


def _cmd_form(args: argparse.Namespace) -> int:
    template = Path(args.template)
    variables = _parse_json(args.data, expect=dict)
    out = Path(args.output) if args.output else None
    try:
        result = fill_form(template, variables, out)
    except OfficeEngineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"OK -> {result}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    try:
        results = asyncio.run(
            batch_process(
                input_dir=args.input,
                operation=args.op,
                output_dir=args.output,
                pattern=args.pattern,
            )
        )
    except OfficeEngineError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1
    print(f"OK 处理 {len(results)} 个文件:")
    for p in results:
        print(f"  - {p}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.cli.office",
        description="office engine 本地 CLI（PDF/Excel/PPT/Form/Batch 直跑，无 HTTP）",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p_pdf = sub.add_parser("pdf", help="docx/html → PDF")
    p_pdf.add_argument("--input", "-i", required=True, help="输入文件路径（.docx/.html）")
    p_pdf.add_argument("--output", "-o", help="输出 PDF 路径（缺省与输入同目录同名 .pdf）")
    p_pdf.set_defaults(func=_cmd_pdf)

    p_excel = sub.add_parser("excel", help="JSON 数据 → xlsx")
    p_excel.add_argument("--data", "-d", required=True, help='JSON 数组字符串，如 \'[{"name":"张三"}]\'')
    p_excel.add_argument("--output", "-o", required=True, help="输出 xlsx 路径")
    p_excel.add_argument("--headers", help='可选 JSON 数组表头，如 \'["name","age"]\'')
    p_excel.add_argument("--sheet-name", default="Sheet1", help="工作表名（默认 Sheet1）")
    p_excel.set_defaults(func=_cmd_excel)

    p_pptx = sub.add_parser("pptx", help="slides JSON → pptx")
    p_pptx.add_argument("--slides", "-s", required=True, help='JSON 数组，如 \'[{"title":"Q1","content":"100万"}]\'')
    p_pptx.add_argument("--output", "-o", required=True, help="输出 pptx 路径")
    p_pptx.add_argument("--template", "-t", help="可选 pptx 模板路径")
    p_pptx.set_defaults(func=_cmd_pptx)

    p_form = sub.add_parser("form", help="docx 模板 + 变量 → 填充文档")
    p_form.add_argument("--template", "-t", required=True, help="含 {{ var }} 占位的 docx 模板")
    p_form.add_argument("--data", "-d", required=True, help='JSON 对象变量，如 \'{"party_a":"大华天麓"}\'')
    p_form.add_argument("--output", "-o", help="输出 docx 路径（缺省 template_filled.docx）")
    p_form.set_defaults(func=_cmd_form)

    p_batch = sub.add_parser("batch", help="文件夹批量处理")
    p_batch.add_argument("--input", "-i", required=True, help="输入目录")
    p_batch.add_argument("--op", required=True, choices=["pdf", "form", "copy"], help="操作类型")
    p_batch.add_argument("--output", "-o", help="输出目录（缺省 input_dir/output_<op>）")
    p_batch.add_argument("--pattern", "-p", default="*", help="glob 匹配模式（默认 *）")
    p_batch.set_defaults(func=_cmd_batch)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
