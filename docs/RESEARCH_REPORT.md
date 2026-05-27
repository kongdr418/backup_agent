# OpenMAIC 核心架构与工作流研究报告

> 研究日期：2026-05-25
> 研究人：Claude Code AI Assistant

---

## 一、项目定位

**OpenMAIC** (Open Multi-Agent Interactive Classroom) 是清华大学 MAIC（多模态 AI 研究中心）开发的开源项目，核心目标是：

> **一键生成沉浸式多智能体互动课堂** — 将任何主题或文档转化为丰富的互动学习体验

### 与 AI Creator 对比

| 维度 | OpenMAIC | AI Creator |
|------|----------|------------|
| **核心场景** | 多智能体互动课堂教学 | 单用户内容生成（PPT/讲义/习题等） |
| **用户模式** | 多 AI agent + 真实用户共同参与 | 单用户发起，AI 生成内容 |
| **交互深度** | 实时讨论、问答、白板协作 | 流式生成、预览 |
| **输出类型** | 互动课堂（幻灯片+测验+白板+视频+讨论） | 10+ 种独立内容格式 |
| **协作方式** | 多 agent 轮询讨论 | 流水线式单 agent 执行 |

**本质区别**：OpenMAIC 是**协作平台**，AI Creator 是**内容工厂**。

---

## 二、技术栈对比

| 类别 | OpenMAIC | AI Creator |
|------|----------|------------|
| **前端框架** | Next.js 16 (App Router) | Vue3 + Vite |
| **语言** | TypeScript 5 | TypeScript |
| **状态管理** | Zustand 5 | Pinia |
| **多智能体编排** | LangGraph 1.1.1 | 自研流程控制 |
| **LLM SDK** | Vercel AI SDK + AI SDK 扩展 | 自研 deepseek_provider |
| **UI 组件** | shadcn/ui + Radix UI | naive-ui + Tailwind |
| **样式方案** | Tailwind CSS 4 | Tailwind CSS |
| **动画** | Motion 12 | CSS transitions |
| **通信协议** | SSE 流式 | SSE 流式 |

---

## 三、核心模块架构

### 3.1 OpenMAIC 模块结构

```
OpenMAIC/
├── app/                          # Next.js App Router
│   ├── page.tsx                  # 首页（生成入口）
│   ├── classroom/[id]/page.tsx   # 课堂回放页
│   ├── generation-preview/       # 生成预览页
│   └── api/                      # API 路由 (~18 端点)
│       ├── generate-classroom/   # 异步课堂生成
│       ├── generate/             # 场景生成流水线
│       │   ├── scene-outlines-stream/  # 大纲流式生成
│       │   ├── scene-content/           # 场景内容生成
│       │   ├── scene-actions/          # 场景动作生成
│       │   ├── image/                  # 图片生成
│       │   ├── tts/                    # 语音合成
│       │   └── agent-profiles/         # 智能体配置
│       ├── chat/                 # 多智能体讨论（SSE）
│       └── quiz-grade/           # 测验评分
│
├── lib/                          # 核心业务逻辑
│   ├── generation/               # 两阶段生成流水线
│   ├── orchestration/            # LangGraph 多智能体编排
│   │   ├── director-graph.ts     # Director 状态机
│   │   ├── stateless-generate.ts # 流式生成核心
│   │   ├── prompt-builder.ts     # Agent prompt 构建
│   │   └── registry/             # 智能体注册表
│   ├── action/
│   │   └── engine.ts             # 统一动作执行引擎（28+ 动作）
│   ├── playback/                 # 回放引擎
│   ├── store/                    # Zustand stores
│   ├── ai/                       # LLM 提供商抽象
│   ├── audio/                    # TTS & ASR
│   ├── media/                    # 图片/视频生成
│   └── export/                   # PPTX/HTML 导出
│
├── components/                   # React 组件
│   ├── slide-renderer/           # Canvas 幻灯片编辑器
│   ├── scene-renderers/          # 测验/交互/PBL 渲染器
│   ├── chat/                     # 聊天区域
│   ├── whiteboard/               # SVG 白板
│   └── agent/                    # 智能体头像/配置
│
├── configs/                      # 幻灯片/图表/动画配置
├── eval/                         # 评测体系
│   ├── outline-language/         # 语言推断评测
│   └── whiteboard-layout/         # 白板布局评测
│
└── packages/                     # 工作区包
    └── pptxgenjs/               # 定制 PPTX 生成
```

### 3.2 AI Creator 模块结构

