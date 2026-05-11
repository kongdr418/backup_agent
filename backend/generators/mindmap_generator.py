"""
思维导图生成器
生成章节总结的思维导图（文本结构版）
"""

import os
import re
from datetime import datetime
from typing import Generator, Optional


class MindmapGenerator:
    """思维导图生成器"""

    def __init__(self, output_dir: str = "generated_mindmaps"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_mindmap_request(self, message: str) -> Optional[dict]:
        """
        解析思维导图生成请求

        支持的格式：
        - 思维导图：Python基础
        - 生成导图：机器学习
        - 章节总结：深度学习
        - 生成思维导图：XXX
        """
        patterns = [
            r'思维导图[：:]\s*(.+)',
            r'生成思维导图[：:]\s*(.+)',
            r'生成导图[：:]\s*(.+)',
            r'导图[：:]\s*(.+)',
            r'章节总结[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'mindmap'
                }
        return None

    def generate_mindmap_stream(self, topic: str) -> Generator[dict, None, None]:
        """流式生成思维导图"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成思维导图：{topic}'
            }

            content = self._generate_mindmap_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 导图生成完成，正在保存...'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
            filename = f"思维导图_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)

            header = f"""---
title: {topic} - 思维导图
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: mindmap
---

"""
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(header + content)

            result_data['filepath'] = filepath

            yield {
                'step': 'complete',
                'progress': 100,
                'status': 'completed',
                'data': result_data,
                'message': '🎉 思维导图生成完成！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_mindmap_content(self, topic: str) -> str:
        """调用 AI 生成符合专业思维导图逻辑的完整总结文档"""
        prompt = f"""你是一位精通知识架构的专家。请为"{topic}"生成一份结构严密、逻辑清晰的深度章节总结思维导图。

### 核心任务
参考以下 10 种专业思维导图模型，根据内容特性自动选择最匹配的逻辑进行构建：
1. **放射型**：用于头脑风暴与知识点发散。
2. **树状型**：用于课程大纲、体系分类与框架梳理。
3. **流程图式**：用于按时间或操作步骤拆解流程。
4. **鱼骨图**：用于因果分析、问题溯源或弊端总结。
5. **括号型**：展示整体与局部的拆分关系。
6. **圆圈图**：用于核心概念解释与特征联想。
7. **双重气泡图/韦恩图**：用于多个主体的异同点对比。
8. **时间线型**：记录发展历程、历史事件或阶段规划。
9. **桥形图**：进行横向类比推理与规律总结。

### 创作要求
- **深度发散**：中心主题应向外扩展 3-5 层，涵盖关键概念、公式、要点及记忆提示。
- **逻辑说明**：必须在文档开头说明所选用的导图逻辑及其适用原因。
- **视觉化**：使用精心设计的 Markdown 字符和 Mermaid 语法，确保复盘时一目了然。

### 输出格式 (请严格按此 Markdown 模板返回)

# 🧠 {topic} - 深度思维导图总结

---

## 🏗️ 逻辑架构说明
- **所选模型**：[例如：树状型 + 流程图式]
- **构建逻辑**：[简述为何选择该逻辑，例如：由于本章涉及大量实验步骤及理论分类，故结合流程与树状结构]

---

## 📊 可视化结构预览
      【{topic}】
           │
  ┌────────┴────────┐
[分支A]           [分支B]
│                │
┌───┴───┐        ┌───┴───┐
要点1    要点2    要点3    要点4
│        │        │        │
细节A    细节B    细节C    细节D


---

## 📝 完整层级内容
### 🎯 {topic}
├─ 📂 [一级分支：主要章节/模块]
│  ├─ 💡 [二级分支：核心主题/原因分类]
│  │  ├─ 📍 [三级分支：具体知识点/细分原因]
│  │  │  └─ 📝 [四/五级分支：关键要点/公式/记忆点]
│  │  └─ 💡 ...
│  └─ 💡 ...
├─ 📂 [一级分支名称]
│  └─ ...

---

## 🛠️ Mermaid 逻辑图
```mermaid
mindmap
  root(({topic}))
    (一级分支)
      ((二级分支))
        [三级分支]
          )四级/五级要点(
    (一级分支)
      ((二级分支))
        [三级分支]
          )四级/五级要点(
```

请直接返回上述 Markdown 内容，严禁包含任何开场白、解释或结束语。"""

        return self._call_llm(prompt)

    def _call_llm(self, prompt: str) -> str:
        """调用大语言模型"""
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
            base_url="https://api.deepseek.com"
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位思维导图专家，擅长用结构化的方式呈现知识体系。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = MindmapGenerator()
    for update in generator.generate_mindmap_stream("机器学习概述"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
