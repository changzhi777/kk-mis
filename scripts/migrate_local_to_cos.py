"""迁移 MediaAsset local → cos（COS Phase 4）

用法（在 services/admin 下跑，用 admin 的 .venv）:
    cd services/admin
    PYTHONPATH=. .venv/bin/python ../../scripts/migrate_local_to_cos.py --dry-run
    # 真跑（需 COS_* env）:
    PYTHONPATH=. COS_SECRET_ID=... COS_SECRET_KEY=... \\
        .venv/bin/python ../../scripts/migrate_local_to_cos.py --run

dry-run: 列所有 storage_backend='local' 的 MediaAsset，不修改
真跑: 每文件 LocalStorage.get_bytes → CosStorage.put → 更新 storage_backend='cos' + storage_key + url + etag

幂等：已 'cos' 的记录跳过；中途失败不影响已迁移的。
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 让脚本能 import admin app（mis-system/services/admin）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "admin"))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from app.models import MediaAsset  # noqa: E402
from app.services.storage import (  # noqa: E402
    CosStorage,
    LocalStorage,
    ObjectKey,
    UploadRequest,
)


def _safe_filename(name: str) -> str:
    base = Path(name or "file").name or "file"
    return base.replace("..", "").replace("/", "_").replace("\\", "_") or "file"


async def migrate(dry_run: bool) -> None:
    # 自建 engine（不经 init_db，避免 create_all + seed 副作用；迁移脚本只读 DB）
    connect_args = {"check_same_thread": False} if settings.db_driver == "sqlite" else {}
    engine = create_async_engine(settings.database_url, connect_args=connect_args)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        rows = (
            await session.execute(
                select(MediaAsset).where(MediaAsset.storage_backend == "local")
            )
        ).scalars().all()
        print(f"local 记录: {len(rows)}")

        if dry_run:
            for a in rows:
                print(f"  [{a.id}] name={a.name} key={a.storage_key} url={a.url}")
            print("\n(dry-run，未修改。真跑加 --run）")
            return

        # 真跑：local 读 → cos 写 → 更新记录
        if not (settings.cos_region and settings.cos_secret_id
                and settings.cos_secret_key and settings.cos_bucket):
            print("❌ 真跑需 COS_REGION/SECRET_ID/SECRET_KEY/BUCKET env")
            return
        local = LocalStorage(root_dir=settings.storage_local_root or "storage/uploads")
        cos = CosStorage(
            region=settings.cos_region,
            secret_id=settings.cos_secret_id,
            secret_key=settings.cos_secret_key,
            bucket=settings.cos_bucket,
            scheme=settings.cos_scheme or "https",
        )

        ok = fail = 0
        for a in rows:
            # ObjectKey：优先 storage_key，fallback 从 url 推 stored_filename（老数据 storage_key=NULL）
            key = (
                ObjectKey(a.storage_key)
                if a.storage_key
                else ObjectKey(_safe_filename(a.url.rsplit("/", 1)[-1]))
            )
            try:
                data = await local.get_bytes(key)
                result = await cos.put(
                    UploadRequest(
                        key=key,
                        data=data,
                        content_type=a.content_type or "application/octet-stream",
                    )
                )
                a.storage_backend = "cos"
                a.storage_key = key.value
                a.url = result.url
                a.etag = result.etag
                await session.commit()
                ok += 1
                print(f"  [{a.id}] ✓ → {result.url}")
            except Exception as exc:
                fail += 1
                print(f"  [{a.id}] ✗ {type(exc).__name__}: {exc}")
        print(f"\n完成: ok={ok} fail={fail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移 MediaAsset local → cos")
    parser.add_argument("--dry-run", action="store_true", help="只列不跑")
    parser.add_argument("--run", action="store_true", help="真跑迁移")
    args = parser.parse_args()
    if not args.dry_run and not args.run:
        parser.print_help()
        return
    asyncio.run(migrate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
