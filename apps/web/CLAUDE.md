[根目录](../../../CLAUDE.md) > [mis-system](../../CLAUDE.md) > [apps](../) > **web**

# apps/web · Vue3 前端

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑增量更新（zcf:init-project）：修正面包屑相对路径（原 `../../CLAUDE.md` 从本文件出发实际指向 `mis-system/apps/` 而非仓库根，改为 `../../../CLAUDE.md`；[mis-system] 链接从 `../` 改为 `../../CLAUDE.md`）；内容保持（vitest 2.1.9 + jsdom + 30 passed 仍准确）。
- 2026-07-12 16:08:16 — 续跑增量（zcf:init-project）：面包屑层级加深（仓库根 → mis-system → apps → web），内容保持。
- 2026-07-12 15:55:11 — 初始化模块级 CLAUDE.md（zcf:init-project）

---

## 模块职责 (Module Responsibility)

`kk-cms` 系统的统一前端 SPA，整合 6 大模块（会议纪要 / 企业管理 / 财务 / 资产 / 代理 / OA）的全部 UI。Teal 湖青主题（`#0d9488`），按需引入 Element Plus（bundle 减小 63%）。

设计要点：
- **单一代码库**：所有 view 在 `apps/web/src/views/` 下按业务域分目录（system / finance / asset / agent / oa / oauth）
- **统一 RBAC**：路由级 `meta.permission` 守卫 + 后端菜单动态下发
- **生产部署**：打包后通过 nginx 在 `/oa/` 子路径下对外

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

### 开发期代理（vite.config.ts）
- `/api` → `http://localhost:8000`（meeting-notes）
- `/llm` → `http://localhost:8000`（meeting-notes LLM 路由）

> 生产环境由 nginx 反代到 `:8200/:8300`，前缀分别为 `/oa/api/` 和 `/oa/admin/`。

---

## 对外接口 (External Interfaces)

### 路由清单（src/router/index.ts）

所有路由 base = `/oa/`，下表是相对路径：

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

### 路由守卫（src/router/index.ts）
1. `meta.public` 公开页（login/register/oauth/callback）直接放行
2. 未登录跳 `/login?redirect=<原路径>`
3. `meta.permission` 不匹配跳 `/`

### API 客户端（src/api/）

| 文件 | baseURL | 用途 |
|------|---------|------|
| `admin.ts` | `import.meta.env.BASE_URL + 'admin'` | 企业/财务/资产/代理/OA 全部接口 |
| `meetings.ts` | `import.meta.env.BASE_URL + 'api'` | 会议上传/列表/详情 |

- 拦截器统一注入 JWT（`Authorization: Bearer xxx`）
- 401 自动清登录态并跳登录
- `adminApi.resource(path)` 提供通用 CRUD（list/get/create/update/remove）
- `adminApi.downloadCsv()` 处理文件下载（解析 `Content-Disposition`）

---

## 关键依赖与配置 (Dependencies & Config)

### package.json 关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| vue | ^3.5.0 | 核心框架 |
| vue-router | ^4.4.0 | 路由 |
| pinia | ^2.2.0 | 状态 |
| element-plus | ^2.8.0 | UI 库（按需） |
| @element-plus/icons-vue | ^2.3.0 | 图标 |
| axios | ^1.7.0 | HTTP |
| echarts | ^6.1.0 | 图表（财务/看板） |

### Dev 依赖

| 包 | 用途 |
|----|------|
| vite ^5.4.0 | 构建 |
| @vitejs/plugin-vue ^5.1.0 | SFC |
| typescript ^5.6.0 | 类型 |
| vue-tsc ^2.1.0 | 类型检查 |
| sass ^1.101.0 | 样式 |
| unplugin-auto-import ^21.0.0 | 自动导入 vue/router/pinia/EP API |
| unplugin-vue-components ^32.1.0 | 自动注册 EP 组件 |

