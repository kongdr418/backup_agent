"""
课程讲义生成器
为教师生成 Markdown 格式的课程讲义
"""

import os
import re
from datetime import datetime
from pathlib import Path


class LectureGenerator:
    """课程讲义生成器"""
    
    def __init__(self, output_dir: str = "generated_lectures"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
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
    
    def generate_lecture_prompt(self, topic: str) -> str:
        """生成用于 AI 的提示词"""
        return f'''请为"{topic}"这个主题生成一份详细的教师课程讲义。

请按以下 Markdown 格式返回：

# {topic} 课程讲义

## 一、基础信息

| 项目 | 内容 |
|------|------|
| **内容提要** | [本讲主要内容的简要概述，分1-2点列出] |
| **知识目标** | [学生应了解/掌握/理解的具体知识点] |
| **能力目标** | [学生应提高的能力，能运用的方法或技能] |
| **情感目标** | [应激发/培养的兴趣、精神或态度] |
| **教学重点** | [本讲核心知识点] |
| **教学难点** | [学生理解或掌握有困难的地方] |
| **教学方法** | [讲授法、练习法、讨论法、案例法等] |
| **教学手段** | [多媒体课件、学习平台、雨课堂等] |
| **学时** | X学时 |

---

## 二、授课内容

### 【课堂导入】（5分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| [介绍本课程/本讲内容的地位和作用，说明学习方法，建立与本节的关联。激发学习兴趣，引入主题] | **播放PPT/课件演示**<br>**教师讲解**<br>引导学生思考，建立知识衔接 |

---

### 【讲解新知】（主体时间）

#### 知识点一：[名称]（X分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| **概念/原理讲解：**<br><br>[详细解释概念定义、核心原理，注意准确性和逻辑性]<br><br>**示例/案例：**<br><br>[具体例子，含详细分析或推导过程]<br><br>**注意事项：**<br>- [易错点1]<br>- [易错点2] | **教师板书**<br>**课件演示**<br>**教师示范，学生练习**<br>**启发学生发现规律**<br>**提示学生：此处为后面内容奠定理论基础** |

#### 知识点二：[名称]（X分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| [同上格式：概念讲解 + 示例/案例 + 注意事项] | [教师讲解/学生练习/互动问答/小组讨论等] |

---

### 【随堂练习】（6分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| **练习题：**<br>1. [基础巩固题]<br>2. [基础巩固题]<br><br>**参考答案要点：**<br>[简要说明解题思路] | **学生练习**<br>**学习平台发布练习题**<br>**教师点拨学生**<br>**注意常见错误** |

---

### 【拓展提升】（10-12分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| **思考题/综合题：**<br>1. [进阶题目，考查综合运用能力]<br>2. [开放性讨论或案例分析]<br><br>**思路点拨：**<br>[引导学生思考的方向] | **小组讨论**<br>**学生展示**<br>**教师点评总结** |

---

### 【课堂小结】（1-2分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| 1. 回顾本节课主要内容：[列出核心知识点]<br>2. 强调重点和难点<br>3. 预告下节课内容：[简要说明下节主题] | **教师总结**<br>**学生复述要点** |

---

### 【课后作业】（1分钟）

| 授课内容 | 教学活动 |
|---------|---------|
| 1. [具体作业任务，如完成在线作业/习题]<br>2. [阅读材料或观看视频]<br>3. [预习下节内容] | **布置作业**<br>**说明提交方式和时间** |

---

## 三、板书设计
【主板书】
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

【副板书】
补充说明/推导过程
学生提问解答
临时演算/示例

---

## 四、教学反思

| 项目 | 内容 |
|------|------|
| **预设效果** | [预期达成的教学效果] |
| **课堂反馈** | [观察到的学生反应、参与度] |
| **存在问题** | [实际授课中可能遇到的问题] |
| **改进措施** | [针对问题的调整方案] |

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
内容详实，适合教师直接用于授课
采用"授课内容 + 教学活动"双栏对应格式
每个环节标注具体时长（参考：导入5分钟、新知主体、随堂练习6分钟、拓展提升10-12分钟、小结1-2分钟、作业1分钟）
提供结构化的板书设计建议
包含基础练习和拓展提升两个层次
教学反思包含预设效果、课堂反馈、存在问题、改进措施
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
