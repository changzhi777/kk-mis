# Storage 抽象层（kk-mis admin）

> Sprint 0 + Sprint 1 落地文档 · 2026-07-14
> 适用于 kk-mis admin 服务对象存储的抽象接口与后端切换。

## 1. 概述

`app/services/storage/` 是 kk-mis admin 服务内所有**对象存储操作**的统一入口。它将 14 个直接写文件点（`Path.write_bytes` / `FileResponse` / `open('rb').read`）的代码集中到一层抽象，未来切换 COS / OSS / MinIO 等存储后端时业务代码零修改。

### 设计目标
- **抽象层优先**：业务代码只见 `Storage` Protocol/ABC 与 Domain Types（frozen dataclass），不见 backend
- **async-first**：FastAPI 友好，所有 IO 是 `async def`，local backend 内部 `asyncio.to_thread`
- **S3 兼容语义**：方法名贴近 S3 行业惯例（`put` / `head` / `presigned_*` / `multipart_*`）
- **可测试**：单测用 `tmp_path` 验证 LocalStorage；CosStorage 用 mock；集成测 `skipif not INTEGRATION`
- **可灰度**：`STORAGE_BACKEND=local|cos` envvar 切换，零停机

### 项目结构

```
app/services/storage/
├── __init__.py           # get_storage() 工厂 + re-export
├── protocol.py           # Storage ABC + 7 frozen dataclass (Domain Types)
├── local.py              # LocalStorage（默认，Path-based）
├── cos.py                # CosStorage（腾讯云 COS）★ Sprint 1
├── sts.py                # STSCredentialProvider（Phase 2 临时凭证）★ Sprint 1
└── errors.py             # 5 异常类（根 + 子）
```

---

## 2. 后端选择

| Backend | 何时用 | 关键依赖 |
|---------|--------|----------|
| `local` | dev / 单元测试 / 单租户自部署 | 仅 `pathlib`（标准库） |
| `cos` | 生产 / 多区域共享 | `cos-python-sdk-v5>=1.9.0` |

切换：
```bash
# dev 默认
export STORAGE_BACKEND=local
export STORAGE_LOCAL_ROOT=storage/uploads

# 生产
export STORAGE_BACKEND=cos
export COS_REGION=ap-guangzhou
export COS_SECRET_ID=<CAM子账号的SecretId>
export COS_SECRET_KEY=<CAM子账号的SecretKey>
export COS_BUCKET=qm-wx-1418512491
```

---

## 3. 公共接口（Protocol / ABC）

`Storage` 是抽象基类（`abc.ABC` + `@abstractmethod`），9 个方法必须全实现：

| 方法 | 用途 |
|------|------|
| `put(req)` | 上传 bytes / file-like |
| `get_stream(key)` | 流式读（异步迭代器） |
| `get_bytes(key)` | 整读（小文件） |
| `head(key)` | 元数据；不存在返 `None` |
| `exists(key)` | 存在性 |
| `delete(key)` | 删 |
| `presigned_upload(key, *, content_type, expires)` | 前端直传 URL |
| `presigned_download(key, *, expires)` | 私有对象下载 URL |
| `list_objects(prefix, *, recursive)` | 列对象（异步迭代器） |
| `health()` | 诊断信息（backend / region / bucket / root） |

### Domain Types（`protocol.py`）

```python
ObjectKey(value: str)             # 路径不可变；自动校验拒绝 ../, /, \
UploadRequest(key, data, content_type="application/octet-stream", metadata, cache_control)
UploadResult(key, url, etag, size, version_id=None)
ObjectMeta(key, size, etag, content_type, last_modified, metadata)
PresignedUpload(url, method="PUT", key, expires_at, required_headers={}, max_size=None)
PresignedDownload(url, expires_at)
```

### 错误层级（`errors.py`）