### vite.config.ts 关键配置
- `base: '/oa/'`（生产子路径）
- SCSS 全局注入 `@/styles/element/_variables.scss`（覆盖 EP 主题色）
- dev proxy：`/api`、`/llm` → `:8000`

---

## 数据模型 (Data Models)

前端不持有业务模型，主要在 `src/types/`：
- `index.ts` — 通用类型
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

---

## 测试与质量 (Testing & Quality)

### 当前状态
- ✅ vitest 2.1.9 + jsdom + @vue/test-utils（2026-07-12 配置）
- ✅ 测试覆盖（30 个全过）：`stores/user`（RBAC）+ `router/guard`（守卫）+ `views/detail-export`（Markdown 构建）+ `views/render-md`（XSS 防护）

### 测试命令
```bash
pnpm test          # run 模式
pnpm test:watch    # watch 模式
```

### 环境要求
- `environment: 'jsdom'`（happy-dom 与 DOMPurify 不兼容）
- happy-dom 在 SSR/单元测试时 localStorage 注入时机不稳，已用内存 mock 替代

### 类型检查
```bash
pnpm build   # vue-tsc -b 内含完整类型检查
```

---

## 常见问题 (FAQ)

**Q1: 改了路由但页面 404？**
A: 检查 `createWebHistory('/oa/')` 是否一致；生产环境确认 nginx `/oa/` location 配置正确。

**Q2: EP 组件样式不对？**
A: 暗色模式需要 `element-plus/theme-chalk/dark/css-vars.css` 在 custom CSS **之前**引入（见 `main.ts`）。

**Q3: 登录后菜单空白？**
A: 检查 `userStore.fetchMenus()` 是否成功（401 时静默清空）；用 admin/admin123 登录验证种子数据。

**Q4: 修改主题色没生效？**
A: 主题色变量在 `src/styles/element/_variables.scss`，SCSS 编译期注入；检查 `vite.config.ts` 的 `additionalData`。

**Q5: axios 请求 404？**
A: dev 检查 `vite.config.ts` 的 proxy；prod 检查 nginx 反代 `/oa/api/` 与 `/oa/admin/`。

---

## 相关文件清单 (Key Files)

### 入口与配置
- `index.html` — Vite HTML 模板
- `package.json` — 依赖与脚本
- `vite.config.ts` — 构建配置（proxy / 自动导入 / SCSS）

### 应用骨架
- `src/main.ts` — 应用启动
- `src/App.vue` — 根组件
- `src/env.d.ts` — 环境类型

### 路由 / Store / API
- `src/router/index.ts` — 全部路由 + 守卫
- `src/stores/user.ts` — 用户/登录态/RBAC
- `src/api/admin.ts` — admin 服务 API 客户端
- `src/api/meetings.ts` — meeting-notes API 客户端

### 组件
- `src/components/AppSidebar.vue` — 主导航侧边栏
- `src/components/TimeText.vue` — 相对时间显示
- `src/components/StatusTag.vue` — 会议状态标签
- `src/components/ThemeToggle.vue` — 主题切换
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

### 样式（重设计进行中）
- `src/styles/theme/light.css` / `dark.css` / `sidebar.css` — 设计 Token
- `src/styles/element/_variables.scss` — EP 主题色覆盖（Teal 湖青 #0d9488）
- `src/styles/base.scss` — 全局重置

### 自动生成（勿改）
- `src/types/auto-imports.d.ts`
- `src/types/components.d.ts`

---

## 变更记录 (Changelog)

- 2026-07-13 10:58:44 — 续跑：修正面包屑相对路径（`../../../CLAUDE.md` 指向仓库根，`../../CLAUDE.md` 指向 mis-system）
- 2026-07-12 16:08:16 — 续跑：面包屑加深到 3 级（仓库根 → mis-system → apps → web）
- 2026-07-12 15:55:11 — 初始化模块文档
