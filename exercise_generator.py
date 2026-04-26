"""
习题集生成器
生成选择/填空/简答习题集
"""

import os
import re
from datetime import datetime
from typing import Generator, Optional


class ExerciseGenerator:
    """习题集生成器"""

    def __init__(self, output_dir: str = "generated_exercises"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_exercise_request(self, message: str) -> Optional[dict]:
        """
        解析习题集生成请求

        支持的格式：
        - 习题集：Python基础
        - 生成习题：机器学习
        - 习题：深度学习章节2
        """
        patterns = [
            r'习题集[：:]\s*(.+)',
            r'生成习题[：:]\s*(.+)',
            r'习题[：:]\s*(.+)',
            r'练习题[：:]\s*(.+)',
            r'生成练习[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'exercise'
                }
        return None

    def generate_exercise_stream(self, topic: str) -> Generator[dict, None, None]:
        """流式生成习题集"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成习题集：{topic}'
            }

            content = self._generate_exercise_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 习题生成完成，正在保存...'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
            filename = f"习题集_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)

            header = f"""---
title: {topic} - 习题集
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: exercise
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
                'message': '🎉 习题集生成完成！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_exercise_content(self, topic: str) -> str:
        """调用 AI 生成习题内容"""
        prompt = f"""请为"{topic}"生成一份完整的习题集。

要求：
1. 包含三种题型：选择题、填空题、简答题
2. 每种题型至少5-10道题
3. 题目难度适中，覆盖核心知识点
4. 包含答案（单独放在最后）
5. 使用 Markdown 格式输出

请按以下格式返回：

# {topic} - 习题集

## 一、选择题（每题X分，共X道）

**1. （难度：易/中/难）**
A. 选项1
B. 选项2
C. 选项3
D. 选项4
【答案：A】

---

**2. ...**

---

## 二、填空题（每题X分，共X道）

**1. （难度：易/中/难）**
【答案：XXX】

---

**2. ...**

---

## 三、简答题（每题X分，共X道）

**1. （难度：易/中/难）**
【参考答案】
- 要点1
- 要点2
- 要点3

---

**2. ...**

---

## 答案汇总

### 选择题答案
1. A
2. B
3. C
...

### 填空题答案
1. XXX
2. XXX
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
                {"role": "system", "content": "你是一位专业的教育工作者，擅长编写高质量的习题集。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = ExerciseGenerator()
    for update in generator.generate_exercise_stream("Python基础语法"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
