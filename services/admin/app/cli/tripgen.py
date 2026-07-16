"""TripGen CLI 入口（admin 内部库版）

用法:
  python -m app.cli.tripgen init trip.yaml       # 写示例配置
  python -m app.cli.tripgen build trip.yaml -o out/  # 生成 4 件套
  python -m app.cli.tripgen html trip.yaml -o out/   # 只生成 HTML
"""
from __future__ import annotations
import argparse
import os
import sys

from ..services.tripgen import config, pipeline, html_guide
from ..services.tripgen.cli import EXAMPLE


def cmd_init(args):
    if os.path.exists(args.path) and not args.force:
        sys.exit(f"{args.path} 已存在，加 --force 覆盖。")
    with open(args.path, "w", encoding="utf-8") as f:
        f.write(EXAMPLE)
    print(f"已写出示例配置: {args.path}\n编辑后运行: python -m app.cli.tripgen build {args.path} -o out/")


def cmd_build(args):
    trip = config.build_trip(args.path, assume_yes=getattr(args, "yes", False))
    outs = pipeline.generate(trip, args.out, online=args.online,
                             font=args.font, font_bold=args.font_bold,
                             log=lambda s: print("✓ " + s if "⚠" not in s else s))
    print(f"\n完成，共 {len(outs)} 个文件 → {args.out}")


def cmd_html(args):
    trip = config.build_trip(args.path, assume_yes=getattr(args, "yes", False))
    os.makedirs(args.out, exist_ok=True)
    p = os.path.join(args.out, f"{pipeline.slug(trip.title)}_图文攻略.html")
    html_guide.write_html(trip, p)
    print(f"✓ HTML 攻略: {p}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="tripgen", description="旅游攻略生成器（admin 内部库）。")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="写出示例配置")
    pi.add_argument("path", nargs="?", default="trip.yaml")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_init)

    def add_common(sp):
        sp.add_argument("path", help="行程配置(.yaml/.json)")
        sp.add_argument("-o", "--out", default="out")
        sp.add_argument("--online", action="store_true")
        sp.add_argument("--yes", action="store_true")
        sp.add_argument("--font")
        sp.add_argument("--font-bold", dest="font_bold")

    pb = sub.add_parser("build", help="生成全部（PDF正文/攻略HTML+PDF/合并）")
    add_common(pb)
    pb.set_defaults(func=cmd_build)

    ph = sub.add_parser("html", help="只生成图文攻略 HTML")
    add_common(ph)
    ph.set_defaults(func=cmd_html)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
