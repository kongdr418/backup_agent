# PPT Engine 功能迁移设计文档

> **日期**: 2026-05-27
> **来源**: paper-ppt-agent (commit aab5417)
> **目标**: backup_agent/backend/ppt_engine
> **策略**: 逐项增量迁移，每项独立可测试

---

## 一、迁移范围

### P0 — 高优先级（SVG 质量提升）

| # | 功能 | 新建/改动 | 改动量 |
|---|---|---|---|
| 1 | Static Critic 补全 10 条规则 | 改 `critic/static_critic.py` | ~300 行 |
| 2 | svg_text_reflow | 新建 `finalize/svg_text_reflow.py` | ~200 行 |
| 3 | Visual Critic (VLM) | 新建 `critic/visual_critic.py` + 改动 | ~400 行 |

### P1 — 中优先级（内容质量 + 模板管理）

| # | 功能 | 新建/改动 | 改动量 |
|---|---|---|---|
| 4 | Provider Guidance | 新建 `agents/provider_guidance.py` | ~100 行 |
| 5 | Deep Research 4-Pass | 新建 `agents/research_agent.py` + 4 个 prompt | ~1000 行 |
| 6 | 模板导入系统 | 新建 `template_import/` 目录（12 个文件） | ~3000 行 |

---

## 二、设计决策

| 决策 | 选择 | 原因 |
|---|---|---|
| 页面类型 | 5 种基础类型 | cover/toc/chapter/content/ending 覆盖 90% 教育 PPT |
| Visual Critic | 可选开关，默认关闭 | DeepSeek 暂不支持视觉，用户配置多模态模型后开启 |
| Deep Research | 可选开关，默认关闭 | 4-Pass 增加成本和延迟，用户按需开启 |
| VLM 渲染 | resvg-py | 高质量 SVG→PNG 渲染 |
| 模板协作模式 | classic + direct | 覆盖大部分场景，不依赖 Agent SDK |
| 迁移策略 | 逐项增量 | 每项独立可测试，风险最低 |

---

## 三、模块详细设计

### 3.1 Static Critic 补全 10 条规则

**改动文件**: `ppt_engine/critic/static_critic.py`

在现有 `check_svg()` 函数中新增以下规则检测：

| 规则 ID | 严重度 | 检测逻辑 |
|---|---|---|
| `image_missing_href` | error | `<image>` 元素无 `href` 或 `xlink:href` 属性 |
| `image_internal_ref` | error | `<image href="#...">` 引用内部 SVG 元素 |
| `text_too_close_to_edge` | warning | 文本 bbox 距画布边缘 < 30px |
| `text_too_dense` | warning | 文本总面积 > 内容区域 80% |
| `text_overflow_in_container` | error | 文本 bbox 超出其所在容器（card/callout）bbox |
| `empty_bullet` | error | `<text>` 包含 bullet 字符（•、-、*）但 30px 内无相邻文本 |
| `icon_text_misalign` | warning | `<use>` 图标与相邻 `<text>` 垂直中心差 > 8px |
| `bold_tspan_in_cjk` | warning | CJK 字符范围内含 `<tspan font-weight="bold">`，CJK 粗体渲染不佳 |
| `inline_emphasis_drift` | error | 短彩色关键词（<15 字符）与同 baseline 前文水平距离 > 100px |
| `line_space_waste` | warning | 同一 `<text>` 内 `<tspan>` 行间距 > 2.5x 字号，浪费垂直空间 |

**CriticConfig 新增字段**:
```python
edge_margin_px: float = 30.0         # text_too_close_to_edge 阈值
density_threshold: float = 0.80      # text_too_dense 阈值
bullet_search_radius: float = 30.0   # empty_bullet 搜索半径
misalign_tolerance: float = 8.0      # icon_text_misalign 容差
emphasis_drift_gap: float = 100.0    # inline_emphasis_drift 距离阈值
line_space_waste_ratio: float = 2.5  # line_space_waste 比率阈值
```

