"""
课程大纲生成器
生成章节/课时/重难点结构化的课程大纲
"""

import os
import re
from datetime import datetime
from typing import Generator, Dict, Optional


class CourseOutlineGenerator:
    """课程大纲生成器"""

    def __init__(self, output_dir: str = "generated_outlines"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_outline_request(self, message: str) -> Optional[Dict]:
        """
        解析课程大纲生成请求

        支持的格式：
        - 课程大纲：Python基础
        - 生成大纲：机器学习
        - 大纲：深度学习
        """
        patterns = [
            r'课程大纲[：:]\s*(.+)',
            r'生成大纲[：:]\s*(.+)',
            r'大纲[：:]\s*(.+)',
            r'生成章节[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'course_outline'
                }
        return None

    def generate_outline_stream(self, topic: str) -> Generator[Dict, None, None]:
        """流式生成课程大纲"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成课程大纲：{topic}'
            }

            # 调用 AI 生成大纲
            content = self._generate_outline_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 大纲内容生成完成，正在保存...'
            }

            # 保存文件
            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
            filename = f"大纲_{safe_topic}_{timestamp}.md"
            filepath = os.path.join(self.output_dir, filename)

            header = f"""---
title: {topic} - 课程大纲
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: course_outline
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
                'message': '🎉 课程大纲生成完成！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_outline_content(self, topic: str) -> str:
        """调用 AI 生成大纲内容"""
        prompt = f"""请为"{topic}"这门课程生成一份详细的课程大纲。

要求：
1. 包含完整的章节/课时结构
2. 每章节标注课时数和教学重难点
3. 包含教学目标概述
4. 使用 Markdown 格式输出

请按以下格式返回：

# {topic} - 课程大纲

## 课程概述
（简要说明课程定位、学习目标、适用对象）

## 章节结构

### 第1章 章节名称（X课时）
**教学目标：**
- 掌握...
- 理解...

**教学重点：**
- 重点1
- 重点2

**教学难点：**
- 难点1

### 第2章 章节名称（X课时）
...

## 课时总览表
| 章节 | 课时 | 重难点 |
|------|------|--------|
| 第1章 | X | 重点/难点 |
...

## 考核方式
（期末考试/平时作业/实践项目等）

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
                {"role": "system", "content": "你是一位专业的课程设计专家，擅长编写课程大纲和教学设计。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = CourseOutlineGenerator()
    for update in generator.generate_outline_stream("Python编程基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
