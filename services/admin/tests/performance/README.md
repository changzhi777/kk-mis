# 性能 / 负载基准（locust）

## 前置条件

```bash
pip install locust
```

## 启动 admin（被测服务）

```bash
cd mis-system/services/admin
DB_DRIVER=sqlite SQLITE_PATH=./perf.db \
JWT_SECRET=perf-test-secret-1234567890123456 \
INIT_ADMIN_PASSWORD=admin1234 \
LOG_LEVEL=WARNING \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8300 --log-level warning
```

## 跑性能基准

```bash
cd mis-system/services/admin

# 50 并发 × 30 秒（基线）
locust -f tests/performance/locustfile.py \
  --host=http://127.0.0.1:8300 \
  --headless -u 50 -r 10 -t 30s \
  --html tests/performance/report.html
```

## 跑可视化（带 UI）

```bash
locust -f tests/performance/locustfile.py --host=http://127.0.0.1:8300
# 打开 http://localhost:8089 配置 Users/Spawn rate/Run time
```

## 覆盖端点（决策 #3 关键路径）

| 端点 | 任务 | 用途 |
|---|---|---|
| `POST /auth/login` | on_start | 鉴权（基础）|
| `GET /agent/agents` | 5x | 列出区域代理（决策 #3 重构后）|
| `GET /agent/orders/quote` | 3x | 实时折扣报价（VIP 关键路径）|
| `GET /agent/orders` | 2x | 订单列表 |
| `GET /agent/yearly-commission` | 1x | 年度返佣 |
| `GET /asset/cards/verify/{code}` | 1x | 公开防伪核销（无鉴权）|

## 基线目标（决策 #5 低并发 < 100 QPS）

| 指标 | 目标 | 实测 |
|---|---|---|
| P95 延迟（所有端点）| < 200ms | 待测 |
| P99 延迟 | < 500ms | 待测 |
| 50 并发 × 30s 失败率 | < 0.1% | 待测 |
| QPS | > 50（单核）| 待测 |

## 性能瓶颈预警（决策 #5 触发升级）

| 阈值 | 触发动作 |
|---|---|
| 慢查询 > 200ms 持续出现 | 加索引 + EXPLAIN |
| 连接池等待 > 10ms | 调大 pool_size |
| 单表 > 5000 万行 | 分区表 / 归档冷数据 |
| 写 QPS > 500 | 评估读写分离 |

## 已知瓶颈（决策 #3 实施后）

- `func.extract("year", AgentOrder.created_at)` 不走索引 → yearly_commission 聚合慢
  - 建议：schema 加 `created_year` generated column + 复合 index `(agent_id, created_year, status)`
- `agent_orders.created_at` 单字段索引（已有）| 复合索引优化空间大
- `cards.py:generate` per-card 唯一性校验（5 次重试）| 大批量生成时延迟高
