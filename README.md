# kk-mis · 企业 MIS 管理系统

> 5 大模块一体化：会议纪要 / 企业管理(RBAC) / 财务统计 / 资产管理(卡券) / 代理销售(3级分销)

🌐 **线上**：`https://aisport.tech/oa/` · 📦 **仓库**：https://github.com/changzhi777/kk-mis

---

## 五大模块

| 模块 | 功能 | 服务 |
|---|---|---|
| 🤝 会议纪要 | 上传音频→ASR 转写→LLM 整理(摘要/要点/决策/行动项) | `services/meeting-notes` + `mlx-asr` |
| 🏢 企业管理 | 用户/角色/权限(RBAC)/部门 + JWT 认证 + 动态菜单 + 审计日志 | `services/admin` |
| 💰 财务统计 | 收支流水/账户/科目/报表(ECharts) | `services/admin` |
| 🎫 资产管理 | 卡券(批次-库存-核销)全生命周期，4类型(VIP/代金券/兑换/储值) | `services/admin` |
| 🔗 代理销售 | 3级分销(企业→一级→二级)，订单/分润记账 | `services/admin` |

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python FastAPI + SQLAlchemy 2.0 async |
| 数据库 | PostgreSQL（`kk_mis` 库，两服务共用）+ Redis |
| 前端 | Vue 3.5 + TypeScript + Element Plus + Vite（Teal 湖青，暗色+响应式+按需引入） |
| ASR | Mac 本地 MLX Whisper（Belle-whisper-zh-punct） |
| LLM | 智谱 GLM-4.7 / minimax / 本地 oMLX |
| 部署 | Nginx（`/oa/` 反代）+ systemd + Tailscale VPN(Mac↔Server) |

## 仓库结构

```
mis-system/
├── apps/web/                      # Vue3 前端
│   └── src/{views(15页), components, composables, stores, api}
├── services/
│   ├── meeting-notes/             # 会议纪要 FastAPI（:8200）
│   ├── admin/                     # 企业+财务+资产+代理 FastAPI（:8300）
│   ├── mlx-asr/                   # Mac 本地 ASR（:9000）
│   └── asr-cluster/               # ASR 集群管理（:9100）
└── infra/                         # 部署配置（仓库外，scp 部署）
    ├── systemd/                   # kk-mis-{meeting-notes,admin}.service
    ├── nginx/                     # aisport.tech 内联（/oa/api + /oa/admin/api）
    └── scripts/                   # backup_pg / health_check / reconcile
```

## 部署架构

```
浏览器 → Nginx(443) → /oa/api/        → meeting-notes:8200（会议纪要，验 JWT）
                     → /oa/admin/api/ → admin:8300（企业/财务/资产/代理，验 JWT）
                     → /oa/           → 前端 dist
admin:8300 → Tailscale → Mac mlx-asr:9000（ASR）
admin:8300 → PostgreSQL kk_mis + Redis
```

- **统一认证**：admin 签 JWT（admin/admin1234），会议纪要接入同一 JWT
- **动态菜单**：`/auth/menus` 按用户权限返回菜单树，前端递归渲染

## 运维（服务器 crontab）

| 时间 | 脚本 | 作用 |
|---|---|---|
| 03:00 | `backup_pg.sh` | PG 每日备份，保留 7 天 → `/backup/pg/` |
| 03:30 | `reconcile.sh` | 卡券库存/分润/订单对账 → `/var/log/kk-mis/asset-reconcile.log` |
| */5 | `health_check.sh` | 服务 health 检查，异常记日志 + webhook 告警 |

- **审计**：admin 中间件自动记录所有写操作（POST/PUT/DELETE）→ `audit_log` 表，前端 `/system/audit` 查看
- **systemd**：服务挂自动重启（Restart=always）

## 开发

```bash
# 前端
cd apps/web && pnpm install && pnpm dev      # http://localhost:5173/oa/

# 后端 admin
cd services/admin && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash start.sh                                 # http://localhost:8300

# 后端 meeting-notes
cd services/meeting-notes && source .venv/bin/activate
bash start.sh                                 # http://localhost:8200
```

## 生产部署

```bash
# 服务器（43.129.201.118 / aisport.tech）
git pull origin main
systemctl restart kk-mis-admin kk-mis-meeting-notes

# 前端
cd apps/web && pnpm build
# dist 上传到服务器 /var/www/kk-mis/web/

# Mac ASR 节点
cd services/mlx-asr && bash start.sh          # :9000
```

## 默认账号

`admin / admin1234`（超管，首次启动 seed 自动创建）

## License

MIT © 2026 changzhi777
