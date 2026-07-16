# -*- coding: utf-8 -*-
"""中文字体子集化。

reportlab 不支持 CFF(OTTO)轮廓,而多数免费中文字体(思源黑体等)是 CFF。
本模块把源字体按“实际用到的字符”子集化,并把 CFF 轮廓转成 glyf(TrueType),
生成 reportlab 可用、体积很小的 .ttf。

源字体查找顺序:
  1) 显式传入的 regular/bold 路径
  2) 环境变量 TRIPGEN_FONT_DIR 下的 NotoSansSC-Regular/Bold 等
  3) 常见系统路径(思源黑体 / Noto Sans CJK / PingFang 兜底提示)
"""
from __future__ import annotations
import os
from typing import Optional, Tuple

_CANDIDATES_REG = [
    "NotoSansSC-Regular.ttf", "NotoSansSC-Regular.otf", "NotoSC-Regular.ttf",
    "SourceHanSansSC-Regular.otf", "SourceHanSansCN-Regular.otf",
]
_CANDIDATES_BOLD = [
    "NotoSansSC-Bold.ttf", "NotoSansSC-Bold.otf", "NotoSC-Bold.ttf",
    "SourceHanSansSC-Bold.otf", "SourceHanSansCN-Bold.otf",
]
_SYS_DIRS = [
    os.environ.get("TRIPGEN_FONT_DIR", ""),
    ".", "./fonts",
    "/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto",
    "/System/Library/Fonts", os.path.expanduser("~/Library/Fonts"),
    "C:/Windows/Fonts",
]
# 始终纳入子集:全 ASCII 可打印(车次号 D7196/K9275、App、SUP、tripgen 等)+ 常用符号
import string as _string
_EXTRA = (_string.ascii_letters + _string.digits + _string.punctuation + " "
          + "¥·—–（）“”、，。：；×→↗℃°√•‧∙")


def _find(cands) -> Optional[str]:
    for d in _SYS_DIRS:
        if not d:
            continue
        for name in cands:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


def resolve_sources(reg: Optional[str], bold: Optional[str]) -> Tuple[str, str]:
    reg = reg or _find(_CANDIDATES_REG)
    bold = bold or _find(_CANDIDATES_BOLD) or reg
    if not reg:
        raise FileNotFoundError(
            "找不到中文源字体。请设置 TRIPGEN_FONT_DIR 指向含 "
            "NotoSansSC-Regular.(ttf|otf) 的目录,或用 --font/--font-bold 指定。")
    return reg, bold


def subset(src: str, out: str, text: str) -> str:
    """把 src 按 text 中的字符子集化并转 glyf,写到 out。返回 out。"""
    from fontTools.ttLib import TTFont, newTable
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools import subset as ftsubset

    chars = sorted(set(text) | set(_EXTRA))
    f = TTFont(src)
    is_cff = "CFF " in f

    ss = ftsubset.Subsetter(ftsubset.Options(
        glyph_names=False, recalc_bounds=True, notdef_outline=True,
        layout_features="*"))
    ss.populate(text="".join(chars))
    ss.subset(f)

    if is_cff:
        glyph_set = f.getGlyphSet()
        glyf = newTable("glyf")
        glyf.glyphs = {}
        glyf.glyphOrder = f.getGlyphOrder()
        for name in glyf.glyphOrder:
            pen = TTGlyphPen(glyph_set)
            f.getGlyphSet()[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
            glyf.glyphs[name] = pen.glyph()
        f["glyf"] = glyf

        from fontTools.ttLib.tables._m_a_x_p import table__m_a_x_p
        maxp = table__m_a_x_p()
        maxp.tableVersion = 0x00010000
        maxp.numGlyphs = len(glyf.glyphOrder)
        for a in ("maxPoints", "maxContours", "maxCompositePoints",
                  "maxCompositeContours", "maxZones", "maxTwilightPoints",
                  "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                  "maxStackElements", "maxSizeOfInstructions",
                  "maxComponentElements", "maxComponentDepth"):
            setattr(maxp, a, 0)
        maxp.maxZones = 1
        f["maxp"] = maxp
        f["loca"] = newTable("loca")

        from fontTools.ttLib.tables._p_o_s_t import table__p_o_s_t
        post = table__p_o_s_t()
        post.formatType = 3.0
        post.italicAngle = 0
        post.underlinePosition = -100
        post.underlineThickness = 50
        post.isFixedPitch = 0
        for a in ("minMemType42", "maxMemType42", "minMemType1", "maxMemType1"):
            setattr(post, a, 0)
        f["post"] = post

        f.sfntVersion = "\x00\x01\x00\x00"
        if "head" in f:
            f["head"].glyphDataFormat = 0
        for t in ("CFF ", "VORG"):
            if t in f:
                del f[t]

    f.save(out)
    return out


def build_fonts(out_dir: str, text: str,
                reg: Optional[str] = None, bold: Optional[str] = None,
                prefix: str = "TripGen") -> Tuple[str, str]:
    """生成 regular/bold 两个子集字体,返回 (reg_path, bold_path)。"""
    src_reg, src_bold = resolve_sources(reg, bold)
    r = subset(src_reg, os.path.join(out_dir, f"{prefix}-R.ttf"), text)
    b = subset(src_bold, os.path.join(out_dir, f"{prefix}-B.ttf"), text)
    return r, b
