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
        """调用 AI 生成讲稿内容"""
        prompt = f"""请为"{topic}"生成一份教师可直接念出来的授课讲稿。

要求：
1. 语言口语化，可以直接朗读
2. 包含开场白、过渡语、总结语
3. 每段标注预计时长
4. 包含课堂互动引导语
5. 使用 Markdown 格式，【】标注动作和语气

请按以下格式返回：

# {topic} - 授课讲稿

## 基本信息
- 课程名称：{topic}
- 预计时长：XX分钟
- 适用对象：XXX

---

## 【开场】（约X分钟）

同学们好！今天我们来学习【topic】。

（自我介绍+课程导入）

【过渡】那么，首先让我们来了解一下...

---

## 【第一章 X】（约X分钟）

### 知识点一：XXX

**讲解：**
同学们好，前面我们学习了XXX，现在我们来了解一下XXX。
（核心概念讲解，口语化，解释清楚）

【互动】有没有同学知道这个在生活中有什么应用？
（等待学生回应）

**过渡：** 好的，那我们继续往下看...

### 知识点二：XXX

（继续讲解...）

---

## 【课堂小结】（约X分钟）

今天我们学习了【topic】的以下内容：
- 第一，XXX
- 第二，XXX
- 第三，XXX

【布置作业】课后请大家完成XXX，下节课我们继续...

【结束语】今天的课就到这里，谢谢大家！

---

## 备注
（教学注意事项、延伸内容等）

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
