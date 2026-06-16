"""
课堂测验生成器
生成快问快答形式的课堂测验
"""

import os
import re
import json
import threading
import time
from datetime import datetime
from typing import Generator, Optional

from learner_profile.storage import LearnerProfileStorage


class QuizGenerator:
    """课堂测验生成器"""

    def __init__(self, output_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_quizzes")):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        # 延迟初始化，避免循环导入
        self._profile_storage = None

    def _get_profile_storage(self):
        """延迟获取画像存储实例"""
        if self._profile_storage is None:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._profile_storage = LearnerProfileStorage(backend_dir)
        return self._profile_storage

    def _load_profile_hint(self, user_id: str) -> str:
        """加载学生画像并生成提示词片段"""
        if not user_id or user_id == 'anonymous':
            return ""
        try:
            storage = self._get_profile_storage()
            profile = storage.load_profile(user_id)
            basic = profile.get("basic", {})
            preferences = profile.get("preferences", {})

            stage = basic.get("learning_stage") or ""
            basis = basic.get("learning_basis") or ""
            goal = preferences.get("goal") or ""
            difficulty = preferences.get("preferred_difficulty") or ""

            parts = []
            if stage:
                parts.append(f"学习阶段：{stage}")
            if basis:
                parts.append(f"当前基础：{basis}")
            if goal:
                parts.append(f"学习目标：{goal}")
            if difficulty:
                parts.append(f"期望难度：{difficulty}")

            if parts:
                return "\n\n【学生画像信息】\n" + "\n".join(parts) + "\n请根据以上画像信息调整测验难度和题目侧重。"
        except Exception:
            pass
        return ""

    def parse_quiz_request(self, message: str) -> Optional[dict]:
        """
        解析课堂测验生成请求

        支持的格式：
        - 课堂测验：Python基础
        - 快问快答：机器学习
        - 随堂测验：深度学习
        - 课堂小测：XXX
        - 课堂测验docx：Python基础
        """
        output_format = "md"
        if re.search(r'测验.*docx|docx.*测验', message, re.IGNORECASE):
            output_format = "docx"
            message = re.sub(r'\s*docx\s*', '', message, flags=re.IGNORECASE)

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
                    'type': 'quiz',
                    'format': output_format
                }
        return None

    def generate_quiz_stream(self, topic: str, output_format: str = "md", user_id: str = 'anonymous') -> Generator[dict, None, None]:
        """流式生成课堂测验"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成课堂测验：{topic}'
            }

            yield {
                'step': 'generating',
                'progress': 5,
                'status': 'running',
                'data': {},
                'message': '✨ 正在构思测验结构...'
            }

            result_container: list = [None]   # JSON string (always)
            md_container: list = [None]       # Markdown string (md flow only)
            error_container: list = [None]

            def llm_task():
                try:
                    json_str = self._generate_quiz_json(topic, user_id)
                    # LLM 可能用 markdown 代码块包裹 JSON，需要清理
                    cleaned = json_str.strip()
                    if cleaned.startswith('```'):
                        # 去掉 ```json 和 ``` 包裹
                        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
                        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
                    result_container[0] = cleaned
                    if output_format != "docx":
                        quiz_dict = json.loads(cleaned)
                        md_container[0] = self._json_to_markdown(quiz_dict)
                except Exception as e:
                    error_container[0] = e

            thread = threading.Thread(target=llm_task)
            thread.start()

            last_progress = 5
            while thread.is_alive():
                time.sleep(0.5)
                if last_progress < 90:
                    last_progress += 1
                yield {
                    'step': 'generating',
                    'progress': last_progress,
                    'status': 'running',
                    'data': {},
                    'message': '🤖 正在生成测验题目...'
                }

            thread.join()

            if error_container[0]:
                raise error_container[0]

            json_str = result_container[0]
            if json_str is None:
                raise RuntimeError("生成内容为空")

            yield {
                'step': 'generating',
                'progress': 92,
                'status': 'running',
                'data': {},
                'message': '💾 正在保存文件...'
            }

            if output_format == "docx":
                filename = f"课堂测验_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(json_str, filepath)
            else:
                filename = f"课堂测验_{safe_topic}_{timestamp}.md"
                filepath = os.path.join(self.output_dir, filename)
                header = f"""---
title: {topic} - 课堂测验
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: quiz
---

