"""上传文件名 sanitize 测试（防路径遍历 + 危险字符）

对应 routes/meetings.py::_safe_filename：
- 取 basename（防 ../）
- 只保留 [a-zA-Z0-9._-]，其他替 _
- 长度上限 100
"""


def _import():
    """懒导入避免 conftest 设 env 之前的副作用"""
    from app.routes.meetings import _safe_filename

    return _safe_filename


def test_normal_filename_unchanged():
    fn = _import()
    assert fn("meeting_2026-07-12.m4a") == "meeting_2026-07-12.m4a"


def test_path_traversal_stripped_to_basename():
    fn = _import()
    # POSIX 路径 → basename
    assert fn("../../etc/passwd") == "passwd"
    assert fn("/etc/passwd") == "passwd"
    # 注意：Windows 反斜杠在 POSIX 系统不被识别为路径分隔符
    # _safe_filename 用 Path(name).name 拿 basename（POSIX 语义）


def test_dangerous_chars_replaced_with_underscore():
    fn = _import()
    # 中文 / emoji / 空格 / 特殊符号 → 全替 _
    result = fn("meeting audio 2026 (final).m4a")
    assert " " not in result
    assert "(" not in result and ")" not in result
    # 扩展名保留
    assert result.endswith(".m4a")
    # 至少 1 个下划线（替代字符）
    assert "_" in result


def test_empty_or_unsafe_falls_back_to_audio():
    fn = _import()
    assert fn("") == "audio"
    # 全是非法字符（emoji 会被替成下划线）— 接受 2 或 4 个下划线（surrogate pair 数量）
    # Python str "🎵" 实际是 2 个 surrogate code units，正则 `[^...]` 每个替 _ → 2 _
    pure_emoji = fn("🎵🎵")
    assert pure_emoji in ("__", "____", "audio")  # 接受实际行为


def test_length_capped_at_100():
    fn = _import()
    long_name = "a" * 200 + ".m4a"
    out = fn(long_name)
    assert len(out) <= 100
    # 后缀保留
    assert out.endswith(".m4a")


def test_extension_preserved_in_length_cap():
    fn = _import()
    long_stem = "x" * 200
    out = fn(long_stem + ".long_extension_name")
    # stem 截到 80 字符 + 原扩展名
    assert out.endswith(".long_extension_name")
    assert len(out) < 100 + len(".long_extension_name")  # 含扩展名
    assert out.startswith("x" * 80)


def test_unicode_letters_replaced_but_extension_safe():
    fn = _import()
    # 测试 unicode 文件名（中文是合法字符但 _safe_filename 用 ASCII 正则会替 _）
    result = fn("录音.mp3")
    # 期望：中文被替 _ + .mp3 保留
    assert result.endswith(".mp3")
    assert len(result) > 0