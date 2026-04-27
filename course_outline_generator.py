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
        """调用 AI 生成高度标准化的课程大纲内容"""
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
    for update in generator.generate_outline_stream("Python编程基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
