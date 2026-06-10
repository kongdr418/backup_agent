"""
课程讲义生成器
为教师生成 Markdown 格式的课程讲义
"""

import os
import re
from datetime import datetime
from pathlib import Path

from learner_profile.storage import LearnerProfileStorage


class LectureGenerator:
    """课程讲义生成器"""

    def __init__(self, output_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_lectures")):
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
            background = basic.get("background") or ""
            goal = preferences.get("goal") or ""
            difficulty = preferences.get("preferred_difficulty") or ""
            content_style = preferences.get("content_style", [])
            style_str = "、".join(content_style) if content_style else ""

            parts = []
            if stage:
                parts.append(f"学习阶段：{stage}")
            if basis:
                parts.append(f"当前基础：{basis}")
            if background:
                parts.append(f"学习背景：{background}")
            if goal:
                parts.append(f"学习目标：{goal}")
            if difficulty:
                parts.append(f"期望难度：{difficulty}")
            if style_str:
                parts.append(f"内容偏好：{style_str}")

            if parts:
                return "\n\n【学生画像信息】\n" + "\n".join(parts) + "\n请根据以上画像信息调整讲义内容深度、案例类型和讲解方式。"
        except Exception:
            pass
        return ""
    
    def parse_lecture_request(self, message: str) -> dict:
        """
        解析讲义生成请求
        
        支持的格式：
        - 生成讲义：机器学习第一章 历史
        - 讲义：Python 基础
        - 课程讲义：深度学习导论
        """
        patterns = [
            r'生成讲义[：:]\s*(.+)',
            r'讲义[：:]\s*(.+)',
            r'课程讲义[：:]\s*(.+)',
            r'生成教案[：:]\s*(.+)',
            r'教案[：:]\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return {
                    'topic': match.group(1).strip(),
                    'type': 'lecture'
                }
        
        return None
    
    def generate_lecture_prompt(self, topic: str, user_id: str = 'anonymous') -> str:
        """生成用于 AI 的提示词"""
        profile_hint = self._load_profile_hint(user_id)

        return f'''请为"{topic}"这个主题生成一份详细的学习讲义，帮助你系统地理解和掌握这个知识点。

请按以下 Markdown 格式返回：

# {topic} 学习讲义

## 一、学习概览

| 项目 | 内容 |
|------|------|
| **内容提要** | [本讲主要内容的简要概述，分1-2点列出] |
| **学习目标** | [你应该了解/掌握/理解的具体知识点] |
| **能力目标** | [你应该提高的能力，能运用的方法或技能] |
| **学习重点** | [本讲核心知识点] |
| **学习难点** | [可能理解或掌握有困难的地方] |
| **建议学时** | X学时 |
{profile_hint}

---

## 二、学习内容

### 【导入】（5分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| [介绍本讲内容的地位和作用，说明学习方法，建立与已学知识的关联。激发学习兴趣，引入主题] | **阅读导引**<br>**思考问题**<br>建立知识衔接 |

---

### 【核心知识讲解】（主体时间）

#### 知识点一：[名称]（X分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| **概念/原理讲解：**<br><br>[详细解释概念定义、核心原理，注意准确性和逻辑性]<br><br>**示例/案例：**<br><br>[具体例子，含详细分析或推导过程]<br><br>**注意事项：**<br>- [易错点1]<br>- [易错点2] | **仔细阅读**<br>**动手实践**<br>**尝试自己推导**<br>**发现规律**<br>**做好笔记** |

#### 知识点二：[名称]（X分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| [同上格式：概念讲解 + 示例/案例 + 注意事项] | [阅读/实践/思考/总结等] |

---

### 【随堂练习】（6分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| **练习题：**<br>1. [基础巩固题]<br>2. [基础巩固题]<br><br>**参考答案要点：**<br>[简要说明解题思路] | **独立完成**<br>**对照答案**<br>**标记错题**<br>**总结方法** |

---

### 【拓展提升】（10-12分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| **思考题/综合题：**<br>1. [进阶题目，考查综合运用能力]<br>2. [开放性讨论或案例分析]<br><br>**思路点拨：**<br>[引导思考的方向] | **深入思考**<br>**尝试解答**<br>**总结方法** |

---

### 【本讲小结】（1-2分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| 1. 回顾本讲主要内容：[列出核心知识点]<br>2. 强调重点和难点<br>3. 预告下讲内容：[简要说明下节主题] | **回顾总结**<br>**整理笔记** |

---

### 【课后任务】（1分钟）

| 学习内容 | 学习活动 |
|---------|---------|
| 1. [具体任务，如完成在线练习/习题]<br>2. [阅读材料或观看视频]<br>3. [预习下讲内容] | **按时完成**<br>**记录疑问** |

---

## 三、知识框架
【核心知识结构】
{topic}
│
├─ 一、 [核心概念/模块一]
│      ├─ 要点1
│      ├─ 要点2
│      └─ 公式/定理/结论
│
├─ 二、 [核心概念/模块二]
│      ├─ 要点1
│      └─ 要点2
│
└─ 三、 [核心概念/模块三]
└─ ...

【学习要点】
重点概念整理
易错点提醒
记忆技巧

---

## 四、学习反思

| 项目 | 内容 |
|------|------|
| **学习效果** | [预期达成的学习效果] |
| **学习建议** | [针对不同基础的学习建议] |
| **常见问题** | [学习中可能遇到的问题] |
| **改进方向** | [针对问题的调整方案] |

---

## 五、参考资料

1. [教材/专著名称及页码]
2. [论文/文章名称]
3. [在线资源/视频链接]

---

## 六、附录

### 附录 A：专业术语表
| 术语 | 英文/缩写 | 解释 |
|------|-----------|------|
| | | |

### 附录 B：延伸阅读
- [推荐书目/文章1]
- [推荐书目/文章2]

要求：
内容详实，适合学习者直接用于自学
采用"学习内容 + 学习活动"双栏对应格式
每个环节标注具体时长
提供结构化的知识框架
包含基础练习和拓展提升两个层次
学习反思包含学习效果、学习建议、常见问题、改进方向
只返回 Markdown 内容，不要其他说明'''

    def create_lecture_file(self, topic: str, content: str) -> str:
        """
        创建讲义文件
        
        Args:
            topic: 课程主题
            content: 讲义内容
            
        Returns:
            生成的文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r'[^\w\u4e00-\u9fff]+', '_', topic)[:50]
        filename = f"{safe_topic}_{timestamp}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        # 添加文件头信息
        header = f"""---
title: {topic}
created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
type: lecture_notes
---

"""
        
        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + content)
        
        return filepath
    
    def list_lectures(self) -> list:
        """列出所有生成的讲义"""
        if not os.path.exists(self.output_dir):
            return []
        
        lectures = []
        for f in os.listdir(self.output_dir):
            if f.endswith('.md'):
                filepath = os.path.join(self.output_dir, f)
                stat = os.stat(filepath)
                lectures.append({
                    'filename': f,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        
        # 按时间倒序
        lectures.sort(key=lambda x: x['created'], reverse=True)
        return lectures
    
    def get_lecture_preview(self, filepath: str, max_lines: int = 50) -> str:
        """
        获取讲义预览
        
        Args:
            filepath: 讲义文件路径
            max_lines: 最大预览行数
            
        Returns:
            预览文本
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                preview = ''.join(lines[:max_lines])
                if len(lines) > max_lines:
                    preview += f"\n\n...（共 {len(lines)} 行，此处省略）"
                return preview
        except Exception as e:
            return f"读取讲义失败: {e}"


if __name__ == "__main__":
    # 测试
    generator = LectureGenerator()
    print("讲义生成器测试")
    print(f"输出目录: {generator.output_dir}")
    
    # 测试解析
    test_messages = [
        "生成讲义：机器学习第一章",
        "讲义：Python 基础",
        "课程讲义：深度学习导论",
    ]
    
    for msg in test_messages:
        result = generator.parse_lecture_request(msg)
        print(f"\n输入: {msg}")
        print(f"解析: {result}")
