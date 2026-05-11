# AI Creator Frontend — 开发规划与进度

> 后端: `D:\ai_creator\backup_agent_33\backup_agent\` (Flask, http://127.0.0.1:5000)
> 前端: `D:\ai_creator\backup_agent_33\frontend\` (本目录, Vite dev http://127.0.0.1:5173)

---

## 1. 决策记录

| 项 | 决策 |
|---|---|
| 项目位置 | `D:\ai_creator\backup_agent_33\frontend\` (与 backup_agent 同级) |
| 框架 | Vue 3 + TypeScript + Vite |
| 组件库 | Naive UI |
| 样式 | TailwindCSS |
| 状态管理 | Pinia (+ persistedstate) |
| 路由 | Vue Router |
| 视觉风格 | **克制的浅色专业风** — 远离 AI 紫色渐变 / sparkles 滥用; 借鉴 Notion / Linear / Stripe |
| PPT Engine 形态 | 独立页面 `/ppt-studio` 优先 + 弹窗卡片备用形态 |
| 旧入口处理 | 聊天框「制作PPT：」触发词保留备用,不删除 |

---

## 2. 视觉系统 (浅色克制专业风)

### 配色

```
背景        #fafafa  /  #ffffff  (主区)
卡片        #ffffff
描边        #e5e7eb
分割线      #f1f5f9
文字主要    #111827  (slate-900)
文字次要    #4b5563  (slate-600)
文字弱化    #9ca3af
主色 ink    #0f172a  (深 slate, 用于按钮 / 重点)
点缀绿      #10b981  (emerald, 仅用于成功 / 进度)
点缀琥珀    #d97706  (warning)
错误红      #dc2626
```

**禁用**: 紫色渐变 / 霓虹色 / 大面积 hero 玻璃光晕 / 旋转 sparkles。
**允许**: 极轻 hover 变化、200ms 淡入、低浮雕阴影 (`shadow-sm` / `shadow-md`)、12px 圆角。

### 字体 (全部免费可商用)

| 用途 | 字体 | 许可 | 来源 |
|---|---|---|---|
| 英文主字体 | **Inter** | SIL OFL 1.1 ✅ 免费商用 | Google Fonts / 自托管 |
| 中文主字体 | **HarmonyOS Sans SC** | 华为自定义许可 ✅ 免费商用 (含商业产品) | 华为官方下载 |
| 等宽 (代码) | **JetBrains Mono** | SIL OFL 1.1 ✅ 免费商用 | JetBrains 官方 |

CSS font-family 链:
```css
font-family: 'Inter', 'HarmonyOS Sans SC', -apple-system, BlinkMacSystemFont,
             "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