```
backup_agent/
├── backend/
│   ├── app.py                    # Flask 主入口（26 个 endpoint）
│   ├── minimax_agent.py          # 对话 Agent 核心，触发词分发
│   ├── memory_manager.py         # 长期记忆
│   ├── ppt_engine/               # SVG 多 Agent PPT 流水线
│   │   ├── pipeline.py           # 入口
│   │   ├── sse_bridge.py        # SSE 流式输出
│   │   ├── agents/               # content_planner / design_strategist / svg_executor / critic
│   │   ├── llm/                  # deepseek_provider + retry
│   │   ├── finalize/             # SVG 后处理
│   │   ├── svg_to_pptx/          # SVG → PPTX 导出
│   │   └── prompts/              # 各阶段 prompt 模板
│   └── generators/               # 11 个内容生成器
│       ├── ppt_generator.py      # 旧版 pptxgenjs
│       ├── course_outline_generator.py
│       ├── speech_generator.py
│       ├── lecture_generator.py
│       ├── exercise_generator.py
│       └── ... (共 11 个)
│
├── frontend/
│   ├── src/
│   │   ├── api/                  # 与后端协议对应
│   │   ├── stores/               # Pinia stores
│   │   ├── composables/          # useChat / usePptStream
│   │   ├── components/
│   │   │   ├── chat/             # ChatInput / ChatMessage
│   │   │   ├── ppt/              # ParamPanel / SvgCarousel / ProgressBar
│   │   │   └── library/          # FileGrid / PreviewDrawer
│   │   └── views/                # 6 个页面
│   └── PLAN.md
│
└── generated_*/                  # 各类型输出目录
```

---

## 四、核心工作流对比

### 4.1 OpenMAIC 多智能体协作流程

```
用户输入 (主题/PDF)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 1: 大纲生成 (scene-outlines-stream)                   │
│  LLM 分析 + 结构化输出                                       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 2: 场景内容生成 (scene-content)                        │
│  每个大纲条目 → 幻灯片/测验/交互内容                          │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段 3: 多智能体实时讨论 (LangGraph Director Pattern)        │
│                                                             │
│  START → Director Node                                      │
│             │                                                │
│             ├── 决策: next_agent / USER / END               │
│             │                                                │
│             ▼                                               │
│          Agent Node (per-agent generation)                   │
│             │                                                │
│             ├── buildStructuredPrompt()                      │
│             │       ├── role guidelines                      │
│             │       ├── peer context                        │
│             │       ├── whiteboard state                     │
│             │       └── length guidelines                    │
│             │                                                │
│             ├── LLM 流式输出 JSON array                      │
│             │       [{"type":"action","name":"spotlight",...}│
│             │        {"type":"text","content":"..."}]       │
│             │                                                │
│             └── yield agent_end                              │
│                                                             │
│  循环直到 END                                                │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
      完整课堂 → 回放引擎
```

### 4.2 OpenMAIC Director Pattern 详解

Director 是 LangGraph 状态机中的**路由节点**，职责：

1. 接收当前对话状态（已发言智能体、白板状态、turn 数）
2. LLM 决策下一个发言的智能体（或用户/结束）
3. 调度对应 Agent 节点执行

**Director 决策类型**：
```json
{"next_agent": "default-1"}   // 调度教师智能体
{"next_agent": "USER"}        // 等待用户输入
{"next_agent": "END"}         // 结束本轮讨论
```

**智能体角色与动作权限**：

| 角色 | 优先级 | 可执行动作 |
|------|--------|-----------|
| teacher | 10 | spotlight, laser, play_video + 白板全部动作 |
| assistant | 7 | 白板全部动作 |
| student | 4-6 | 白板全部动作（需教师邀请） |

### 4.3 AI Creator PPT 流水线

```
用户输入 (主题/内容)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  content_planner → design_strategist → svg_executor(+Critic) │
│  → svg_finalize → pptx_exporter                             │
│                                                             │
│  阶段 1: 内容规划 (content_planner)                          │
│  - 分析主题，生成结构化大纲                                   │
│  - 确定每页内容类型（标题/正文/图表/总结）                   │
│                                                             │
│  阶段 2: 设计策略 (design_strategist)                        │
│  - 确定视觉风格、配色、布局                                   │
│  - 生成每页设计指令                                          │
│                                                             │
│  阶段 3: SVG 执行 (svg_executor + Critic)                    │
│  - 生成每页 SVG 内容                                         │
│  - Critic 评审并反馈                                        │
│                                                             │
│  阶段 4: 后处理 (svg_finalize)                              │
│  - SVG 裁剪、嵌入字体、规范化、修复                          │
│                                                             │
│  阶段 5: 导出 (pptx_exporter)                               │
│  - SVG → PPTX 转换                                          │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
      生成完成
```

---

## 五、动作执行引擎对比

### 5.1 OpenMAIC ActionEngine

OpenMAIC 的 `lib/action/engine.ts` 实现了**统一的动作执行引擎**，支持 28+ 动作类型：

**动作分类**：
- **Fire-and-forget**: spotlight, laser（立即返回）
- **同步动作**: speech, video, whiteboard 操作
- **Widget 动作**: highlight, setState, annotation, reveal

**白板动作类型**：
```
wb_open, wb_close, wb_draw_text, wb_draw_shape,
wb_draw_chart, wb_draw_latex, wb_draw_table,
wb_draw_line, wb_draw_code, wb_edit_code,
wb_clear, wb_delete
```