**不变式**: 现有 12 条规则的检测逻辑和阈值完全保留，不做任何修改。

---

### 3.2 svg_text_reflow

**新建文件**: `ppt_engine/finalize/svg_text_reflow.py`

**插入位置**: `finalize/finalize.py` 步骤序列中，在 `merge_adjacent_text`(step 7) 之后、`normalize_fonts`(step 8) 之前。

**功能**:

1. **图标-文本对齐修复**:
   - 扫描所有 `<use>` 元素（图标占位符）
   - 查找同父容器内最近的 `<text>` 元素
   - 计算图标和文本的垂直中心，调整 `y` 坐标使对齐（容差 4px 内跳过）

2. **文本行合并**:
   - 检测同一容器内相邻 `<text>` 元素
   - 如果 x 坐标相同（±2px）、行间距 < 1.5x 字号、内容语义连续，则合并为单个 `<text>` + 多 `<tspan>`

**接口**:
```python
def reflow_text(svg_content: str) -> str:
    """对单个 SVG 进行文本重排优化。返回修改后的 SVG 字符串。"""
```

**finalize.py 改动**:
```python
# 在 merge_adjacent_text 之后插入
from ppt_engine.finalize.svg_text_reflow import reflow_text
# ... 在流水线中添加 step 7.5
```

---

### 3.3 Visual Critic（可选开关）

**新建文件**: `ppt_engine/critic/visual_critic.py`
**改动文件**: `agents/svg_executor.py`、`config.py`、`app.py`、`sse_bridge.py`

#### 3.3.1 visual_critic.py

```python
async def visual_check(
    svg_content: str,
    *,
    llm: LLMProvider,
    model: str,
    page_num: int,
    page_title: str = "",
    style: str = "education",
    config: VisualCriticConfig | None = None,
) -> VisualCheckOutcome:
    """
    1. 用 resvg-py 将 SVG 渲染为 PNG
    2. 将 PNG 发给 VLM（多模态模型）
    3. VLM 返回 JSON 格式的视觉问题报告
    4. 解析为 VisualCheckOutcome
    """
```

**VLM 系统提示词**（复用 paper-ppt-agent）:
```
You are a visual QA reviewer for presentation slides.
Look for: overlapping elements, text escaping containers,
decorative horizontal LINE under title (forbidden AI pattern),
low contrast text, cramped spacing, misalignment, figures too small,
text-only slides, centered body text, decorative clutter.
Respond with strict JSON: {"issues": [...]}
```

**VisualCriticConfig**:
```python
@dataclass
class VisualCriticConfig:
    enabled: bool = False           # 默认关闭
    model: str = "deepseek-v4-pro"  # VLM 模型
    max_issues: int = 10            # 最大返回问题数
```

**VisualCheckOutcome**:
```python
@dataclass
class VisualCheckOutcome:
    issues: list[dict]   # [{"rule": "...", "severity": "...", "detail": "..."}]
    has_errors: bool     # 是否有 error 级别问题
    raw_response: str    # VLM 原始响应
```

#### 3.3.2 svg_executor.py 改动

在 static critic 之后、修复循环之前插入：

```python
# 现有: static_violations = check_svg(svg_content)
# 新增:
if visual_critic_enabled:
    visual_outcome = await visual_check(
        svg_content, llm=llm, model=visual_critic_model,
        page_num=page_num, page_title=page_title,
    )
    if visual_outcome.has_errors:
        # 将 visual issues 合并到修复 prompt
        repair_prompt += visual_outcome.to_prompt_block()
```

#### 3.3.3 config.py 新增

```python
visual_critic_enabled: bool = False
visual_critic_model: str = "deepseek-v4-pro"
```

#### 3.3.4 app.py 改动

`/api/ppt-svg/generate` 端点新增参数：
```python
visual_critic: bool = False  # 用户可选开启
```

