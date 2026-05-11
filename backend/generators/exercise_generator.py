"""
习题集生成器
生成选择/填空/简答习题集
支持 Markdown 和 Word (.docx) 格式
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
        - 习题集：Python基础 docx
        - 习题集docx：Python基础
        """
        # 检测是否指定 docx 格式
        output_format = "md"
        if re.search(r'习题集.*docx|docx.*习题集', message, re.IGNORECASE):
            output_format = "docx"
            message = re.sub(r'\s*docx\s*', '', message, flags=re.IGNORECASE)

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
                    'type': 'exercise',
                    'format': output_format
                }
        return None

    def generate_exercise_stream(self, topic: str, output_format: str = "md") -> Generator[dict, None, None]:
        """流式生成习题集

        Args:
            topic: 主题
            output_format: 输出格式，"md" 或 "docx"，默认为 "md"
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': '', 'format': output_format}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成习题集：{topic}'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]

            if output_format == "docx":
                content = self._generate_json_content(topic)
                filename = f"习题集_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(content, filepath)
            else:
                content = self._generate_markdown_content(topic)
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
                'message': f'🎉 习题集生成完成！格式：{output_format.upper()}'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_markdown_content(self, topic: str) -> str:
        """调用 AI 生成可读性强的 Markdown 格式"""
        prompt = f"""请为"{topic}"生成一份完整的习题集。

要求：
1. 包含三种题型：选择题、填空题、简答题
2. 每种题型至少5道题
3. 题目难度适中，覆盖核心知识点
4. 直接返回 Markdown 格式，不要其他说明

请按以下格式返回：

# {topic} - 习题集

## 一、选择题

**1.** 题目内容
A. 选项1
B. 选项2
C. 选项3
D. 选项4
【答案：A】

---

**2.** 题目内容
...

## 二、填空题

**1.** 题目内容
【答案：XXX】

---

## 三、简答题

**1.** 题目内容
【参考答案】
- 要点1
- 要点2

---

## 答案汇总

### 选择题答案
1. A
2. B
...

### 填空题答案
1. XXX
2. XXX
...

请直接返回 Markdown 内容，不要开场白。"""

        return self._call_llm(prompt)

    def _generate_json_content(self, topic: str) -> str:
        """调用 AI 生成纯数据 JSON（格式由 docx-js 决定）"""
        prompt = f"""请为"{topic}"生成一份完整的习题集。

要求：
1. 包含三种题型：选择题、填空题、简答题
2. 每种题型至少5道题
3. 题目难度适中，覆盖核心知识点
4. 直接返回 JSON 格式，不要其他内容

重要：answer 字段只包含纯答案，不要包含任何格式符号（如【】等）
例如：选择题答案应该是 "A" 或 "B"，不是 "【答案：A】"
填空题答案是具体的词或短语，不是 "【答案：XXX】"

请按以下 JSON 格式返回：

{{
  "title": "{topic}",
  "choiceQuestions": [
    {{
      "num": "1",
      "text": "题目内容",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "answer": "A"
    }}
  ],
  "fillQuestions": [
    {{
      "num": "1",
      "text": "题目内容",
      "answer": "答案"
    }}
  ],
  "essayQuestions": [
    {{
      "num": "1",
      "text": "题目内容",
      "points": ["要点1", "要点2", "要点3"],
      "answer": "参考答案内容"
    }}
  ]
}}

请直接返回 JSON，不要任何其他内容。"""

        return self._call_llm(prompt)

    def _save_as_docx(self, json_str: str, filepath: str):
        """使用 Node.js 直接构建 docx"""
        import json
        import subprocess
        import tempfile

        # 解析 JSON
        exercise_data = json.loads(json_str)

        # 写入临时 JSON 文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(exercise_data, f, ensure_ascii=False)
            temp_json = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), 'create_exercise_docx.js')
            result = subprocess.run(
                ['node', script_path, temp_json, filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                raise Exception(result.stderr or result.stdout)
        finally:
            if os.path.exists(temp_json):
                os.unlink(temp_json)

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
