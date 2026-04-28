"""
讲稿生成器
生成教师可直接念出来的授课讲稿
"""

import os
import re
from datetime import datetime
from typing import Generator, Optional


class SpeechGenerator:
    """讲稿生成器"""

    def __init__(self, output_dir: str = "generated_speeches"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_speech_request(self, message: str) -> Optional[dict]:
        """
        解析讲稿生成请求

        支持的格式：
        - 讲稿：机器学习第一章
        - 生成讲稿：深度学习
        - 授课讲稿：Python基础
        - 讲稿docx：机器学习第一章
        """
        output_format = "md"
        if re.search(r'讲稿.*docx|docx.*讲稿', message, re.IGNORECASE):
            output_format = "docx"
            message = re.sub(r'\s*docx\s*', '', message, flags=re.IGNORECASE)

        patterns = [
            r'讲稿[：:]\s*(.+)',
            r'生成讲稿[：:]\s*(.+)',
            r'授课讲稿[：:]\s*(.+)',
            r'讲课稿[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'speech',
                    'format': output_format
                }
        return None

    def generate_speech_stream(self, topic: str, output_format: str = "md") -> Generator[dict, None, None]:
        """流式生成讲稿"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': '', 'format': output_format}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成讲稿：{topic}'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]

            if output_format == "docx":
                content = self._generate_speech_json(topic)
                filename = f"讲稿_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(content, filepath)
            else:
                content = self._generate_speech_markdown(topic)
                filename = f"讲稿_{safe_topic}_{timestamp}.md"
                filepath = os.path.join(self.output_dir, filename)
                header = f"""---
title: {topic} - 授课讲稿
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: speech_script
---

"""
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(header + content)

            result_data['content'] = content
            result_data['filepath'] = filepath

            yield {
                'step': 'complete',
                'progress': 100,
                'status': 'completed',
                'data': result_data,
                'message': f'🎉 讲稿生成完成！格式：{output_format.upper()}'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_speech_markdown(self, topic: str) -> str:
        """调用 AI 生成具有教研深度且口语化的授课讲稿（Markdown格式）"""
        prompt = f"""请为"{topic}"生成一份专业、生动、可直接用于课堂教学的深度讲稿。

# 角色指令
你是一位擅长"化繁为简"的金牌讲师。请根据"{topic}"生成一份结构精妙、互动感强、且包含深层价值引导的授课讲稿。

# 输出结构要求

## 一、 教学导入：【引发共鸣/争议点】
- **核心内容**：以一个时下热点、生活案例或冲突点切入。
- **互动提问**：设计一个能引发学生讨论的问题。
- **【导入话术】**：口语化、有吸引力的开场白。

## 二、 知识详解（分章节/要点呈现）
请按逻辑拆解为3-5个核心章节，每章需包含：
1. **== 章节标题 ==**：标注预计时长。
2. **【教学要点】**：列出本章必须掌握的硬核知识点。
3. **【通俗解释】**：使用比喻或生活化语言解释复杂概念（如："XX就像是... "）。
4. **【重点标注】**：★ 用一句话提炼本章的灵魂金句。
5. **【互动提问】**：设计一个具体的互动环节或思考题。
6. **【举例说明】**：提供2-3个鲜活的案例或数据支撑。
7. **【讲解话术】**：提供一段教师可直接朗读的、带有动作指导【】和语气提示的文案。

## 三、 课堂总结：【使命与担当】
- 总结核心逻辑图谱。
- 强调该课程对学生个人成长或社会发展的长远意义。
- 结尾话术：有力、感人且留有余味。

# 约束条件
- **语感**：拒绝说教，采用"朋友式对话"或"启发式引导"的口语风格。
- **标注**：使用【】标注动作、眼神或语气（如：【扫视全场】、【语重心长地】）。
- **格式**：严格使用示例中的模块标签（教学要点、通俗解释、重点标注等）。
- **输出**：直接返回 Markdown 内容，不要开场白。
"""

        return self._call_llm(prompt)

    def _generate_speech_json(self, topic: str) -> str:
        """调用 AI 生成讲稿（JSON格式）"""
        prompt = f"""请为"{topic}"生成一份专业、生动、可直接用于课堂教学的深度讲稿，以JSON格式返回。

# 讲稿标准模板

## 输出结构

### 一、教学导入
- **opening**：口语化、有吸引力的开场白
- **question**：能引发学生讨论的互动提问

### 二、知识详解（3-5个章节）
每章包含：
- **title**：章节标题（标注预计时长，如"第一章：变量定义（10分钟）"）
- **summary**：本章内容概述
- **points**：教学要点数组（必须掌握的硬核知识点）
- **analogy**：通俗解释（使用比喻或生活化语言解释复杂概念）
- **keyPoint**：★ 一句话提炼本章的灵魂金句
- **discussion**：互动提问（设计一个具体的互动环节或思考题）
- **examples**：举例说明数组（2-3个鲜活的案例或数据支撑）
- **script**：讲解话术（教师可直接朗读的、带有动作指导的文案）

### 三、课堂总结
- **conclusion**：总结核心逻辑图谱
- **mission**：强调课程对学生个人成长或社会发展的长远意义

格式示例：
{{
  "title": "{topic}",
  "created": "2024-01-01",
  "intro": {{
    "opening": "同学们好，今天我们来学习...",
    "question": "有人知道XX吗？"
  }},
  "chapters": [
    {{
      "title": "第一章：变量定义（10分钟）",
      "summary": "本章介绍变量的基本概念和使用方法",
      "points": ["变量的定义", "变量命名规则", "变量赋值"],
      "analogy": "变量就像是数据的容器，变量名就是标签",
      "keyPoint": "变量是存储数据的基本单元",
      "discussion": "生活中有哪些地方用到了'容器+标签'的模式？",
      "examples": ["成绩单上的学生姓名", "通讯录中的联系人"],
      "script": "【扫视全场】同学们，今天我们来聊聊编程中最基本的概念——变量。【指向黑板】变量其实就像..."
    }}
  ],
  "summary": {{
    "conclusion": "今天我们学习了变量的定义、赋值和使用。",
    "mission": "掌握变量是编程的起点，希望大家在生活中也能发现'变量思维'的魅力。"
  }}
}}

注意：
- 不要包含任何格式符号（如【】等）
- 生成3-5个章节
- 每章内容要精炼但完整
- 请直接返回JSON，不要其他内容。"""

        return self._call_llm(prompt)

    def _save_as_docx(self, json_str: str, filepath: str):
        """使用 Node.js 直接构建 docx"""
        import json
        import subprocess
        import tempfile

        speech_data = json.loads(json_str)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(speech_data, f, ensure_ascii=False)
            temp_json = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), 'create_speech_docx.js')
            result = subprocess.run(['node', script_path, temp_json, filepath], capture_output=True, text=True, timeout=30)
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
                {"role": "system", "content": "你是一位经验丰富的教师，擅长编写口语化的授课讲稿。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = SpeechGenerator()
    for update in generator.generate_speech_stream("机器学习概述", "md"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
