[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [apps](../) > **web**

# apps/web · Vue3 前端

## 变更记录 (Changelog)

- 2026-07-14 14:54:32 — 续跑增量更新（zcf:init-project）：
  - **CMS 内容管理前端视图全完成**（详见 memory `project-cms-module-2026-07-14.md`）：`src/views/cms/` 新增 11 视图（ProductList / ProductEdit / MediaLibrary / MerchantList / LeadList / OrderList / CouponList / ReviewList / Dashboard / ProductView / Search）+ RichEditor（TipTap）+ MediaPicker 弹窗 + `stores/endUser` C 端账号 store；公开页 `/product/:slug`（无 /oa 前缀，SEO 友好）；移动端 H5 响应式；vue-tsc 0 / vitest 46 全过；
  - **前端 `any` 159→87**（`api/admin.ts` 类型化 13→0 + 建 `getApiError(e: unknown)` DRY 39 处 catch + `as any`→`as const` 13→0 + 9 个新 interface；剩 87 个 `ref<any[]>` 为 EP `el-table` row 框架限制保留）；
  - **vitest 覆盖扩展**至 46 个（含 CMS 视图 + 状态映射 + agent UI + Detail 导出 + XSS 防护）；
  - **清理底部重复 Changelog 段**（原 L260-264 孤立段删除）。
- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/apps/` 而非仓库根，改为 `../../../CLAUDE.md`；[mis-system] 链接从 `../` 改为 `../../CLAUDE.md`）；内容保持（vitest 2.1.9 + jsdom + 30 passed 仍准确）。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑层级加深（仓库根 → mis-system → apps → web），内容保持。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-cms` 系统的统一前端 SPA，整合 **7 大模块**（会议纪要 / 企业管理 / 财务 / 资产 / 代理 / OA / **CMS 内容管理**）的全部 UI。Teal 湖青主题（`#0d9488`），按需引入 Element Plus（bundle 减小 63%）。

设计要点：
- **单一代码库**：所有 view 在 `apps/web/src/views/` 下按业务域分目录（system / finance / asset / agent / oa / **cms** / oauth）
- **统一 RBAC**：路由级 `meta.permission` 守卫 + 后端菜单动态下发
- **生产部署**：打包后通过 nginx 在 `/oa/` 子路径下对外（**CMS 公开页 `/product/:slug` 例外**，无 /oa 前缀便于 SEO）
- **CMS 公开页**：`/product/:slug` 公开访问（无需登录），含 SEO meta + 行程/权益/评价/相关推荐 + 目的地天气卡片

---

## 入口与启动 (Entry Point)

- **入口 HTML**: `index.html`（`<div id="app"></div>`）
- **入口 TS**: `src/main.ts`
  - 加载样式顺序：EP 暗色 → light.css → dark.css → sidebar.css → base.scss
  - Pinia + Router 注入
  - EP 组件/API 由 `unplugin-auto-import` 按需加载
- **根组件**: `src/App.vue`

### 启动命令
```bash
cd apps/web
pnpm install          # 装依赖（pnpm，monorepo 风格）
pnpm dev              # vite dev server :5173（带 /api /llm proxy → :8000）
pnpm build            # vue-tsc 类型检查 + vite build 打包到 dist/
pnpm preview          # 预览打包产物
```

### 开发期代理（vite.config.js — ⚠️ .js 优先于 .ts）

> **⚠️ 重要坑**：`apps/web/` 同时有 `vite.config.js` + `vite.config.ts`，**vite 默认加载 .js**。改 `.ts` 无效——改 dev 配置务必改 `.js`（或两者同步，本项目已让两者一致）。

- `/api` → `http://localhost:8000`（meeting-notes）
- `/llm` → `http://localhost:8000`（meeting-notes LLM 路由）
- `/admin` → `http://localhost:8300`（admin，含 CMS / office 桥）

**base '/oa/' 前缀修复（2026-07-15）**：前端 baseURL（`BASE_URL+'admin'` = `/oa/admin`）请求 path 含 /oa，而 proxy key `/admin` 匹配 raw path → 不匹配 → 404（整个前端 dev 调后端都 404）。修复：`devStripOaPrefix` plugin（`configureServer` 中间件，不返回函数 = 前置于 proxy）把 `/oa/admin|api|llm` 去 /oa 前缀让原 proxy 匹配。prod 走 nginx 不受影响。

> 生产环境由 nginx 反代到 `:8200/:8300`，前缀分别为 `/oa/api/` 和 `/oa/admin/`。

---

## 对外接口 (External Interfaces)

### 路由清单（src/router/index.ts）

所有 admin/meeting/oa 路由 base = `/oa/`；**CMS 公开页 `/product/:slug` 例外**。下表是相对路径：

| 路径 | 名称 | 权限码 | 业务域 |
|------|------|--------|--------|
| `/login` | login | 公开 | - |
| `/register` | register | 公开 | - |
| `/oauth/callback` | oauth-callback | 公开 | - |
| `/dashboard` | dashboard | - | 工作台 |
| `/upload` | upload | - | meeting |
| `/list` | list | - | meeting |
| `/meetings/:id` | detail | - | meeting |
| `/system/user` | sys-user | `system:user:list` | system |
| `/system/role` | sys-role | `system:role:save` | system |
| `/system/permission` | sys-perm | `system:permission:save` | system |
| `/system/dept` | sys-dept | `system:dept:save` | system |
| `/system/audit` | sys-audit | `system:audit:view` | system |
| `/announcement` | oa-announcement | `oa:announcement:save` | oa |
| `/leave` | oa-leave | - | oa |
| `/expense` | oa-expense | - | oa |
| `/approval` | oa-approval | - | oa |
| `/report` | oa-report | - | oa |
| `/attendance` | oa-attendance | - | oa |
| `/finance/transaction` | fin-tx | `finance:transaction:save` | finance |
| `/finance/account` | fin-acc | `finance:account:save` | finance |
| `/finance/category` | fin-cat | `finance:category:save` | finance |
| `/finance/report` | fin-rpt | `finance:report:view` | finance |
| `/asset/type` | asset-type | `asset:type:list` | asset |
| `/asset/batch` | asset-batch | `asset:batch:list` | asset |
| `/asset/card` | asset-card | `asset:card:list` | asset |
| `/asset/redemption` | asset-redemption | `asset:card:list` | asset |
| `/agent/agent` | agent-agent | `agent:list` | agent |
| `/agent/region` | agent-region | `agent:list` | agent |
| `/agent/order` | agent-order | `agent:order:list` | agent |
| `/agent/commission` | agent-commission | `agent:commission:view` | agent |
| `/verify/:code` | verify-card | **public**（防伪核销） | — |
| **`/cms/products`** | **cms-products** | **`cms:product:list`** | **🆕 cms（2026-07-14）** |
| **`/cms/products/edit/:id?`** | **cms-product-edit** | **`cms:product:save`** | **🆕 cms** |
| **`/cms/media`** | **cms-media** | **`cms:media:list`** | **🆕 cms** |
| **`/cms/merchants`** | **cms-merchants** | **`cms:merchant:list`** | **🆕 cms** |
| **`/cms/leads`** | **cms-leads** | **`cms:lead:list`** | **🆕 cms** |
| **`/cms/orders`** | **cms-orders** | **`cms:order:list`** | **🆕 cms** |
| **`/cms/coupons`** | **cms-coupons** | **`cms:coupon:list`** | **🆕 cms** |
| **`/cms/reviews`** | **cms-reviews** | **`cms:review:list`** | **🆕 cms** |
| **`/cms/dashboard`** | **cms-dashboard** | **`cms:stats:view`** | **🆕 cms** |
| **`/cms/search`** | **cms-search** | - | **🆕 cms（公开搜索）** |
| **`/product/:slug`** | **product-view** | **public**（无需登录，**无 /oa 前缀 SEO**） | **🆕 cms** |

### 路由守卫（src/router/index.ts）
1. `meta.public` 公开页（login/register/oauth/callback/**product-view**/cms-search/verify-card）直接放行
2. 未登录跳 `/login?redirect=<原路径>`
3. `meta.permission` 不匹配跳 `/`

### API 客户端（src/api/）

| 文件 | baseURL | 用途 |
|------|---------|------|
| `admin.ts` | `import.meta.env.BASE_URL + 'admin'` | 企业/财务/资产/代理/OA/CMS 全部接口（**2026-07-14 全量类型化**） |
| `meetings.ts` | `import.meta.env.BASE_URL + 'api'` | 会议上传/列表/详情 |
| `cms-public.ts` | `import.meta.env.BASE_URL + 'admin/api/v1/cms'` | 🆕 CMS 公开接口（产品详情/搜索/天气/下单/评论） |
| `endUser.ts` | 同上 | 🆕 C 端账号（注册/登录/me） |

- 拦截器统一注入 JWT（`Authorization: Bearer xxx`）
- 401 自动清登录态并跳登录
- `adminApi.resource(path)` 提供通用 CRUD（list/get/create/update/remove）
- `adminApi.downloadCsv()` 处理文件下载（解析 `Content-Disposition`）
- **`getApiError(e: unknown)` 统一错误处理**（2026-07-14 统一，39 处 catch 复用 DRY）

---

## 关键依赖与配置 (Dependencies & Config)

### package.json 关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| vue | ^3.5.0 | 核心框架 |
| vue-router | ^4.4.0 | 路由 |
| pinia | ^2.2.0 | 状态（含 `endUser` store for CMS C 端） |
| element-plus | ^2.8.0 | UI 库（按需） |
| @element-plus/icons-vue | ^2.3.0 | 图标 |
| axios | ^1.7.0 | HTTP |
| echarts | ^6.1.0 | 图表（财务/看板/CMS 漏斗） |
| **@tiptap/vue-3** | ^2.x | 🆕 CMS 富文本编辑器（ProductEdit） |
| **@tiptap/starter-kit** | ^2.x | 🆕 CMS 富文本扩展 |

### Dev 依赖

| 包 | 用途 |
|----|------|
| vite ^5.4.0 | 构建 |
| @vitejs/plugin-vue ^5.1.0 | SFC |
| typescript ^5.6.0 | 类型 |
| vue-tsc ^2.1.0 | 类型检查（**0 errors** for CMS） |
| sass ^1.101.0 | 样式 |
| unplugin-auto-import ^21.0.0 | 自动导入 vue/router/pinia/EP API |
| unplugin-vue-components ^32.1.0 | 自动注册 EP 组件 |
| **vitest** | ^2.1.9 | 测试（jsdom + @vue/test-utils） |

### vite.config.ts 关键配置
- `base: '/oa/'`（生产子路径；CMS 公开页 base 例外）
- SCSS 全局注入 `@/styles/element/_variables.scss`（覆盖 EP 主题色）
- dev proxy：`/api`、`/llm` → `:8000`；`/admin` → `:8300`（含 CMS）
- `vitest.config.ts`：`environment: 'jsdom'`

---

## 数据模型 (Data Models)

前端不持有业务模型，主要在 `src/types/`：
- `index.ts` — 通用类型（**2026-07-14 新增 9 接口**：MenuItem / PermissionNode / Attendance / Commission / WorkReport / TourProduct / MediaAsset / Merchant / EndUser / EpTagType）
- `auto-imports.d.ts` — `unplugin-auto-import` 自动生成（**勿手改**）
- `components.d.ts` — `unplugin-vue-components` 自动生成（**勿手改**）

### 用户状态（Pinia store: src/stores/user.ts）

```ts
useUserStore = {
  token: Ref<string>          // localStorage 'kk-cms-admin-token'
  userInfo: Ref<UserInfo | null>  // { id, username, name, roles, permissions }
  menus: Ref<any[]>           // 后端拉取的菜单树

  isLogin, roles, permissions, isSuperAdmin  // computed
  hasPermission(code: string): boolean
  login(username, password)
  register(payload)
  applyOAuthLogin(accessToken, refreshToken)  // OAuth 回调用
  fetchMenus() / fetchMe() / logout()
}
```

### 🆕 C 端账号状态（Pinia store: src/stores/endUser.ts）

```ts
useEndUserStore = {
  token: Ref<string>          // localStorage 'kk-cms-cms-end-user-token'（独立于 admin token）
  userInfo: Ref<EndUser | null>  // { id, phone, nickname, ... }
  isLogin: ComputedRef<boolean>
  login(phone, password) / register(payload) / logout() / fetchMe()
}
```

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-14 续跑重置基线）
- ✅ vitest 2.1.9 + jsdom + @vue/test-utils（2026-07-12 配置）
- ✅ **46 个测试全过**（2026-07-14 扩展，含 CMS 视图 + 状态映射）：
  - `stores/user` — RBAC 权限判断
  - `router/guard` — 路由守卫
  - `views/detail-export` — Markdown 构建
  - `views/render-md` — XSS 防护（DOMPurify）
  - `api/admin-agent` — agent API 方法 + resource CRUD（mock axios）
  - `views/agent-status-helpers` — OrderList/Commission 状态映射纯函数
  - **`stores/endUser`** — C 端账号
  - **`views/cms-*`** — CMS 11 视图覆盖

### 测试命令
```bash
pnpm test          # run 模式
pnpm test:watch    # watch 模式
pnpm test:coverage # 覆盖率
```

### 环境要求
- `environment: 'jsdom'`（happy-dom 与 DOMPurify 不兼容）
- happy-dom 在 SSR/单元测试时 localStorage 注入时机不稳，已用内存 mock 替代

### 类型检查
```bash
pnpm build   # vue-tsc -b 内含完整类型检查
```

> 2026-07-14：`any` 159→87（api/admin.ts 13→0 + getApiError DRY + `as any`→`as const` 13→0 + 9 个新 interface）；剩 87 个 `ref<any[]>` 为 EP `el-table` row 框架限制保留（业界通行做法，ROI 低可暂缓）

---

## 常见问题 (FAQ)

**Q1: 改了路由但页面 404？**
A: 检查 `createWebHistory('/oa/')` 是否一致；生产环境确认 nginx `/oa/` location 配置正确。**CMS 公开页 `/product/:slug` 例外**（无 /oa 前缀），nginx 需单独配 location。

**Q2: EP 组件样式不对？**
A: 暗色模式需要 `element-plus/theme-chalk/dark/css-vars.css` 在 custom CSS **之前**引入（见 `main.ts`）。

**Q3: 登录后菜单空白？**
A: 检查 `userStore.fetchMenus()` 是否成功（401 时静默清空）；用 admin/admin123 登录验证种子数据。

**Q4: 修改主题色没生效？**
A: 主题色变量在 `src/styles/element/_variables.scss`，SCSS 编译期注入；检查 `vite.config.ts` 的 `additionalData`。

**Q5: axios 请求 404？**
A: dev 检查 `vite.config.ts` 的 proxy；prod 检查 nginx 反代 `/oa/api/` 与 `/oa/admin/`。

**Q6: CMS 公开页 SEO 不收录？**
A: 确认 `<meta name="robots" content="index,follow">` + `/product/:slug` 返回服务端渲染或预渲染（当前 SPA 需考虑 SSG/预渲染方案）。

**Q7: CMS 真发卡链路？**
A: 后端 `cms/orders/{id}/pay` → `payment.py:MockGateway.pay()` → `cms/orders/{id}/issue-card` → `asset/cards` 实际写入；前端调用顺序：选产品→加购物车→下单→pay→issue-card→跳成功页（含卡号 + QR URL）。

---

## 相关文件清单 (Key Files)

### 入口与配置
- `index.html` — Vite HTML 模板
- `package.json` — 依赖与脚本
- `vite.config.ts` — 构建配置（proxy / 自动导入 / SCSS）
- **`vitest.config.ts`** — 测试配置（jsdom）

### 应用骨架
- `src/main.ts` — 应用启动
- `src/App.vue` — 根组件
- `src/env.d.ts` — 环境类型

### 路由 / Store / API
- `src/router/index.ts` — 全部路由 + 守卫（含 CMS 11 + 公开页 `/product/:slug`）
- `src/stores/user.ts` — 用户/登录态/RBAC
- **`src/stores/endUser.ts`**（🆕）— C 端账号状态
- `src/api/admin.ts` — admin 服务 API 客户端（**2026-07-14 全量类型化**）
- `src/api/meetings.ts` — meeting-notes API 客户端
- **`src/api/cms-public.ts`**（🆕）— CMS 公开接口
- **`src/api/endUser.ts`**（🆕）— C 端账号接口
- **`src/utils/api-error.ts`**（🆕）— `getApiError(e: unknown)` 统一错误处理

### 组件
- `src/components/AppSidebar.vue` — 主导航侧边栏（含 CMS 菜单）
- `src/components/TimeText.vue` — 相对时间显示
- `src/components/StatusTag.vue` — 会议状态标签
- `src/components/ThemeToggle.vue` — 主题切换
- **`src/components/RichEditor.vue`**（🆕）— TipTap 富文本编辑器（CMS ProductEdit 用）
- **`src/components/MediaPicker.vue`**（🆕）— 媒体素材选择弹窗
- `src/composables/useTheme.ts` — 主题 hook
- `src/composables/useMeetingStatus.ts` — 会议状态 hook
- `src/composables/useMenuIcon.ts` — 菜单图标 hook

### View（业务页面）
- `src/views/Login.vue` / `Register.vue` — 登录注册
- `src/views/Dashboard.vue` — 工作台
- `src/views/Upload.vue` / `List.vue` / `Detail.vue` — 会议（含 marked + DOMPurify XSS 防护）
- `src/views/oauth/Callback.vue` — OAuth 回调
- `src/views/system/` — UserList / RoleList / PermissionList / DeptList / AuditLog
- `src/views/finance/` — TransactionList / AccountList / CategoryList / Report
- `src/views/asset/` — CardTypeList / BatchList / CardList / Redemption
- `src/views/agent/` — **RegionList**（区域代理）/ OrderList / Commission（2026-07-13 重构，删 AgentList）
- `src/views/asset/Verify.vue` — **防伪公开核销页**（扫码直达）
- `src/views/oa/` — Announcement / Leave / Expense / Approval / Report / Attendance
- **`src/views/cms/`**（🆕）— **CMS 11 视图**：
  - `ProductList.vue` — 产品列表（管理）
  - `ProductEdit.vue` — 产品编辑（TipTap 富文本 + MediaPicker）
  - `ProductView.vue` — **产品公开页 `/product/:slug`**（SEO + 行程/权益/评价 + 天气）
  - `MediaLibrary.vue` — 媒体素材库
  - `MerchantList.vue` — 商家管理
  - `LeadList.vue` — 询价线索
  - `OrderList.vue` — 订单管理
  - `CouponList.vue` — 优惠券
  - `ReviewList.vue` — 评论审核
  - `Dashboard.vue` — CMS 数据看板（ECharts 漏斗：浏览→询价→订单→支付）
  - `Search.vue` — 公开搜索
- **`src/views/office/`**（🆕 2026-07-15）— **办公协同（oa-agent 桥前端）**：
  - `OfficeCenter.vue` — **办公中心 `/office`**（el-tabs 三 demo：文档读取 read_* + docx 预览 mammoth/DOMPurify + 模板合并 docxtpl；调 `/api/v1/office/*` 桥 oa-agent）
  - `SheetSpike.vue` — Univer Sheets S2 可行性 spike（`/office/sheet-spike`）

### 样式（重设计进行中）
- `src/styles/theme/light.css` / `dark.css` / `sidebar.css` — 设计 Token
- `src/styles/element/_variables.scss` — EP 主题色覆盖（Teal 湖青 #0d9488）
- `src/styles/base.scss` — 全局重置

### 自动生成（勿改）
- `src/types/auto-imports.d.ts`
- `src/types/components.d.ts`
