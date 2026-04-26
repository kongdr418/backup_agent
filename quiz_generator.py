"""
课堂测验生成器
生成快问快答形式的课堂测验
"""

import os
import re
import json
from datetime import datetime
from typing import Generator, Optional


class QuizGenerator:
    """课堂测验生成器"""

    def __init__(self, output_dir: str = "generated_quizzes"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_quiz_request(self, message: str) -> Optional[dict]:
        """
        解析课堂测验生成请求

        支持的格式：
        - 课堂测验：Python基础
        - 快问快答：机器学习
        - 随堂测验：深度学习
        - 课堂小测：XXX
        """
        patterns = [
            r'课堂测验[：:]\s*(.+)',
            r'快问快答[：:]\s*(.+)',
            r'随堂测验[：:]\s*(.+)',
            r'课堂小测[：:]\s*(.+)',
            r'生成测验[：:]\s*(.+)',
            r'测验[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'quiz'
                }
        return None

    def generate_quiz_stream(self, topic: str) -> Generator[dict, None, None]:
        """流式生成课堂测验"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成课堂测验：{topic}'
            }

            content = self._generate_quiz_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 测验生成完成，正在保存...'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
            filename = f"课堂测验_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)

            header = f"""---
title: {topic} - 课堂测验
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: quiz
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
                'message': '🎉 课堂测验生成完成！快问快答模式！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_quiz_content(self, topic: str) -> str:
        """调用 AI 生成测验内容"""
        prompt = f"""请为"{topic}"生成一份课堂快问快答测验。

要求：
1. 题目简短，适合口头回答
2. 每题控制在10秒内回答
3. 包含判断题、选择题、简答题
4. 题目活泼有趣，吸引学生参与
5. 适合课堂互动
6. 使用 Markdown 格式输出

请按以下格式返回：

# {topic} - 课堂快问快答

## 基本信息
- 测验时长：5-10分钟
- 题量：10-15道
- 适用场景：课堂开头/中间互动/结尾复习

---

## 开始测验！

### 第1题（判断题 - 5秒）
**"{topic}相关概念" 是真的吗？**
A. 真的
B. 假的

【答案：B】

---

### 第2题（选择题 - 8秒）
**关于XXX，以下哪个正确？**
A. 选项1
B. 选项2
C. 选项3
D. 选项4

【答案：C】

---

### 第3题（简答题 - 10秒）
**请用一句话解释XXX**

【参考答案】XXX是...

---

（继续生成10-15道题目）

---

## 答案汇总
1. B
2. C
3. XXX
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
                {"role": "system", "content": "你是一位有趣的课堂主持人，擅长设计有趣的快问快答测验。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=3000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = QuizGenerator()
    for update in generator.generate_quiz_stream("机器学习基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
