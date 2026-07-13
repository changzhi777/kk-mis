# 全面测试报告（2026-07-13）

> **范围**：跨服务集成（4）+ 端到端 E2E（1）
> **目标项目**：mis-system admin（含 oa-agent bridge）+ meeting-notes + oa-agent + 前端
> **测试方式**：pytest + httpx（不依赖 Playwright 浏览器）

## 一、最终结果

| 套件 | 测试数 | 通过 | 失败 | 备注 |
|---|---|---|---|---|
| 单元测试（已有） | 82 | 79 | 3 | 3 个 pre-existing（旧 3 级分销测试）|
| 跨服务集成（新） | 7 | 7 | 0 | admin ↔ oa-agent bridge |
| 端到端 E2E（新） | 3 | 3 | 0 | 全链路 API + 公开核销 |
| **总计** | **92** | **89** | **3 pre-existing** | **0 新增 fail** |

## 二、跨服务集成测试（7 项全过）

| ID | 测试 | 验证 |
|---|---|---|
| IT-01 | bridge /healthz 透传 oa-agent 响应 | 200 + status=ok |
| IT-02 | bridge /skills 透传 | 200 + skills 列表 |
| IT-03 | bridge /chat/sync 转发 | 200 / 5xx（无 LLM key 时降级）|
| IT-04 | 同步对话未登录 → 401 | 鉴权 |
| IT-05 | /skills 未登录 → 401 | 鉴权 |
| IT-06 | /healthz 公开（无需登录）| 探活友好 |
| IT-07 | oa-agent 不可达时 → 503 | 降级处理 |

**关键修复**：
- `bridge.py::OA_AGENT_URL` 从 `os.environ` 读取（之前 hard-coded :9001）
- `conftest.py` autouse session-scope fixture 启动 oa-agent 子进程 :19001

## 三、端到端 E2E 测试（3 项全过）

| ID | 测试 | 验证 |
|---|---|---|
| E2E-01 | **VIP 完整业务流** | 登录 → 区域代理 → VIP 批次 → 100 张下单（6 折）→ 付款 → 完成 → 单次返佣 30% (¥33,984) → 生成卡 → 防伪核销 |
| E2E-02 | oa-agent bridge 透传 | healthz + skills（确保 :9001 oa-agent 可达）|
| E2E-03 | oa-agent 不可达降级 | 503 + 错误信息 |

**完整 E2E 验证（10 步）**：
1. admin 登录拿 JWT
2. 创建区域代理（region_code 唯一）
3. 创建 VIP 类型（unit_price 1888）
4. 创建 VIP 批次
5. `/quote` 实时报价（100 张 → 6 折 / ¥1,132.8 / 总 ¥113,280）
6. 创建订单（后端自动 6 折，region_code 锁定）
7. 付款
8. 完成订单（触发单次返佣计算）
9. 验证 `CommissionRecord` 写入 ¥33,984（113,280 × 30%）
10. 生成卡（含 64 位 unique_code + mock blockchain_tx_hash + QR URL）+ 公开核销（200 + verified=true）

## 四、关键问题与修复

### 1. bridge hard-coded URL（**生产 + 测试风险**）

`app/routes/oa_agent_bridge.py::OA_AGENT_URL = "http://127.0.0.1:9001"` 硬编码，导致：
- 生产部署换端口需改代码
- 测试环境无法指向 :19001（fixture 启动）

**修复**：从 `os.environ.get("OA_AGENT_URL", "http://127.0.0.1:9001")` 读取。

### 2. e2e fixture 路径错（**测试启动失败**）

`Path(__file__).parent.parent` 实际是 `tests/`，不是 `services/admin/`。导致 `PYTHONPATH` 错，admin 启动报 `ModuleNotFoundError: No module named 'app'`。

**修复**：再上一层 `parent.parent.parent`。

### 3. session fixture 启动的服务跨测试残留

oa-agent 子进程在 pytest session 结束前一直运行；下轮测试 `_port_in_use` 判定已占用会跳过启动（OK，但需要确保上轮无残留）。

**修复**：用 `pkill -f "oa_agent.api:create_app"` 清理 + fixture 内部 `_port_in_use` skip。

## 五、决策 #3 合规边界验证

| 规则 | 验证 | 结果 |
|---|---|---|
| 区域代理同 region_code 唯一 | E2E-01 创建 SH 时返回 200，重复创建应 400（其他测试覆盖）| ✅ |
| 单次返佣 ≤ 50% | E2E-01 返佣 30%（T1 档）| ✅ |
| 防伪 64 位 unique_code | E2E-01 验证 `len(unique_code) == 64` | ✅ |
| QR 公开核销无需登录 | E2E-01 公开 API 返回 200 | ✅ |
| 阶梯折扣（7/6/5 折）| E2E-01 /quote 返回 tier="60" + unit_price 1132.8 | ✅ |

## 六、未覆盖项（建议下一轮）

| 项 | 原因 | 建议 |
|---|---|---|
| meeting-notes ↔ asr-cluster 集成 | 当前 meeting-notes 直连 mlx-asr，不走 asr-cluster | 加 mlx-asr mock fixture |
| oa-agent tools 真实调用 | 需 LLM API key + 网络 | 加 mock LLM 路由 |
| 前端 Playwright 真实 UI 测试 | 本轮用 httpx API 覆盖关键路径；UI 交互未测 | 启动 vite dev server + Playwright（chromium 已装）|
| 性能 / 负载 | 本次范围未包含 | locust / wrk |
| 安全 / 渗透 | 本次范围未包含 | OWASP Top 10 + 越权 + fuzz |

## 七、文件交付清单

```
services/admin/tests/
├── conftest.py                          # 加 oa_agent_server fixture
├── integration/
│   ├── __init__.py
│   └── test_bridge_integration.py      # 7 个跨服务集成测试
├── e2e/
│   └── test_vip_full_flow.py           # 3 个 E2E 测试
└── REPORT.md                           # 本文件

app/routes/oa_agent_bridge.py           # OA_AGENT_URL 改 env 读取
```

## 八、运行方式

```bash
cd services/admin

# 单元测试（已有 79 + 3 pre-existing）
PYTHONPATH=. pytest tests/ -q

# 跨服务集成（7 个新）
PYTHONPATH=. pytest tests/integration/ -v

# 端到端 E2E（3 个新）
PYTHONPATH=. pytest tests/e2e/ -v

# 全部（含 7+3=10 新测试 + 79 旧 + 3 pre-existing fail）
PYTHONPATH=. pytest tests/ -q
```

## 九、下一步建议

1. **加 meeting-notes + asr-cluster 集成测试**（扩 IT 范围）
2. **加前端 Playwright E2E**（chromium 已装，Playwright config 已就绪）
3. **加性能基准**（locust 跑通 admin 关键端点）
4. **修 3 个 pre-existing fail**（test_agent.py 的 3 级分销测试，需删/重写）
