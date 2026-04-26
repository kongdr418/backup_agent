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
        """调用 AI 生成思维导图内容"""
        prompt = f"""请为"{topic}"生成一份章节总结思维导图。

要求：
1. 使用文本形式展示树状结构
2. 中心主题向外扩展3-5层
3. 每个分支包含关键概念和要点
4. 适合快速复盘整个章节
5. 使用 Markdown 格式输出

请按以下格式返回：

# {topic} - 思维导图

## 使用说明
使用 Mermaid 或文本树状结构展示思维导图结构

---

## 文本树状结构

```
                    【{topic}】
                        │
        ┌───────────────┼───────────────┐
        │               │               │
      章节一          章节二          章节三
        │               │               │
    ┌───┴───┐       ┌───┴───┐       ┌───┴───┐
    │       │       │       │       │       │
  要点1   要点2   要点1   要点2   要点1   要点2
    │       │       │       │       │       │
  细节   细节     细节   细节     细节   细节
```

---

## 层级结构

### 一级分支：主要章节/模块
### 二级分支：该章节的核心主题
### 三级分支：具体知识点
### 四级分支：关键要点/公式/概念
### 五级分支：记忆点/注意事项

---

## 完整导图

### 🎯 {topic}
├─ 📚 第一章 XXX
│  ├─ 💡 核心概念1
│  │  ├─ 要点1.1
│  │  └─ 要点1.2
│  ├─ 💡 核心概念2
│  │  └─ 要点2.1
│  └─ 📝 章节小结
│
├─ 📚 第二章 XXX
│  ├─ 💡 核心概念3
│  └─ ...
│
└─ 📚 第三章 XXX
   └─ ...

---

## 核心关系图

```mermaid
mindmap
  root((主题))
    一级节点
      二级节点A
        三级节点1
        三级节点2
      二级节点B
        三级节点3
```

请直接返回 Markdown 内容，不要其他说明。"""

        return self._call_llm(prompt)

    def _call_llm(self, prompt: str) -> str:
        """调用大语言模型"""
        from openai import OpenAI
        client = OpenAI(
            api_key="sk-d95d1b8567d844889648d0bda30a8ebe",
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
