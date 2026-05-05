# PPT SVG 引擎

基于 SVG 中间格式的多 Agent PPT 生成引擎。输入课程主题，输出高质量 SVG 预览 + 可编辑 PPTX。

## 快速开始

### 1. 启动服务

```bash
pip3 install -r requirements.txt
python3 app.py
```

服务运行在 `http://127.0.0.1:5000`

### 2. 生成 PPT

```bash
curl -N -X POST http://127.0.0.1:5000/api/ppt-svg/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Python 基础语法", "num_slides": 8}'
```

返回 SSE 事件流，实时推送每一页 SVG 生成进度。

### 3. 预览 SVG

```bash
# 预览单页
curl http://127.0.0.1:5000/api/ppt-svg/preview/<job_id>/1

# 预览全部
curl http://127.0.0.1:5000/api/ppt-svg/preview-all/<job_id>
```

### 4. 下载 PPTX

```bash
curl -O http://127.0.0.1:5000/api/ppt-svg/download/<job_id>
```

### 5. 查看历史

```bash
curl http://127.0.0.1:5000/api/ppt-svg/list
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ppt-svg/generate` | POST | SSE 流式生成 PPT |
| `/api/ppt-svg/preview/<job_id>/<page>` | GET | 获取单页 SVG |
| `/api/ppt-svg/preview-all/<job_id>` | GET | 获取全部 SVG |
| `/api/ppt-svg/download/<job_id>` | GET | 下载 PPTX 文件 |
| `/api/ppt-svg/list` | GET | 列出所有生成记录 |

---

## 生成参数

`POST /api/ppt-svg/generate` 请求体：

```json
{
  "topic": "课程主题（必填）",
  "num_slides": 8,
  "style": "education",
  "language": "zh",
  "detail_level": "normal",
  "canvas_format": "ppt169"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `topic` | string | **必填** | 课程主题 |
| `num_slides` | int | 自动 | 页数，不填由 AI 决定 |
| `style` | string | `education` | 设计风格 |
| `language` | string | `zh` | 语言（zh/en） |
| `detail_level` | string | `normal` | 详细程度（brief/normal/detailed） |
| `canvas_format` | string | `ppt169` | 画布格式 |

### 可用风格

| 风格 | 说明 |
|------|------|
| `education` | 教育课件（默认） |
| `academic` | 学术风格 |
| `consulting` | 咨询风格 |
| `tech` | 科技风格 |
| `general` | 通用风格 |

### 可用画布格式

| 格式 | 尺寸 |
|------|------|
| `ppt169` | 1280×720（16:9） |
| `ppt43` | 1024×768（4:3） |
| `a4` | 794×1123（A4 竖版） |

---

## SSE 事件格式

生成过程中返回的 SSE 事件：

```json
// 进度事件
{"type": "ppt_svg_progress", "stage": "svg_generation", "message": "第 3/8 页生成完成", "progress": 0.45, "slide": {"page": 3, "svg": "<svg>...</svg>"}}

// 阶段开始
{"type": "ppt_svg_started", "stage": "design", "message": "正在生成设计规范...", "progress": 0.15}

// 阶段完成
{"type": "ppt_svg_complete", "stage": "design", "message": "设计规范生成完成", "progress": 0.3}

// 全部完成
{"type": "ppt_svg_complete", "stage": "export", "message": "PPT 生成完成!", "progress": 1.0, "output_path": "...", "job_id": "..."}

// 错误
{"type": "ppt_svg_error", "stage": "svg_generation", "message": "生成失败: ...", "progress": 0.5}

// 结束信号
{"done": true}
```

### stage 阶段说明

| stage | 说明 | 进度范围 |
|-------|------|----------|
| `init` | 初始化 | 0% |
| `content_planning` | 内容规划（AI 生成手稿） | 0%~15% |
| `design` | 设计策略（AI 生成设计规范） | 15%~30% |
| `svg_generation` | 逐页 SVG 生成 | 30%~75% |
| `finalize` | SVG 后处理 | 75%~85% |
| `export` | PPTX 导出 | 85%~100% |

---

## 生成流程

```
课程主题 → Content Planner Agent → Design Strategist Agent → SVG Executor（含 Critic）→ SVG 后处理 → PPTX 导出
```

1. **Content Planner**：根据主题生成课程手稿（Markdown 格式，`---` 分隔每页）
2. **Design Strategist**：根据手稿生成设计规范（配色、布局、字体等）
3. **SVG Executor**：逐页生成 SVG，每页经过 Static Critic 校验，不合格自动修复（最多 2 次）
4. **SVG Finalize**：后处理（图标嵌入、图片 Base64 化、文本扁平化、圆角矩形转 path）
5. **PPTX Export**：SVG → DrawingML XML → PPTX（原生可编辑），失败时降级为 PNG 嵌入

---

## 工作区目录结构

每次生成会创建独立目录：

```
generated_svg_ppt/
└── course_ppt_20260505_143022/
    ├── metadata.json          # 生成参数
    ├── manuscript.md          # 课程手稿
    ├── design_spec.md         # 设计规范
    ├── svg_output/            # 原始 SVG
    │   ├── 01_title.svg
    │   └── ...
    ├── svg_final/             # 后处理 SVG（用于预览和导出）
    └── exports/
        └── presentation_*.pptx
```

---

## 环境变量

```bash
DEEPSEEK_API_KEY=sk-xxx       # DeepSeek API Key（必填）
DEEPSEEK_BASE_URL=...         # 自定义 API 地址（可选）
```

---

## 前端接入示例

### JavaScript（EventSource）

```javascript
const source = new EventSource('/api/ppt-svg/generate?' + new URLSearchParams({
  topic: 'Python 基础语法',
  num_slides: 8,
}));

source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.done) {
    source.close();
    return;
  }
  if (data.slide) {
    // 渲染 SVG 到页面
    renderSlide(data.slide.page, data.slide.svg);
  }
  // 更新进度条
  updateProgress(data.progress);
};
```

### Python（requests）

```python
import requests
import json

response = requests.post(
    'http://127.0.0.1:5000/api/ppt-svg/generate',
    json={'topic': 'Python 基础语法', 'num_slides': 8},
    stream=True,
)

for line in response.iter_lines():
    if line.startswith(b'data: '):
        data = json.loads(line[6:])
        if data.get('done'):
            job_id = last_job_id
            break
        if 'job_id' in data:
            last_job_id = data['job_id']
        print(f"[{data['stage']}] {data['message']} ({data['progress']*100:.0f}%)")
```
