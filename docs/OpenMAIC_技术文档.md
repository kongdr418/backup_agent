# OpenMAIC 技术文档

> Open Multi-Agent Interactive Classroom —— 多智能体交互式课堂平台
> 适合 LLM 快速理解项目架构和核心流程

---

## 1. 项目概述

OpenMAIC 是一个开源的 AI 课堂生成与播放平台。用户输入一个主题或上传 PDF，系统通过多智能体协作生成完整的交互式课堂内容，包括幻灯片、测验、互动 Widget、多 Agent 讨论等。生成完成后可在播放器中实时观看 AI 教师的授课过程。

**核心能力：**
- 两阶段 AI 生成（大纲 → 完整场景）
- 多智能体课堂（教师、助教、学生等多种 AI 角色）
- 21 种教学动作（白板、聚光灯、激光笔、Widget 交互等）
- 实时播放引擎（状态机驱动，支持暂停/讨论/中断）
- 16 家 LLM Provider 支持

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Next.js 16 + React 19 + TypeScript 5 |
| 样式 | Tailwind CSS 4 + shadcn/ui |
| 状态 | Zustand 5 + IndexedDB (Dexie) |
| LLM | Vercel AI SDK 6 |
| 多智能体 | LangGraph 1.x |
| 图表 | ECharts 6 |
| 白板 | ProseMirror + KaTeX |
| PPT | pptxgenjs |
| 包管理 | pnpm |

---

## 3. 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 首页输入  │  │ 生成预览  │  │ 课堂播放  │  │ 设置面板  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └─────────────┴─────────────┴─────────────┘           │
│                         │                                   │
│              ┌──────────▼──────────┐                        │
│              │   Zustand Store     │                        │
│              │  (stage/settings/   │                        │
│              │   media/chat/...)   │                        │
│              └──────────┬──────────┘                        │
│                         │                                   │
│              ┌──────────▼──────────┐                        │
│              │   IndexedDB (Dexie) │                        │
│              └─────────────────────┘                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ SSE / POST
┌─────────────────────────▼───────────────────────────────────┐
│                      服务端 (Next.js API)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ /api/generate │  │ /api/chat    │  │ /api/...     │      │
│  │ (生成流水线)  │  │ (多Agent对话) │  │ (其他API)    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         └─────────────────┴─────────────────┘              │
│                         │                                   │
│              ┌──────────▼──────────┐                        │
│              │   LLM 统一层        │                        │
│              │  (callLLM/streamLLM) │                        │
│              └──────────┬──────────┘                        │
│                         │                                   │
│         ┌───────────────┼───────────────┐                   │
│         ▼               ▼               ▼                   │
│    ┌────────┐    ┌──────────┐    ┌──────────┐              │
│    │OpenAI  │    │Anthropic │    │ Google   │  + 13 more   │
│    └────────┘    └──────────┘    └──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 生成流水线（核心流程 1）

用户输入需求 → 生成完整课堂内容，分为两阶段：

### 4.1 Stage 1: 大纲生成

```
UserRequirements (文本/PDF/选项)
    ↓
构建 Prompt（含用户需求 + PDF 内容 + 用户画像 + 可选研究上下文）
    ↓
LLM 调用 → 返回 SceneOutline[]
    ↓
处理：去重 ID、类型降级（interactive/pbl 无配置 → slide）
```

**SceneOutline 结构：**
```typescript
interface SceneOutline {
  id: string;
  type: 'slide' | 'quiz' | 'interactive' | 'pbl';
  title: string;
  description: string;
  keyPoints: string[];
  order: number;
  widgetType?: string;     // interactive 类型用
  widgetOutline?: object;  // Widget 配置
  quizConfig?: object;     // 测验配置
  pblConfig?: object;      // 项目配置
}
```

### 4.2 Stage 2: 场景生成（并行）

```
对每个 SceneOutline 并行执行：
    ├─ 生成内容 → SlideContent / QuizContent / InteractiveContent / PBLContent
    └─ 生成动作 → Action[]（教师的教学动作序列）
         ↓
    组装为 Scene → 存入 StageStore
```

**4 种场景类型：**
| 类型 | 内容 | 用途 |
|------|------|------|
| `slide` | Canvas 元素（文本、图片、形状、图表等）| 常规幻灯片 |
| `quiz` | 选择题/简答题 + 自动评分 | 课堂测验 |
| `interactive` | HTML Widget（仿真、图表、代码、游戏、3D）| 互动教学 |
| `pbl` | 项目配置 + Agentic 工具 | 项目式学习 |