"""
                md_content = md_container[0] or ''
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(header + md_content)

            result_data = {
                'topic': topic,
                'filepath': filepath,
                'format': output_format,
                'quiz_data': json_str,
            }

            yield {
                'step': 'complete',
                'progress': 100,
                'status': 'completed',
                'data': result_data,
                'message': f'🎉 课堂测验生成完成！格式：{output_format.upper()}'
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

    def _generate_quiz_markdown(self, topic: str) -> str:
        """调用 AI 生成测验内容（Markdown格式）"""
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

    def _generate_quiz_json(self, topic: str, user_id: str = 'anonymous') -> str:
        """调用 AI 生成测验内容（JSON格式）"""
        profile_hint = self._load_profile_hint(user_id)

        prompt = f"""请为"{topic}"生成一份随堂测验，帮助检验你对这个知识点的掌握程度。

## 题目要求

1. **按章节/模块组织**：将题目划分为2-4个知识模块，每个模块对应一个子主题
2. **题型分布**：
   - 单选题：占70%左右，考查概念识记、基础理解、细节辨析
   - 多选题：占30%左右，考查综合判断、多要点掌握
3. **每题结构**：
   - num（题号，如"1"、"2"）
   - type（单选题/多选题）
   - text（题干，简洁明确，避免歧义）
   - options（四个选项的数组，干扰项具有合理性）
   - answer（单选题答案为一个字母，多选题答案为多个字母如"AB"）
4. **内容范围**：围绕"{topic}"的核心概念、关键知识点、重要原理、常见辨析点展开
5. **难度**：由浅入深，覆盖基础到进阶
6. **总量**：每个模块4-8题，总计15-25题
{profile_hint}

## 输出格式

直接返回JSON格式，包含modules数组，每个module包含title和questions数组。

格式示例：
{{
  "title": "{topic}",
  "modules": [
    {{
      "title": "第一模块：基础概念",
      "questions": [
        {{"num": "1", "type": "单选题", "text": "题干内容", "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"], "answer": "A"}},
        {{"num": "2", "type": "多选题", "text": "题干内容", "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"], "answer": "AB"}}
      ]
    }}
  ]
}}

注意：
- 单选题答案是一个字母（A/B/C/D）
- 多选题答案是多个字母（如"AB"、"ACD"）
- answer字段只包含纯答案，不要包含任何格式符号（如【】、答案：等）
- 不要包含任何格式符号（如【】等）
- 请直接返回JSON，不要其他内容。"""

        return self._call_llm(prompt)

    def _generate_json_content(self, topic: str) -> str:
        """调用 AI 生成测验内容（JSON格式）（兼容接口）"""
        return self._generate_quiz_json(topic)

    def _json_to_markdown(self, quiz_data: dict) -> str:
        """从结构化 JSON 派生 Markdown（无 LLM 调用）"""
        title = quiz_data.get('title', '')
        lines = [f'# {title} 随堂练习参考答案\n']
        for i, module in enumerate(quiz_data.get('modules', [])):
            if i > 0:
                lines.append('\n---\n')
            lines.append(f'## {module.get("title", f"模块{i+1}")}\n')
            for q in module.get('questions', []):
                num = q.get('num', '')
                qtype = q.get('type', '单选题')
                text = q.get('text', '')
                options = q.get('options', [])
                answer = q.get('answer', '')
                lines.append(f'> **{num}.** ({qtype}) {text}\n>')
                for opt in options:
                    lines.append(f'>\n> {opt}')
                lines.append(f'>\n> 答案：{answer}\n')
        return '\n'.join(lines)

    def _save_as_docx(self, json_str: str, filepath: str):
        """使用 Node.js 直接构建 docx"""
        import json
        import subprocess
        import tempfile

        quiz_data = json.loads(json_str)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(quiz_data, f, ensure_ascii=False)
            temp_json = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), '../docx_generators/create_quiz_docx.js')
            result = subprocess.run(['node', script_path, temp_json, filepath], capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise Exception(result.stderr or result.stdout)
        finally:
            if os.path.exists(temp_json):
                os.unlink(temp_json)

    def _call_llm(self, prompt: str) -> str:
        """调用大语言模型"""
        from generators.shared_config import content_llm_call
        return content_llm_call(
            messages=[
                {"role": "system", "content": "你是一位专业的测验设计助手，擅长根据学生的学习情况设计有针对性的测验题目，帮助学生检验学习效果、发现薄弱环节。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            # 提升上限：prompt 要求 15-25 题 × 4 选项，3000 tokens 在题目数/长度稍多时
            # 会被截断，导致 JSON 字符串未闭合、json.loads 抛 Unterminated string 错误。
            # 6000 留出充足余量，覆盖常规课堂测验输出。
            max_tokens=6000
        )


if __name__ == "__main__":
    generator = QuizGenerator()
    for update in generator.generate_quiz_stream("机器学习基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