#### 3.3.5 依赖

新增 `requirements.txt` 依赖：
```
resvg>=0.2.0
```

---

### 3.4 Provider Guidance

**新建文件**: `ppt_engine/agents/provider_guidance.py`

```python
def is_deepseek_provider(provider_name: str, base_url: str | None) -> bool:
    """检测是否为 DeepSeek provider。"""

def deepseek_research_guidance(detail_level: str) -> str:
    """Research 阶段的 DeepSeek 特化校准提示词。"""

def deepseek_strategy_guidance(detail_level: str) -> str:
    """Strategy 阶段的 DeepSeek 特化校准提示词。"""

def deepseek_executor_guidance(detail_level: str) -> str:
    """Executor 阶段的 DeepSeek 特化校准提示词。"""
```

**改动文件**:
- `agents/content_planner.py`（或新的 `agents/research_agent.py`）：注入 research guidance
- `agents/design_strategist.py`：注入 strategy guidance
- `agents/svg_executor.py`：注入 executor guidance

**校准内容**（以 very_high 为例）:
- Research: 确保保留分析深度、机制命名、证据块，避免纯标签式幻灯片
- Strategy: 要求每页有具体的内容块，不允许空洞的布局描述
- Executor: 保持内容深度，避免因 SVG 空间限制而过度简化

---

### 3.5 Deep Research 4-Pass（可选开关）

**新建文件**:
- `ppt_engine/agents/research_agent.py` — 主逻辑
- `ppt_engine/prompts/research_pass1_topic_analysis.md` — Pass 1 主题深度分析
- `ppt_engine/prompts/research_pass2_narrative.md` — Pass 2 叙事弧设计
- `ppt_engine/prompts/research_pass3_manuscript.md` — Pass 3 手稿生成
- `ppt_engine/prompts/research_pass4_review.md` — Pass 4 质量自审

**改动文件**: `pipeline.py`、`config.py`、`app.py`

#### 3.5.1 Pass 适配（从论文→教育主题）

| Pass | 原版（论文） | 适配后（教育主题） |
|---|---|---|
| 1 | 批评性论文分析 | **主题深度分析**: 多角度拆解主题，识别核心概念、关键知识点、常见误区、先修知识、实践应用 |
| 2 | 叙事弧设计 | **教学叙事弧**: 设计适合教学的叙事结构（引入→基础→深入→应用→总结） |
| 3 | 手稿生成 | 手稿生成（保留原逻辑） |
| 4 | 质量自审 | 质量自审（保留原逻辑） |

#### 3.5.2 research_agent.py 核心接口

```python
async def run_deep_research(
    topic: str,
    llm: LLMProvider,
    model: str,
    *,
    language: str = "zh",
    num_slides: int | None = None,
    detail_level: str = "normal",
    provider_guidance: str = "",
) -> AsyncIterator[ResearchEvent]:
    """
    4-Pass 深度研究流程:
    Pass 1: 主题深度分析 → research_pass1.md
    Pass 2: 叙事弧设计 → research_pass2.md
    Pass 3: 手稿生成 → manuscript.md
    Pass 4: 质量自审 → 可能修订 manuscript.md
    """
```

#### 3.5.3 质量阈值

复用 paper-ppt-agent 的 7 维度 x 5 分制评分：
- 连贯性、信息密度、叙事一致性、结构合理性、内容深度、语言质量、视觉提示
- 阈值: 28/35 分，低于阈值重试（最多 3 次 manuscript 生成）

#### 3.5.4 pipeline.py 改动

```python
# Stage 1: Content Planning
yield PipelineEvent("content_planning", "started", "...", 0.05)

if deep_research:
    async for event in run_deep_research(topic, llm, model, ...):
        yield PipelineEvent(event.stage, event.status, event.message, event.progress, event.data)
    manuscript = (project_dir / "manuscript.md").read_text(encoding="utf-8")
else:
    manuscript = await plan_content(topic, llm, model, ...)  # 现有逻辑
```