### 4.3 服务端编排流程

```
initializing (5%)  → 解析配置、验证 API Key
researching (10%)  → 可选 Web 搜索
generating_outlines (15%-30%) → Stage 1
generating_scenes (30%-90%)   → Stage 2（顺序生成）
generating_media (90%)        → 图片/视频生成
generating_tts (94%)          → 语音合成
persisting (98%)              → 存入 IndexedDB
completed (100%)
```

---

## 5. 多智能体编排（核心流程 2）

### 5.1 Agent 体系

**默认 6 个 AI 角色：**
| ID | 名称 | 角色 | 优先级 | 权限 |
|----|------|------|--------|------|
| default-1 | AI Teacher | teacher | 10 | 全部（slide + 白板） |
| default-2 | AI助教 | assistant | 7 | 白板 |
| default-3 | 显眼包 | student | 4 | 白板 |
| default-4 | 好奇宝宝 | student | 5 | 白板 |
| default-5 | 笔记员 | student | 5 | 白板 |
| default-6 | 思考者 | student | 6 | 白板 |

**角色权限：**
- `teacher`: spotlight、laser、play_video + 全部白板动作
- `assistant`/`student`: 仅白板动作（wb_open/wb_draw_*/wb_close 等 12 种）

### 5.2 Director 决策流程

```
START → director → agent_generate → director → ... → END
              ↑_________________________|
```

Director 是一个 LangGraph StateGraph：
1. **Director Node**: 根据对话上下文、Agent 优先级、白板状态、用户画像，决定下一个发言的 Agent
2. **Agent Generate Node**: 被选中的 Agent 执行 LLM 调用，注入人设 prompt，输出结构化内容（文本 + 动作）
3. **条件路由**: 根据是否结束讨论，决定回到 Director 还是结束

**决策逻辑：**
- **单 Agent 模式**: 纯代码逻辑，零 LLM 开销
- **多 Agent 模式**: LLM 决策（带 fast-path：Turn 0 存在 triggerAgentId 时直接分派）
- 每轮限制 maxTurns（默认每轮只多一个 director→agent 周期）

### 5.3 客户端 Agent Loop

```
while (turnCount < maxTurns):
    1. 构建请求 = { messages + storeState + directorState + agentConfigs }
    2. POST /api/chat → SSE 流
    3. 解析 SSE 事件，实时更新 UI
    4. 检查退出条件（cue_user / end / max_turns / aborted）
    5. 更新 directorState，继续下一轮
```

**关键特性：**
- **完全无状态**: 所有状态由客户端维护，服务端只处理单次请求
- **可中断**: AbortSignal 贯穿客户端→服务端→LangGraph
- **SSE 流式**: 实时显示 Agent 发言、思考、动作

### 5.4 SSE 事件类型

| 事件 | 说明 |
|------|------|
| `agent_start` | Agent 开始发言 |
| `text_delta` | 文本增量（流式输出） |
| `action` | Agent 执行动作 |
| `thinking` | Director/Agent 加载中 |
| `cue_user` | 提示用户发言 |
| `done` | 本轮完成 |
| `error` | 错误 |

---

## 6. 动作与播放引擎（核心流程 3）

### 6.1 Action 类型（21 种）

**Fire-and-forget（不阻塞）：**
- `spotlight` — 聚焦元素，其余变暗
- `laser` — 激光笔指向效果

**Synchronous（同步执行，等待完成）：**
- `speech` — TTS 语音播放
- `play_video` — 播放视频元素
- `discussion` — 触发圆桌讨论
- `wb_open` / `wb_close` — 打开/关闭白板
- `wb_draw_text` / `wb_draw_shape` / `wb_draw_chart` / `wb_draw_latex` / `wb_draw_table` / `wb_draw_line` / `wb_draw_code` — 白板绘制
- `wb_edit_code` — 代码块行级编辑
- `wb_clear` / `wb_delete` — 清空白板/删除元素
- `widget_highlight` / `widget_setState` / `widget_annotation` / `widget_reveal` — Widget 交互

### 6.2 ActionEngine 执行

