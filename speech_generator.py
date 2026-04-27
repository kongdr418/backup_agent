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
        """
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
                    'type': 'speech'
                }
        return None

    def generate_speech_stream(self, topic: str) -> Generator[dict, None, None]:
        """流式生成讲稿"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': ''}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成讲稿：{topic}'
            }

            content = self._generate_speech_content(topic)
            result_data['content'] = content

            yield {
                'step': 'generate_content',
                'progress': 60,
                'status': 'running',
                'data': {},
                'message': '✅ 讲稿内容生成完成，正在保存...'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]
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

            result_data['filepath'] = filepath

            yield {
                'step': 'complete',
                'progress': 100,
                'status': 'completed',
                'data': result_data,
                'message': '🎉 讲稿生成完成！可直接用于授课！'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_speech_content(self, topic: str) -> str:
        """调用 AI 生成具有教研深度且口语化的授课讲稿"""
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
    for update in generator.generate_speech_stream("机器学习概述"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
