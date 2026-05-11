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
        - 课程大纲docx：Python基础
        """
        output_format = "md"
        if re.search(r'大纲.*docx|docx.*大纲', message, re.IGNORECASE):
            output_format = "docx"
            message = re.sub(r'\s*docx\s*', '', message, flags=re.IGNORECASE)

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
                    'type': 'course_outline',
                    'format': output_format
                }
        return None

    def generate_outline_stream(self, topic: str, output_format: str = "md") -> Generator[Dict, None, None]:
        """流式生成课程大纲"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': '', 'format': output_format}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成课程大纲：{topic}'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]

            if output_format == "docx":
                content = self._generate_outline_json(topic)
                filename = f"大纲_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(content, filepath)
            else:
                content = self._generate_outline_markdown(topic)
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

            result_data['content'] = content
            result_data['filepath'] = filepath

            yield {
                'step': 'complete',
                'progress': 100,
                'status': 'completed',
                'data': result_data,
                'message': f'🎉 课程大纲生成完成！格式：{output_format.upper()}'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_outline_markdown(self, topic: str) -> str:
        """调用 AI 生成高度标准化的课程大纲内容（Markdown格式）"""
        prompt = f"""请为"{topic}"这门课程生成一份严谨、专业的课程大纲。

# 角色指令
你是一位资深教务专家，请参考标准教学大纲格式，为"{topic}"构建一份结构清晰、逻辑严密的课程大纲。

# 输出要求与格式

## 一、 课程基本信息
包含课程名称、适用专业、先修课程（根据"{topic}"特性推测）、课程性质（如：专业核心必修课）。

## 二、 课程概述
简要说明课程定位及其对后续课程或职业发展的支撑作用。

## 三、 课程目标（需从以下三个维度拆解）
1. **知识目标**：掌握的核心定义、原理与基础算法/理论。
2. **能力目标**：能够解决的实际问题、代码实现能力或决策分析能力。
3. **素养目标**：培养思维模型（如抽象建模）、规范习惯或严谨的工程意识。

## 四、 教学内容与学时分配
请按章节列出，要求：
1. 每章标题需标注总课时（如：6学时）。
2. **课时拆分**：明确标注"理论X学时 + 实验/实践Y学时"。
3. **核心内容**：列出3-5个关键知识点。
4. **重难点**：精准区分"重点"与"难点"。

## 五、 课时总览表
使用 Markdown 表格，包含列：章节名称、理论学时、实验学时、总学时、核心重难点。

## 六、 考核方式
包含平时成绩（30%）、实验/实践成绩（20%）、期末考核（50%）的加权分配说明。

## 七、 常见问题FAQ
针对学习该课程可能遇到的3个典型困难（如基础薄弱如何上手、实践环境搭建等）给出专业解答。

# 约束条件
- 使用标准的 Markdown 层级标题（#、##、###）。
- 内容要专业、硬核，避免泛泛而谈。
- 请直接返回 Markdown 文本，不要包含任何开场白或解释性文字。
"""

        return self._call_llm(prompt)

    def _generate_outline_json(self, topic: str) -> str:
        """调用 AI 生成课程大纲（JSON格式）"""
        prompt = f"""请为"{topic}"这门课程生成一份严谨、专业的课程大纲，以JSON格式返回。

# 课程大纲标准模板

请按以下结构生成课程大纲JSON：

- **title**：课程名称
- **created**：创建时间（使用当前日期）
- **courseInfo**：包含name（课程名称）、major（适用专业）、nature（课程性质，如专业核心必修课）、prerequisites（先修课程，可选）的对象
- **overview**：课程概述，说明课程定位及对后续课程或职业发展的支撑作用
- **objectives**：课程目标数组，从三个维度拆解：
  - 知识目标：掌握的核心定义、原理与基础算法/理论
  - 能力目标：能够解决的实际问题、代码实现能力或决策分析能力
  - 素养目标：培养思维模型、规范习惯或严谨的工程意识
- **chapters**：章节数组，每章包含：
  - title：章节标题（需标注总课时，如"第一章：基础知识（6学时）"）
  - hours：课时拆分（如"理论4学时 + 实验2学时"）
  - points：核心内容数组（3-5个关键知识点）
  - keyPoints：重难点标注（如"重点：XX，难点：XX"）
- **assessment**：考核方式数组（如"平时成绩30%、实验成绩20%、期末考核50%"）
- **faq**：常见问题FAQ数组（3个典型困难及专业解答）

格式示例：
{{
  "title": "{topic}",
  "created": "2024-01-01",
  "courseInfo": {{
    "name": "{topic}",
    "major": "计算机科学专业",
    "nature": "专业核心必修课",
    "prerequisites": ["编程基础"]
  }},
  "overview": "本课程是XX方向的核心基础课，为后续XX课程奠定基础。",
  "objectives": [
    "知识目标：掌握XX的核心概念、原理与算法",
    "能力目标：能够使用XX解决实际问题",
    "素养目标：培养抽象建模思维和工程规范意识"
  ],
  "chapters": [
    {{
      "title": "第一章：基础知识",
      "hours": "6学时（理论4 + 实验2）",
      "points": ["知识点1", "知识点2", "知识点3"],
      "keyPoints": "重点：XX，难点：XX"
    }}
  ],
  "assessment": ["平时成绩30%", "实验成绩20%", "期末考核50%"],
  "faq": [
    {{"q": "基础薄弱如何上手？", "a": "建议先复习XX基础知识"}}
  ]
}}

注意：
- 不要包含任何格式符号（如【】等）
- 每章内容要精炼，章节数量3-5章
- 请直接返回JSON，不要其他内容。"""

        return self._call_llm(prompt)

    def _save_as_docx(self, json_str: str, filepath: str):
        """使用 Node.js 直接构建 docx"""
        import json
        import subprocess
        import tempfile

        outline_data = json.loads(json_str)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(outline_data, f, ensure_ascii=False)
            temp_json = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), 'create_outline_docx.js')
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
                {"role": "system", "content": "你是一位专业的课程设计专家，擅长编写课程大纲和教学设计。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = CourseOutlineGenerator()
    for update in generator.generate_outline_stream("Python编程基础", "md"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
