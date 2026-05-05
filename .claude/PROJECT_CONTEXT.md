# MiniMax Agent 后端

## 项目简介
Flask 后端服务，提供 AI 教育内容生成功能（PPT、讲义、习题集、测验、知识卡片、思维导图、课程大纲、讲稿等），支持生成 Markdown、Word (docx) 和 OPML 格式。

## 技术栈
- Python Flask
- MiniMax API / DeepSeek API
- pptxgenjs (Node.js) - PPT 生成
- docx-js - Word 文档生成
- Mermaid + Puppeteer - SVG 思维导图渲染

## 模块进度
- 讲义生成器：已完成，支持 MD/DOCX 输出
- 习题集生成器：已完成，支持 MD/DOCX 输出
- 课堂测验生成器：已完成，支持 MD/DOCX 输出
- 知识卡片生成器：已完成，支持 MD/DOCX 输出
- 课程大纲生成器：已完成，支持 MD/DOCX 输出
- 讲稿生成器：已完成，支持 MD/DOCX 输出
- 思维导图生成器：已完成，支持 MD/OPML/HTML(SVG)/Mermaid 四种格式
- PPT 生成器：已完成
- 社媒内容生成器：已完成

## 最近修改

### 2026-04-29 09:40 - 思维导图 SVG 渲染集成（进行中）
- 创建 `mindmap_render.js`：使用 Mermaid + Puppeteer 渲染真正的 SVG 思维导图
- 修改 `mindmap_generator.py`：调用 Node.js 脚本生成 SVG
- 使用系统已有的 Chrome：`C:\Program Files\Google\Chrome\Application\chrome.exe`
- 修复 `subprocess.run` 的 `encoding='utf-8'` 参数解决 emoji 编码问题
- **问题**：Mermaid 渲染报错 "Syntax error in text"，emoji 过滤不完全

## 存在问题
- Mermaid mindmap 渲染失败：emoji 字符（特别是 variation selector）未被完全过滤
- 需要修复 `mindmap_render.js` 中的 emoji 过滤正则

## 下一步计划
- 修复 `mindmap_render.js` 中的 emoji 正则过滤
- 使用更完整的 emoji Unicode range 或手动过滤特定字符
- 测试完整流程的 SVG 思维导图生成

## 文件清单
- `mindmap_generator.py` - 思维导图生成器 Python 代码
- `mindmap_render.js` - Mermaid + Puppeteer SVG 渲染 Node.js 脚本
- `generated_mindmaps/` - 生成文件目录