```
execute(action) → 检查是否需要自动打开白板 → switch(action.type)
    ├─ spotlight/laser    → 立即执行，5秒后自动清除
    ├─ speech             → 等待 audioPlayer.onEnded
    ├─ play_video         → 等待视频播放结束（5分钟超时）
    ├─ wb_open            → delay(2000ms) 等开启动画
    ├─ wb_draw_*          → delay(800ms) 等淡入动画
    ├─ wb_draw_code       → delay(按行数计算) 等打字动画
    ├─ wb_clear           → delay(按元素数计算) 等级联退出动画
    └─ widget_*           → postMessage + delay(300ms)
```

### 6.3 PlaybackEngine 状态机

```
                    start()                pause()
   idle ───────────────→ playing ───────────────→ paused
    ▲                       ▲                       │
    │                       │    resume()           │
    │                       └───────────────────────┘
    │
    │  handleEndDiscussion()
    │                       confirmDiscussion()
    │                            │
    │                            ▼         pause()
    └────────────────────── live ─────────────────→ paused
                               ▲                      │
                               │ resume / user msg    │
                               └──────────────────────┘
```

**状态说明：**
| 状态 | 说明 |
|------|------|
| `idle` | 空闲，未开始或已停止 |
| `playing` | 正常播放中（讲座模式） |
| `paused` | 暂停（讲座或讨论中都可暂停） |
| `live` | 讨论模式，用户与 Agent 实时对话 |

**核心方法：**
- `start()` — 从头开始播放
- `pause()` — 暂停，保存 TTS/阅读定时器剩余时间
- `resume()` — 恢复播放或讨论
- `stop()` — 停止，重置所有状态
- `confirmDiscussion()` — 用户加入讨论，保存讲座位置
- `handleUserInterrupt()` — 用户消息打断，进入 live 模式

**播放进度跟踪：**
- `sceneIndex` / `actionIndex` — 当前场景/动作游标
- `savedSceneIndex` / `savedActionIndex` — 讨论中断时保存的位置
- 场景切换时自动清除 spotlight/laser 效果

---

## 7. LLM 统一层

### 7.1 统一接口

```typescript
// 非流式
callLLM(params, source, retryOptions?, thinking?) → Promise<GenerateTextResult>

// 流式
streamLLM(params, source, thinking?) → StreamTextResult
```

**设计要点：**
- `params` 直接透传给 Vercel AI SDK，保持兼容性
- `source` 标签用于日志分组（如 'scene-stream'、'agent-chat'）
- `thinking` 配置统一映射为各厂商特有的 providerOptions
- 独立重试机制：处理验证失败（如空响应）

### 7.2 Provider 支持（16 家）

| Provider | API 类型 | 说明 |
|----------|----------|------|
| OpenAI | openai | GPT 系列 |
| Anthropic | anthropic | Claude 系列 |
| Google | google | Gemini 系列 |
| DeepSeek | openai | DeepSeek V4 等 |
| Qwen | openai | 通义千问 |
| Kimi | openai | Moonshot |
| MiniMax | anthropic | 走 Anthropic 兼容层 |
| GLM | openai | 智谱 |
| SiliconFlow | openai | 硅基流动 |
| Doubao | openai | 字节豆包 |
| OpenRouter | openai | 聚合平台 |
| Grok | openai | xAI |
| Tencent Hunyuan | openai | 腾讯混元 |
| Xiaomi MiMo | openai | 小米 |
| Lemonade | openai | 本地代理 |
| Ollama | openai | 本地模型 |

### 7.3 Thinking 适配

6 种 thinking 控制类型，自动映射到各厂商参数：
- `none` — 不可配置
- `toggle` — 简单开关
- `toggle-budget` — 开关 + token 预算
- `effort` — 离散档位（OpenAI/Anthropic/DeepSeek 等）
- `level` — 离散 level 档位（Gemini 3.x）
- `budget-only` — 仅预算调节（Gemini 2.5 Pro）
- `mode` — 模式选择（豆包 Seed 1.8）

**双路径注入：**
- **Native Provider** → `providerOptions`（OpenAI/Anthropic/Google 原生支持）
- **OpenAI-compatible** → `AsyncLocalStorage` + 自定义 fetch wrapper 注入 HTTP body

---

## 8. 状态管理

### 8.1 Zustand Store 架构

| Store | 用途 | 持久化 |
|-------|------|--------|
| `stageStore` | 课堂数据（scenes、slides、actions） | IndexedDB |
| `settingsStore` | LLM/TTS/ASR/Media/WebSearch 配置 | localStorage |
| `chatStore` | 多 Agent 对话历史 | IndexedDB |
| `mediaGenerationStore` | 媒体生成任务跟踪 | 内存 |
| `userProfileStore` | 用户昵称、头像、简介 | localStorage |