#### 3.5.5 config.py 新增

```python
deep_research_enabled: bool = False
deep_research_quality_threshold: int = 28  # 7x5=35 满分
deep_research_max_attempts: int = 3
```

#### 3.5.6 app.py 改动

`/api/ppt-svg/generate` 端点新增参数：
```python
deep_research: bool = False  # 用户可选开启
```

---

### 3.6 模板导入系统

**新建目录**: `ppt_engine/template_import/`

#### 3.6.1 文件清单

| 文件 | 来源 | 适配工作 |
|---|---|---|
| `__init__.py` | 新建 | 包初始化 |
| `pipeline.py` | 迁移 | 去掉 agent 模式，保留 classic + direct |
| `types.py` | 迁移 | 去掉 agent 相关类型 |
| `manifest.py` | 迁移 | 去掉论文关键词，改为通用分类 |
| `page_classifier.py` | 迁移 | 调整关键词（去掉"第三章""谢谢"等学术词） |
| `chrome_detector.py` | 直接迁移 | 无需改动 |
| `asset_extractor.py` | 直接迁移 | 无需改动 |
| `templateizer.py` | 迁移 | 调整占位符推断逻辑 |
| `placeholder_schema.py` | 迁移 | 保留通用占位符，去掉论文专用的 |
| `llm_client.py` | 迁移 | 修改系统提示词为通用模板分析 |
| `persistence.py` | 直接迁移 | 无需改动 |
| `renderer/__init__.py` | 直接迁移 | 无需改动 |
| `renderer/powerpoint_com.py` | 直接迁移 | 无需改动 |
| `renderer/libreoffice.py` | 直接迁移 | 无需改动 |
| `renderer/slide_metrics.py` | 直接迁移 | 无需改动 |

#### 3.6.2 页面类型保留

```python
PageType = Literal["cover", "toc", "chapter", "content", "ending"]
```

5 种基础类型，与 paper-ppt-agent 一致。

#### 3.6.3 占位符白名单

```python
PLACEHOLDER_WHITELIST = {
    "TITLE", "PAGE_TITLE", "SUBTITLE", "AUTHOR", "DATE",
    "CHAPTER_NUM", "CHAPTER_NUMBER", "CHAPTER_TITLE",
    "TOC_LIST", "TOC_ITEM_1", "TOC_ITEM_2", "TOC_ITEM_3",
    "TOC_ITEM_4", "TOC_ITEM_5",
    "CONTENT_AREA", "ENDING_TITLE", "ENDING_MESSAGE",
    "LOGO_HEADER", "LOGO_FOOTER",
}
```

与原版一致，这些占位符对教育 PPT 同样适用。

#### 3.6.4 Page Classifier 适配

**保留的信号**: is_first_slide, is_last_slide, text_density, decoration_ratio, large_font_ratio

**调整的关键词**:
```python
# 原版学术词 → 通用词
keyword_toc = {"目录", "contents", "outline", "agenda", "目录"}
keyword_chapter = {"chapter", "章", "节", "part", "section", "模块", "单元"}
keyword_thanks = {"谢谢", "thanks", "thank you", "结束", "q&a", "questions"}
```

**权重保持不变**——原版的权重矩阵对通用 PPT 同样有效。

#### 3.6.5 协作模式

- **classic**: 完整流程（上传→分析→渲染→资源检测→LLM 审查→复核→确认）
- **direct**: 5 页 PPTX 直接作为模板（跳过模板化，生成 design_spec.md）

去掉 agent 模式（不依赖 Claude Agent SDK）。

#### 3.6.6 API 端点

新增到 `app.py`：

