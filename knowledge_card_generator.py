"""
知识卡片生成器
生成学生复习用的知识卡片
"""

import os
import re
from datetime import datetime
from typing import Generator, Optional


class KnowledgeCardGenerator:
    """知识卡片生成器"""

    def __init__(self, output_dir: str = "generated_cards"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def parse_card_request(self, message: str) -> Optional[dict]:
        """
        解析知识卡片生成请求

        支持的格式：
        - 知识卡片：Python基础
        - 生成卡片：机器学习
        - 卡片：深度学习
        - 生成知识卡：XXX
        - 知识卡片docx：Python基础
        """
        output_format = "md"
        if re.search(r'卡片.*docx|docx.*卡片', message, re.IGNORECASE):
            output_format = "docx"
            message = re.sub(r'\s*docx\s*', '', message, flags=re.IGNORECASE)

        patterns = [
            r'知识卡片[：:]\s*(.+)',
            r'生成卡片[：:]\s*(.+)',
            r'生成知识卡[：:]\s*(.+)',
            r'卡片[：:]\s*(.+)',
            r'知识卡[：:]\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'knowledge_card',
                    'format': output_format
                }
        return None

    def generate_card_stream(self, topic: str, output_format: str = "md") -> Generator[dict, None, None]:
        """流式生成知识卡片"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_data = {'topic': topic, 'filepath': '', 'format': output_format}

            yield {
                'step': 'start',
                'progress': 0,
                'status': 'running',
                'data': {},
                'message': f'🚀 开始生成知识卡片：{topic}'
            }

            safe_topic = re.sub(r'[^\w一-鿿]+', '_', topic)[:50]

            if output_format == "docx":
                content = self._generate_card_json(topic)
                filename = f"知识卡片_{safe_topic}_{timestamp}.docx"
                filepath = os.path.join(self.output_dir, filename)
                self._save_as_docx(content, filepath)
            else:
                content = self._generate_card_markdown(topic)
                filename = f"知识卡片_{safe_topic}_{timestamp}.md"
                filepath = os.path.join(self.output_dir, filename)
                header = f"""---
title: {topic} - 知识卡片
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: knowledge_card
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
                'message': f'🎉 知识卡片生成完成！格式：{output_format.upper()}'
            }

        except Exception as e:
            yield {
                'step': 'error',
                'progress': 0,
                'status': 'error',
                'data': {'error': str(e)},
                'message': f'❌ 生成失败: {e}'
            }

    def _generate_card_content(self, topic: str) -> str:
        """调用 AI 生成高度浓缩、模块化的原子知识卡片"""
        prompt = f"""请将"{topic}"拆解为一套适合手机端快速检索、深度复习的"原子化知识卡片"。

# 角色指令
你是一位擅长"知识脱水"的思维导图大师，请将"{topic}"的核心精髓提炼为 8-12 张高密度的知识卡片，确保每张卡片都能在 30 秒内提供深度启发。

# 知识卡片标准模板 (严格执行)

---

## 📌 【卡片序号：知识点名称】
> **一句话定义**：用最通俗、有力的话揭示其本质。

### 🧩 核心逻辑 / 底层原理
- **运作机制**：简述其背后的逻辑链路（1-3点）。
- **关键公式/模型**：如有相关的理论模型或数学公式，请在此列出。

### 💡 深度洞察 (Insights)
- **高手思维**：提供一个常人容易忽略的独特视角或核心洞见。
- **关联锚点**：连接到【卡片X】或实际应用场景。

### 🛠 应用与避坑 (Actionable)
- **✅ 典型应用**：在[XX情况]下，直接使用[XX策略]。
- **❌ 避坑指南**：列出一个最隐蔽的错误理解或操作雷区。

### 🔔 记忆金句 (Soul Sentence)
★ "此处提炼一句能瞬间产生'原来如此'感叹的结语。"

---

# 整体要求
1. **模块化排版**：严格使用加粗标题、Markdown 列表以及 Emoji 符号（📌, 🧩, 💡, 🛠, ✅, ❌, ★）增强视觉扫描效率。
2. **拒绝泛谈**：删除所有"首先、其次、综上所述"等废话，只保留纯度最高的干货。
3. **内容数量**：稳定生成 8-12 张卡片，并在结尾提供一个简洁的【知识图谱索引表】。

请直接返回 Markdown 格式内容，不要任何开场白或额外解释。"""

        return self._call_llm(prompt)

    def _generate_card_markdown(self, topic: str) -> str:
        """调用 AI 生成高度浓缩、模块化的原子知识卡片（Markdown格式）"""
        prompt = f"""请将"{topic}"拆解为一套适合手机端快速检索、深度复习的"原子化知识卡片"。

# 角色指令
你是一位擅长"知识脱水"的思维导图大师，请将"{topic}"的核心精髓提炼为 8-12 张高密度的知识卡片，确保每张卡片都能在 30 秒内提供深度启发。

# 知识卡片标准模板 (严格执行)

---

## 📌 【卡片序号：知识点名称】
> **一句话定义**：用最通俗、有力的话揭示其本质。

### 🧩 核心逻辑 / 底层原理
- **运作机制**：简述其背后的逻辑链路（1-3点）。
- **关键公式/模型**：如有相关的理论模型或数学公式，请在此列出。

### 💡 深度洞察 (Insights)
- **高手思维**：提供一个常人容易忽略的独特视角或核心洞见。
- **关联锚点**：连接到【卡片X】或实际应用场景。

### 🛠 应用与避坑 (Actionable)
- **✅ 典型应用**：在[XX情况]下，直接使用[XX策略]。
- **❌ 避坑指南**：列出一个最隐蔽的错误理解或操作雷区。

### 🔔 记忆金句 (Soul Sentence)
★ "此处提炼一句能瞬间产生'原来如此'感叹的结语。"

---

# 整体要求
1. **模块化排版**：严格使用加粗标题、Markdown 列表以及 Emoji 符号（📌, 🧩, 💡, 🛠, ✅, ❌, ★）增强视觉扫描效率。
2. **拒绝泛谈**：删除所有"首先、其次、综上所述"等废话，只保留纯度最高的干货。
3. **内容数量**：稳定生成 8-12 张卡片，并在结尾提供一个简洁的【知识图谱索引表】。

请直接返回 Markdown 格式内容，不要任何开场白或额外解释。"""

        return self._call_llm(prompt)

    def _generate_card_json(self, topic: str) -> str:
        """调用 AI 生成知识卡片（JSON格式）"""
        prompt = f"""请将"{topic}"拆解为一套适合手机端快速检索、深度复习的"原子化知识卡片"，以JSON格式返回。

# 知识卡片标准模板

请按以下标准模板生成8-12张卡片，每张卡片包含：

- **title**：卡片标题，格式为"卡片序号：知识点名称"（如"卡片1：变量定义"）
- **definition**：一句话定义，用最通俗、有力的话揭示其本质
- **mechanism**：核心逻辑/底层原理，包含运作机制（简述背后逻辑链路1-3点）和关键公式/模型
- **insights**：深度洞察数组，包含高手思维（常人易忽略的独特视角）和关联锚点（连接到其他卡片或实际应用场景）
- **applications**：典型应用数组，格式为"在[XX情况]下，直接使用[XX策略]"
- **pitfalls**：避坑指南数组，列出一个最隐蔽的错误理解或操作雷区
- **memory**：记忆金句，一句能瞬间产生"原来如此"感叹的结语

格式示例：
{{
  "title": "{topic}",
  "cards": [
    {{
      "title": "卡片1：变量定义",
      "definition": "变量是存储数据的容器",
      "mechanism": {{"mechanism": "内存中分配空间存储值，通过变量名访问", "formula": ""}},
      "insights": ["高手思维：变量名是数据的标签，不是数据本身", "关联锚点：与【卡片3】函数参数相关"],
      "applications": ["在需要重复使用数据时先定义变量", "在函数内部使用局部变量避免副作用"],
      "pitfalls": ["避免使用保留字（如if、for）作为变量名", "不要在同一作用域内重复声明同名变量"],
      "memory": "变量是数据的容器，命名即赋义"
    }}
  ]
}}

注意：
- 生成8-12张卡片，并在结尾提供【知识图谱索引表】
- answer字段只包含纯答案，不要包含任何格式符号（如【】等）
- 不要包含任何格式符号（如【】等）
- 请直接返回JSON，不要其他内容。"""

        return self._call_llm(prompt)

    def _save_as_docx(self, json_str: str, filepath: str):
        """使用 Node.js 直接构建 docx"""
        import json
        import subprocess
        import tempfile

        card_data = json.loads(json_str)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(card_data, f, ensure_ascii=False)
            temp_json = f.name

        try:
            script_path = os.path.join(os.path.dirname(__file__), 'create_card_docx.js')
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
                {"role": "system", "content": "你是一位学习方法专家，擅长制作简洁有效的知识卡片。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    generator = KnowledgeCardGenerator()
    for update in generator.generate_card_stream("Python编程基础"):
        print(f"[{update.get('progress', 0)}%] {update['message']}")
