# VIP 卡旅游产品 · 内容管理模块研究报告

> 2026-07-14 · 业务形态 **A+C**（高端订制游 + 目的地权益卡）· 供"内容管理模块 + 产品介绍页"开发参考
> 本研究为 zcf:workflow「先研究后开发」阶段交付，确认方案后再进入开发。

---

## 背景与目标

为 VIP 卡旅游产品新增：
1. **内容管理模块**（admin 后台 CMS）：管理产品介绍页的图文/视频/行程/价格/权益素材
2. **产品介绍页**（前端公开页）：展示订制游（A）+ 权益卡（C）产品

业务形态：**A（高端订制游，一单一议）+ C（目的地权益卡，权益聚合）** 混合。

---

## 第一部分：产品介绍页内容结构（行业范例）

### 通用板块（2026 行业共识）

| 板块 | 订制游（A） | 权益卡（C） |
|------|------------|------------|
| **Hero** | 目的地大图 + 标题 + 一句价值 | 卡面视觉 + 核心权益摘要 |
| **内容主体** | 每日行程分解 / 亮点 / 服务流程 | 权益清单 + 合作商户列表 |
| **价格** | 阶梯报价 / 按需询价 | 卡面值 / 权益总价 / 折扣对比 |
| **信任** | 案例展示 / 顾问介绍 / 客户评价 | 合作商户 logo / 使用案例 / 销量 |
| **CTA** | 立即咨询 / 定制行程 | 立即购买 / 查看权益明细 |

### 订制游（A）特有
- **行程分解**：Day-by-Day（每日：交通/景点/餐饮/住宿/描述）
- **服务流程**：咨询 → 方案 → 确认 → 出行 → 售后
- **顾问卡片**：专属顾问（头像/资历/案例数）
- **定制案例**：过往案例（目的地/天数/主题/客户评价）

### 权益卡（C）特有
- **权益清单**：明细（权益项 / 价值 / 数量 / 适用商户）
- **合作商户**：商户卡片（logo / 地址 / 权益内容）
- **使用规则**：有效期 / 预约方式 / 退换政策
- **性价比对比**：权益总价 vs 卡面值