**执行特点**：
- 线上（实时）和离线（回放）共用同一执行层
- 通过 iframe 消息与 widget 通信
- whiteboardLedger 记录所有操作供后续智能体参考

### 5.2 AI Creator PPT 动作系统

AI Creator 的 PPT 流水线通过 SSE 事件传递状态：

| 后端 type | 前端 stage | 用途 |
|-----------|-----------|------|
| ppt_svg_planning | planning | 内容规划 |
| ppt_svg_designing | designing | 设计策略 |
| ppt_svg_executing | executing | SVG 生成 |
| ppt_svg_finalizing | finalizing | 后处理 |
| ppt_svg_exporting | exporting | 导出 PPTX |
| ppt_svg_done | done | 完成 |

---

## 六、评测体系对比

### 6.1 OpenMAIC 双轨评测

| 评测类型 | 目标 | 方法 |
|---------|------|------|
| Outline Language | 语言推断能力 | LLM-as-Judge，33 个测试用例 |
| Whiteboard Layout | 白板协作布局质量 | VLM Scoring，5 维度评分 |

**Whiteboard Layout 评分维度**：
- readability（可读性）
- overlap（重叠度）
- rendering_correctness（渲染正确性）
- content_completeness（内容完整性）
- layout_logic（布局逻辑）

### 6.2 AI Creator 评测现状

AI Creator 目前**没有独立的评测体系**，主要依靠：
- 人工测试验证
- 用户反馈收集问题

---

## 七、关键差异与可借鉴点

### 7.1 架构差异总结

| 维度 | OpenMAIC | AI Creator | 借鉴价值 |
|------|----------|------------|---------|
| **智能体模式** | 多 agent 协作讨论 | 单 agent 流水线执行 | 高：可引入多 agent 评审 |
| **Director Pattern** | LLM 动态调度 | 固定流程顺序 | 高：可变流程编排 |
| **状态管理** | Zustand 分层 + LangGraph | Pinia stores | 中：分层状态可借鉴 |
| **动作系统** | 统一 ActionEngine | SSE 事件分发 | 高：抽象动作层 |
| **评测体系** | VLM + LLM-as-Judge | 无 | 高：需建立评测 |
| **前端框架** | Next.js App Router | Vue3 | 低：技术栈差异 |

### 7.2 可借鉴的核心设计

1. **Director Pattern**
   - 用 LLM 动态决定下一个执行节点
   - 支持条件分支（USER/AGENT/END）
   - 可应用于 AI Creator 的 PPT 多阶段评审

2. **ActionEngine 统一抽象**
   - 28+ 动作类型统一执行
   - 线上/线下共用同一执行层
   - 便于扩展新动作类型

3. **Peer Context 构建**
   - 每个 agent 知道本轮已发言的内容
   - 避免重复，促进互补
   - 对话式内容生成可借鉴

4. **VLM 辅助评测**
   - 用视觉模型评分白板布局
   - 自动化多维度质量评估

---

## 八、文件索引

### OpenMAIC 核心文件

```
OpenMAIC/
├── lib/orchestration/
│   ├── director-graph.ts          # LangGraph 状态机核心
│   ├── stateless-generate.ts       # 流式生成入口
│   ├── prompt-builder.ts          # Agent prompt 构建
│   └── registry/store.ts          # 智能体注册表
├── lib/action/engine.ts           # 统一动作执行引擎
├── lib/orchestration/types.ts     # 类型定义
├── app/api/chat/route.ts         # 聊天 API 入口
├── lib/prompts/templates/
│   ├── director/system.md        # Director prompt
│   └── agent-system/system.md     # Agent prompt
└── eval/
    ├── outline-language/runner.ts
    └── whiteboard-layout/runner.ts
```

### AI Creator 核心文件

```
backup_agent/
├── backend/ppt_engine/
│   ├── pipeline.py               # PPT 流水线入口
│   ├── sse_bridge.py             # SSE 流式输出
│   └── agents/
│       ├── content_planner.py    # 内容规划
│       ├── design_strategist.py   # 设计策略
│       └── svg_executor.py        # SVG 执行
├── backend/minimax_agent.py       # 触发词分发
└── frontend/src/
    ├── api/chat.ts               # 聊天 API
    └── stores/ppt.ts             # PPT 状态
```

---

## 九、结论

OpenMAIC 是一个**多智能体协作平台**，其核心创新在于：

1. **Director Pattern** — LLM 动态调度多 agent 轮询讨论
2. **统一 ActionEngine** — 28+ 动作类型的抽象执行层
3. **VLM 辅助评测** — 视觉模型自动评分布局质量
4. **两阶段生成** — 大纲 + 场景内容的流水线

AI Creator 是**单用户内容工厂**，采用**固定流水线**。未来可考虑：
- 引入 Director Pattern 实现**多 agent 评审**
- 建立**自动化评测体系**（参考 VLM Scoring）
- 统一**动作抽象层**（参考 ActionEngine）

---

*本报告由 Claude Code AI Assistant 生成，基于 OpenMAIC v1.0 源码分析。*