### 8.2 IndexedDB 结构（Dexie）

10 张表，版本 10：
- `stages` — 课堂元数据
- `scenes` — 场景数据
- `slides` — 幻灯片 Canvas 数据
- `actions` — 动作序列
- `chatMessages` — 聊天消息
- `whiteboards` — 白板数据
- `media` — 生成的媒体文件（Blob）
- `mediaTasks` — 媒体生成任务
- `ttsAudio` — TTS 音频缓存
- `agentProfiles` — Agent 配置

---

## 9. 关键文件索引

### 生成流水线
| 文件 | 说明 |
|------|------|
| `lib/generation/pipeline-runner.ts` | 顶层入口：createGenerationSession + runGenerationPipeline |
| `lib/generation/outline-generator.ts` | Stage 1: 大纲生成 |
| `lib/generation/scene-generator.ts` | Stage 2: 并行场景生成 |
| `lib/generation/scene-builder.ts` | 场景组装 |
| `lib/server/classroom-generation.ts` | 服务端 7 阶段编排 |
| `app/api/generate/scene-outlines-stream/route.ts` | SSE 流式大纲 API |

### 多智能体编排
| 文件 | 说明 |
|------|------|
| `lib/orchestration/director-graph.ts` | LangGraph Director-Agent 图 |
| `lib/orchestration/registry/store.ts` | Agent 注册表（6 个默认 Agent） |
| `lib/orchestration/registry/types.ts` | AgentConfig 类型定义 |
| `lib/chat/agent-loop.ts` | 客户端 Agent 循环 |
| `app/api/chat/route.ts` | 聊天 API |
| `lib/types/chat.ts` | SSE 事件类型 |

### 动作与播放
| 文件 | 说明 |
|------|------|
| `lib/action/engine.ts` | ActionEngine（21 种动作执行） |
| `lib/playback/engine.ts` | PlaybackEngine（状态机） |
| `lib/playback/derived-state.ts` | 派生状态计算 |
| `lib/types/action.ts` | Action 类型定义 |

### LLM 层
| 文件 | 说明 |
|------|------|
| `lib/ai/llm.ts` | callLLM / streamLLM 统一接口 |
| `lib/ai/providers.ts` | 16 家 Provider 注册表 |
| `lib/ai/thinking-adapters.ts` | Thinking 配置映射 |
| `lib/ai/model-metadata.ts` | 50+ 模型的 thinking 能力元数据 |
| `lib/store/settings.ts` | 设置存储（Provider 配置） |

### 类型定义
| 文件 | 说明 |
|------|------|
| `lib/types/generation.ts` | UserRequirements, SceneOutline, GenerationSession |
| `lib/types/stage.ts` | Stage, Scene, SceneContent |
| `lib/types/action.ts` | Action 联合类型（21 种） |
| `lib/types/chat.ts` | ChatSession, StatelessEvent |
| `lib/types/provider.ts` | ProviderId, ModelInfo, ThinkingConfig |

---

## 10. 数据流总结

```
【生成流程】
用户输入 → outline-generator → SceneOutline[]
                              ↓
                    scene-generator（并行）
                    ├─ generateSceneContent() → Slide/Quiz/Interactive/PBL
                    └─ generateSceneActions() → Action[]
                              ↓
                         StageStore → IndexedDB

【播放流程】
用户点击播放 → PlaybackEngine.start()
                    ↓
              processNext() 循环
              ├─ speech → ActionEngine.execute() → 等待 TTS
              ├─ spotlight/laser → 立即执行
              ├─ wb_draw_* → 等待动画
              ├─ discussion → 暂停讲座 → 等待用户确认 → live 模式
              └─ widget_* → postMessage → 等待响应
                    ↓
              所有动作执行完 → completed

【多 Agent 对话流程】
用户消息 → AgentLoop
              ↓
         POST /api/chat → Director Graph
              ↓
         Director Node → 决定 nextAgent
              ↓
         Agent Generate Node → LLM 生成（人设注入）
              ↓
         结构化输出 → SSE 流回客户端
              ↓
         客户端解析 → 更新 UI（文本 + 动作）
              ↓
         检查退出条件 → 继续/结束
```

---

*文档生成时间: 2026-05-25*
*基于 OpenMAIC v0.2.1 代码分析*