### 参考来源
- [Design Monks · 旅游网站 UX 标准](https://www.designmonks.co/blog/travel-website-design-examples)
- [99designs · 旅游网站设计灵感](https://99designs.com/inspiration/websites/travel)
- [Landing Page Flow · 行程页范例](https://www.landingpageflow.com/example/travel-itineraries)
- [Colorlib · 30 旅游网站案例](https://colorlib.com/wp/travel-agency-website-examples/)

---

## 第二部分：CMS 技术方案

### 开源 Headless CMS 对比（2026 共识）

| CMS | 定位 | 优势 | 劣势 | 适合本项目 |
|-----|------|------|------|-----------|
| **Strapi** | 自托管通用 CMS | 最大生态、成熟、插件多 | 独立 Node 服务、认证割裂 | ❌ 重复造 admin |
| **Directus** | 包装现有 SQL DB | 即时包装 PG、数据所有权 | 独立服务、学习成本 | ⚠️ 多余（已有 admin） |
| **Payload** | 现代 Headless | 开发者友好、TS、灵活 | 独立 Node 服务 | ❌ 同上 |
| **AdminJS** | Admin 框架 | 可嵌入 Node 应用 | 非 Python 栈 | ❌ 栈不符 |

来源：[focusreactive 2026 CMS 对比](https://focusreactive.com/blog/compare-open-source-cms-in-2026/) · [TECHSY 2026](https://techsy.io/en/blog/best-headless-cms-2026) · [Strapi vs Directus vs Payload](https://hungvu.tech/strapi-vs-directus-vs-payload-headless-cms-comparison) · [Reddit r/selfhosted](https://www.reddit.com/r/selfhosted/comments/1hrucxw/opensource_headless_cms_suggestions/)

### ⭐ 推荐：自建内容管理模块（扩展现有 admin）

**理由（DRY/KISS）**：
1. 项目已有 admin（FastAPI + SQLAlchemy + RBAC + JWT + Vue 前端）—— **不缺 admin 框架**
2. 引入独立 CMS 会：① 多一个独立服务（部署/运维成本翻倍）② 认证割裂（两套登录态）③ 数据分散（CMS 库 vs 业务库）
3. 内容管理本质 = CRUD + 富文本 + 素材上传，现有 admin 完全能扩展

**方案**：admin 加 `cms` 业务域（`routes/cms/` + `models/cms.py` + `schemas/cms.py`），复用现有 RBAC/JWT/部署/前端框架。

---

## 第三部分：内容结构设计建议

### 内容模型（A+C 统一抽象）

**旅游产品 `TourProduct`**（type 区分 A/C）：
```
id, title, slug(URL), type(custom|pass)
destination, theme(海岛|亲子|商务|蜜月...)
cover_image, gallery(图集 JSON), video_url
summary, content(富文本)
highlights(亮点 JSON)
status(draft|published|archived), sort
seo_title, seo_description
published_at, created_at, updated_at
```

**订制游扩展 `TourCustom`**：
```
product_id(关联)
itinerary(行程 JSON: [{day, title, transport, spots[], meals, hotel, description}])
service_flow(服务流程 JSON)
price_mode(inquiry|tier), price_tiers(阶梯报价 JSON?)
consultant_ids(顾问关联)
```

**权益卡扩展 `TourPass`**：
```
product_id(关联)
face_value(卡面值), total_worth(权益总价)
valid_period, usage_rules
benefits(权益 JSON: [{name, value, quantity, merchant_id}])
merchant_ids(合作商户关联)
```

**素材库 `MediaAsset`**：
```
id, name, type(image|video), url, size, alt, tags[]
uploaded_by, created_at
```

**合作商户 `Merchant`**（权益卡 C 用）：
```
id, name, logo, address, contact, benefit_desc, location(geo?)
```

### 与现有 admin 集成点

| 集成 | 方式 |
|------|------|
| RBAC | 新权限码 `cms:product:{list,save,publish}` + `cms:media:upload` |
| 菜单 | `seed.py` 加"内容管理"菜单（产品列表 / 素材库） |
| 认证 | 复用 JWT + `get_current_user` |
| 素材存储 | 复用 meeting-notes 上传模式（`upload_dir` + `_safe_filename` + 大小校验） |
| 前端 | `apps/web/src/views/cms/`（ProductList / ProductEdit / MediaLibrary） |
| 公开介绍页 | `/product/:slug`（无需登录，复用防伪核销页 `verify` 的公开访问模式） |

### 富文本编辑器选型（前端）
- **TipTap**（推荐）：Vue 友好、模块化、可嵌入 Element Plus
- wangEditor：中文友好、开箱即用
- 输出 HTML，展示端用 DOMPurify 净化（复用 `OaAgent.vue` 的 renderMd/XSS 防护模式）

---

## 开发顺序建议（确认方案后）

1. **素材库** MediaAsset（上传/列表/复用）—— 其他模块的基础
2. **产品 CRUD** TourProduct + A/C 扩展（admin 后台）
3. **富文本编辑**（TipTap 集成）
4. **前端介绍页** `/product/:slug`（公开页，按 A/C 模板渲染）
5. **测试**（复用现有 pytest/vitest 体系）

---

## 参考来源汇总
- [focusreactive · 2026 开源 CMS 对比](https://focusreactive.com/blog/compare-open-source-cms-in-2026/)
- [TECHSY · 2026 Headless CMS](https://techsy.io/en/blog/best-headless-cms-2026)
- [Strapi vs Directus vs Payload 详细对比](https://hungvu.tech/strapi-vs-directus-vs-payload-headless-cms-comparison)
- [Design Monks · 旅游网站 UX](https://www.designmonks.co/blog/travel-website-design-examples)
- [99designs · 旅游网站灵感](https://99designs.com/inspiration/websites/travel)
- [Landing Page Flow · 行程页](https://www.landingpageflow.com/example/travel-itineraries)
