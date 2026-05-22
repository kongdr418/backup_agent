"""
PPT 视频生成器
将 PPTX 文件转换为带配音和字幕的说课视频（MP4）

依赖: LibreOffice, poppler, ffmpeg, python-pptx
"""

import os
import json
import base64
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class VideoGenerator:
    """PPT 视频生成器"""

    # MIMO-TTS API 配置
    MIMO_API_KEY = os.environ.get('MIMO_API_KEY', '')
    MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
    MIMO_MODEL = "mimo-v2.5-tts"
    MIMO_VOICE = "mimo_default"

    def __init__(self, workspace_dir: str = None):
        """
        初始化视频生成器

        Args:
            workspace_dir: 工作目录，默认为 backend/generators/generated_videos
        """
        if workspace_dir is None:
            backend_dir = Path(__file__).resolve().parent
            workspace_dir = backend_dir / "generated_videos"
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def generate_video(
        self,
        pptx_path: str,
        topic: str = None,
        voice: str = "mimo_default",
        progress_callback=None
    ):
        """
        生成说课视频

        Args:
            pptx_path: PPTX 文件路径
            topic: 视频主题（用于输出目录命名）
            voice: MIMO-TTS 语音（默认: mimo_default）
            progress_callback: 进度回调函数

        Returns:
            包含视频路径、字幕路径等信息的字典
        """
        pptx_path = Path(pptx_path).resolve()
        if not pptx_path.exists():
            raise FileNotFoundError(f"PPTX 文件不存在: {pptx_path}")

        # 解析主题名
        if topic is None:
            topic = pptx_path.stem

        # 创建临时目录和输出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = topic.replace(" ", "_").replace("/", "_")
        temp_dir = self.workspace_dir / f"temp_{safe_topic}_{timestamp}"
        output_dir = self.workspace_dir / f"{datetime.now().strftime('%Y-%m-%d')}-{safe_topic}"

        temp_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "slides").mkdir(exist_ok=True)
        (temp_dir / "audio").mkdir(exist_ok=True)

        yield from self._send_progress(progress_callback, 0.1, "导出页图...")

        # 阶段1: 导出页图 (LibreOffice → PDF → PNG)
        self._export_slides(pptx_path, temp_dir)
        slide_count = len(list((temp_dir / "slides").glob("*.png")))
        yield from self._send_progress(progress_callback, 0.25, f"页图导出完成 ({slide_count} 页)")

        # 阶段2: 解析PPT生成讲稿
        slides_data = self._parse_ppt(pptx_path, temp_dir)
        yield from self._send_progress(progress_callback, 0.35, "讲稿解析完成")

        # 阶段2.5: 对无备注的页用 LLM 生成自然讲稿（有备注则跳过）
        yield from self._generate_llm_scripts(slides_data, topic, progress_callback)

        # 阶段3: 生成配音
        yield from self._generate_audio(slides_data, temp_dir, voice, progress_callback)
        yield from self._send_progress(progress_callback, 0.6, "配音生成完成")

        # 阶段4: 获取音频时长
        durations = self._get_durations(slides_data, temp_dir)
        yield from self._send_progress(progress_callback, 0.65, "获取音频时长")

        # 阶段5: 生成字幕
        subtitle_path = output_dir / "05-subtitles.srt"
        self._generate_subtitles(slides_data, durations, subtitle_path)
        yield from self._send_progress(progress_callback, 0.7, "字幕生成完成")

        # 阶段6: 合成视频
        video_path = self._合成视频(slides_data, durations, temp_dir, output_dir, progress_callback)
        yield from self._send_progress(progress_callback, 0.9, "视频合成完成")

        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)

        # 复制资源到输出目录
        self._copy_assets(pptx_path, slides_data, durations, output_dir)

        # 生成元数据
        self._generate_metadata(topic, slides_data, durations, output_dir)

        yield from self._send_progress(progress_callback, 1.0, "视频生成完成")

        yield {
            "success": True,
            "video_path": str(video_path),
            "subtitle_path": str(subtitle_path),
            "output_dir": str(output_dir),
            "slide_count": len(slides_data),
            "total_duration": sum(durations.values()),
        }

    def _send_progress(self, callback, progress: float, message: str):
        if callback:
            yield from callback(progress, message)

    def _export_slides(self, pptx_path: Path, temp_dir: Path):
        """导出页图: LibreOffice → PDF → PNG"""
        # 转换为 PDF
        libreoffice = self._find_libreoffice()
        pdf_path = temp_dir / f"{pptx_path.stem}.pdf"

        subprocess.run([
            str(libreoffice), "--headless",
            "--convert-to", "pdf",
            str(pptx_path),
            "--outdir", str(temp_dir)
        ], check=True, capture_output=True)

        # PDF → PNG
        subprocess.run([
            "pdftoppm", "-r", "150", "-png",
            str(pdf_path),
            str(temp_dir / "slides" / "slide")
        ], check=True, capture_output=True)

        # 删除 PDF
        pdf_path.unlink(missing_ok=True)

    def _find_libreoffice(self) -> Path:
        """查找 LibreOffice 可执行文件"""
        import platform

        # 1. 先尝试环境变量
        env_path = os.environ.get('LIBREOFFICE_PATH')
        if env_path and Path(env_path).exists():
            return Path(env_path)

        system = platform.system()

        if system == 'Darwin':  # macOS
            mac_path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
            if mac_path.exists():
                return mac_path

        elif system == 'Windows':  # Windows
            for prog in [os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', '')]:
                if prog:
                    path = Path(prog) / 'LibreOffice/program/soffice.exe'
                    if path.exists():
                        return path

        # 2. 再检查 PATH 中是否有 soffice/libreoffice
        result = shutil.which("soffice") or shutil.which("libreoffice")
        if result:
            return Path(result)

        raise FileNotFoundError("未找到 LibreOffice")

    def _parse_ppt(self, pptx_path: Path, temp_dir: Path) -> List[Dict]:
        """解析PPT，生成讲稿"""
        from pptx import Presentation

        prs = Presentation(str(pptx_path))
        slides = []

        for i, slide in enumerate(prs.slides, 1):
            title = ""
            content_lines = []

            for shape in slide.shapes:
                if shape.has_text_frame:
                    text = shape.text_frame.text.strip()
                    if not title and text:
                        title = text[:100]
                    if text and len(text) > 5:
                        content_lines.append(text[:200])

            notes = ""
            try:
                if slide.has_notes_slide and slide.notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
            except Exception:
                pass

            needs_llm = not notes
            combined_script = notes if notes else (
                "；".join(content_lines[:5]) if content_lines else f"这是第{i}页内容"
            )

            slides.append({
                "index": i,
                "title": title,
                "content": "\n".join(content_lines[:10]),
                "script": combined_script,
                "needs_llm": needs_llm,
            })

        # 保存讲稿
        script_path = temp_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(slides, f, ensure_ascii=False, indent=2)

        return slides

    def _generate_llm_scripts(self, slides_data, topic, progress_callback):
        """对无备注的页用 DeepSeek 批量生成自然讲稿，原地回填 slide['script']。失败时静默回退。"""
        missing_pages = [s for s in slides_data if s.get("needs_llm")]
        if not missing_pages:
            return

        yield from self._send_progress(
            progress_callback, 0.38,
            f"LLM 生成讲稿中 ({len(missing_pages)} 页)..."
        )

        api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
        if not api_key:
            print("[VIDEO] DEEPSEEK_API_KEY 未配置，跳过 LLM 讲稿生成")
            return

        try:
            from openai import OpenAI
        except ImportError:
            print("[VIDEO] openai SDK 未安装，跳过 LLM 讲稿生成")
            return

        slides_context = [
            {
                "index": s["index"],
                "title": s.get("title", ""),
                "content": (s.get("content", "") or "")[:500],
            }
            for s in slides_data
        ]
        missing_indices = [s["index"] for s in missing_pages]
        topic_hint = f"\n课程主题：{topic}" if topic else ""

        prompt = (
            f"你是一位经验丰富的教师，需要为一个PPT课件配上口播讲稿。{topic_hint}\n\n"
            f"下面是这个PPT课件的全部页面信息（JSON 数组，提供完整上下文）：\n\n"
            f"{json.dumps(slides_context, ensure_ascii=False, indent=2)}\n\n"
            f"请仅为以下页码生成讲稿：{missing_indices}\n\n"
            "【重要】请根据每一页的角色合理分配讲解时长，不要平均分配。识别规则与长度建议：\n\n"
            "- 封面页（通常是第1页，标题简短如\"XX课程\"\"XX介绍\"，几乎无内容）\n"
            "  → 30-60 字，简短开场欢迎 + 点题，不要展开内容\n"
            "- 目录/大纲页（标题含\"目录\"\"大纲\"\"提纲\"\"Contents\"，内容是章节列表）\n"
            "  → 40-80 字，简要概述课程结构，不要逐条朗读目录\n"
            "- 章节过渡/分隔页（仅含章节号或一句小标题，内容极少）\n"
            "  → 20-40 字，一句话过场即可\n"
            "- 正文内容页（包含具体知识点、要点、案例、数据等）\n"
            "  → 100-180 字，展开讲解，举例说明，避免单纯堆砌要点\n"
            "- 总结/结语/谢谢页（标题含\"总结\"\"小结\"\"结语\"\"谢谢\"\"Q&A\"）\n"
            "  → 60-100 字，回顾要点 + 自然收尾\n\n"
            "通用要求：\n"
            "1. 口语化、自然流畅，适合中文 TTS 朗读\n"
            "2. 多页之间有自然过渡（\"接下来\"\"我们再看\"\"刚才提到的\"）\n"
            "3. 纯文本，不要 markdown、emoji，标点要规范\n"
            "4. 不要硬凑字数，封面/过渡页该短就短，正文页该详细就详细\n"
            "5. 严格按 JSON 数组格式返回，不要任何额外说明\n\n"
            "返回格式（必须严格遵守）：\n"
            "[\n"
            '  {"index": 1, "script": "..."},\n'
            '  {"index": 2, "script": "..."}\n'
            "]\n"
        )

        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                timeout=30.0,
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一位中文教学讲解专家，擅长把课件内容转化为自然流畅的口播讲稿。封面、目录、过渡页要简短，正文页要详细，节奏分明。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            content = response.choices[0].message.content or ""
        except Exception as e:
            print(f"[VIDEO] LLM 讲稿生成调用失败，回退到原讲稿: {e}")
            return

        scripts = self._parse_llm_scripts(content)
        if not scripts:
            print("[VIDEO] LLM 返回内容无法解析为 JSON 数组，回退到原讲稿")
            return

        by_index = {s["index"]: s for s in slides_data}
        updated = 0
        for item in scripts:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            script = (item.get("script") or "").strip()
            if idx in by_index and script:
                by_index[idx]["script"] = script
                updated += 1

        print(f"[VIDEO] LLM 讲稿生成完成: {updated}/{len(missing_pages)} 页")

        yield from self._send_progress(
            progress_callback, 0.45,
            f"LLM 讲稿生成完成 ({updated} 页)"
        )

    def _parse_llm_scripts(self, content):
        """从 LLM 返回文本中提取 JSON 数组，宽容处理 markdown 围栏。"""
        import re

        text = (content or "").strip()
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if fence_match:
            text = fence_match.group(1).strip()

        array_match = re.search(r'\[[\s\S]*\]', text)
        if not array_match:
            return None

        try:
            parsed = json.loads(array_match.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return None

        return None

    def _generate_mimo_audio(self, voiceover_text: str, voice: str = "") -> bytes:
        """调用 MiMo V2-TTS 生成音频"""
        from openai import OpenAI

        client = OpenAI(
            api_key=self.MIMO_API_KEY,
            base_url=self.MIMO_BASE_URL
        )

        response = client.chat.completions.create(
            model=self.MIMO_MODEL,
            messages=[
                {"role": "user", "content": "请朗读以下内容"},
                {"role": "assistant", "content": voiceover_text}
            ],
            audio={
                "format": "wav",
                "voice": voice or self.MIMO_VOICE
            }
        )

        audio_data = response.choices[0].message.audio.data
        return base64.b64decode(audio_data)

    def _generate_audio(
        self,
        slides: List[Dict],
        temp_dir: Path,
        voice: str,
        callback
    ):
        """生成配音（MIMO-TTS 在线 API）"""
        audio_dir = temp_dir / "audio"

        # 顺序生成（避免并发问题）
        for slide in slides:
            i = slide["index"]
            script = slide["script"] or f"这是第{i}页内容，请观看。"
            outfile = audio_dir / f"page_{i}.wav"

            # 调用 MIMO-TTS API 生成配音
            audio_bytes = self._generate_mimo_audio(script, voice)
            with open(outfile, "wb") as f:
                f.write(audio_bytes)

            if callback:
                yield from callback(0.6 + (i / len(slides)) * 0.1, f"生成配音 {i}/{len(slides)}")

    def _get_durations(self, slides: List[Dict], temp_dir: Path) -> Dict[int, float]:
        """获取每段音频时长"""
        durations = {}
        audio_dir = temp_dir / "audio"

        for slide in slides:
            i = slide["index"]
            audio_path = audio_dir / f"page_{i}.wav"

            try:
                result = subprocess.run([
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json", str(audio_path)
                ], capture_output=True, text=True, check=True)
                data = json.loads(result.stdout)
                durations[i] = float(data["format"]["duration"])
            except:
                durations[i] = 5.0  # 默认5秒

        return durations

    def _generate_subtitles(
        self,
        slides: List[Dict],
        durations: Dict[int, float],
        output_path: Path
    ):
        """生成 SRT 字幕 和 ASS 字幕（直接输出 ASS 避免 ffmpeg 默认转换的字号过大问题）"""
        import re
        import unicodedata

        MAX_WIDTH = 36          # 视觉宽度上限（≈18个中文字）
        MIN_CHUNK_DUR = 0.5     # 最短显示时长（秒）

        def display_width(text: str) -> int:
            """计算文本显示宽度：中文字/全角=2，英文字/半角=1"""
            return sum(
                2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1
                for c in text
            )

        def force_split_chars(text: str, max_width: int) -> list:
            """按字符显示宽度强制切分，末尾标点合并到前一行"""
            result = []
            current = ""
            current_w = 0
            for i, c in enumerate(text):
                w = 2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1
                if current_w + w > max_width:
                    # 如果剩余全是标点，合并到当前行
                    remaining = text[i:]
                    if re.match(r'^[。！？；.!?;，、,\s]+$', remaining):
                        current += remaining
                        break
                    result.append(current)
                    current = c
                    current_w = w
                else:
                    current += c
                    current_w += w
            if current:
                result.append(current)
            return result

        def force_split(text: str, max_width: int = MAX_WIDTH) -> list:
            """按显示宽度强制切分，英文优先在空格/词边界断开"""
            if display_width(text) <= max_width:
                return [text]

            # 包含空格时优先按词切分（保留英文单词完整）
            if ' ' in text:
                words = text.split(' ')
                result = []
                current = ""
                current_w = 0
                for word in words:
                    word_w = display_width(word)
                    space_w = 1 if current else 0
                    if current_w + space_w + word_w <= max_width:
                        current += (" " if current else "") + word
                        current_w += space_w + word_w
                    else:
                        if current:
                            result.append(current)
                        # 单个词超长，按字符硬切
                        if word_w > max_width:
                            result.extend(force_split_chars(word, max_width))
                        else:
                            current = word
                            current_w = word_w
                if current:
                    result.append(current)
                return result

            # 无空格（纯中文/连续字符）：按字符硬切
            return force_split_chars(text, max_width)

        def split_text_cascade(text: str, max_width: int = MAX_WIDTH) -> list:
            """三级断句：句末标点 → 逗号停顿 → 强制切分，确保不超 max_width"""
            text = text.strip()
            if not text:
                return []

            # 第一级：句末标点（中英混合）
            primary = re.split(r'([。！？；.!?;])', text)
            chunks = []
            for idx in range(0, len(primary) - 1, 2):
                sent = primary[idx]
                punct = primary[idx + 1] if idx + 1 < len(primary) else ""
                if not sent.strip():          # 跳过连续标点产生的空片段
                    continue
                combined = (sent + punct).strip()
                if combined:
                    chunks.append(combined)
            if len(primary) % 2 == 1:
                tail = primary[-1].strip()
                # 尾部纯标点也跳过（由前一个 chunk 继承）
                if tail and not re.match(r'^[。！？；.!?;\s]+$', tail):
                    chunks.append(tail)

            # 第二级：逗号等次级停顿（中英混合）
            refined = []
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk:
                    continue
                if display_width(chunk) <= max_width:
                    refined.append(chunk)
                    continue

                secondary = re.split(r'([，、,（）()])', chunk)
                buffer = ""
                for idx in range(0, len(secondary) - 1, 2):
                    seg = secondary[idx]
                    punct = secondary[idx + 1] if idx + 1 < len(secondary) else ""
                    if not seg.strip():       # 跳过连续标点产生的空片段
                        continue
                    combined = seg + punct
                    if display_width(buffer) + display_width(combined) <= max_width:
                        buffer += combined
                    else:
                        if buffer.strip():
                            refined.append(buffer.strip())
                        buffer = combined
                if len(secondary) % 2 == 1:
                    tail = secondary[-1].strip()
                    # 尾部纯标点跳过，由前一个 chunk 继承
                    if tail and not re.match(r'^[，、,（）()\s]+$', tail):
                        if display_width(buffer) + display_width(tail) <= max_width:
                            buffer += tail
                        else:
                            if buffer.strip():
                                refined.append(buffer.strip())
                            buffer = tail
                if buffer.strip():
                    refined.append(buffer.strip())

            # 第三级：仍超长则强制切分
            final = []
            for chunk in refined:
                chunk = chunk.strip()
                if not chunk:
                    continue
                if display_width(chunk) > max_width:
                    final.extend(force_split(chunk, max_width))
                else:
                    final.append(chunk)

            # 第四级：后处理，合并纯标点 chunk 到相邻文本
            punct_only = re.compile(r'^[。！？；.!?;，、,\s]+$')
            merged = []
            for chunk in final:
                chunk = chunk.strip()
                if not chunk:
                    continue
                if punct_only.match(chunk):
                    if merged:
                        merged[-1] += chunk
                    else:
                        merged.append(chunk)
                else:
                    merged.append(chunk)

            # 第五级：合并过短的 chunk 到相邻 chunk，避免单字成行
            MIN_CHUNK_WIDTH = 8  # 视觉宽度下限（≈4个中文字）
            if len(merged) > 1:
                short_merged = []
                for chunk in merged:
                    if short_merged:
                        prev_w = display_width(short_merged[-1])
                        curr_w = display_width(chunk)
                        if prev_w < MIN_CHUNK_WIDTH or curr_w < MIN_CHUNK_WIDTH:
                            candidate = short_merged[-1] + chunk
                            if display_width(candidate) <= max_width:
                                short_merged[-1] = candidate
                                continue
                    short_merged.append(chunk)
                merged = short_merged

            return [c.strip() for c in merged if c.strip()]

        def srt_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        def ass_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h:01d}:{m:02d}:{s:05.2f}"

        def escape_ass(text: str) -> str:
            """转义 ASS 特殊字符"""
            return (text
                    .replace("\\", "")
                    .replace("{", "(")
                    .replace("}", ")")
                    .replace("\n", " ")
                    .replace("\r", ""))

        srt_entries = []
        ass_events = []
        srt_idx = 1
        cursor = 0.0

        for slide in slides:
            i = slide["index"]
            script = slide.get("script") or ""
            dur = durations.get(i, 5.0)

            paragraphs = re.split(r'\n+', script.strip())
            all_chunks = []
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                all_chunks.extend(split_text_cascade(para))

            if not all_chunks:
                # 无脚本也要推进时间，防止后续时间戳错位
                cursor += dur
                continue

            # 字符数加权时长分配
            slide_start = cursor
            total_chars = sum(len(c) for c in all_chunks)
            if total_chars == 0:
                cursor += dur
                continue

            for chunk in all_chunks:
                chunk_chars = len(chunk)
                chunk_dur = max(MIN_CHUNK_DUR, dur * chunk_chars / total_chars)
                start = cursor
                end = cursor + chunk_dur
                cursor = end

                # SRT
                srt_entries.append(
                    f"{srt_idx}\n{srt_time(start)} --> {srt_time(end)}\n{chunk}\n"
                )
                srt_idx += 1

                # ASS event
                safe_text = escape_ass(chunk)
                ass_events.append(
                    f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{safe_text}"
                )

            # 严格对齐到 slide 结束时间（消除累计误差）
            cursor = slide_start + dur

        # 写入 SRT 文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_entries))

        # 生成 ASS 文件（自定义样式）
        ass_path = output_path.parent / "06-subtitles.ass"
        ass_header = (
            "[Script Info]\n"
            "Title: AI Creator Subtitles\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n"
            "WrapStyle: 0\n"
            "ScaledBorderAndShadow: yes\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Microsoft YaHei,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,200,200,80,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(ass_events))

    def _合成视频(
        self,
        slides: List[Dict],
        durations: Dict[int, float],
        temp_dir: Path,
        output_dir: Path,
        callback
    ) -> Path:
        """合成 MP4 视频"""
        # 合并音频
        concat_list = temp_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for slide in slides:
                i = slide["index"]
                f.write(f"file 'audio/page_{i}.wav'\n")

        full_audio = temp_dir / "full_audio.wav"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            str(full_audio)
        ], check=True, capture_output=True)

        # 生成各页视频片段
        segments_list = temp_dir / "segments.txt"
        with open(segments_list, "w") as f:
            for slide in slides:
                i = slide["index"]
                slide_img = temp_dir / "slides" / f"slide-{i}.png"
                audio = temp_dir / "audio" / f"page_{i}.wav"
                dur = durations.get(i, 5.0)
                seg = temp_dir / f"seg_{i}.mp4"

                if slide_img.exists():
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-loop", "1", "-i", str(slide_img),
                        "-i", str(audio),
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-pix_fmt", "yuv420p", "-t", str(dur), "-r", "30",
                        "-movflags", "+faststart",
                        str(seg)
                    ], check=True, capture_output=True)

                    f.write(f"file 'seg_{i}.mp4'\n")

        # 拼接片段
        preview = temp_dir / "preview.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(segments_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-movflags", "+faststart",
            str(preview)
        ], check=True, capture_output=True)

        # 烧录字幕（ASS 已由 _generate_subtitles 直接生成，跳过 ffmpeg 默认转换）
        ass_path = output_dir / "06-subtitles.ass"
        video_path = output_dir / "07-video.mp4"
        temp_video = output_dir / "07-video.tmp.mp4"
        if not ass_path.exists():
            raise FileNotFoundError(f"字幕文件不存在: {ass_path}")

        # 先写临时文件，完成后原子 rename，避免前端加载到未写完的文件
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(preview),
            "-i", str(full_audio),
            "-vf", f"ass={ass_path.name}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(temp_video)
        ], check=True, capture_output=True, cwd=str(output_dir))

        temp_video.rename(video_path)
        return video_path

    def _copy_assets(
        self,
        pptx_path: Path,
        slides: List[Dict],
        durations: Dict[int, float],
        output_dir: Path
    ):
        """复制资源到输出目录"""
        assets_dir = output_dir / "assets"
        (assets_dir / "slides").mkdir(parents=True, exist_ok=True)
        (assets_dir / "audio").mkdir(parents=True, exist_ok=True)

    def _generate_metadata(
        self,
        topic: str,
        slides: List[Dict],
        durations: Dict[int, float],
        output_dir: Path
    ):
        """生成元数据文件"""
        total_dur = sum(durations.values())

        # 简报
        brief = f"""# 视频简报

- **主题**: {topic}
- **日期**: {datetime.now().strftime('%Y-%m-%d')}
- **总页数**: {len(slides)}
- **总时长**: {total_dur:.2f}s
"""
        with open(output_dir / "01-brief.md", "w", encoding="utf-8") as f:
            f.write(brief)

        # 幻灯片摘要
        with open(output_dir / "02-slide-summary.md", "w", encoding="utf-8") as f:
            f.write("# 幻灯片摘要\n\n")
            for s in slides:
                f.write(f"## 第{s['index']}页: {s['title']}\n")
                f.write(f"内容: {s['content'][:200]}\n\n")

        # 讲稿
        with open(output_dir / "03-script.json", "w", encoding="utf-8") as f:
            json.dump(slides, f, ensure_ascii=False, indent=2)
