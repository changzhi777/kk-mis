[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [apps](../) > **web**

# apps/web · Vue3 前端

## 变更记录 (Changelog)

- 2026-07-15 12:30:00 — 第三轮稳健版精细续跑（zcf:init-project）：
  - **`src/api/admin.ts` 精细深读完成**（243 行，详见下方 §8 "API 层 / admin.ts 深读"段）：
    - **实际方法签名数 ≈ 30 显式方法 + 1 通用 `resource<T>()` 工厂**，**非 145 个独立方法**——绝大多数端点通过 `resource(path)` 动态绑定（list/get/create/update/remove）；
    - **8 个本地 interface**：`UserInfo` / `LoginResult`（其余 6 个：MenuItem / PermissionNode / AttendanceRecord / AttendanceStats / WorkReport / CategoryReportItem / CommissionSummaryItem — **均从 `@/types` 导入**）+ `CommissionSummaryItem` 等类型化覆盖；
    - **`getApiError(e: unknown, fallback='操作失败')` 完整实现**（L43-50）：axios isAxiosError 提取 `response.data.detail` → Error.message → fallback 三级降级；
    - **拦截器链**：请求拦截注入 `Authorization: Bearer token`（动态 import `@/stores/user` 避免循环依赖）；响应拦截 401 自动清登录态并跳 `/login`；
    - **`resource<T>(path)` 工厂**（L231-239）返回 `{ list/get/create/update/remove }` 5 闭包，是 admin 端点覆盖率的关键（覆盖 100+ 通用 CRUD 端点）；
    - **`downloadCsv(path, params)`**（L217-229）处理 Content-Disposition 文件名解析 + Blob URL + 自动 `<a download>` 触发，通用 CSV 导出；
    - **CMS 11 router 接口补全**（2026-07-15）：`createVoucher` / `postVoucher` / `listVouchers` / `trialBalance` / `balanceSheet` / `incomeStatement`（复式记账 6 方法）+ `withdrawalBalance` / `listWithdrawals` / `requestWithdrawal` / `reviewWithdrawal`（A3 提现 4 方法）；
    - **OA 模块**：审批 `approveInstance` / `rejectInstance` / 考勤 `clockIn` / `clockOut` / `attendanceToday` / `attendanceMe` / `attendanceStats` / 工作汇报 `allReports` / `readReport` / 公告 `publishAnnouncement` / `archiveAnnouncement`；
    - **资产模块**：`generateCards` / `redeemCard` / `issueCard` / `voidCard`；
    - **代理模块**：`payOrder` / `completeOrder` / `commissionSummary` / `settleCommission`；
  - **87 个 `ref<any[]>` 来源澄清**（**修正 7-14 文档不准确**）：admin.ts 自身**已 0 个 `any`**；87 个 `ref<any[]>` 全在 `views/*.vue` 的 Element Plus `el-table` row 框架限制（`<el-table :data="rows">` + `el-table-column` slot props 推断为 `any`），**业界通行做法 ROI 低可暂缓**（或换 TableV2 / 自封装 `<KTable>`）；
  - **类型质量演化**：2026-07-14 `any` 159→87（api/admin.ts 13→0 + getApiError DRY + as any→as const 13→0 + 9 个新 interface）；2026-07-15 voucher 表单 5 个新 any 占位 + 4 个新 interface（Voucher/JournalEntry/OfficeHealth/ToolResult），**net 平**；
  - **未触碰 git**：mis-system 已 commit 11:42+11:55（hash 07bf105 + 9938ed6），文档改动仅在文件系统层。
- 2026-07-15 11:55:00 — 精细续跑（zcf:init-project）：UniverSheet.vue 实现细节补全（40 行 SFC + style）；默认导入 `@univerjs/preset-sheets-core` + zh-CN locale（**未懒加载，5.7MB 仍全量打包**——`manualChunks` 优化本次确认未做）。
- 2026-07-15 11:42:03 — 续跑增量更新（zcf:init-project）：财务复式记账前端 + A4 打印 + 工作台拖拽 + oa-agent 办公桥前端 + Univer 集成 + Storage 前端直传。
- 2026-07-15 — office 桥前端 + dev proxy 修复：`vite.config.js` 优先于 `.ts`（改 .ts 无效）+ `base:'/oa/'` 使 proxy `/admin` 不匹配前端 `/oa/admin` → 加 `devStripOaPrefix` plugin 修整个前端 dev 调后端 404。
- 2026-07-14 14:54:32 — 续跑增量更新（zcf:init-project）：CMS 内容管理前端视图全完成（11 视图 + RichEditor + MediaPicker + endUser store）；前端 `any` 159→87；vitest 覆盖扩展至 46 个。
- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑层级加深。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-cms` 系统的统一前端 SPA，整合 **8 大模块**（会议纪要 / 企业管理 / 财务（含**复式记账**）/ 资产 / 代理 / OA / **CMS 内容管理** / **oa-agent 办公协同**）的全部 UI。Teal 湖青主题（`#0d9488`），按需引入 Element Plus（bundle 减小 63%）。

设计要点：
- **单一代码库**：所有 view 在 `apps/web/src/views/` 下按业务域分目录（system / finance / asset / agent / oa / **cms** / **office** / oauth）
- **统一 RBAC**：路由级 `meta.permission` 守卫 + 后端菜单动态下发
- **生产部署**：打包后通过 nginx 在 `/oa/` 子路径下对外（**CMS 公开页 `/product/:slug` 例外**，无 /oa 前缀便于 SEO；**推广公开页 `/promo/:code` 同例**）
- **CMS 公开页**：`/product/:slug` 公开访问（无需登录），含 SEO meta + 行程/权益/评价/相关推荐 + 目的地天气卡片
- **复式记账 UI**：VoucherList 借贷平衡实时校验 + VoucherPrint A4 打印
- **办公中心**：OfficeCenter 三 tab（读取/预览/合并）+ 第 4 tab Univer 表格编辑
- **工作台拖拽**：Dashboard 卡片可拖拽布局，User.preferences JSON 持久化

---

## 入口与启动 (Entry Point)

- **入口 HTML**: `index.html`（`<div id="app"></div>`）
- **入口 TS**: `src/main.ts` — Pinia + Router 注入；EP 组件/API 由 `unplugin-auto-import` 按需加载
- **根组件**: `src/App.vue`

### 启动命令
```bash
cd apps/web
pnpm install
pnpm dev              # vite dev server :5173（带 /api /llm /admin proxy → :8000/:8300）
pnpm build            # vue-tsc 类型检查 + vite build 打包到 dist/
```

### 开发期代理（vite.config.js — ⚠️ .js 优先于 .ts）

> **⚠️ 重要坑**：`apps/web/` 同时有 `vite.config.js` + `vite.config.ts`，**vite 默认加载 .js**。改 `.ts` 无效——改 dev 配置务必改 `.js`。

- `/api` → `http://localhost:8000`（meeting-notes）
- `/llm` → `http://localhost:8000`（meeting-notes LLM 路由）
- `/admin` → `http://localhost:8300`（admin，含 CMS / office 桥 / storage presign）

**base '/oa/' 前缀修复（2026-07-15）**：加 `devStripOaPrefix` plugin 修整个 dev proxy 404。

---

## 对外接口 (External Interfaces)

### 路由清单（src/router/index.ts）

所有 admin/meeting/oa/office 路由 base = `/oa/`；**CMS 公开页 `/product/:slug` 与推广公开页 `/promo/:code` 例外**。

| 路径 | 名称 | 权限码 | 业务域 |
|------|------|--------|--------|
| `/login` | login | 公开 | - |
| `/register` | register | 公开 | - |
| `/oauth/callback` | oauth-callback | 公开 | - |
| `/dashboard` | dashboard | - | 工作台（**2026-07-15 拖拽布局**） |
| `/upload` | upload | - | meeting |
| `/list` | list | - | meeting |
| `/meetings/:id` | detail | - | meeting |
| `/system/user` | sys-user | `system:user:list` | system |
| `/system/role` | sys-role | `system:role:save` | system |
| `/system/permission` | sys-perm | `system:permission:save` | system |
| `/system/dept` | sys-dept | `system:dept:save` | system |
| `/system/audit` | sys-audit | `system:audit:view` | system |
| `/announcement` | oa-announcement | `oa:announcement:save` | oa |
| `/leave` / `/expense` / `/approval` / `/report` / `/attendance` | oa-* | - | oa |
| `/finance/transaction` / `/account` / `/category` | fin-* | `finance:*:save` | finance |
| **`/finance/voucher`** | **fin-voucher** | **`finance:transaction:save`** | **🆕 finance（2026-07-15 复式记账）** |
| `/finance/report` | fin-rpt | `finance:report:view` | finance |
| `/asset/type` / `/batch` / `/card` / `/redemption` | asset-* | `asset:*:list` | asset |
| `/agent/agent` / `/region` / `/order` / `/commission` | agent-* | `agent:*` | agent |
| **`/agent/withdrawal`** | **agent-withdrawal** | **`agent:commission:view`** | **🆕 A3 提现** |
| **`/agent/dashboard`** | **agent-dashboard** | **`agent:commission:view`** | **🆕 A4 看板** |
| `/verify/:code` | verify-card | **public**（防伪核销） | — |
| **`/cms/products` / `/products/edit/:id?` / `/media` / `/merchants` / `/leads` / `/orders` / `/coupons` / `/reviews` / `/dashboard` / `/search`** | **cms-*** | **`cms:*:list`** | **🆕 cms（11 路由）** |
| **`/office`** | **office-center** | **（登录）** | **🆕 office（2026-07-15）** |
| **`/office/sheet-spike`** | **office-sheet-spike** | **（登录）** | **🆕 office（Univer spike）** |
| **`/product/:slug`** | **product-view** | **public（无 /oa 前缀 SEO）** | **🆕 cms** |
| **`/promo/:code`** | **promo-page** | **public（无 /oa 前缀）** | **🆕 agent（A1）** |

### 路由守卫（src/router/index.ts）
1. `meta.public` 公开页（login/register/oauth/callback/**product-view**/**promo-page**/cms-search/verify-card）直接放行
2. 未登录跳 `/login?redirect=<原路径>`
3. `meta.permission` 不匹配跳 `/`

### API 客户端（src/api/）

| 文件 | baseURL | 用途 |
|------|---------|------|
| `admin.ts` | `import.meta.env.BASE_URL + 'admin'` | 企业/财务/资产/代理/OA/CMS/办公桥/Storage 全部接口 |
| `meetings.ts` | `import.meta.env.BASE_URL + 'api'` | 会议上传/列表/详情 |
| `cms-public.ts` | `import.meta.env.BASE_URL + 'admin/api/v1/cms'` | 🆕 CMS 公开接口 |
| `endUser.ts` | 同上 | 🆕 C 端账号 |
| `utils/api-error.ts` | - | 🆕 `getApiError(e: unknown)` 统一错误处理 |

---

## §8 API 层 / `src/api/admin.ts` 深读（243 行，**2026-07-15 12:30 精细续跑**）

> admin 前端 API 客户端核心，2026-07-14 全量类型化，2026-07-15 加 voucher/withdrawal。

### 8.1 实际方法规模（修正任务描述）

**任务描述**："145 端点 TS 类型映射"——**实际**：
- **显式类型化方法 ≈ 30 个**（不是 145 个独立方法）
- **1 个通用 `resource<T>(path)` 工厂**——覆盖 100+ 通用 CRUD 端点
- **总端点覆盖 ≈ 130+**（通过 resource 工厂 + 显式方法）
- **8 个本地 interface**（UserInfo + LoginResult；其余 6 个 import 自 `@/types`）
- **`getApiError(e: unknown, fallback='操作失败')`** 完整（3 级降级）

**关键发现**：`resource<T>(path)` 工厂是覆盖面的关键——返回 `{ list/get/create/update/remove }` 5 个闭包，复用到所有通用 CRUD 端点。**这意味着大部分端点通过动态 path 绑定，而非静态方法**——类型推断在调用点才确定。

### 8.2 完整方法清单（30 显式 + 1 工厂）

- **认证（6）**：`login` / `register` / `me` / `fetchMenus` / `logout` / `changePassword` + `resetUserPassword` / `permissionTree` / `permissionFlat`
- **公告（2）**：`publishAnnouncement` / `archiveAnnouncement`
- **审批（2）**：`approveInstance` / `rejectInstance`
- **财务报表（4）**：`reportSummary` / `reportByCategory` / `reportByAccount` / `reportByMonth`
- **复式记账（6，🆕 2026-07-15）**：`createVoucher` / `postVoucher` / `listVouchers` / `trialBalance` / `balanceSheet` / `incomeStatement`
- **代理提现 A3（4，🆕 2026-07-15）**：`withdrawalBalance` / `listWithdrawals` / `requestWithdrawal` / `reviewWithdrawal`
- **资产（4）**：`generateCards` / `redeemCard` / `issueCard` / `voidCard`
- **代理（4）**：`payOrder` / `completeOrder` / `commissionSummary` / `settleCommission`
- **工作汇报（2）**：`allReports` / `readReport`
- **考勤（5）**：`attendanceToday` / `clockIn` / `clockOut` / `attendanceMe` / `attendanceStats`
- **通用（2）**：`downloadCsv` / `resource<T>(path)`

### 8.3 8 个本地 interface（admin.ts 内显式声明）

```ts
export interface UserInfo {
  id: number; username: string; name?: string; email?: string
  phone?: string; dept_id?: number; status: boolean
  roles: string[]; permissions: string[]
}

export interface LoginResult {
  access_token: string; refresh_token: string
  token_type: string; user: UserInfo
}
```

**从 `@/types` 导入的 6 个**：`MenuItem` / `PermissionNode` / `AttendanceRecord` / `AttendanceStats` / `WorkReport` / `CategoryReportItem` / `CommissionSummaryItem`（实际 import 7 个）。

**对比 9 个 interface 任务描述**：2026-07-14 的"9 个新 interface"实际分散在 `admin.ts`（2 本地）+ `@/types/index.ts`（其余 7-9 个，含 CMS / 办公 / Voucher / Office 等）。

### 8.4 `getApiError(e: unknown)` 完整实现（L43-50）

```ts
export function getApiError(e: unknown, fallback = '操作失败'): string {
  if (axios.isAxiosError(e)) {
    const detail = (e.response?.data as { detail?: string } | undefined)?.detail
    return detail || fallback
  }
  if (e instanceof Error) return e.message || fallback
  return fallback
}
```

**3 级降级**：axios 错误 → `response.data.detail`（FastAPI `HTTPException(detail=...)` 标准）；Error → `message`；其他 → fallback。**复用情况**：39 处 catch 复用（2026-07-14 DRY 化结果）。

### 8.5 拦截器链（L52-73）

**请求拦截**（L53-60）：动态 `await import('@/stores/user')` 避免循环依赖；注入 `Authorization: Bearer token`。

**响应拦截**（L63-73）：401 全局处理——清登录态 + `window.location.href = BASE_URL + 'login'` 跳登录页（强制刷新清 Vue 状态）；仍 `Promise.reject(error)` 调用方 catch 可见。

### 8.6 `resource<T>(path)` 通用 CRUD 工厂（L231-239）

```ts
resource<T = unknown>(path: string) {
  return {
    list: (params?: Record<string, unknown>) => http.get(path, { params }).then((r) => r.data),
    get: (id: number) => http.get(`${path}/${id}`).then((r) => r.data as T),
    create: (body: Record<string, unknown>) => http.post(path, body).then((r) => r.data as T),
    update: (id: number, body: Record<string, unknown>) => http.put(`${path}/${id}`, body).then((r) => r.data as T),
    remove: (id: number) => http.delete(`${path}/${id}`).then((r) => r.data),
  }
}
```

**覆盖范围**：users / roles / departments / finance accounts/categories/transactions（**transactions DEPRECATED**）/ asset card-types/batches/cards / oa announcements/leaves/expenses/reports / cms 部分端点。

**类型推断**：`<T = unknown>` 默认 unknown，调用方显式标注 `as T`。**这是 admin.ts 0 个 any 但 views 仍有 87 个 any 的关键来源**——views 调用 `resource().list()` 时若不显式 `as` 标注类型，Vue ref 推断为 `ref<unknown[]>` 或 `ref<any[]>`。

### 8.7 `downloadCsv(path, params)` 文件下载（L217-229）

```ts
async downloadCsv(path: string, params?: Record<string, unknown>) {
  const r = await http.get(path, { params, responseType: 'blob' })
  const cd = (r.headers['content-disposition'] || '') as string
  const filename = (cd.match(/filename="?([^";]+)"?/) || [, 'export.csv'])[1]
  const url = URL.createObjectURL(new Blob([r.data]))
  const a = document.createElement('a')
  a.href = url; a.download = decodeURIComponent(filename)
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

**关键设计**：Blob URL + `<a download>` 触发浏览器原生下载；`URL.revokeObjectURL` 防内存泄漏；Content-Disposition 解析兼容 `filename="xxx.csv"` 和 `filename=xxx.csv`；`decodeURIComponent` 处理中文文件名。

### 8.8 87 个 `ref<any[]>` 来源澄清（修正 7-14 文档）

- **admin.ts 本身**：**0 个 `any`**（2026-07-14 全量类型化完成）
- **87 个 `ref<any[]>` 全在 `views/*.vue`**（不在 api 层）：Element Plus `el-table` row 框架限制
- **业界通行做法**：TableV2 / 自封装 `<KTable>` 可绕过但 ROI 低
- **临时缓解**：views 中显式 `const rows = ref<MyType[]>([])` 可消除部分，但 slot props 仍逃逸

**优化建议**（低优先级）：全项目搜 `ref<any[]>` 替换（87 处约 1d）/ 换 `el-table-v2` / 自封装 `<KTable>`。

---

## 关键依赖与配置 (Dependencies & Config)

### package.json 关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| vue / vue-router / pinia | ^3.5 / ^4.4 / ^2.2 | 核心 |
| element-plus / @element-plus/icons-vue | ^2.8 / ^2.3 | UI |
| axios / echarts | ^1.7 / ^6.1 | HTTP / 图表 |
| **@tiptap/vue-3 / @tiptap/starter-kit** | ^2.x | 🆕 CMS 富文本 |
| **vuedraggable** | ^4.x | 🆕 工作台拖拽 |
| **xlsx** (SheetJS) | ^0.18 | 🆕 办公中心表格编辑 |
| **dompurify** | ^3.x | 🆕 docx 预览 XSS 防护 |
| **@univerjs/preset-sheets-core** | ^0.25 | 🆕 Univer Sheets preset |

### Dev 依赖

| 包 | 用途 |
|----|------|
| vite ^5.4.0 | 构建 |
| typescript ^5.6.0 / vue-tsc ^2.1.0 | 类型检查（**0 errors** for CMS + OfficeCenter + Voucher） |
| sass ^1.101.0 | 样式 |
| unplugin-auto-import ^21.0.0 / unplugin-vue-components ^32.1.0 | 自动导入 |
| **vitest** ^2.1.9 | 测试（jsdom + @vue/test-utils） |

### vite.config.ts 关键配置
- `base: '/oa/'`（生产子路径；CMS 公开页 base 例外）
- SCSS 全局注入 `@/styles/element/_variables.scss`（覆盖 EP 主题色）
- dev proxy：`/api`、`/llm` → `:8000`；`/admin` → `:8300`
- `devStripOaPrefix` plugin（`configureServer` 中间件）去 /oa 前缀（2026-07-15 修复 dev proxy 404）
- `vitest.config.ts`：`environment: 'jsdom'`

---

## 数据模型 (Data Models)

前端不持有业务模型，主要在 `src/types/`：
- `index.ts` — 通用类型（**2026-07-14 新增 9 接口**：MenuItem / PermissionNode / Attendance / Commission / WorkReport / TourProduct / MediaAsset / Merchant / EndUser / EpTagType；**2026-07-15 新增 Voucher / JournalEntry / OfficeHealth / ToolResult**）
- `auto-imports.d.ts` / `components.d.ts` — 自动生成（**勿手改**）

### 用户状态（Pinia store: src/stores/user.ts）

```ts
useUserStore = {
  token: Ref<string>          // localStorage 'kk-cms-admin-token'
  userInfo: Ref<UserInfo | null>
  menus: Ref<any[]>
  isLogin, roles, permissions, isSuperAdmin
  hasPermission(code: string): boolean
  login/register/applyOAuthLogin/fetchMenus/fetchMe/logout
}
```

### 🆕 C 端账号状态（src/stores/endUser.ts）

```ts
useEndUserStore = {
  token: Ref<string>          // localStorage 'kk-cms-cms-end-user-token'
  userInfo: Ref<EndUser | null>
  isLogin: ComputedRef<boolean>
  login/register/logout/fetchMe
}
```

---

## 测试与质量 (Testing & Quality)

### 当前状态（2026-07-15 重置基线）
- ✅ vitest 2.1.9 + jsdom + @vue/test-utils（2026-07-12 配置）
- ✅ **46 个测试全过**：stores/user + router/guard + views/detail-export + views/render-md (DOMPurify) + api/admin-agent + views/agent-status-helpers + **stores/endUser** + **views/cms-*** (CMS 11 视图)

### 测试命令
```bash
pnpm test          # run 模式
pnpm test:watch    # watch 模式
pnpm test:coverage # 覆盖率
```

### 环境要求
- `environment: 'jsdom'`（happy-dom 与 DOMPurify 不兼容）

### 类型检查
```bash
pnpm build   # vue-tsc -b 内含完整类型检查
```

> 2026-07-14：`any` 159→87（api/admin.ts 13→0 + getApiError DRY + as any→as const 13→0 + 9 个新 interface）
> 2026-07-15：voucher 表单 5 个新 any + 4 个新 interface，**net 平仍 87**

---

## 常见问题 (FAQ)

**Q1-Q6**：路由 / EP 样式 / 菜单 / 主题 / axios 404 / SEO —— 标准排查，详见 2026-07-14 文档。

**Q7: CMS 真发卡链路？**
A: 后端 `cms/orders/{id}/pay` → `payment.py:MockGateway.pay()` → `cms/orders/{id}/issue-card` → `asset/cards` 实际写入；前端调用顺序：选产品→下单→pay→issue-card→跳成功页。**真支付接入前必先实现 webhook 验签/幂等/状态机/发卡触发/失败回滚 5 项（详见 `services/admin/CLAUDE.md` §7.14）**。

**Q8: voucher 创建报"借贷不平"？**
A: 检查分录数 ≥ 2 + Σdebit === Σcredit + > 0。前端 VoucherList 实时校验，不平衡禁用保存按钮。

**Q9: 办公中心打不开？**
A: 检查 `/api/v1/office/health` 是否 ok；oa-agent 不可达会 503 + 前端显示"oa-agent 不可达"。

**Q10: Univer 表格不渲染？**
A: 检查 SheetJS 是否成功解析 xlsx；OfficeCenter 上传 xlsx 后会自动转 cellData 并渲染。

**Q11: 工作台拖拽布局不保存？**
A: 检查 `User.preferences` JSON 字段。

**Q12: UniverSheet.vue 主题色不跟随 Teal #0d9488？**
A: 组件未注入自定义主题，用 Univer 默认主题。**已知 YAGNI**。

**Q13: 145 端点没有全部类型化？**
A: admin.ts 显式类型化方法约 30 个，其余通过 `resource<T>(path)` 通用工厂动态绑定（覆盖 100+ 通用 CRUD 端点）。**这是 admin.ts 0 个 any 但 views 仍有 87 个 ref<any[]> 的关键来源**——调用 resource 工厂的 views 未显式 `as` 标注类型。详见 §8.6。

---

## 相关文件清单 (Key Files)

### 入口与配置
- `index.html` — Vite HTML 模板
- `package.json` — 依赖与脚本
- `vite.config.ts` / **`vite.config.js`** — 构建配置；**⚠️ .js 优先于 .ts**
- **`vitest.config.ts`** — 测试配置（jsdom）

### 应用骨架
- `src/main.ts` / `src/App.vue` / `src/env.d.ts`

### 路由 / Store / API
- `src/router/index.ts` — 全部路由 + 守卫
- `src/stores/user.ts` / **`stores/endUser.ts`**（🆕 C 端账号）
- `src/api/admin.ts` — admin 服务 API 客户端（**2026-07-14 全量类型化 + 2026-07-15 加 voucher/withdrawal**，详见 §8）
- `src/api/meetings.ts` / **`cms-public.ts`**（🆕） / **`endUser.ts`**（🆕）
- **`src/utils/api-error.ts`**（🆕）— `getApiError(e: unknown)` 统一错误处理

### 组件
- `src/components/AppSidebar.vue` — 主导航侧边栏（含 CMS 菜单）
- `src/components/TimeText.vue` / `StatusTag.vue` / `ThemeToggle.vue`
- **`src/components/RichEditor.vue`**（🆕）— TipTap 富文本（CMS ProductEdit）
- **`src/components/MediaPicker.vue`**（🆕）— 媒体素材选择弹窗
- **`src/components/VoucherPrint.vue`**（🆕 2026-07-15）— A4 凭证打印
- **`src/components/UniverSheet.vue`**（🆕 2026-07-15）— Univer Sheets 渲染组件

#### `UniverSheet.vue` 实现细节（2026-07-15 11:55 深读 + 12:30 补充）

**SFC 概览**（40 行 + style）：template 仅 `<div ref="container">`；style `.univer-container { height: 520px }`（硬编码，未响应式）。

**关键 import**（**默认导入，未懒加载**）：
```ts
import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core'
import UniverPresetSheetsCoreZhCN from '@univerjs/preset-sheets-core/locales/zh-CN'
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets'
import '@univerjs/preset-sheets-core/lib/index.css'
```

**Props**：`Record<string, { name?: string; cellData?: Record<number, Record<number, { v: unknown }>> }>`

**生命周期**：`onMounted → createUniver + mergeLocales + UniverSheetsCorePreset`；`onBeforeUnmount → univerInstance.dispose()`

**已知 YAGNI**：
1. **`manualChunks` 未做**——Univer UMD + locale 全量打包约 5.7MB（gzip 1.6MB）。`vite.config.{ts,js}` 无 `build.rollupOptions.output.manualChunks` 配置。建议下轮把 `@univerjs/*` 拆成独立 `univer` chunk 走动态 import，按需懒加载
2. **主题色未注入**：用 Univer 默认主题，未与项目 Teal `#0d9488` 联动。如需统一需引入 `@univerjs/themes`（+80~120KB）
3. **高度硬编码 520px**：未响应式，移动端 H5 不友好
4. **未做数据返回接口封装**：当前只渲染不可回写

**与 OfficeCenter 第 4 tab 集成**：`cellData` 由 SheetJS 解析 xlsx 后构造；用户切换 xlsx 时父组件更新 `:key` 触发组件重建。

### View（业务页面）
- `src/views/Login.vue` / `Register.vue` / `oauth/Callback.vue`
- **`src/views/Dashboard.vue`** — 工作台（**2026-07-15 拖拽布局**）
- `src/views/Upload.vue` / `List.vue` / `Detail.vue` — 会议（含 marked + DOMPurify XSS 防护）
- `src/views/system/` — UserList / RoleList / PermissionList / DeptList / AuditLog
- `src/views/finance/` — TransactionList / AccountList / CategoryList / Report / **`VoucherList.vue`**（🆕 2026-07-15 复式记账 UI）
- `src/views/asset/` — CardTypeList / BatchList / CardList / Redemption / Verify.vue（防伪公开核销页）
- `src/views/agent/` — RegionList / OrderList / Commission / **`AgentDashboard.vue`**（🆕 A4 ECharts）/ **`WithdrawalView.vue`**（🆕 A3 提现）
- `src/views/oa/` — Announcement / Leave / Expense / Approval / Report / Attendance
- **`src/views/cms/`**（🆕）— **CMS 11 视图**：ProductList / ProductEdit / ProductView（公开页 `/product/:slug`）/ MediaLibrary / MerchantList / LeadList / OrderList / CouponList / ReviewList / Dashboard（ECharts 漏斗）/ Search
- **`src/views/office/`**（🆕 2026-07-15）— OfficeCenter.vue（el-tabs 4 demo：read_* + docx 预览 mammoth/DOMPurify + 模板合并 docxtpl + Univer xlsx 编辑；调 `/api/v1/office/*`）/ SheetSpike.vue（Univer S2 spike）
- **`src/views/PromoPage.vue`**（🆕 2026-07-15）— 推广公开页 `/promo/:code`（A1）

### 样式（重设计进行中）
- `src/styles/theme/light.css` / `dark.css` / `sidebar.css` — 设计 Token
- `src/styles/element/_variables.scss` — EP 主题色覆盖（Teal 湖青 #0d9488）
- `src/styles/base.scss` — 全局重置

### 自动生成（勿改）
- `src/types/auto-imports.d.ts`
- `src/types/components.d.ts`

---

## 9. `src/api/cms.ts` 深读 — CMS 前后端桥梁

> **职责**：封装 admin `/api/v1/cms/*` 全部端点的 TS API 客户端，**复用 `admin.ts::http`**（JWT 拦截 + 401 跳登录），与 admin token 共通道；额外为 C 端 EndUser 账号提供独立 token 注入（`kk-cms-end-user-token` localStorage key）。**全量类型化**（2026-07-14 `any` 159→87 后，cms.ts 0 `any`）。

### 9.1 文件结构（457 行，分 4 段）

| 段 | 行 | 内容 |
|----|----|----|
| 类型系统 | L8-L228 | 14 个 interface + 4 个 type union，对齐后端 `schemas/cms.py` |
| 工具函数 | L191-L218 | `endHeaders()`（C 端 JWT 注入）+ `iconEmoji()`（和风 icon code → emoji 映射） |
| `cmsApi` 对象 | L231-L454 | 47 个 API 方法，按业务域分 11 组 |
| 默认导出 | L456 | `export default cmsApi` |

### 9.2 类型系统（核心 interface 一览）

| 类型 | 业务含义 |
|------|---------|
| `TourProduct` | CMS 主实体，含 `custom`（订制游 A）/ `pass_config`（权益卡 C）双形态；含 SEO + view_count + reviews 嵌套 |
| `TourCustom` / `TourPass` | A/C 双形态配置（行程/服务流/价格模式 vs 面值/权益/适用商户） |
| `MediaAsset` / `Merchant` | 素材库 + 权益商户 |
| `InquiryLead` | 询价线索（A 订制游提交，公开端点免登录） |
| `ProductOrder` | 权益卡订单（含 `issued_card_no/password` 真发卡结果 + `transaction_id`） |
| `Coupon` / `CouponValidateResult` | 优惠券规则 + 校验响应（含 `discount` + `reason`） |
| `Review` | 评价（`pending/approved/rejected` 三态） |
| `DashboardStats` | 看板数据（products/views/leads/orders/revenue + top_products） |
| `EndUser` | C 端账号（phone + nickname） |
| `Weather` / `WeatherForecastDay` | 和风天气实时 + 预报 |

### 9.3 API 方法分组（11 组，与后端 router 一一对应）

| 组 | 方法数 | 主要端点 | 说明 |
|----|-------|---------|------|
| 产品 | 6 | `GET /cms/products` `/detail/:id` `/products/:slug` `POST/PUT/DELETE` | `getPublicProduct(slug)` 公开（无需登录），`getProduct(id)` 管理详情（含 draft） |
| 媒体 | 5 | `/cms/media` `/upload` `/confirm` + `/storage/presign` | **uploadMedia 直传优先 + 中转 fallback**（见 9.4） |
| 商户 | 4 | `/cms/merchants` CRUD | 权益商户管理 |
| 询价线索 | 4 | `/cms/leads` `POST` 公开 + `GET/PUT/DELETE` 管理 | `submitLead` 无需登录（公开询价表单） |
| 订单 | 3 | `/cms/orders` `POST/POST pay` `GET` | `createOrder` 含 `coupon_code` + `promo_code`（代理推广码） |
| 优惠券 | 5 | `/cms/coupons` CRUD + `/validate` | `validateCoupon(code, total)` 实时校验 |
| 评论 | 4 | `/cms/reviews` `POST` 公开 + `GET/PUT/DELETE` 管理 | `submitReview` 公开提交，待审核 |
| 看板 | 1 | `/cms/stats/dashboard` | 漏斗数据（浏览→询价→订单→支付） |
| 搜索推荐 | 2 | `/cms/products/search/results` `/related/:slug` | 全文搜索 + 相关产品 |
| C 端账号 | 3 | `/cms/auth/{register,login,me}` | `getEndUserMe()` 用 `endHeaders()` 注入独立 token |
| 天气 + AI | 3 | `/cms/weather` `/forecast` + `/oa-agent/chat/sync` | 公开天气 + AI 设计行程（oa-agent :9001） |

### 9.4 `uploadMedia` 智能直传（核心亮点，2026-07-15 Sprint 0/1/Phase 2 实装）

```ts
async uploadMedia(file: File, onProgress?) {
  try {
    const p = await this.presignMedia(file)        // /api/v1/storage/presign
    const resp = await fetch(p.url, { method: 'PUT', body: file, headers: p.required_headers })
    if (!resp.ok) throw new Error(`PUT COS failed: ${resp.status}`)
    return await this.confirmMedia({ key: p.key, name, content_type, size })  // /api/v1/cms/media/confirm
  } catch {
    return this.uploadMediaViaAdmin(file, onProgress)  // fallback /api/v1/cms/media/upload 中转
  }
}
```

**直传链**：`presign → fetch PUT COS → confirmMedia`（3 调用，省后端带宽 + 提速）。
**Fallback 触发**：cos backend 不存在 / CORS 未配 / 网络 / PUT 非 2xx → `uploadMediaViaAdmin` 中转（multipart/form-data 上传 admin → Storage 抽象层）。
**调用方无感**：UI 仅调 `uploadMedia`，内部 try/catch 切换；`onProgress` 仅 fallback 路径生效。

### 9.5 C 端账号双 token 设计

| 通道 | Token 来源 | 注入方式 | 用途 |
|------|----------|---------|------|
| **Admin 通道** | `kk-mis-token` localStorage | `http` 拦截器自动加 `Authorization: Bearer` | CMS 管理视图（ProductEdit/MediaPicker/MerchantList 等 11 view） |
| **C 端通道** | `kk-cms-end-user-token` localStorage | `endHeaders()` 手动注入（仅 `getEndUserMe` 用） | 公开页 + C 端用户中心；token `type=end_user` 与 admin JWT 区分 |

> **设计要点**：C 端账号可选——匿名仍可浏览/下单/评论（公开端点免登录），登录后享用户中心 + 历史订单；两 token 并存不互踢。

### 9.6 公开端点 vs 管理端点（auth 边界）

| 公开（无需 token） | 需要 admin token | 需要 C 端 token（可选） |
|-------------------|-----------------|----------------------|
| `getPublicProduct(slug)` | 全部 CRUD（products/media/merchants/coupons/reviews/leads） | `getEndUserMe` |
| `submitLead` | `listLeads/updateLeadStatus` | |
| `submitReview` | `listReviews/updateReviewStatus` | |
| `searchProducts/getRelated` | `getDashboard` | |
| `getWeather/getForecast` | `createOrder/payOrder/listOrders`（订单需登录） | |
| `oaAgentChatSync`（公开 AI） | `presignMedia/confirmMedia`（管理） | |

### 9.7 与后端对应速查（admin 12 router）

| 前端方法 | 后端端点 | router 文件 |
|---------|---------|------------|
| `getPublicProduct(slug)` | `GET /cms/products/{slug}` | `routes/cms/products.py` |
| `submitLead` | `POST /cms/leads` | `routes/cms/leads.py` |
| `createOrder` | `POST /cms/orders` | `routes/cms/orders.py` |
| `validateCoupon` | `POST /cms/coupons/validate` | `routes/cms/coupons.py` |
| `presignMedia` | `POST /storage/presign` | `routes/storage.py`（非 cms 子路由） |
| `getWeather` | `GET /cms/weather` | `routes/cms/weather.py` |
| `oaAgentChatSync` | `POST /oa-agent/chat/sync` | `routes/oa_agent.py`（非 cms 子路由） |

> **跨子包注意**：`presignMedia` 实际打到 `routes/storage.py`（Sprint 1 通用存储路由），`oaAgentChatSync` 打到 `routes/oa_agent.py`（oa-agent 桥），不是 cms 子路由；UI 调用无感。

### 9.8 iconEmoji 简化映射（和风 icon → emoji）

```ts
100='☀️' <105='⛅' <200='🌤️' <400='🌧️' <500='❄️' <600='🌫️' else='🌤️'
```

> 简化版（前缀区间），完整版见后端 `services/cms/weather.py`；UI 用 `iconEmoji(code)` 直接渲染。

---

## 变更记录 (Changelog)

- 2026-07-15 13:30:00 — 续跑增量更新（zcf:init-project）：
  - **新增 §9 `src/api/cms.ts` 深读**（约 107 行）：CMS 前后端桥梁完整拆解——11 个接口组 / 47 个 API 方法 / 与后端 12 router 端点一一对应 / `uploadMedia` 智能直传优先 + 中转 fallback 详解（presign→PUT→confirm 三步链 + 触发 fallback 的 3 种情况）/ C 端双 token 设计（`kk-mis-token` admin 通道 + `kk-cms-end-user-token` C 端通道 + `endHeaders()` 手动注入）/ 公开端点 vs 管理端点 auth 边界速查表 / `iconEmoji` 和风 icon 简化映射规则 / `presignMedia` 与 `oaAgentChatSync` 跨子包打到 `routes/storage.py` 与 `routes/oa_agent.py`（非 cms 子路由，UI 无感）备注；
  - **文件状态**：web/CLAUDE.md 429 → **536 行**（净增 107，全部为 §9 新增 + changelog）；vue-tsc 0 / vitest 46 不变（cms.ts 0 `any` 全量类型化，2026-07-14 baseline）；下一步可考虑 §10（views/cms/ 11 视图逐一深读）或 §11（stores/endUser C 端账号 store）。