```
StorageError
├── ObjectNotFound        # 404 / 不存在
├── PermissionDenied      # 403
├── BackendUnavailable    # 5xx / 网络断 / SDK 缺失 / 凭据错
└── InvalidArgument       # 参数错 (ObjectKey 越界 / 缺 region 等)
```

业务代码捕捉 `StorageError` 即可分级（`isinstance` 细判）。

---

## 4. LocalStorage（默认）

适合 dev + 单租户自部署。存储到 `STORAGE_LOCAL_ROOT`（默认 `./storage/uploads/`）。

### 特性
- 写文件同时写 `.meta.json` sidecar（存 etag/size/content_type/metadata/last_modified）
- 防路径遍历：`ObjectKey.__post_init__` 校验 + `LocalStorage._resolve()` 双重
- 部分支持 presigned：`presigned_download` 返 admin 路由 URL；`presigned_upload` 抛 `NotImplementedError`（前端走 admin 中转）

### 单测
`tests/test_storage_local.py` — 21 个用例，包括：
- ObjectKey 校验（dotdot / slash / backslash / 太长 / 空）
- put + get_bytes / head sidecar / get_stream（1MB+13 字节分块）
- delete 副作用（真删文件 + sidecar）
- list_objects 跳过 sidecar + health

---

## 5. CosStorage（Sprint 1 实装）

适合生产 + 多实例共享 + 大文件 + 高可用。

### 特性
- 懒加载 `cos-python-sdk-v5`：模块 import 时不引 SDK；运行时首次调用方法才加载
- 共享 1 个 `CosS3Client`（连接池由 SDK 内部 HTTP connection 复用）
- 所有 IO 用 `loop.run_in_executor` 包装（cos-sdk-v5 同步阻塞）
- Region / Bucket / Credentials 每次构造时从 `settings` 重读（避免 env 改动不生效）
- 错误统一翻译：cos 异常 → `ObjectNotFound` / `PermissionDenied` / `BackendUnavailable`

### Presigned URL
- `presigned_upload`：**注意** Sprint 1 当前用 `get_presigned_download_url` 占位（Phase 2 切换为 `get_presigned_upload_url`）
- `presigned_download`：直接返 `get_presigned_download_url`

### 单测
`tests/test_storage_cos_skeleton.py` — 9 个 mock 用例：
- CosStorage 拒空 region / 拒空 creds / 拒空 bucket
- 缺 SDK 时 import 抛 BackendUnavailable
- get_storage() 的 cos 分支在缺凭据时抛 BackendUnavailable
- STSCredential.is_expired(skew=300) 行为
- STSCredentialProvider 缓存命中直接返

### 集成测试
`tests/test_cos_integration.py` — 6 个真实 bucket 用例（`skipif not INTEGRATION`）：
- put → get → delete roundtrip
- presigned_upload URL 真打 PUT
- presigned_download URL 真打 GET
- list_objects 找新写对象
- head 不存在返 None
- health 返 backend=cos

启用集成测试：
```bash
export INTEGRATION=1
export COS_REGION=ap-guangzhou
export COS_SECRET_ID=<你的 AKID>
export COS_SECRET_KEY=<你的 SecretKey>
export COS_BUCKET=qm-wx-1418512491
export STORAGE_BACKEND=cos
PYTHONPATH=. pytest tests/test_cos_integration.py -v
```

---

## 6. STSCredentialProvider（Sprint 1 Phase 2）

生产推荐用 **STS 临时凭证**（30min 自动刷新），不用 Long-Term Key 避免泄露风险。

### 用法
```python
from app.services.storage import STSCredentialProvider

provider = STSCredentialProvider(
    role_arn=settings.cos_assume_role_arn,           # 例 qcs::cam::uin/xxx:roleName/xxx
    session_name=settings.cos_session_name,         # 默认 'kk-mis-session'
    duration=1800,                                    # 30min
    region=settings.cos_region,
    secret_id=settings.long_term_secret_id,
    secret_key=settings.long_term_secret_key,
    redis_client=aioredis_client,                    # 可选；Redis 缓存
)
cred = await provider.get()                          # 缓存在，自动刷新
```