```python
@app.route("/api/templates/upload", methods=["POST"])
def templates_upload(): ...

@app.route("/api/templates/import/<import_id>", methods=["GET"])
def templates_import_status(import_id): ...

@app.route("/api/templates/import/<import_id>/review", methods=["GET", "PUT"])
def templates_import_review(import_id): ...

@app.route("/api/templates/import/<import_id>/assist", methods=["POST"])
def templates_import_assist(import_id): ...

@app.route("/api/templates/import/<import_id>/feedback", methods=["POST"])
def templates_import_feedback(import_id): ...

@app.route("/api/templates/import/<import_id>/confirm", methods=["POST"])
def templates_import_confirm(import_id): ...

@app.route("/api/templates/list", methods=["GET"])
def templates_list(): ...

@app.route("/api/templates/<template_id>", methods=["DELETE"])
def templates_delete(template_id): ...
```

#### 3.6.7 存储目录

```
ppt_engine/template_import/workspaces/<import_id>/
  ├── state.json
  ├── review.json
  ├── manifest.json
  ├── svg/
  │   ├── slide-001.svg
  │   └── ...
  ├── assets/
  │   └── <sha1>.<ext>
  └── layouts/
      └── <template_id>/
          ├── 01_cover.svg
          ├── 02_toc.svg
          ├── 03_chapter.svg
          ├── 04_content.svg
          ├── 05_ending.svg
          ├── design_spec.md
          ├── manifest.json
          └── assets/
```

#### 3.6.8 LLM 提示词适配

原版 prompt 以论文分析为导向，需改为通用模板分析：

```
You are a presentation template import analyst.
Analyze the uploaded PPTX template and produce a structured import plan.

Your task:
1. Identify which slides represent each page type (cover, toc, chapter, content, ending)
2. Classify image assets by role (logo, background, decoration, content_image, ignore)
3. Decide which text elements to preserve as chrome (headers, footers, page numbers)
4. Suggest placeholder tokens for replaceable content areas

Respond with a single JSON object matching the LLMTemplateImportPlan schema.
```

---

## 四、迁移顺序

```
Phase 1: Static Critic 补全 (独立，无依赖)
    ↓
Phase 2: svg_text_reflow (独立，无依赖)
    ↓
Phase 3: Visual Critic (依赖 resvg-py)
    ↓
Phase 4: Provider Guidance (独立，无依赖)
    ↓
Phase 5: Deep Research 4-Pass (依赖 Provider Guidance)
    ↓
Phase 6: 模板导入系统 (最大，独立)
```

Phase 1-3 可以并行开发（P0），Phase 4-6 按顺序开发（P1）。

---

## 五、依赖变更

### requirements.txt 新增

```
resvg>=0.2.0          # Visual Critic SVG→PNG 渲染
```

### 可选依赖（模板导入）

```
pymupdf>=1.24.0       # PDF 解析（已有则复用）
Pillow>=10.0.0        # 图像处理（已有则复用）
```

---

## 六、测试计划

| 模块 | 测试方式 |
|---|---|
| Static Critic | 构造违规 SVG，验证每条规则被正确检测 |
| svg_text_reflow | 用现有 SVG PPT 测试 finalize 流水线 |
| Visual Critic | 用生成的 SVG 测试 VLM 调用和报告解析 |
| Provider Guidance | 对比有/无 guidance 的生成结果 |
| Deep Research | 同一主题分别用单次和 4-Pass 生成，对比内容质量 |
| 模板导入 | 上传测试 PPTX，验证完整导入流程 |

---

## 七、风险与缓解

| 风险 | 缓解措施 |
|---|---|
| DeepSeek VLM 不支持图片输入 | Visual Critic 默认关闭，用户自行配置多模态模型 |
| resvg-py 安装失败（Windows） | 降级为 svglib + reportlab |
| 模板导入 PowerPoint COM 不可用 | LibreOffice 降级路径 |
| Deep Research 4-Pass 成本高 | 默认关闭，用户按需开启 |
| 迁移代码引入 bug | 逐项迁移，每项独立测试 |
