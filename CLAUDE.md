# MiniMax Agent 后端 - AI 开发手册

## 项目背景

Flask 后端服务，提供 AI 教育内容生成功能（PPT、讲义、习题、测验等）。

## 技术栈

- **后端**: Python Flask
- **AI 模型**: MiniMax API / DeepSeek API
- **PPT 生成**: pptxgenjs (Node.js)
- **依赖安装**: `pip3 install -r requirements.txt` + `npm install`

## 启动方式

```bash
pip3 install -r requirements.txt  # Python 依赖
npm install                       # Node.js 依赖（pptxgenjs）
python3 app.py                    # 启动服务
```

服务运行在 http://127.0.0.1:5000

---

## MANDATORY: AI 工作流程

每次新会话必须遵循以下流程：

### Step 1: 初始化环境

```bash
pip3 install -r requirements.txt
npm install
python3 app.py
```

确保服务启动后再继续。

### Step 2: 领取任务

读取 `task.json`，选择一个 `passes: false` 的任务。

选择优先级：
1. `passes: false` 的任务
2. 高优先级任务优先
3. 基础功能优先于高级功能

### Step 3: 实现任务

- 仔细阅读任务描述
- 遵循现有代码风格和模式
- 保持代码简洁，不做过度设计

### Step 4: 测试验证

**强制测试要求：**

1. **大幅修改**（新增模块、新增 API 端点、修改核心逻辑）：
   - **必须启动服务测试！**
   - 使用 curl 测试 API
   - 验证功能正常工作

2. **小幅修改**（修复 bug、调整参数、添加注释）：
   - 运行服务验证无报错
   - 检查日志输出

3. **所有修改必须通过：**
   - `python3 -c "import app"` 无语法错误
   - 服务启动无异常
   - API 调用返回正确结果

**重要：生成器测试必须通过 Flask API，不建议直接运行 .py 文件。**

原因：生成器（如 `speech_generator.py`、`knowledge_card_generator.py`）直接调用 `os.environ.get('DEEPSEEK_API_KEY')`，但 `.env` 文件由 Flask 的 `load_dotenv()` 加载。直接运行 `python xxx_generator.py` 会因缺少 API Key 而失败。

正确方式：
```bash
# 启动 Flask 服务
python3 app.py
# 新开终端，用 curl 测试
curl -s -X POST http://127.0.0.1:5000/api/chat/stream -H "Content-Type: application/json; charset=utf-8" -d @/tmp/test.json
```

### Step 5: 更新进度

在 `progress.txt` 末尾追加：

```
## [日期] - Task: [任务描述]

### What was done:
- [具体改动]

### Testing:
- [如何测试]

### Notes:
- [备注]
```

### Step 6: 提交代码

**所有更改必须在同一个 commit 中！**

```bash
# 1. 更新 task.json，passes: false → true
# 2. 更新 progress.txt
# 3. 提交
git add .
git commit -m "[任务描述] - completed"
```

**规则：**
- 只在所有步骤验证通过后才标记 `passes: true`
- 永远不要删除或修改任务描述
- **一个任务的所有内容必须在同一个 commit 中提交**

---

## 项目结构

```
backup_agent_32/
├── CLAUDE.md              # 本文件 - 工作规范
├── task.json              # 任务列表
├── progress.txt            # 进度日志
├── app.py                 # Flask 主应用
├── minimax_agent.py        # MiniMax Agent 核心
├── lecture_generator.py    # 讲义生成器
├── content_generator.py    # 社媒内容生成器
├── ppt_generator.py        # PPT 生成器
├── course_outline_generator.py  # 课程大纲
├── speech_generator.py     # 讲稿
├── exercise_generator.py    # 习题集
├── quiz_generator.py        # 课堂测验
├── knowledge_card_generator.py  # 知识卡片
├── mindmap_generator.py     # 思维导图
├── memory_manager.py       # 记忆管理
├── generated_ppt/          # 生成的 PPT
├── generated_outlines/     # 课程大纲
├── generated_speeches/     # 讲稿
├── generated_exercises/    # 习题集
├── generated_quizzes/       # 课堂测验
├── generated_cards/        # 知识卡片
├── generated_mindmaps/     # 思维导图
├── generated_content/      # 社媒内容
├── memory/                 # 记忆系统
└── ...
```

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/chat` | POST | 非流式聊天 |
| `/api/chat/stream` | POST | 流式聊天（主要接口） |
| `/api/files` | GET | 获取生成的文件列表 |
| `/api/files/delete` | POST | 删除文件 |
| `/api/settings` | GET/POST | 设置读写 |
| `/api/memory` | GET | 记忆摘要 |

---

## 生成功能触发词

| 功能 | 触发命令 |
|------|----------|
| PPT | `制作PPT：主题` |
| 课程大纲 | `课程大纲：主题` |
| 讲稿 | `讲稿：主题` |
| 习题集 | `习题集：主题` |
| 课堂测验 | `课堂测验：主题` |
| 知识卡片 | `知识卡片：主题` |
| 思维导图 | `思维导图：主题` |
| 小红书图文 | `生成图文：主题` |
| 短视频脚本 | `生成短视频：主题` |

---

## 阻塞处理

**如果任务无法完成，必须：**

1. 在 `progress.txt` 记录当前进度和阻塞原因
2. 清晰说明需要什么帮助
3. **不要提交 git commit**
4. **不要标记 passes: true**

### 阻塞信息格式：

```
🚫 任务阻塞 - 需要人工介入

**当前任务**: [任务名称]

**已完成的工作**:
- [已完成的内容]

**阻塞原因**:
- [具体原因]

**需要人工帮助**:
1. [步骤 1]
2. [步骤 2]

**解除阻塞后**:
- 运行 [命令] 继续任务
```

---

## 关键规则

1. **一次一个任务** - 专注完成一个任务
2. **测试后再标记完成** - 所有步骤必须验证
3. **大幅修改必须启动服务测试** - 新增功能必须在浏览器/curl 测试
4. **记录到 progress.txt** - 帮助后续 AI 理解工作
5. **一个任务一个 commit** - 代码、progress.txt、task.json 同时提交
6. **不删除任务** - 只翻转 passes 状态
7. **阻塞时停止** - 需要人工时不要假装完成
8. **推送前需用户确认** - 推送到 GitHub 前必须征得用户明确同意
