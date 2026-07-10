# kk-mis · 企业 MIS 管理系统

> 企业一体化管理平台：企业管理 / 资产 / 代理销售 / 卡券 / 财务 / 会议纪要 AI 整理

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-MVP%20in%20progress-yellow.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)]()
[![Vue](https://img.shields.io/badge/Vue-3.5+-green.svg)]()

---

## 📦 模块规划

| # | 模块 | 优先级 | 状态 |
|---|---|---|---|
| 1 | **会议纪要 AI 整理** | P0 | 🚧 开发中 |
| 2 | 卡券 / VIP 卡 / 代金券 | P1 | ⏳ |
| 3 | 代理销售 / 分销 | P1 | ⏳ |
| 4 | 财务统计（复式记账）| P0 | ⏳ |
| 5 | 资产管理（实物 + 非实物）| P1 | ⏳ |
| 6 | 企业管理（RBAC）| P0 | ⏳ |

## 🛠 技术栈

- **后端**：Python 3.11+ / FastAPI / SQLModel / LangGraph
- **前端**：Vue 3 + TypeScript + Element Plus
- **数据库**：PostgreSQL 13+
- **缓存/队列**：Redis 7+
- **ASR**：阿里云通义听悟（云）
- **LLM**：通义千问 / 豆包（云）
- **部署**：Docker Compose + Nginx + 云服务器

## 🚀 快速开始

```bash
# 克隆
git clone https://github.com/changzhi777/kk-mis.git
cd kk-mis

# 待初始化（开发中）
# docker compose up -d
```

## 📂 目录结构（规划）

```
kk-mis/
├── services/
│   ├── meeting-notes/      # 会议纪要 AI 服务（FastAPI + LangGraph）
│   ├── finance/            # 财务核心
│   ├── asset/              # 资产管理
│   ├── voucher/            # 卡券
│   └── agent/              # 代理销售
├── apps/
│   └── web/                # Vue3 前端
├── infra/
│   ├── docker-compose.yml
│   └── nginx/
├── docs/
│   ├── architecture.md
│   └── api.md
├── .zcf/
│   └── plan/               # 工作流计划与归档
│       ├── current/
│       └── history/
└── README.md
```

## 📜 License

MIT © 2026 changzhi777