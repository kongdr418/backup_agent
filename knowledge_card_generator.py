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
        """调用 AI 生成高度浓缩、模块化的原子知识卡片"""
        prompt = f"""请将"{topic}"拆解为一套适合手机端快速检索、深度复习的"原子化知识卡片"。

# 角色指令
你是一位擅长"知识脱水"的思维导图大师，请将"{topic}"的核心精髓提炼为 8-12 张高密度的知识卡片，确保每张卡片都能在 30 秒内提供深度启发。

# 知识卡片标准模板 (严格执行)

---

## 📌 【卡片序号：知识点名称】
> **一句话定义**：用最通俗、有力的话揭示其本质。

### 🧩 核心逻辑 / 底层原理
- **运作机制**：简述其背后的逻辑链路（1-3点）。
- **关键公式/模型**：如有相关的理论模型或数学公式，请在此列出。

### 💡 深度洞察 (Insights)
- **高手思维**：提供一个常人容易忽略的独特视角或核心洞见。
- **关联锚点**：连接到【卡片X】或实际应用场景。

### 🛠 应用与避坑 (Actionable)
- **✅ 典型应用**：在[XX情况]下，直接使用[XX策略]。
- **❌ 避坑指南**：列出一个最隐蔽的错误理解或操作雷区。

### 🔔 记忆金句 (Soul Sentence)
★ "此处提炼一句能瞬间产生'原来如此'感叹的结语。"

---

# 整体要求
1. **模块化排版**：严格使用加粗标题、Markdown 列表以及 Emoji 符号（📌, 🧩, 💡, 🛠, ✅, ❌, ★）增强视觉扫描效率。
2. **拒绝泛谈**：删除所有"首先、其次、综上所述"等废话，只保留纯度最高的干货。
3. **内容数量**：稳定生成 8-12 张卡片，并在结尾提供一个简洁的【知识图谱索引表】。

请直接返回 Markdown 格式内容，不要任何开场白或额外解释。"""

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