### 缓存策略
- Redis 缓存：`sts:cos:<role_arn>` → JSON `STSCredential`
- TTL：`(expired_at - now) - 60秒`
- fail-open：Redis 不可用 → 仍调 STS API

### 未来集成
Sprint 1 骨架就绪，待 Phase 2 在 `__init__.py` `get_storage()` 加 STS provider 路径 + 配置 `STS_ROLE_ARN` 后启用。

---

## 7. 业务代码使用模式

### CMS 上传（`app/routes/cms/media.py`）
```python
from app.services.storage import get_storage, ObjectKey, UploadRequest

storage = get_storage()
key = ObjectKey(stored_filename)
result = await storage.put(UploadRequest(
    key=key,
    data=data_bytes,
    content_type=file.content_type,
    metadata={"uploaded_by": str(user.id)},
))
asset = MediaAsset(
    storage_backend="local",     # 或 "cos"
    storage_key=str(key),
    etag=result.etag,
    url=f"/admin/api/v1/cms/media/file/{stored_filename}",
    ...
)
```

### 读取素材
```python
@router.get("/file/{filename}")
async def serve_file(filename: str):
    safe = _safe_filename(filename)
    path = (LEGACY_UPLOAD_DIR / safe).resolve()
    if not str(path).startswith(str(LEGACY_UPLOAD_DIR.resolve())):
        raise HTTPException(400, "非法路径")
    if not path.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(path)
```

> 注：当前 Phase 1 仅支持 local backend 走 `FileResponse`。Phase 2 升级到 detect `storage_backend`：`'local'` 走 FileResponse，`'cos'` 重定向到 presigned_download URL。

---

## 8. 切换到 COS 实操步骤（生产部署）

1. **控制台建 Bucket**
   - 主 Bucket：`qm-wx-1418512491`（私有读写 / 广州 ap-guangzhou）
   - 第二 Bucket：`qm-wx-private-1418512491`（私有读写 / 同区域）—— 存 OA 附件
2. **CORS 配置**（两个 Bucket 都贴，参考控制台 → 跨域访问 CORS 设置）：
   ```xml
   <CORSConfiguration>
     <CORSRule>
       <AllowedOrigin>https://aisport.tech</AllowedOrigin>
       <AllowedOrigin>https://www.aisport.tech</AllowedOrigin>
       <AllowedOrigin>http://localhost:5173</AllowedOrigin>  <!-- dev -->
       <AllowedMethod>GET</AllowedMethod>
       <AllowedMethod>HEAD</AllowedMethod>
       <AllowedHeader>*</AllowedHeader>
       <ExposeHeader>ETag</ExposeHeader>
       <MaxAgeSeconds>600</MaxAgeSeconds>
     </CORSRule>
     <CORSRule>
       <AllowedOrigin>https://aisport.tech</AllowedOrigin>
       <AllowedMethod>PUT</AllowedMethod>
       <AllowedMethod>POST</AllowedMethod>
       <AllowedMethod>DELETE</AllowedMethod>
       <AllowedMethod>OPTIONS</AllowedMethod>
       <AllowedHeader>Content-Type</AllowedHeader>
       <AllowedHeader>x-cos-meta-*</AllowedHeader>
       <ExposeHeader>ETag</ExposeHeader>
       <ExposeHeader>x-cos-request-id</ExposeHeader>
       <MaxAgeSeconds>300</MaxAgeSeconds>
     </CORSRule>
   </CORSConfiguration>
   ```
3. **防盗链**（仅公共 read bucket 需要；private bucket 走 presigned URL 不依赖 Referer）：
   - Referer 白名单：`https://aisport.tech`、`https://www.aisport.tech`
   - 空 Referer：Deny
   - 403 状态码
