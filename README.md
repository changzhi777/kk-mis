# kk-mis · 企业 MIS 管理系统

> 企业一体化管理平台：企业管理 / 资产 / 代理销售 / 卡券 / 财务 / 会议纪要 AI 整理

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)]()
[![Vue](https://img.shields.io/badge/Vue-3.5+-green.svg)]()
[![Status](https://img.shields.io/badge/status-MVP%20done-success.svg)]()

🌐 **线上入口**：`https://43.129.201.118/oa/`
📦 **GitHub**：https://github.com/changzhi777/kk-mis

---

## ✨ 已实现功能

### 🤖 AI 会议纪要（端到端跑通）
- 上传会议音频 → **本地 Mac MLX Whisper**（Belle 中文微调 + 标点）转写
- **GLM-4-plus** LLM 智能整理 → 摘要 + 要点 + 决策 + 行动项
- 完整链路：公网 → Nginx → meeting-notes → Tailscale VPN → Mac mlx-asr

### 🏗 多节点 ASR 集群架构
- 节点注册 / 心跳监控 / 健康检查 / 负载均衡 / 任务分发
- 当前 1 个 Mac M5 节点，可水平扩展更多 MLX 节点

### 🤖 三大 LLM 集成
| Provider | 类型 | 模型 |
|---|---|---|
| 智谱 GLM | 云 API | glm-4-plus |
| minimax | 云 API | MiniMax-Text-01 |
| oMLX | 本地 MLX | gemma-4-e4b-it-4bit |

### 🎨 Vue3 前端
- 上传页（拖拽、LLM 选择）
- 会议列表（分页、状态筛选）
- 详情页（轮询进度、纪要、行动项）
- Element Plus + TypeScript

---

## 📂 项目结构

```
kk-mis/
├── services/
│   ├── mlx-asr/                  # Mac 本地 ASR（MLX Whisper）
│   ├── asr-cluster/              # 多节点集群管理
│   └── meeting-notes/            # 主应用 FastAPI（公网入口）
├── apps/
│   └── web/                      # Vue3 前端
├── infra/
│   ├── systemd/                  # 服务管理
│   └── nginx/                    # 反向代理配置
├── docs/                         # 文档
└── .zcf/plan/                    # 工作流归档
```

---

## 🚀 部署

### 服务器（43.129.201.118）
```bash
# systemd 服务
systemctl status kk-mis-meeting-notes.service
systemctl status kk-mis-asr-cluster.service
systemctl restart kk-mis-meeting-notes.service
```

### Mac（MLX 节点）
```bash
cd services/mlx-asr
source .venv/bin/activate
bash start.sh  # 监听 :9000
```

### 公网入口
- 前端：`https://43.129.201.118/oa/`
- API 文档：`https://43.129.201.118/oa/docs`
- 健康检查：`https://43.129.201.118/oa/health`

---

## 🧪 端到端测试

```bash
# 上传会议音频
curl -X POST https://43.129.201.118/oa/api/v1/meetings/upload \
  -F "audio=@meeting.mp3" \
  -F "title=产品评审会" \
  -F "language=zh" \
  -F "llm_provider=glm"

# 查询处理结果
curl https://43.129.201.118/oa/api/v1/meetings/1
```

---

## 🛠 技术栈

| 类别 | 选型 |
|---|---|
| 后端框架 | FastAPI 0.139 + SQLAlchemy 2.0 (async) |
| 数据库 | PostgreSQL 15 |
| 缓存/队列 | Redis 7 |
| LLM | 智谱 GLM-4-Plus / minimax MiniMax-Text-01 |
| 本地 LLM | oMLX (OpenAI 兼容) |
| ASR | MLX Whisper + Belle-whisper-large-v3-zh-punct |
| 前端 | Vue 3.5 + TypeScript + Element Plus + Vite |
| 反代 | Nginx (SSL + 路径前缀 /oa/) |
| VPN | Tailscale（Mac ↔ Server） |
| 服务管理 | systemd |

---

## 📜 License

MIT © 2026 changzhi777