```

**字重**: 标题 600 / 正文 400 / 辅文 400 / 数字强调 500
**加载策略**: 自托管 woff2,关键子集 (常用 3500 汉字 + 拉丁) 内联,其余按需加载,`font-display: swap` 防 FOIT。
**备选**: 若不想自托管,可用 [字节跳动美团 ByteDance Sans](https://font.itheima.net/) 或 思源黑体 (Adobe SIL OFL) — 同样免费可商用。

> 实施时统一在 `src/assets/fonts/` 放 woff2 文件,通过 `@font-face` 注册,避免运行时再加载 Google Fonts CDN (国内访问稳定性问题)。

### 间距 / 圆角

- 圆角: 卡片 12px / 按钮 8px / 输入框 8px / 头像 8px
- 间距: 统一 4 的倍数 (Tailwind 默认)
- 容器最大宽: 1280px (主内容)

---

## 3. 信息架构 (路由)

```
/                  仪表盘 (功能入口 + 最近文件 + 快捷生成)
/chat              对话 (流式生成 / 多媒体卡片 / 会话管理)
/ppt-studio        PPT 工作台 (独立页, 三栏)
/library           文件库
/settings          设置
/memory            记忆管理
```

---

## 4. 模块清单

### A. Dashboard `/`
- 入口卡片 (PPT / 讲义 / 习题 / 图文 / 短视频...) → 跳转或弹窗
- 最近文件 (按更新时间)
- API Key / 服务状态条
- 快捷指令: 一键打开「快速生成 PPT」弹窗

### B. Chat `/chat`
- 复用 31 版本核心: SSE 流式 / Markdown / 代码块 / DOMPurify
- 多媒体消息卡片: PPT 预览 (轮播)、封面图、AI 配音、思维导图
- 会话管理: 侧栏会话列表 + 新建 / 重命名 / 删除
- 改进: 消息复制 / 重新生成 / 取消生成
- **持久化** (重点强化):
  - **会话列表**: localStorage `ai_creator.sessions` (id, name, created_at, updated_at)
  - **消息历史**: 每个会话独立键 `ai_creator.messages.{sessionId}` 存全量消息
  - **当前会话**: localStorage `ai_creator.current_session_id`
  - **持久化时机**: 每次消息追加 / 流式增量 / 重命名 / 删除 → 立即写入 (debounce 200ms 防频繁写)
  - **存储版本号**: `ai_creator.schema_version = 1`,后续 schema 变更时迁移
  - **限制兜底**: 单会话超 500 条时弹窗提示"建议新开会话"; 总存储超 4MB 时按更新时间清理最久未用会话
  - **多媒体瘦身**: 持久化时丢弃 base64 大字段 (slides[].base64 / imageBase64 / audioBase64),仅保留 metadata + 文件路径,刷新后从后端按需重取
  - **后端兜底**: 应用启动可选拉取 `/api/history?session_id=xxx` 校准 (后端有则覆盖,无则保留本地)
  - **导出/导入**: 设置页提供"导出全部对话 JSON / 导入恢复"按钮 (体验优化)
  - 实现基于 Pinia + `pinia-plugin-persistedstate` (统一管理) + 自定义 storage 适配器处理瘦身

### C. PPT Studio `/ppt-studio` ⭐ 新增重点

```
┌──────────────────────────────────────────────────────────┐
│ 顶栏: PPT 工作台   [历史]  [新建]                          │
├────────────┬────────────────────────────────────────────┤
│ 左:参数面板 │ 中/右:预览区                                  │
│            │                                            │
│ 主题       │   ┌──────────────────────────┐              │
│ ▭▭▭▭▭     │   │   (生成前)               │              │
│            │   │   空状态: 填写参数开始    │              │
│ 页数       │   │                          │              │
│ 自动 / 5-20│   │   (生成中)               │              │
│            │   │   ▮▮▮▮▮▮▭▭▭ 60%        │              │
│ 风格 (卡片)│   │   阶段: 设计策略...       │              │
│ □ 教育     │   │   ┌──┐┌──┐┌──┐         │              │
│ □ 学术     │   │   │SVG││SVG││...│ 实时   │              │
│ □ 咨询     │   │   └──┘└──┘└──┘         │              │
│ □ 科技     │   │                          │              │
│ □ 通用     │   │   (生成完)               │              │
│            │   │   SVG 轮播 + 缩略图条     │              │
│ 详细程度   │   │   [⬇下载 PPTX]           │              │
│ ○简略      │   └──────────────────────────┘              │
│ ●正常      │                                            │
│ ○详细      │                                            │
│            │                                            │
│ 语言       │                                            │
│ 中 / 英    │                                            │
│            │                                            │
│ 画布比例   │                                            │
│ 16:9 / 4:3 │                                            │
│            │                                            │
│ 模型       │                                            │
│ deepseek...│                                            │
│            │                                            │
│ API Key 可选│                                           │
│            │                                            │
│ [生成 PPT] │                                            │
└────────────┴────────────────────────────────────────────┘
```

#### SSE 事件流处理
- `ppt_svg_planning` → "内容规划中"
- `ppt_svg_designing` → "设计策略中"
- `ppt_svg_executing` → "SVG 生成中" (含 slide.page + slide.svg)
- `ppt_svg_finalizing` → "后处理中"
- `ppt_svg_exporting` → "导出 PPTX"
- `ppt_svg_done` → 完成 (含 job_id, pptx_filename)
- `ppt_svg_error` → 错误处理

#### 历史记录 (右上角抽屉)
- 调 `/api/ppt-svg/list` 获取所有 jobs
- 点击某 job 调 `/api/ppt-svg/preview-all/<job_id>` 重看 SVG
- 下载历史 PPTX

#### 弹窗卡片备用形态
- Dashboard / Chat 等位置可触发"快速生成 PPT"模态弹窗 (简化版,只 主题+风格+页数)
- 提交后跳转 `/ppt-studio` 自动开始生成

### D. 文件库 `/library`
- 类型 Tab: 全部 / PPT (旧) / SVG-PPT (新, 来自 ppt_engine) / 讲义 / 讲稿 / 习题 / 测验 / 卡片 / 思维导图 / 图文 / 音频 / 图片
- 网格 / 列表切换
- 预览抽屉:
  - PPT (旧 .pptx): 缩略图 (调 `/api/ppt-preview/<filename>`)
  - SVG-PPT (job_id): SVG 轮播
  - 图片: 直链
  - 音频: `<audio>` 控件
  - md/txt: 内嵌 markdown 渲染
- 操作: 删除 / 重命名 / 批量清空

### E. 设置 `/settings`
- 语音合成 (mimo_voice / mimo_style) — 同 31
- 封面比例 / 风格 — 同 31
- **新增**: PPT 默认参数 (默认风格 / 默认页数 / 默认模型 / 默认详细度)
- **新增**: 主题色调微调 (浅色 / 系统 / 暗色, 后续扩展)

### F. 记忆 `/memory`
- 显示记忆摘要 (`GET /api/memory`)
- 搜索 (`GET /api/memory/search?q=`)
- 操作: 保存 / 清空 / 单日清空

---

## 5. API 客户端结构

```
src/api/
├── client.ts            axios 实例 + 拦截器
├── sse.ts               fetch 流式工具 (返回 AsyncIterable<SseEvent>)
├── chat.ts              /api/chat /api/chat/stream /api/clear /api/history
├── meta.ts              /api/health /api/info /api/models
├── files.ts             /api/files /api/files/delete /api/files/rename /api/files/clear
├── settings.ts          /api/settings GET/POST
├── memory.ts            /api/memory*
├── pptSvg.ts            /api/ppt-svg/* (SSE generate, preview, preview-all, download, list)
└── preview.ts           /api/ppt-preview /api/graphic/image /api/video/audio (URL 拼装工具)
```

---

## 6. Pinia Store 结构

```
src/stores/
├── chatStore.ts         消息映射 / loading / abort
├── sessionStore.ts      会话列表 / 当前会话
├── fileStore.ts         文件列表 / 筛选 / fetch
├── settingStore.ts      用户设置 + options
├── memoryStore.ts       记忆摘要
└── pptStore.ts          ⭐ 当前生成任务 / 参数草稿 / SVG 列表 / 历史 jobs
```

---

## 7. 目录结构

```
frontend/
├── PLAN.md                           ← 本文件
├── package.json
├── vite.config.ts                    proxy /api → 5000
├── tailwind.config.ts
├── postcss.config.js
├── tsconfig.json
├── index.html
└── src/
    ├── main.ts
    ├── App.vue
    ├── router.ts
    ├── api/
    ├── stores/
    ├── composables/
    │   ├── useChat.ts
    │   ├── usePptStream.ts           ⭐ PPT SSE
    │   └── useMessage.ts             toast 包装
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.vue
    │   │   ├── AppSidebar.vue
    │   │   └── AppHeader.vue
    │   ├── chat/
    │   │   ├── ChatInput.vue
    │   │   ├── ChatMessage.vue
    │   │   ├── PptPreviewCard.vue
    │   │   ├── GraphicImageCard.vue
    │   │   └── VideoAudioCard.vue
    │   ├── ppt/                      ⭐
    │   │   ├── ParamPanel.vue
    │   │   ├── StyleCard.vue
    │   │   ├── PreviewStage.vue
    │   │   ├── ProgressBar.vue
    │   │   ├── SvgCarousel.vue
    │   │   ├── HistoryDrawer.vue
    │   │   └── QuickGenerateModal.vue
    │   ├── library/
    │   │   ├── FileGrid.vue
    │   │   └── PreviewDrawer.vue
    │   └── common/
    │       ├── EmptyState.vue
    │       ├── PageHeader.vue
    │       └── StatusPill.vue
    ├── views/
    │   ├── DashboardView.vue
    │   ├── ChatView.vue
    │   ├── PptStudioView.vue         ⭐
    │   ├── LibraryView.vue
    │   ├── SettingsView.vue
    │   └── MemoryView.vue
    ├── types/
    │   └── index.ts
    ├── utils/
    │   ├── format.ts
    │   ├── storage.ts
    │   └── id.ts
    └── assets/
        └── styles/
            ├── tailwind.css
            └── theme.css
```

---

## 8. 实施步骤 (分阶段)

### Phase 0: 项目初始化
- [ ] 创建 `frontend/` 目录
- [ ] `npm create vite@latest` → vue-ts
- [ ] 安装依赖: vue, vue-router, pinia, pinia-plugin-persistedstate, naive-ui, axios, lucide-vue-next, marked, dompurify, tailwindcss, postcss, autoprefixer, @types/node
- [ ] 配置 vite.config.ts (proxy `/api` → 5000, alias `@`)
- [ ] 配置 tailwind.config.ts (自定义 tokens 浅色克制风)
- [ ] tsconfig.json + ESLint/Prettier (轻量)
- [ ] 创建基础目录结构

### Phase 1: 基础布局 + 主题
- [ ] `assets/styles/theme.css` 定义 CSS 变量 (浅色克制)
- [ ] `tailwind.config.ts` 扩展 tokens
- [ ] `App.vue` + NConfigProvider themeOverrides
- [ ] `layout/AppShell.vue` (sidebar + header + main slot)
- [ ] `layout/AppSidebar.vue` (导航 + 折叠)
- [ ] `layout/AppHeader.vue` (面包屑 + 状态)
- [ ] `router.ts` 注册所有路由 (空白占位 view)

### Phase 2: API 客户端 + 类型定义
- [ ] `types/index.ts` ChatMessage / SseEvent / GeneratedFile / PptJob / Settings
- [ ] `api/client.ts` axios 实例
- [ ] `api/sse.ts` fetch SSE 工具
- [ ] `api/{chat,meta,files,settings,memory,pptSvg,preview}.ts`
- [ ] 全部 store 骨架

### Phase 3: Chat 对话模块
- [ ] `composables/useChat.ts` 基于 sse.ts 重写
- [ ] `components/chat/ChatInput.vue` 输入框 + 快捷指令
- [ ] `components/chat/ChatMessage.vue` 渲染分发
- [ ] `components/chat/PptPreviewCard.vue` (旧 ppt 预览, 兼容)
- [ ] `components/chat/GraphicImageCard.vue`
- [ ] `components/chat/VideoAudioCard.vue`
- [ ] `views/ChatView.vue`
- [ ] 会话管理逻辑
- [ ] **持久化**: pinia-plugin-persistedstate + 自定义 storage 适配器 (剔除 base64 大字段) + schema_version + 配额兜底

### Phase 4: PPT Studio (重点)
- [ ] `composables/usePptStream.ts` SSE 处理
- [ ] `stores/pptStore.ts`
- [ ] `components/ppt/StyleCard.vue` 风格选择卡
- [ ] `components/ppt/ParamPanel.vue` 完整参数表单
- [ ] `components/ppt/ProgressBar.vue` 阶段进度
- [ ] `components/ppt/SvgCarousel.vue` SVG 轮播 + 缩略图
- [ ] `components/ppt/PreviewStage.vue` 预览区域 (空 / 中 / 完)
- [ ] `components/ppt/HistoryDrawer.vue` 历史 jobs
- [ ] `components/ppt/QuickGenerateModal.vue` 弹窗卡片备用
- [ ] `views/PptStudioView.vue` 三栏组装
- [ ] 联调 5 个 ppt-svg 端点

### Phase 5: 文件库
- [ ] `components/library/FileGrid.vue`
- [ ] `components/library/PreviewDrawer.vue` (PPT/SVG/图/音频)
- [ ] `views/LibraryView.vue`

### Phase 6: 设置 + 记忆
- [ ] `views/SettingsView.vue` (含 PPT 默认参数新增节)
- [ ] `views/MemoryView.vue`

### Phase 7: 仪表盘
- [ ] `views/DashboardView.vue`
- [ ] 入口卡片 + 最近文件 + 快捷生成弹窗

### Phase 8: 联调测试 + 构建
- [ ] 启动后端 5000
- [ ] 启动前端 5173,浏览器走通所有功能
- [ ] 错误边界 / 网络错误 toast
- [ ] 骨架屏 / loading
- [ ] `npm run build` 验证产物

---

## 9. 进度追踪

> 每完成一个 Phase 在此勾选并记录关键备注。

| Phase | 状态 | 完成时间 | 备注 |
|---|---|---|---|
| 0 项目初始化 | ✅ done | 2026-05-09 | Vite+Vue3+TS+Naive+Tailwind+Pinia 全部 OK,build 通过 |
| 1 基础布局+主题 | ✅ done | 2026-05-09 | AppShell+sidebar+EmptyState+PageHeader+StatusPill,浅色克制 token 就位 |
| 2 API 客户端+类型 | ✅ done | 2026-05-09 | types/api/stores/utils 全部就位,build 通过 |
| 3 Chat 对话 | ✅ done | 2026-05-09 | useChat+ChatView+ChatInput+ChatMessage 三件套+多媒体卡;持久化(瘦身base64)就位 |
| 4 PPT Studio | ✅ done | 2026-05-09 | 三栏布局+SSE多Agent进度+SVG实时预览+下载+历史抽屉+QuickGenerate弹窗 |
| 5 文件库 | ✅ done | 2026-05-09 | 网格视图+13类筛选+预览抽屉(图/音/svg-ppt)+删除/重命名/清空,合并旧/新PPT |
| 6 设置+记忆 | ✅ done | 2026-05-09 | Settings 三大节(PPT默认+语音+封面),Memory 含搜索/保存/清空操作 |
| 7 仪表盘 | ✅ done | 2026-05-09 | 8 模块入口卡+最近文件+4 项统计+QuickGenerate 弹窗联动 |
| 8 联调+构建 | ✅ done | 2026-05-09 | 后端+前端起服+proxy 验证;health/files/settings/ppt-svg/list/memory/chat-stream 全通 |

---

## 12. 验证记录 (Phase 8)

启动栈:
- 后端 `python app.py` 在 `:5000` (有 GBK 日志编码警告但不影响功能,既有 bug)
- 前端 `npm run dev` 在 `:5173`,`/api` 代理到后端

冒烟通过的端点 (经 :5173 vite 代理):
- `GET /api/health` → `{status: "ok", ...}`
- `GET /api/info` → endpoints 列表
- `GET /api/models` → `[{id: "MiniMax-M2.5-highspeed", ...}]`
- `GET /api/files` → 已生成文件列表 (mindmap, lecture, etc.)
- `GET /api/settings` → settings + options 完整对象
- `GET /api/ppt-svg/list` → 已有历史 jobs (含 `course_ppt_20260507_111124`,`has_pptx: true`)
- `GET /api/memory` → 摘要文本
- `POST /api/chat/stream` → SSE `data: {"chunk": "..."}\ndata: {"done": true}` 格式与前端 sse.ts 一致
- `POST /api/ppt-svg/generate` (空 topic) → `400 课程主题不能为空` 校验生效

构建:
- `npm run build` 22s, 总产物 gzip ~250KB,按路由懒加载分块
- `npx vue-tsc --noEmit` 无错

---

## 10. 后端 API 对照表 (实现完整覆盖)

| 后端端点 | 方法 | 前端调用位置 |
|---|---|---|
| `/api/health` | GET | Dashboard 状态条 |
| `/api/info` | GET | Dashboard 状态条 |
| `/api/models` | GET | Settings / PPT Studio 模型选项 |
| `/api/chat` | POST | (备用,主要走 stream) |
| `/api/chat/stream` | POST SSE | Chat 模块 |
| `/api/clear` | POST | Chat 清空 |
| `/api/history` | GET | Chat 加载历史 |
| `/api/settings` | GET/POST | Settings 模块 |
| `/api/files` | GET | 文件库 |
| `/api/files/delete` | POST | 文件库 |
| `/api/files/rename` | POST | 文件库 |
| `/api/files/clear` | POST | 文件库 |
| `/api/memory` | GET | 记忆模块 |
| `/api/memory/save` | POST | 记忆模块 |
| `/api/memory/clear` | POST | 记忆模块 |
| `/api/memory/clear-daily` | POST | 记忆模块 |
| `/api/memory/search` | GET | 记忆模块 |
| `/api/ppt-preview/<filename>` | GET | 文件库 PPT 旧预览 |
| `/api/graphic/image/<filename>` | GET | 文件库 / Chat 图片 |
| `/api/video/audio/<filename>` | GET | 文件库 / Chat 音频 |
| `/api/ppt-svg/generate` | POST SSE | PPT Studio |
| `/api/ppt-svg/preview/<job_id>/<n>` | GET | PPT Studio 单页 |
| `/api/ppt-svg/preview-all/<job_id>` | GET | PPT Studio 历史回看 |
| `/api/ppt-svg/download/<job_id>` | GET | PPT Studio 下载 |
| `/api/ppt-svg/list` | GET | PPT Studio 历史 |

---

## 11. 风险与注意

1. **SSE 中文编码** — 后端 `ensure_ascii=False`,前端 `TextDecoder('utf-8')` 即可,但要测试中文不乱码。
2. **大 SVG 性能** — 实时预览每页 SVG 直接 `v-html` 渲染,高页数 (>20) 时考虑虚拟滚动。
3. **PPTX 下载跨域** — 走 vite proxy 代理到 5000。
4. **会话隔离** — `session_id` 由前端 uuid 生成,持久化到 localStorage。
5. **API Key 安全** — 用户输入的 api_key 仅存内存,不持久化。
6. **localStorage 配额** — 单域 ~5MB 上限。多媒体 (base64 图/音频/SVG) 必须**剔除后再持久化**,只保留文字内容和元数据;否则几条消息就溢出。
7. **字体许可** — 全部使用 SIL OFL / 华为开源协议字体,自托管 woff2 避免 CDN 不稳。商用前在最终交付前确认每个字体的最新协议版本。

---

*最后更新: 2026-05-09 (Phase 0 即将开始)*