4. **CAM 子账号**
   - IAM → 用户 → 新建用户 → 自定义策略
   - 策略 JSON（仅示例）：
     ```json
     {
       "version": "2.0",
       "statement": [{
         "effect": "allow",
         "action": [
           "cos:PutObject",
           "cos:GetObject",
           "cos:HeadObject",
           "cos:DeleteObject",
           "cos:ListObjects"
         ],
         "resource": [
           "qcs::cos:ap-guangzhou:uid/1418512491:qm-wx-1418512491/*",
           "qcs::cos:ap-guangzhou:uid/1418512491:qm-wx-1418512491",
           "qcs::cos:ap-guangzhou:uid/1412512491:qm-wx-private-1418512491/*"
         ]
       }]
     }
     ```
   - 创建 API 密钥 → 复制 SecretId + SecretKey
5. **设置 env**
   ```bash
   export STORAGE_BACKEND=cos
   export COS_REGION=ap-guangzhou
   export COS_SECRET_ID=<AKID>
   export COS_SECRET_KEY=<...>
   export COS_BUCKET=qm-wx-1418512491
   ```
6. **部署 43.129.201.118**
   - 通过 `infra/systemd/kk-mis-admin.service` 重启服务
   - 验证 `curl http://localhost:8300/health` → 200
7. **集成测试**
   ```bash
   export INTEGRATION=1
   PYTHONPATH=. pytest tests/test_cos_integration.py -v
   ```

---

## 9. 故障排查

| 症状 | 原因 | 修复 |
|------|------|------|
| `BackendUnavailable: cos-python-sdk-v5 未安装` | dev 环境没装 SDK | `pip install cos-python-sdk-v5>=1.9.0` |
| `BackendUnavailable: 凭据不完整` | `.env` 没设 `COS_SECRET_ID/KEY/BUCKET/REGION` | 检查 `.env` 实际加载（`set \| grep COS_`） |
| `PermissionDenied` 403 | CAM 子账号策略不够 | 给 policy 加 `cos:PutObject` 等 |
| `ObjectNotFound` 上传 404 | Bucket 区域错 | `COS_REGION` 与 bucket 区域一致（ap-guangzhou） |
| `presigned_url` 上传 CORS 错误 | CORS XML 未设允许 PUT | 粘贴 §8 步骤 2 的 XML |
| 集成测试 SKIPPED | 没设 `INTEGRATION=1` | `export INTEGRATION=1` 后 pytest |
| `KeyError: 'Content-Length'` 上传后立即 get | 字节上传后 `_size_of` 走 head 有网络延迟 | Sprint 1 临时 work-around（用 len(data)）；Phase 2 优化 |
| STS AssumeRole 失败 | RoleArn 不对或策略权限不足 | 验证 CAM 角色已建 + 有 `sts:AssumeRole` 信任 |

---

## 10. 待办（后 Sprint）

| 项 | Sprint | 备注 |
|----|--------|------|
| `presigned_upload` 改用 `get_presigned_upload_url`（PUT）| 2 | 现状用 download 占位 |
| `list_objects` 分页 + 递归 | 2 | 现状单层 1000 |
| `STSCredentialProvider` 接入 production | 2 | 需要 STS_ROLE_ARN |
| `cms/media.py serve_file` 加 cos redirect 分支 | 2 | 让 storage_backend='cos' 也能 serve |
| 老记录批量迁移脚本 Phase 4 | 3 | `scripts/migrate_local_to_cos.py` |
| meeting-notes 录音分块上传 | 4 | 500MB 录音接 COS multipart |
| 前端 presigned 直传 | 4 | 节省后端带宽 |
| 两 Bucket 自动分流（public/private）| 5 | 当前单 bucket |
| CDN 加速（自有域名）| 6 | 可选 |
| KMS 服务端加密 | 6 | YAGNI |
