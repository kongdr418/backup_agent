"""
MiniMax Agent - 教师辅助 AI 助手
使用 MiniMax 大模型 API
支持 PPT 制作、课程讲义生成等功能
"""

import requests
import json
import os
import re
from datetime import datetime
from typing import Generator, Optional
from ppt_generator import PPTGenerator
from ppt_preview import generate_text_preview, PPTPreviewer
from lecture_generator import LectureGenerator
from content_generator import ContentGenerator
from memory_manager import MemoryManager
from course_outline_generator import CourseOutlineGenerator
from speech_generator import SpeechGenerator
from exercise_generator import ExerciseGenerator
from quiz_generator import QuizGenerator
from knowledge_card_generator import KnowledgeCardGenerator
from mindmap_generator import MindmapGenerator


class MiniMaxAgent:
    """MiniMax 大模型 Agent"""
    
    BASE_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    
    def __init__(self, api_key: str, session_id: str = None):
        self.api_key = api_key
        self.session_id = session_id or "default"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.conversation_history = []
        self.ppt_generator = PPTGenerator()
        self.ppt_previewer = PPTPreviewer()
        self.lecture_generator = LectureGenerator()
        self.content_generator = ContentGenerator()
        self.course_outline_generator = CourseOutlineGenerator()
        self.speech_generator = SpeechGenerator()
        self.exercise_generator = ExerciseGenerator()
        self.quiz_generator = QuizGenerator()
        self.knowledge_card_generator = KnowledgeCardGenerator()
        self.mindmap_generator = MindmapGenerator()
        # 初始化记忆系统
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.memory = MemoryManager(base_dir, self.session_id)
        # 生成历史（用于 /save-memory 保存多次生成内容）
        self._generation_history = []

        # 从会话记录恢复对话历史
        self._restore_conversation_history()

    def _restore_conversation_history(self):
        """从会话记录文件恢复对话历史到内存"""
        session_file = os.path.join(self.memory.session_dir, f"{self.session_id}.md")
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析会话记录，还原为 conversation_history 格式
            # 直接按顺序提取所有 **用户** 和 **AI** 消息
            import re
            user_msgs = re.findall(r'\*\*用户\*\*[：:]\s*(.+?)(?=\n\*\*|\Z)', content, re.DOTALL)
            ai_msgs = re.findall(r'\*\*AI\*\*[：:]\s*(.+?)(?=\n\*\*|\Z)', content, re.DOTALL)

            # 按顺序添加到对话历史
            for user_content, ai_content in zip(user_msgs, ai_msgs):
                self.conversation_history.append({
                    "role": "user",
                    "content": user_content.strip()
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": ai_content.strip()
                })

    def update_content_settings(self, settings: dict):
        """更新内容生成设置"""
        self.content_generator.update_settings(settings)
    
    def check_teacher_request(self, message: str):
        """
        检查是否是教师辅助相关请求
        支持：制作PPT、预览PPT、列出PPT、生成讲义、列出讲义

        意图分析策略：
        1. 优先精确匹配（命令式指令如"制作PPT：主题"）
        2. 然后模糊匹配（口语化如"做PPT"、"帮我做个PPT"）
        3. 最后智能分析（AI辅助判断复杂意图）
        """
        # ========== 1. 精确匹配：命令式指令 ==========

        # 检查是否是内容生成请求（优先级最高）
        content_request = self.content_generator.parse_content_request(message)
        if content_request:
            topic = content_request['topic']
            content_type = content_request['type']
            return self._create_content_with_ai(topic, content_type)

        # 检查是否是列出内容请求
        if re.search(r'(列出|查看|显示).*?(?:内容|文案|音频|封面)', message) or message.lower() in ['list content', 'content list', '我的内容']:
            return self._list_contents()

        # 检查是否是讲义相关请求
        lecture_request = self.lecture_generator.parse_lecture_request(message)
        if lecture_request:
            topic = lecture_request['topic']
            return self._create_lecture_with_ai(topic)

        # 检查是否是列出讲义请求
        if re.search(r'(列出|查看|显示).*?讲义', message) or message.lower() in ['list lecture', 'lecture list', '我的讲义']:
            return self._list_lectures()

        # 检查是否是预览请求
        preview_match = re.search(r'预览[Pp][Pp][Tt][:：]?\s*(.+)?', message)
        if preview_match or '预览' in message and 'ppt' in message.lower():
            return self._handle_preview_request(message)

        # 检查是否是列出PPT请求
        if re.search(r'(列出|查看|显示).*?[Pp][Pp][Tt]', message) or message.lower() in ['list ppt', 'ppt list', '我的ppt']:
            return self._list_ppts()

        # 检查是否是制作PPT请求（精确匹配，需要冒号和主题）
        ppt_request = self.ppt_generator.parse_ppt_request(message)
        if ppt_request:
            topic = ppt_request['topic']
            return self._create_ppt_with_ai(topic)

        # ========== 新增教育功能路由 ==========

        # 检查是否是课程大纲请求
        outline_request = self.course_outline_generator.parse_outline_request(message)
        if outline_request:
            topic = outline_request['topic']
            output_format = outline_request.get('format', 'md')
            return self._create_outline_with_ai(topic, output_format)

        # 检查是否是讲稿请求
        speech_request = self.speech_generator.parse_speech_request(message)
        if speech_request:
            topic = speech_request['topic']
            output_format = speech_request.get('format', 'md')
            return self._create_speech_with_ai(topic, output_format)

        # 检查是否是习题集请求
        exercise_request = self.exercise_generator.parse_exercise_request(message)
        if exercise_request:
            topic = exercise_request['topic']
            output_format = exercise_request.get('format', 'md')
            return self._create_exercise_with_ai(topic, output_format)

        # 检查是否是课堂测验请求
        quiz_request = self.quiz_generator.parse_quiz_request(message)
        if quiz_request:
            topic = quiz_request['topic']
            output_format = quiz_request.get('format', 'md')
            return self._create_quiz_with_ai(topic, output_format)

        # 检查是否是知识卡片请求
        card_request = self.knowledge_card_generator.parse_card_request(message)
        if card_request:
            topic = card_request['topic']
            output_format = card_request.get('format', 'md')
            return self._create_card_with_ai(topic, output_format)

        # 检查是否是思维导图请求
        mindmap_request = self.mindmap_generator.parse_mindmap_request(message)
        if mindmap_request:
            topic = mindmap_request['topic']
            return self._create_mindmap_with_ai(topic)

        # ========== 2. 模糊匹配：口语化指令 ==========
        # 这些模式不需要冒号，更宽松匹配

        # PPT 相关模糊匹配
        ppt_fuzzy = self._analyze_ppt_intent(message)
        if ppt_fuzzy:
            return ppt_fuzzy

        # 讲义模糊匹配
        lecture_fuzzy = self._analyze_lecture_intent(message)
        if lecture_fuzzy:
            return lecture_fuzzy

        # ========== 3. 智能意图分析：AI 辅助判断 ==========
        # 对于无法识别的请求，调用 AI 做二次判断
        ai_analysis = self._intelligent_intent_analysis(message)
        if ai_analysis:
            return ai_analysis

        # ========== 4. 记忆系统命令 ==========
        memory_result = self._handle_memory_command(message)
        if memory_result:
            return memory_result

        return None

    def _analyze_ppt_intent(self, message: str):
        """
        模糊匹配：智能分析 PPT 相关意图（不需要冒号的口语化表达）
        支持：做PPT、做个PPT、帮我做PPT、你会不会做PPT
        """
        msg_lower = message.lower().strip()

        # 排除已精确匹配的情况（避免重复处理）
        # 检查是否已有冒号分隔的主题（已在上层精确匹配中处理）
        if re.search(r'[Pp][Pp][Tt].*[:：]', msg_lower):
            return None

        # ========== 意图类型判断 ==========

        # 类型1：询问能力 "你能不能做PPT"、"你会做PPT吗"
        if re.search(r'(能不能|会不会|能不能|可不可以|会不会).*?[Pp][Pp][Tt]', msg_lower):
            return "✅ 我可以制作 PPT！\n\n📌 请告诉我您想制作什么主题的 PPT，例如：\n• 制作PPT：人工智能发展史\n• 制作PPT：Python 入门教程\n\n或者直接说「做个PPT」我来帮您生成！"

        # 类型2：请求制作（无主题）"做PPT"、"做个PPT"、"帮我做PPT"
        if re.search(r'^([帮]?我)?[做出个给]个?[Pp][Pp][Tt]$', msg_lower) or \
           re.search(r'^([帮]?我)?做.*?[Pp][Pp][Tt]$', msg_lower):
            return "🎯 我来帮您制作 PPT！\n\n请告诉我您想制作什么主题的 PPT，例如：\n• 制作PPT：人工智能发展史\n• 制作PPT：机器学习入门\n\n您也可以直接说「制作PPT：您的主题」，我会为您生成完整的演示文稿！"

        # 类型3：询问已有PPT "看看PPT"、"有哪些PPT"
        if re.search(r'(看看|查看|浏览).*?[Pp][Pp][Tt]', msg_lower):
            return self._list_ppts()

        return None

    def _analyze_lecture_intent(self, message: str):
        """
        模糊匹配：智能分析讲义相关意图
        """
        msg_lower = message.lower().strip()

        # 排除已有冒号的情况
        if re.search(r'讲义.*[:：]', msg_lower):
            return None

        # 类型1：询问能力 "你能不能生 成讲义"
        if re.search(r'(能不能|会不会|能不能|可不可以).*讲义', msg_lower):
            return "✅ 我可以生成课程讲义！\n\n📌 请告诉我您想生成什么主题的讲义，例如：\n• 生成讲义：机器学习入门\n• 讲义：Python 基础\n\n我会为您生成完整的 Markdown 格式教案！"

        # 类型2：请求制作（无主题）"做个讲义"、"生成讲义"
        if re.search(r'^([帮]?我)?[做个给]个?讲义', msg_lower) or \
           re.search(r'(生成|制作|写).*讲义', msg_lower):
            return "🎯 我来帮您生成课程讲义！\n\n请告诉我您想生成什么主题的讲义，例如：\n• 生成讲义：数据结构与算法\n• 讲义：深度学习导论\n\n我会为您生成包含教学目标、重难点、课时安排等的完整教案！"

        return None

    def _intelligent_intent_analysis(self, message: str):
        """
        智能意图分析：使用 AI 辅助判断复杂/模糊的教师辅助请求

        当用户输入无法被规则匹配时，调用此方法。
        AI 会分析用户是否想要：制作PPT、生成讲义、生成图文内容、生成视频脚本等
        """
        # 只对包含关键词的模糊请求进行 AI 分析
        keywords = ['ppt', '讲义', '图文', '视频', '视频脚本', '课程', '教学', '课件', '教案']
        has_keyword = any(kw in message.lower() for kw in keywords)

        if not has_keyword:
            return None

        prompt = f"""你是一个教师助手，擅长理解用户的教学内容生成需求。

用户输入：「{message}」

请判断用户是否想要执行以下操作之一：
1. 制作/生成 PPT（演示文稿）
2. 生成课程讲义（教案）
3. 生成图文内容（小红书风格）
4. 生成视频脚本（短视频）

判断规则：
- 如果用户明确询问"能不能"、"会不会"，这是询问能力，应该回答"可以"并引导用户提供主题
- 如果用户说"做/生成/制作 + 内容类型"，但没有提供具体主题，应该引导用户提供主题
- 如果用户提供了具体主题，应该识别主题并返回：{{"intent": "ppt/lecture/graphic/video", "topic": "具体主题"}}
- 如果用户只是在闲聊或询问其他问题，返回 null

请以 JSON 格式返回：
{{"intent": "ppt" | "lecture" | "graphic" | "video" | null, "topic": "提取的主题或null", "response": "直接回复用户的话"}}

只返回 JSON，不要有其他内容。"""

        try:
            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,  # 低温度，更确定的输出
                    "max_tokens": 500
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            ai_output = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON 响应
            import json
            try:
                analysis = json.loads(ai_output)
                intent = analysis.get('intent')
                topic = analysis.get('topic')
                user_response = analysis.get('response', '')

                # 如果 AI 判断这是一个有效的意图
                if intent and user_response:
                    if topic:
                        # 有主题，路由到对应的生成器
                        if intent == 'ppt':
                            return self._create_ppt_with_ai(topic)
                        elif intent == 'lecture':
                            return self._create_lecture_with_ai(topic)
                        elif intent == 'graphic':
                            return self._create_content_with_ai(topic, 'graphic_content')
                        elif intent == 'video':
                            return self._create_content_with_ai(topic, 'video_script')
                    else:
                        # 没有主题，返回引导回复
                        return user_response

            except json.JSONDecodeError:
                # AI 输出不是有效 JSON，忽略
                pass

        except Exception as e:
            # AI 分析失败，记录错误但不中断流程
            print(f"[智能意图分析] 分析失败: {e}")

        return None

    def _list_ppts(self) -> str:
        """列出所有生成的 PPT"""
        import os
        ppt_dir = "generated_ppt"
        if not os.path.exists(ppt_dir):
            return "还没有生成任何 PPT 文件。"
        
        # 过滤掉临时文件（以 ~$ 开头）
        ppt_files = [f for f in os.listdir(ppt_dir) if f.endswith('.pptx') and not f.startswith('~$')]
        if not ppt_files:
            return "还没有生成任何 PPT 文件。"
        
        result = ["已生成的 PPT 文件：", "─────────────────────────"]
        for i, f in enumerate(ppt_files, 1):
            file_path = os.path.join(ppt_dir, f)
            size = os.path.getsize(file_path) / 1024  # KB
            result.append(f"{i}. {f} ({size:.1f} KB)")
        
        result.append("<br>使用 '预览PPT: 文件名' 查看内容")
        return '<br>'.join(result)
    
    def _handle_memory_command(self, message: str):
        """处理记忆系统相关命令"""
        msg_lower = message.lower().strip()
        
        # /memory - 查看记忆摘要
        if msg_lower in ['/memory', '/记忆', '查看记忆', '我的记忆']:
            return self.memory.get_memory_summary()

        # /history - 查看生成历史
        if msg_lower in ['/history', '/历史', '生成历史', '我的生成']:
            if not self._generation_history:
                return "📋 当前没有生成历史"
            lines = ["📋 最近生成内容：", "=" * 40]
            for i, item in enumerate(self._generation_history, 1):
                lines.append(f"{i}. 【{item['type']}】{item['topic']}")
            return "<br>".join(lines)

        # /new - 新对话（清除所有历史记录，包括会话记录）
        if msg_lower in ['/new', '/new session', '新会话']:
            self.clear_history()
            # 清除会话记录，确保新对话不干扰
            self.memory.clear_session_file()
            return "✅ 新对话"

        # /clear-session - 清除当前会话记录（文件和内存）
        if msg_lower in ['/clear-session', '/clear-daily', '/clearsession']:
            self.clear_history()
            self.memory.clear_session_file()
            return "✅ 当前会话记录已清除"
        
        # /clear-memory - 清除长期记忆
        if msg_lower in ['/clear-memory', '/clearmemory', '清除记忆']:
            self.memory.clear_long_term_memory()
            return "✅ 长期记忆已清除"
        
        # /save-memory - 保存当前对话到长期记忆
        save_match = re.match(r'^/save-memory\s*(.*)', msg_lower)
        if save_match or msg_lower.startswith('/save-memory'):
            # 提取要保存的内容
            extra = save_match.group(1).strip() if save_match else ""
            if extra:
                self.memory.upgrade_to_long_term(extra)
                return f"✅ 已保存到长期记忆：{extra[:100]}"
            else:
                # 让 AI 分析对话精华，自动生成值得记忆的内容
                return self._save_conversation_essence()
        
        # /search-memory 关键词 - 搜索记忆
        search_match = re.match(r'^/search-memory\s+(.+)', msg_lower)
        if search_match or msg_lower.startswith('/search-memory'):
            keyword = search_match.group(1).strip() if search_match else message.replace('/search-memory', '').replace('搜索记忆', '').strip()
            if keyword:
                results = self.memory.search_memory(keyword)
                if results:
                    response = [f"🔍 搜索 '{keyword}' 的结果：", "=" * 40]
                    for r in results[:5]:
                        response.append(f"<br>📂 来源：{r['source']}")
                        response.append(f"📄 {r['content'][:300]}")
                    return "<br>".join(response)
                return f"没有找到包含 '{keyword}' 的记忆"
            return "请提供搜索关键词，例如：/search-memory Python"
        
        # /set-name 名字 - 设置用户名
        name_match = re.match(r'^/set-name\s+(.+)', msg_lower)
        if name_match or msg_lower.startswith('/set-name'):
            name = name_match.group(1).strip() if name_match else message.replace('/set-name', '').replace('设置名字', '').strip()
            if name:
                self.memory.set_user_name(name)
                return f"✅ 用户名已设置为：{name}"
            return "请提供用户名，例如：/set-name 张老师"
        
        # /preference 键=值 - 设置偏好
        pref_match = re.match(r'^/preference\s+(.+)=(.+)', msg_lower)
        if pref_match or msg_lower.startswith('/preference'):
            try:
                if pref_match:
                    key, value = pref_match.group(1).strip(), pref_match.group(2).strip()
                else:
                    # 尝试中文字符
                    match_cn = re.match(r'^/preference\s+(\S+)\s*=\s*(.+)', message)
                    if match_cn:
                        key, value = match_cn.group(1).strip(), match_cn.group(2).strip()
                    else:
                        return "格式错误，请使用：/preference 键=值，例如：/preference 学科=语文"
                self.memory.set_preference(key, value)
                return f"✅ 偏好已设置：{key} = {value}"
            except:
                return "格式错误，请使用：/preference 键=值"
        
        return None

    def _summarize_with_ai(self, content: str, gen_type: str) -> str:
        """使用 AI 精简内容"""
        prompts = {
            '对话': '''请分析以下对话，提取出值得永久记住的知识、偏好或重要信息。

【对话记录】
{content}

请按以下固定格式返回（只返回记忆内容，不要其他说明）：
**主题**：一句话概括主题
**关键知识点**：1-3条要点，用分号分隔''',

            'ppt': '''请分析以下PPT大纲，提取核心要点。

【PPT内容】
{content}

请严格按以下格式返回（必须包含**主题**和**核心要点**，不要其他文字）：
**主题**：[一句话概括PPT主题]
**核心要点**：[3-5个核心要点，用分号分隔]''',

            'lecture': '''请分析以下讲义内容，提取核心要点。

【讲义内容】
{content}

请按以下固定格式返回（只返回记忆内容，不要其他说明）：
**主题**：讲义主题
**核心要点**：3-5个核心要点，用分号分隔''',

            'graphic_content': '''请分析以下图文内容，提取核心要点。

【图文内容】
{content}

请按以下固定格式返回（只返回记忆内容，不要其他说明）：
**主题**：内容主题
**核心要点**：3-5个核心要点，用分号分隔''',

            'video_script': '''请分析以下视频脚本，提取核心要点。

【视频脚本】
{content}

请按以下固定格式返回（只返回记忆内容，不要其他说明）：
**主题**：视频主题
**核心要点**：3-5个核心要点，用分号分隔'''
        }

        # 根据类型限制内容大小，避免超时
        if gen_type == 'graphic_content':
            content = content[:1500]
        elif gen_type == 'video_script':
            content = content[:2000]
        else:
            content = content[:3000]

        prompt = prompts.get(gen_type, prompts['对话']).format(content=content)
        print(f"[AI精简] 发送请求 - 类型:{gen_type}, 内容长度:{len(content)}, prompt长度:{len(prompt)}")

        import re
        max_retries = 2

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json={
                        "model": "MiniMax-M2.5-highspeed",
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "temperature": 0.7,
                        "max_tokens": 1500
                    },
                    timeout=60
                )
                response.raise_for_status()
                result = response.json()
                ai_output = result["choices"][0]["message"]["content"]
                print(f"[AI精简] 原始返回({len(ai_output)}字符): {ai_output[:300]}")
                print(f"[AI精简调试] 状态码: {response.status_code}, choices数: {len(result.get('choices', []))}")
                if not ai_output:
                    print(f"[AI精简调试] 完整响应: {json.dumps(result, ensure_ascii=False)[:500]}")
                    # 检查是否有 finish_reason
                    try:
                        finish_reason = result["choices"][0].get("finish_reason", "无")
                        print(f"[AI精简调试] finish_reason: {finish_reason}")
                    except:
                        pass

                summary = ai_output.strip()

                # 清理 markdown 格式
                summary = re.sub(r'^```(?:markdown)?\s*', '', summary)
                summary = re.sub(r'\s*```$', '', summary)

                # 如果返回内容但没有包含格式关键词，尝试用正则提取
                if summary and '**主题**' not in summary and '**核心要点**' not in summary:
                    topic_match = re.search(r'(?:主题|Title)[:：]\s*(.+?)(?:\n|$)', summary)
                    key_match = re.search(r'(?:核心要点|要点|关键)[:：]\s*(.+?)(?:\n|$)', summary, re.IGNORECASE)
                    if topic_match or key_match:
                        topic = topic_match.group(1).strip() if topic_match else '[提取的主题]'
                        keys = key_match.group(1).strip() if key_match else '[提取的要点]'
                        summary = f"**主题**：{topic}\n**核心要点**：{keys}"
                        print(f"[记忆] AI格式不标准，已用正则提取: {topic[:20]}")

                return summary if summary else None
            except requests.exceptions.Timeout:
                print(f"[AI精简超时] 尝试 {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # 等待 2 秒后重试
            except requests.exceptions.HTTPError as e:
                print(f"[AI精简HTTP错误] 尝试 {attempt+1}/{max_retries}: 状态码 {e.response.status_code}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
            except Exception as e:
                print(f"[AI精简失败] 尝试 {attempt+1}/{max_retries}: {type(e).__name__}: {str(e)}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(1)

        return None

    def _save_conversation_simple(self) -> str:
        """保存对话内容到长期记忆（AI 精简）"""
        if not self.conversation_history:
            return "当前没有对话内容"

        # 取最近 6 条对话
        recent = self.conversation_history[-6:]
        history_lines = []
        for msg in recent:
            role = "用户" if msg.get('role') == 'user' else "AI"
            content = msg.get('content', '')[:500]
            history_lines.append(f"{role}：{content}")

        raw_content = "\n".join(history_lines)

        # AI 精简
        summary = self._summarize_with_ai(raw_content, '对话')
        if summary:
            content = f"【对话】\n{summary}"
        else:
            # AI 精简失败时降级为简单截断
            content = f"【对话】\n**主题**：对话记录\n**关键知识点**：{raw_content[:200]}..."

        self.memory.upgrade_to_long_term(content)
        return f"✅ 已保存 {len(recent)} 条对话到长期记忆（AI 精简）"

    def _save_generation_simple(self) -> str:
        """保存生成内容到长期记忆（AI 精简）"""
        if not self._generation_history:
            return "当前没有生成内容"

        saved = []
        for item in self._generation_history:
            gen_type = item.get('type', 'unknown')
            topic = item.get('topic', '未知主题')
            data = item.get('data', {})

            # 收集原始内容用于 AI 精简
            raw_content = f"主题：{topic}\n"

            # 如果是 PPT，格式化大纲
            if gen_type == 'ppt' and 'slides' in data:
                slides = data['slides']
                raw_content += "PPT大纲：\n"
                for i, slide in enumerate(slides):
                    slide_type = slide.get('type', 'content')
                    slide_title = slide.get('title', f'第{i+1}页')
                    if slide_type == 'title':
                        raw_content += f"  封面：{slide_title}\n"
                    elif slide_type == 'section':
                        raw_content += f"  章节：{slide_title}\n"
                    else:
                        raw_content += f"  内容页：{slide_title}\n"
                        slide_content = slide.get('content', [])
                        if slide_content:
                            for sc_item in slide_content:
                                if isinstance(sc_item, dict):
                                    raw_content += f"    - {sc_item.get('text', '')}\n"
                                else:
                                    raw_content += f"    - {sc_item}\n"
                        else:
                            raw_content += f"    - [页面内容略]\n"

            # 如果是讲义
            elif gen_type == 'lecture' and 'lecture_content' in data:
                raw_content += f"讲义内容：\n{data['lecture_content']}"

            # 如果是图文内容
            elif gen_type == 'graphic_content' and 'xiaohongshu' in data:
                raw_content += f"图文文案：\n{data['xiaohongshu']}"

            # 如果是视频脚本
            elif gen_type == 'video_script' and 'video_script' in data:
                raw_content += f"视频脚本：\n{data['video_script']}"

            # AI 精简
            summary = self._summarize_with_ai(raw_content, gen_type)
            if summary and '**主题**' in summary and '**核心要点**' in summary:
                content = f"【{gen_type}】\n{summary}"
                print(f"[记忆] AI精简成功 - {gen_type}: {topic[:30]}")
            else:
                # AI 精简失败时降级为简单截断（保存前200字原始内容）
                preview = raw_content[:200].replace('\n', ' ').strip()
                if not preview:
                    preview = topic  # 如果raw_content为空，用标题
                content = f"【{gen_type}】\n**主题**：{topic}\n**核心要点**：{preview}..."
                print(f"[记忆] AI精简失败，使用Fallback - {gen_type}: {topic[:30]}")

            self.memory.upgrade_to_long_term(content)
            saved.append(f"【{gen_type}】{topic}")

        self._generation_history.clear()
        return f"✅ 已保存 {len(saved)} 个生成内容到长期记忆（AI 精简）"

    def _save_conversation_essence(self) -> str:
        """
        保存生成历史或对话到长期记忆（统一使用 AI 精简）
        """
        # 如果有生成历史，调用 _save_generation_simple
        if self._generation_history:
            return self._save_generation_simple()

        if not self.conversation_history:
            return "当前没有对话内容，也无法提取生成内容"

        # 对话历史使用 AI 精简
        return self._save_conversation_simple()

    def _handle_preview_request(self, message: str) -> str:
        """处理预览请求"""
        import os
        import re
        
        # 尝试提取文件名
        match = re.search(r'预览[Pp][Pp][Tt][:：]?\s*(.+)', message)
        
        ppt_dir = "generated_ppt"
        if not os.path.exists(ppt_dir):
            return "还没有生成任何 PPT 文件。"
        
        # 过滤掉临时文件（以 ~$ 开头）
        ppt_files = [f for f in os.listdir(ppt_dir) if f.endswith('.pptx') and not f.startswith('~$')]
        if not ppt_files:
            return "还没有生成任何 PPT 文件。"
        
        # 如果指定了文件名
        if match:
            file_hint = match.group(1).strip()
            # 查找匹配的 PPT
            for f in ppt_files:
                if file_hint.lower() in f.lower():
                    ppt_path = os.path.join(ppt_dir, f)
                    return self._generate_preview(ppt_path)
            return f"未找到包含 '{file_hint}' 的 PPT 文件。<br>可用文件：" + ', '.join(ppt_files)
        
        # 如果没有指定，预览最新的 PPT
        latest_ppt = max(ppt_files, key=lambda f: os.path.getmtime(os.path.join(ppt_dir, f)))
        ppt_path = os.path.join(ppt_dir, latest_ppt)
        return self._generate_preview(ppt_path)
    
    def _generate_preview(self, ppt_path: str) -> str | dict:
        """生成 PPT 预览"""
        try:
            # 尝试生成图片预览
            preview_data = self.ppt_previewer.get_preview_data(ppt_path)
            
            if 'error' in preview_data:
                # 如果图片预览失败，返回文本预览
                preview_text = generate_text_preview(ppt_path)
                return f"📊 PPT 预览<br><br>{preview_text}<br><br>💡 提示：文件位于 {ppt_path}"
            
            # 返回预览数据（包含图片）
            return {
                'type': 'ppt_preview',
                'filename': preview_data['filename'],
                'total_pages': preview_data['total_pages'],
                'slides': preview_data['slides']
            }
        except Exception as e:
            return f"预览生成失败: {str(e)}"
    
    def _list_lectures(self) -> str:
        """列出所有生成的讲义"""
        lectures = self.lecture_generator.list_lectures()
        if not lectures:
            return "还没有生成任何课程讲义。<br><br>使用 '生成讲义：主题' 来创建讲义。"
        
        result = ["📚 已生成的课程讲义：", "=" * 50]
        for i, lec in enumerate(lectures, 1):
            size_kb = lec['size'] / 1024
            result.append(f"{i}. {lec['filename']}")
            result.append(f"   创建时间: {lec['created']} | 大小: {size_kb:.1f} KB")
        
        result.append("<br>💡 提示：讲义保存在 generated_lectures/ 目录")
        return '<br>'.join(result)

    def _list_contents(self) -> str:
        """列出所有生成的内容"""
        contents = self.content_generator.list_generated_content()
        if not contents:
            return "还没有生成任何内容。<br><br>使用 '生成内容：主题' 或 '短视频：主题' 来创建内容。"

        result = ["📦 已生成的内容文件：", "=" * 50]

        # 分类统计
        text_count = sum(1 for c in contents if c['type'] == 'text')
        audio_count = sum(1 for c in contents if c['type'] == 'audio')
        image_count = sum(1 for c in contents if c['type'] == 'image')

        result.append(f"<br>📄 文案: {text_count} 个 | 🔊 音频: {audio_count} 个 | 🖼️ 图片: {image_count} 个<br>")

        for i, item in enumerate(contents[:10], 1):  # 最多显示10个
            size_kb = item['size'] / 1024
            type_emoji = {'text': '📄', 'audio': '🔊', 'image': '🖼️'}.get(item['type'], '📦')
            result.append(f"{i}. {type_emoji} {item['filename']}")
            result.append(f"   类型: {item['type']} | 时间: {item['created']} | 大小: {size_kb:.1f} KB")

        if len(contents) > 10:
            result.append(f"<br>... 还有 {len(contents) - 10} 个文件")

        result.append("<br>💡 提示：内容保存在 generated_content/ 目录")
        return '<br>'.join(result)

    def _create_content_with_ai(self, topic: str, content_type: str = 'graphic_content'):
        """
        使用 AI 生成自媒体内容
        content_type: 'graphic_content' = 图文内容（小红书文案+封面图）
                     'video_script' = 短视频脚本（脚本+AI配音）
        返回生成器，流式输出进度和结果
        """
        if content_type == 'video_script':
            # 短视频脚本：脚本 + AI配音
            outline_msg = f"📋 即将为您生成短视频脚本：<br><br>"
            outline_msg += f"主题：{topic}<br>"
            outline_msg += f"<br>将生成：<br>"
            outline_msg += "  1. 📝 短视频脚本（抖音/B站/视频号）<br>"
            outline_msg += "  2. 🔊 AI 配音音频<br><br>"
            outline_msg += "⏳ 正在生成中，请稍候...<br>"
            outline_msg += "=" * 50
            yield outline_msg

            # 从设置中获取 style
            mimo_style = self.content_generator.settings.get('mimo_style', '')

            for update in self.content_generator.generate_video_script_stream(topic, mimo_style):
                # 优先检查特殊步骤（大数据传输），因为这些的 status 也是 'running'
                if update.get('step') == 'audio_data' and update.get('data', {}).get('type') == 'video_audio_data':
                    # 音频数据单独发送
                    print(f"[DEBUG] 检测到音频数据步骤，base64长度: {len(update['data'].get('audio_base64', ''))}")
                    yield {
                        'type': 'video_audio_data',
                        'audio_base64': update['data']['audio_base64'],
                        'voiceover_text': update['data']['voiceover_text']
                    }
                elif update.get('status') == 'completed':
                    # 过滤掉大的 base64 数据，避免 JSON 过大
                    filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                    result_data = {
                        'type': 'video_complete',
                        'data': filtered_data,
                        'message': update['message']
                    }
                    # 记录到记忆
                    self.memory.log_generation(topic, 'video_script', filtered_data)
                    # 保存到生成历史供 /save-memory 使用
                    self._generation_history.append({
                        'type': 'video_script',
                        'topic': topic,
                        'data': filtered_data
                    })
                    # 最多保留10条
                    if len(self._generation_history) > 10:
                        self._generation_history.pop(0)
                    yield result_data
                elif update.get('status') == 'error':
                    yield f"<br>❌ 生成失败: {update['message']}"
                else:
                    yield f"<br>[{update.get('progress', 0)}%] {update['message']}"
        else:
            # 图文内容：小红书文案 + 封面图
            outline_msg = f"📋 即将为您生成图文内容：<br><br>"
            outline_msg += f"主题：{topic}<br>"
            outline_msg += f"<br>将生成：<br>"
            outline_msg += "  1. 📕 小红书爆款文案<br>"
            outline_msg += "  2. 🎨 AI 封面图<br><br>"
            outline_msg += "⏳ 正在生成中，请稍候...<br>"
            outline_msg += "=" * 50
            yield outline_msg

            for update in self.content_generator.generate_graphic_content_stream(topic):
                # 优先检查特殊步骤（大数据传输），因为这些的 status 也是 'running'
                if update.get('step') == 'image_data' and update.get('data', {}).get('type') == 'graphic_image_data':
                    # 图片数据单独发送
                    print(f"[DEBUG] 检测到图片数据步骤，base64长度: {len(update['data'].get('image_base64', ''))}")
                    yield {
                        'type': 'graphic_image_data',
                        'image_base64': update['data']['image_base64'],
                        'prompt': update['data']['prompt']
                    }
                elif update.get('status') == 'completed':
                    # 过滤掉大的 base64 数据，避免 JSON 过大
                    filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                    result_data = {
                        'type': 'graphic_complete',
                        'data': filtered_data,
                        'message': update['message']
                    }
                    # 记录到记忆
                    self.memory.log_generation(topic, 'graphic_content', filtered_data)
                    # 保存到生成历史供 /save-memory 使用
                    self._generation_history.append({
                        'type': 'graphic_content',
                        'topic': topic,
                        'data': filtered_data
                    })
                    # 最多保留10条
                    if len(self._generation_history) > 10:
                        self._generation_history.pop(0)
                    yield result_data
                elif update.get('status') == 'error':
                    yield f"<br>❌ 生成失败: {update['message']}"
                else:
                    yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_lecture_with_ai(self, topic: str) -> str:
        """
        使用 AI 生成课程讲义
        """
        # 构建提示词
        prompt = self.lecture_generator.generate_lecture_prompt(topic)
        
        try:
            # 调用 AI 生成讲义
            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.7,
                    "max_tokens": 4000
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            
            # 提取 Markdown 内容
            import re
            # 尝试提取代码块中的内容
            code_block_match = re.search(r'```markdown\s*\n(.*?)\n```', ai_response, re.DOTALL)
            if code_block_match:
                lecture_content = code_block_match.group(1)
            else:
                # 如果没有 markdown 标记，使用整个响应
                lecture_content = ai_response
            
            # 保存讲义文件
            output_path = self.lecture_generator.create_lecture_file(topic, lecture_content)

            # 记录到记忆
            self.memory.log_generation(topic, 'lecture', {
                'output_path': output_path,
                'lecture_content': lecture_content,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            # 保存到生成历史供 /save-memory 使用
            self._generation_history.append({
                'type': 'lecture',
                'topic': topic,
                'data': {'output_path': output_path, 'lecture_content': lecture_content}
            })
            # 最多保留10条
            if len(self._generation_history) > 10:
                self._generation_history.pop(0)

            # 生成预览
            preview = self.lecture_generator.get_lecture_preview(output_path, max_lines=30)

            return f"✅ 课程讲义已生成！<br>📄 文件路径: {output_path}<br><br>📋 内容预览：<br>─────────────────────────<br>{preview}<br>─────────────────────────<br><br>💡 提示：这是 Markdown 格式文件，可以用任何文本编辑器打开"
            
        except Exception as e:
            return f"❌ 讲义生成失败: {str(e)}"

    def _create_outline_with_ai(self, topic: str, output_format: str = "md"):
        """使用 AI 生成课程大纲"""
        yield f"📋 即将为您生成课程大纲：{topic}（{output_format.upper()}格式）<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.course_outline_generator.generate_outline_stream(topic, output_format):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'course_outline', filtered_data)
                self._generation_history.append({
                    'type': 'course_outline',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'course_outline_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_speech_with_ai(self, topic: str, output_format: str = "md"):
        """使用 AI 生成讲稿"""
        yield f"📋 即将为您生成授课讲稿：{topic}（{output_format.upper()}格式）<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.speech_generator.generate_speech_stream(topic, output_format):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'speech', filtered_data)
                self._generation_history.append({
                    'type': 'speech',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'speech_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_exercise_with_ai(self, topic: str, output_format: str = "md"):
        """使用 AI 生成习题集"""
        yield f"📋 即将为您生成习题集：{topic}（{output_format.upper()}格式）<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.exercise_generator.generate_exercise_stream(topic, output_format):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'exercise', filtered_data)
                self._generation_history.append({
                    'type': 'exercise',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'exercise_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_quiz_with_ai(self, topic: str, output_format: str = "md"):
        """使用 AI 生成课堂测验"""
        yield f"📋 即将为您生成课堂测验：{topic}（{output_format.upper()}格式）<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.quiz_generator.generate_quiz_stream(topic, output_format):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'quiz', filtered_data)
                self._generation_history.append({
                    'type': 'quiz',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'quiz_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_card_with_ai(self, topic: str, output_format: str = "md"):
        """使用 AI 生成知识卡片"""
        yield f"📋 即将为您生成知识卡片：{topic}（{output_format.upper()}格式）<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.knowledge_card_generator.generate_card_stream(topic, output_format):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'knowledge_card', filtered_data)
                self._generation_history.append({
                    'type': 'knowledge_card',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'knowledge_card_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_mindmap_with_ai(self, topic: str):
        """使用 AI 生成思维导图"""
        yield f"📋 即将为您生成思维导图：{topic}<br><br>⏳ 正在生成中，请稍候...<br>=================================================="

        for update in self.mindmap_generator.generate_mindmap_stream(topic):
            if update.get('status') == 'completed':
                filtered_data = {k: v for k, v in update['data'].items() if 'base64' not in k}
                self.memory.log_generation(topic, 'mindmap', filtered_data)
                self._generation_history.append({
                    'type': 'mindmap',
                    'topic': topic,
                    'data': filtered_data
                })
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)
                yield {
                    'type': 'mindmap_complete',
                    'data': filtered_data,
                    'message': update['message']
                }
            elif update.get('status') == 'error':
                yield f"<br>❌ 生成失败: {update['message']}"
            else:
                yield f"<br>[{update.get('progress', 0)}%] {update['message']}"

    def _create_ppt_with_ai(self, topic: str):
        """
        使用 AI 生成 PPT 内容并创建 PPT 文件
        返回：生成器，先输出大纲文本，再输出预览数据
        """
        # 构建提示词，让 AI 生成 PPT 大纲
        prompt = f'''请为"{topic}"这个主题生成一个PPT大纲。

请按以下格式返回（JSON格式）：
{{
    "title": "PPT标题",
    "slides": [
        {{"type": "title", "title": "封面标题"}},
        {{"type": "content", "title": "页面标题", "content": ["要点1", "要点2", "要点3"]}},
        {{"type": "section", "title": "章节标题"}}
    ]
}}

要求：
1. 包含封面页、3-5个内容页、结束页
2. 内容简洁明了，适合演讲
3. 只返回JSON，不要其他说明文字'''

        try:
            # 调用 AI 生成大纲
            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                json={
                    "model": "MiniMax-M2.5-highspeed",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]

            # 解析 JSON
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                ppt_data = json.loads(json_match.group())
                slides = ppt_data.get('slides', [])
                title = ppt_data.get('title', topic)

                # 1. 先输出大纲
                outline_lines = [f"📋 PPT 大纲：{title}", "─────────────────────────"]
                for i, slide in enumerate(slides, 1):
                    slide_type = slide.get('type', 'content')
                    slide_title = slide.get('title', f'第{i}页')
                    if slide_type == 'title':
                        outline_lines.append(f"<br>🎬 封面：{slide_title}")
                    elif slide_type == 'section':
                        outline_lines.append(f"<br>📑 章节：{slide_title}")
                    else:
                        outline_lines.append(f"<br>📄 第{i}页：{slide_title}")
                        content = slide.get('content', [])
                        if content:
                            for item in content:
                                if isinstance(item, dict):
                                    outline_lines.append(f"   • {item.get('text', '')}")
                                else:
                                    outline_lines.append(f"   • {item}")

                yield '<br>'.join(outline_lines)

                # 2. 生成 PPT
                output_path = self.ppt_generator.create_ppt(title, slides, theme="teal")

                # 记录到记忆（包含完整 slides 用于大纲保存）
                self.memory.log_generation(topic, 'ppt', {
                    'output_path': output_path,
                    'title': title,
                    'slides': slides,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                # 保存到生成历史供 /save-memory 使用
                self._generation_history.append({
                    'type': 'ppt',
                    'topic': topic,
                    'data': {'slides': slides, 'title': title, 'output_path': output_path}
                })
                # 最多保留10条
                if len(self._generation_history) > 10:
                    self._generation_history.pop(0)

                # 3. 输出文件路径和预览提示
                completion_msg = f"<br>─────────────────────────<br>✅ PPT 已生成！<br>📄 文件路径: {output_path}<br>📊 共 {len(slides)} 页幻灯片<br><br>💡 提示：点击左侧「预览最新 PPT」按钮查看预览图"
                yield completion_msg
            else:
                yield "❌ 无法解析 AI 生成的 PPT 大纲"

        except Exception as e:
            yield f"❌ PPT 生成失败: {str(e)}"
    
    def chat(self, message: str, stream: bool = False):
        """
        发送消息给 MiniMax 模型

        Args:
            message: 用户输入的消息
            stream: 是否使用流式输出

        Returns:
            完整回复字符串、流式生成器、或 PPT 预览字典
        """
        # 首先检查是否是教师辅助相关请求（PPT、讲义等）
        teacher_result = self.check_teacher_request(message)
        if teacher_result:
            # 如果是字典（PPT预览数据），直接返回
            if isinstance(teacher_result, dict):
                return teacher_result
            # 如果是生成器（如制作PPT时先输出大纲再输出预览），直接返回
            if hasattr(teacher_result, '__iter__') and not isinstance(teacher_result, (str, bytes)):
                return teacher_result
            # 否则是普通字符串响应
            if stream:
                # 将字符串转换为生成器
                def string_generator():
                    yield teacher_result
                return string_generator()
            return teacher_result
        
        # 获取记忆上下文并注入到对话
        memory_context = self.memory.get_context_for_prompt()
        
        # 添加用户消息到历史记录
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # 构建完整的消息列表（包含记忆上下文）
        if memory_context:
            system_message = {
                "role": "system",
                "content": f"你是一个友好、有知识的AI教师助手。你拥有自己的长期记忆库，当用户询问相关问题时，你应该主动引用记忆中的内容来回答案。{memory_context}"
            }
            messages_with_context = [system_message] + self.conversation_history
        else:
            messages_with_context = self.conversation_history
        
        payload = {
            "model": "MiniMax-M2.5-highspeed",
            "messages": messages_with_context,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        try:
            response = requests.post(
                self.BASE_URL,
                headers=self.headers,
                json=payload,
                stream=stream,
                timeout=60
            )
            response.raise_for_status()
            
            if stream:
                return self._handle_stream_with_memory(response, message)
            else:
                result = response.json()
                assistant_message = result["choices"][0]["message"]["content"]
                
                # 添加助手回复到历史记录
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })
                
                # 记录到会话记忆
                self.memory.log_interaction(message, assistant_message)

                return assistant_message
                
        except requests.exceptions.RequestException as e:
            error_msg = f"请求失败: {str(e)}"
            return error_msg
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = f"解析响应失败: {str(e)}"
            return error_msg
    
    def _handle_stream(self, response) -> Generator[str, None, None]:
        """处理流式响应"""
        full_content = ""
        
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data = line_text[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                full_content += content
                                yield content
                    except json.JSONDecodeError:
                        continue
        
        # 将完整回复添加到历史记录
        if full_content:
            self.conversation_history.append({
                "role": "assistant",
                "content": full_content
            })
    
    def _handle_stream_with_memory(self, response, original_message: str) -> Generator[str, None, None]:
        """处理流式响应并记录到记忆系统"""
        full_content = ""
        
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith('data: '):
                    data = line_text[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            content = delta.get('content', '')
                            if content:
                                full_content += content
                                yield content
                    except json.JSONDecodeError:
                        continue
        
        # 将完整回复添加到历史记录
        if full_content:
            self.conversation_history.append({
                "role": "assistant",
                "content": full_content
            })
            # 记录到会话记忆
            self.memory.log_interaction(original_message, full_content)

    def clear_history(self):
        """清空对话历史（保留长期记忆）"""
        self.conversation_history = []
        self.memory.clear_session_memory()
    
    def get_history(self) -> list:
        """获取对话历史"""
        return self.conversation_history.copy()


if __name__ == "__main__":
    # 测试代码 - 从环境变量读取
    import os
    API_KEY = os.environ.get('MINIMAX_API_KEY', '')

    agent = MiniMaxAgent(API_KEY)
    
    print("=" * 60)
    print("🎓 MiniMax Agent - 教师辅助 AI 助手")
    print("=" * 60)
    print("通用指令:")
    print("  输入 'quit' 退出")
    print("  输入 'clear' 清空历史")
    print("-" * 60)
    print("PPT 功能:")
    print("  制作PPT：主题  - 生成演示文稿")
    print("  预览PPT        - 查看 PPT 内容")
    print("  列出PPT        - 查看所有 PPT 文件")
    print("-" * 60)
    print("讲义功能:")
    print("  生成讲义：主题  - 生成课程讲义(Markdown)")
    print("  列出讲义        - 查看所有讲义文件")
    print("=" * 60)
    
    while True:
        user_input = input("\n你: ").strip()
        
        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'clear':
            agent.clear_history()
            print("历史已清空")
            continue
        
        if not user_input:
            continue
        
        print("\nAI: ", end="", flush=True)
        response = agent.chat(user_input, stream=True)
        
        if isinstance(response, Generator):
            for chunk in response:
                print(chunk, end="", flush=True)
            print()
        else:
            print(response)
