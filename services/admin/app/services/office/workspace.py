"""Office Engine 统一 workspace 沙箱（OFFICE-ENGINE-SANDBOX 修复，2026-07-17）。

设计目标：
1. **路径遏制**：所有本地 Office 输入/输出路径必须在 workspace 根之内，
   防止 `../../etc/passwd` 路径遍历覆盖或读取任意文件。
2. **临时文件 TTL**：`temp_path()` 生成的临时文件统一前缀 `_tmp_`，
   `cleanup()` 按 mtime 过期清理，防止磁盘累积撑爆。
3. **单一真相源**：`OfficeWorkspace` 实例挂在 `app.state.office_workspace`，
   lifespan 启动；路由通过 `request.app.state.office_workspace` 拿到同一份。

不在此处做的事：
- 不做权限校验（路由层 `require_permission("office:tool:invoke")` 已有）
- 不做文件大小/类型校验（路由层 + engine 函数内各自管）
- 不做异步删除（TTL 过期由 lifespan 后台任务每 10 分钟扫一次）
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


# 临时文件统一前缀，便于 cleanup() glob 识别（不会误删用户文件）
_TMP_PREFIX = "_tmp_"


class OfficeWorkspace:
    """统一 workspace 沙箱。

    所有本地 Office 操作（docx_to_pdf / html_to_pdf / data_to_excel /
    template_to_pptx / fill_form / batch_process）的输入路径与临时
    输出文件都必须在沙箱根目录下。

    构造时不强制 root 必须存在；首次 `resolve()` 或 `temp_path()` 时按需
    `mkdir(parents=True, exist_ok=True)`。
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info(f"OfficeWorkspace initialized: {self.root}")

    # ── 路径遏制 ──────────────────────────────────────────────

    def resolve(self, path: str | Path, must_exist: bool = False) -> Path:
        """解析路径，确保在沙箱根之内。

        Args:
            path: 相对沙箱根的相对路径（如 ``docs/a.docx`` 或 ``_tmp_xxx.pdf``）。
                 禁止绝对路径 / 含 ``..`` 段 / UNC。
            must_exist: 若 True 且路径不存在，抛 FileNotFoundError。

        Raises:
            ValueError: 路径逃出沙箱（``..`` 遍历等）。
            FileNotFoundError: ``must_exist=True`` 且路径不存在。
        """
        if not isinstance(path, (str, Path)):
            raise ValueError(f"path must be str or Path, got {type(path).__name__}")

        # 显式拒绝：空 / 绝对路径 / UNC / Windows 盘符
        s = str(path)
        if not s:
            raise ValueError("path 不能为空")
        # UNC 必须先于绝对路径检查（\\\\ 也以 \ 开头）
        if s.startswith("\\\\"):
            raise ValueError(f"path 不允许 UNC 路径: {path!r}")
        if s.startswith("/") or s.startswith("\\"):
            raise ValueError(f"path 不允许绝对路径: {path!r}")
        # Windows 盘符（C:\、D:/）
        if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
            raise ValueError(f"path 不允许盘符绝对路径: {path!r}")

        resolved = (self.root / path).resolve()
        # resolve() 后必须仍以 root 开头（防 .. 段绕过 + symlink）
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise ValueError(
                f"path escapes sandbox: {path!r} → {resolved} 不在 {self.root} 内"
            )

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"path not found in workspace: {resolved}")

        return resolved

    # ── 临时文件 ──────────────────────────────────────────────

    def temp_path(self, suffix: str = ".tmp") -> Path:
        """生成沙箱内临时文件路径（不创建文件，只返回路径）。

        返回的路径以 ``_tmp_<uuid>`` 开头，cleanup() 会按前缀识别清理。
        """
        if not suffix.startswith("."):
            suffix = "." + suffix
        return self.root / f"{_TMP_PREFIX}{uuid.uuid4().hex}{suffix}"

    # ── 过期清理 ──────────────────────────────────────────────

    def cleanup(self, max_age_seconds: int = 3600) -> int:
        """清理过期的临时文件与任务子目录（默认 1 小时）。

        覆盖两类 ``_tmp_`` 前缀条目：
        - 临时文件（office engine ``temp_path()`` 产出）；
        - 临时目录（tripgen 任务产物 ``_tmp_tripgen_*`` 等），按目录 mtime 整体
          删除含内容；tripgen 生成完不再写入，mtime 停在生成时，TTL 后回收。

        Returns:
            实际删除的文件 + 目录数（用于测试断言 / 日志）。
        """
        import shutil

        cutoff = time.time() - max_age_seconds
        removed = 0
        for p in self.root.glob(f"{_TMP_PREFIX}*"):
            try:
                if p.is_dir():
                    if p.stat().st_mtime < cutoff:
                        shutil.rmtree(p)
                        removed += 1
                elif p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except (FileNotFoundError, PermissionError) as e:
                # 条目在扫描间隙被删/无权访问 → 跳过即可
                logger.debug(f"office cleanup skip {p}: {e}")
        if removed:
            logger.info(
                f"OfficeWorkspace cleanup: removed {removed} entries (>{max_age_seconds}s)"
            )
        return removed