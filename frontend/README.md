# 智创空间 · 前端

> 项目全称：**智创空间 —— 基于多智能体交互的智慧课堂平台**（中国软件杯 A3 赛题 · 学生为中心的学习多智能体系统）

Vue 3 + TypeScript + Vite 实现的前端，完整对接 `backup_agent` 后端 (Flask, http://127.0.0.1:5000)。

## 技术栈

- Vue 3 (Composition API + `<script setup>`)
- TypeScript
- Vite 5
- Naive UI (组件库) + TailwindCSS (原子化样式)
- Pinia (状态) + pinia-plugin-persistedstate (持久化)
- Vue Router 4
- Axios + 原生 fetch (SSE 流式)
- marked + DOMPurify (Markdown 渲染)
- lucide-vue-next (图标)

## 目录结构

```
src/
├── main.ts
├── App.vue
├── router.ts
├── api/                  axios 实例 + SSE 工具 + 各端点
├── stores/               Pinia (session/chat/file/setting/memory/ppt)
├── composables/          useChat / usePptStream / useMessage
├── components/
│   ├── layout/           AppShell
│   ├── chat/             ChatInput / ChatMessage / 多媒体卡片
│   ├── ppt/              ParamPanel / SvgCarousel / ProgressBar / HistoryDrawer / QuickGenerateModal
│   ├── library/          FileGrid / PreviewDrawer
│   └── common/           EmptyState / PageHeader / StatusPill
├── views/                DashboardView / ChatView / PptStudioView / LibraryView / SettingsView / MemoryView
├── types/index.ts        全部类型定义
├── utils/                id / storage (含瘦身 + 配额兜底) / format
└── assets/styles/        theme.css + tailwind.css
```

## 启动

### 1. 启动后端 (5000)

参考根目录后端项目 `backup_agent_33/backup_agent/`:

```bash
cd ../backup_agent
pip install -r requirements.txt
npm install
python app.py
```

### 2. 启动前端 (5173)

```bash
npm install
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>。Vite 已配置 `/api` 代理到 5000。

## 构建

```bash
npm run build      # 生成 dist/
npm run preview    # 预览 dist/
npm run type-check # 仅类型检查
```

## 路由

| 路径 | 说明 |
|---|---|
| `/` | 仪表盘 |
| `/chat` | 对话生成 (讲义/讲稿/习题/卡片/思维导图/图文/微课视频) |
| `/ppt-studio` | PPT 工作台 (SVG 多 Agent 流水线) |
| `/video-studio` | 微课视频工作台 |
| `/interactive-classroom` | 互动课堂首页（多智能体智慧课堂入口） |
| `/interactive-classroom/:id` | 互动课堂播放器 |
| `/library` | 文件库 |
| `/settings` | 设置 |
| `/memory` | 记忆 |
| `/student-profile` | 学习者画像 |

## 设计原则

**克制的浅色专业风** — 远离 AI 紫色渐变 / sparkles 滥用,借鉴 Notion / Linear / Stripe。
- 主色: ink slate `#0f172a`
- 点缀: emerald (成功) / amber (警告) / rose (错误)
- 圆角: 12px 卡片 / 8px 控件
- 阴影: 低浮雕,慎用动画
- 字体: Inter + HarmonyOS Sans SC + JetBrains Mono (全部 SIL OFL / 华为开源,免费可商用)

## 持久化

> 说明：键名前缀 `ai_creator.*` 是历史遗留，**为避免老用户数据丢失保留不变**，并不代表当前产品名。

- `ai_creator.sessions` - 会话列表
- `ai_creator.current_session_id` - 当前会话
- `ai_creator.messages.{sessionId}` - 单会话消息 (剔除 base64 大字段后存储)
- `ai_creator.ppt_params` - PPT Studio 参数草稿
- `ai_creator.schema_version` - schema 版本
- 配额兜底: localStorage 写入失败时丢弃最旧 25% 会话消息

## 开发记录

详见 `PLAN.md` 与进度表。
