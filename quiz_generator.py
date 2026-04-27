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
        prompt = f"""请为"{topic}"生成一份随堂练习参考答案。

## 任务说明
根据"{topic}"的内容，按知识点模块组织题目。题型仅限单选题和多选题，每题需包含完整的题干、选项（A/B/C/D）和答案。

## 题目要求

1. **按章节/模块组织**：将题目划分为2-4个知识模块，每个模块对应一个子主题
2. **题型分布**：
   - 单选题：占70%左右，考查概念识记、基础理解、细节辨析
   - 多选题：占30%左右，考查综合判断、多要点掌握
3. **每题结构**：
   - 题号（如 **1.**）
   - 题型标注（单选题/多选题）
   - 题干（简洁明确，避免歧义）
   - 四个选项（A/B/C/D），干扰项具有合理性
   - 答案（格式：答案：X）
4. **内容范围**：围绕"{topic}"的核心概念、关键知识点、重要原理、常见辨析点展开
5. **难度适中**：适合课堂随堂测验或课后自测水平
6. **总量**：每个模块4-8题，总计15-25题

## 输出格式

# {topic} 随堂练习参考答案

## 第一模块：[子主题名称]

> **1.** (单选题) [题干内容]
>
> A. [选项内容]
> B. [选项内容]
> C. [选项内容]
> D. [选项内容]
>
> 答案：X

> **2.** (多选题) [题干内容]
>
> A. [选项内容]
> B. [选项内容]
> C. [选项内容]
> D. [选项内容]
>
> 答案：XX

（继续生成该模块题目...）

---

## 第二模块：[子主题名称]

> **X.** (单选题) [题干内容]
>
> A. [选项内容]
> B. [选项内容]
> C. [选项内容]
> D. [选项内容]
>
> 答案：X

（继续生成...）

---

## 第三模块：[子主题名称]
[同上格式]

---

## 第四模块：[子主题名称]（如需要）
[同上格式]

请直接返回 Markdown 内容，不要其他说明。"""

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
