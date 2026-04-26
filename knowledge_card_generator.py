"""
知识卡片生成器
生成学生复习用的知识卡片
"""

import os
import re
from datetime import datetime
from typing import Generator, Optional


class KnowledgeCardGenerator:
    """知识卡片生成器"""

    def __init__(self, output_dir: str = "generated_cards"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_card_request(self, message: str) -> Optional[dict]:
        """
        解析知识卡片生成请求

        支持的格式：
        - 知识卡片：Python基础
        - 生成卡片：机器学习
        - 卡片：深度学习
        - 生成知识卡：XXX
        """
        patterns = [
            r'知识卡片[：:]\s*(.+)',
            r'生成卡片[：:]\s*(.+)',
            r'生成知识卡[：:]\s*(.+)',
            r'卡片[：:]\s*(.+)',
            r'知识卡[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'knowledge_card'
                }
        return None

    def generate_card_stream(self, topic: str) -> Generator[dict, None, None]:
        """流式生成知识卡片"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成知识卡片：{topic}'
            }

            content = self._generate_card_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 卡片内容生成完成，正在保存...'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
            filename = f"知识卡片_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)

            header = f"""---
title: {topic} - 知识卡片
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: knowledge_card
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
                'message': '🎉 知识卡片生成完成！便于学生复习！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_card_content(self, topic: str) -> str:
        """调用 AI 生成卡片内容"""
        prompt = f"""请为"{topic}"生成一套学生复习用的知识卡片。

要求：
1. 卡片形式，每个知识点一张卡
2. 包含：概念定义、关键要点、记忆口诀、常见误区
3. 简洁明了，适合快速记忆
4. 卡片数量：8-12张
5. 使用 Markdown 格式输出

请按以下格式返回：

# {topic} - 知识卡片

---

## 卡片1：核心概念

**📌 概念名称**

| 项目 | 内容 |
|------|------|
| 定义 | 清晰准确地描述... |
| 关键词 | 关键词1、关键词2 |
| 公式/核心 | 核心公式或要点 |

**💡 记忆口诀**
一句顺口溜帮助记忆

**⚠️ 常见误区**
- 误区1
- 误区2

**🔗 关联知识点**
- 关联到【卡片X】
- 关联到【卡片X】

---

## 卡片2：XXX
（同样的格式）

---

（继续生成8-12张知识卡片）

---

## 快速索引
| 卡片 | 主题 | 页码 |
|------|------|------|
| 卡片1 | 核心概念 | P1 |
| 卡片2 | XXX | P2 |
...

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
                {"role": "system", "content": "你是一位学习方法专家，擅长制作简洁有效的知识卡片。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = KnowledgeCardGenerator()
    for update in generator.generate_card_stream("Python编程基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
