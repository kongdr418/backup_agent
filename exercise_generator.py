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

            if output_format == "docx":
                filename = f"习题集_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(content, filepath, topic)
            else:
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

    def _save_as_docx(self, content: str, filepath: str, topic: str):
        """将 Markdown 格式的习题内容保存为 docx"""
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.style import WD_STYLE_TYPE

        doc = Document()

        # 设置默认字体
        style = doc.styles['Normal']
        style.font.name = 'Arial'
        style.font.size = Pt(11)

        lines = content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # 标题处理 (# 标题)
            if line.startswith('# '):
                p = doc.add_heading(line[2:], level=1)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif line.startswith('## '):
                p = doc.add_heading(line[3:], level=2)
            elif line.startswith('### '):
                p = doc.add_heading(line[4:], level=3)
            # 分隔线
            elif line == '---':
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)
            # 选择题选项 (A. B. C. D.)
            elif line.startswith(('A.', 'B.', 'C.', 'D.', 'A．', 'B．', 'C．', 'D．')):
                p = doc.add_paragraph(line, style='List Bullet')
            # 答案标记 【答案：XXX】
            elif line.startswith('【答案'):
                p = doc.add_paragraph()
                run = p.add_run(line)
                run.font.color.rgb = None  # 保持原样
            # 要点列表
            elif line.startswith('- '):
                p = doc.add_paragraph(line[2:], style='List Bullet')
            # 普通文本
            else:
                # 处理粗体 **text**
                if '**' in line:
                    p = doc.add_paragraph()
                    parts = line.split('**')
                    for j, part in enumerate(parts):
                        if j % 2 == 1:  # 粗体部分
                            run = p.add_run(part)
                            run.bold = True
                        else:
                            p.add_run(part)
                else:
                    doc.add_paragraph(line)

            i += 1

        doc.save(filepath)

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
