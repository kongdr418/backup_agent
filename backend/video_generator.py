"""
PPT 视频生成器
将 PPTX 文件转换为带配音和字幕的说课视频（MP4）

依赖: LibreOffice, poppler, ffmpeg, edge-tts, python-pptx
"""

import os
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class VideoGenerator:
    """PPT 视频生成器"""

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
        voice: str = "zh-CN-XiaoxiaoNeural",
        progress_callback=None
    ) -> Dict:
        """
        生成说课视频

        Args:
            pptx_path: PPTX 文件路径
            topic: 视频主题（用于输出目录命名）
            voice: edge-tts 语音（默认: zh-CN-XiaoxiaoNeural）
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

        self._send_progress(progress_callback, 0.1, "导出页图...")

        # 阶段1: 导出页图 (LibreOffice → PDF → PNG)
        self._export_slides(pptx_path, temp_dir)
        slide_count = len(list((temp_dir / "slides").glob("*.png")))
        self._send_progress(progress_callback, 0.25, f"页图导出完成 ({slide_count} 页)")

        # 阶段2: 解析PPT生成讲稿
        slides_data = self._parse_ppt(pptx_path, temp_dir)
        self._send_progress(progress_callback, 0.35, "讲稿解析完成")

        # 阶段3: 生成配音
        self._generate_audio(slides_data, temp_dir, voice, progress_callback)
        self._send_progress(progress_callback, 0.6, "配音生成完成")

        # 阶段4: 获取音频时长
        durations = self._get_durations(slides_data, temp_dir)
        self._send_progress(progress_callback, 0.65, "获取音频时长")

        # 阶段5: 生成字幕
        subtitle_path = output_dir / "05-subtitles.srt"
        self._generate_subtitles(slides_data, durations, subtitle_path)
        self._send_progress(progress_callback, 0.7, "字幕生成完成")

        # 阶段6: 合成视频
        video_path = self._合成视频(slides_data, durations, temp_dir, output_dir, progress_callback)
        self._send_progress(progress_callback, 0.9, "视频合成完成")

        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)

        # 复制资源到输出目录
        self._copy_assets(pptx_path, slides_data, durations, output_dir)

        # 生成元数据
        self._generate_metadata(topic, slides_data, durations, output_dir)

        self._send_progress(progress_callback, 1.0, "视频生成完成")

        return {
            "success": True,
            "video_path": str(video_path),
            "subtitle_path": str(subtitle_path),
            "output_dir": str(output_dir),
            "slide_count": len(slides_data),
            "total_duration": sum(durations.values()),
        }

    def _send_progress(self, callback, progress: float, message: str):
        if callback:
            callback(progress, message)

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
        pdftoppm = self._find_pdftoppm()
        subprocess.run([
            pdftoppm, "-r", "150", "-png",
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

    def _find_pdftoppm(self) -> str:
        """查找 pdftoppm 可执行文件"""
        env_path = os.environ.get('PDFTOPPM_PATH')
        if env_path and Path(env_path).exists():
            return env_path
        result = shutil.which("pdftoppm")
        if result:
            return result
        raise FileNotFoundError("未找到 pdftoppm")

    def _find_ffmpeg(self) -> str:
        """查找 ffmpeg 可执行文件"""
        env_path = os.environ.get('FFMPEG_PATH')
        if env_path and Path(env_path).exists():
            return env_path
        result = shutil.which("ffmpeg")
        if result:
            return result
        raise FileNotFoundError("未找到 ffmpeg")

    def _find_ffprobe(self) -> str:
        """查找 ffprobe 可执行文件"""
        env_path = os.environ.get('FFPROBE_PATH')
        if env_path and Path(env_path).exists():
            return env_path
        result = shutil.which("ffprobe")
        if result:
            return result
        raise FileNotFoundError("未找到 ffprobe")

    def _find_edgetts(self) -> str:
        """查找 edge-tts 可执行文件"""
        env_path = os.environ.get('EDGE_TTS_PATH')
        if env_path and Path(env_path).exists():
            return env_path
        result = shutil.which("edge-tts")
        if result:
            return result
        raise FileNotFoundError("未找到 edge-tts")

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
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()

            combined_script = notes if notes else (
                "；".join(content_lines[:5]) if content_lines else f"这是第{i}页内容"
            )

            slides.append({
                "index": i,
                "title": title,
                "content": "\n".join(content_lines[:10]),
                "script": combined_script
            })

        # 保存讲稿
        script_path = temp_dir / "script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(slides, f, ensure_ascii=False, indent=2)

        return slides

    def _generate_audio(
        self,
        slides: List[Dict],
        temp_dir: Path,
        voice: str,
        callback
    ):
        """生成配音"""
        audio_dir = temp_dir / "audio"

        # 顺序生成（避免并发问题）
        for slide in slides:
            i = slide["index"]
            script = slide["script"] or f"这是第{i}页内容，请观看。"
            outfile = audio_dir / f"page_{i}.m4a"

            # 生成配音
            edgetts = self._find_edgetts()
            subprocess.run([
                edgetts,
                "--voice", voice,
                "--text", script,
                "--write-media", str(outfile)
            ], check=True, capture_output=True)

            if callback:
                callback(0.6 + (i / len(slides)) * 0.1, f"生成配音 {i}/{len(slides)}")

    def _get_durations(self, slides: List[Dict], temp_dir: Path) -> Dict[int, float]:
        """获取每段音频时长"""
        durations = {}
        audio_dir = temp_dir / "audio"

        for slide in slides:
            i = slide["index"]
            audio_path = audio_dir / f"page_{i}.m4a"

            try:
                ffprobe = self._find_ffprobe()
                result = subprocess.run([
                    ffprobe, "-v", "error",
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
        """生成 SRT 字幕"""
        import re

        def split_long_text(text, max_chars=22):
            paragraphs = re.split(r'\n+', text.strip())
            result = []
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                sentences = re.split(r'([。！？；])', para)
                current = ""
                for idx in range(0, len(sentences) - 1, 2):
                    sent = sentences[idx]
                    punct = sentences[idx + 1] if idx + 1 < len(sentences) else ""
                    combined = sent + punct
                    if len(current) + len(combined) <= max_chars:
                        current += combined
                    else:
                        if current.strip():
                            result.append(current.strip())
                        current = combined
                if current.strip():
                    result.append(current.strip())
            return result

        def time_str(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_index = 1
        current_time = 0.0

        with open(output_path, "w", encoding="utf-8") as f:
            for slide in slides:
                i = slide["index"]
                script = slide["script"]
                dur = durations.get(i, 5.0)

                if not script or not script.strip():
                    continue

                paragraphs = re.split(r'\n+', script.strip())
                para_count = len([p for p in paragraphs if p.strip()])
                if para_count == 0:
                    continue

                avg_para_dur = dur / para_count

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    chunks = split_long_text(para)
                    if not chunks:
                        continue
                    chunk_dur = avg_para_dur / len(chunks)
                    for chunk in chunks:
                        start = current_time
                        end = current_time + chunk_dur
                        current_time = end
                        f.write(f"{srt_index}\n")
                        f.write(f"{time_str(start)} --> {time_str(end)}\n")
                        f.write(f"{chunk}\n\n")
                        srt_index += 1

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
                f.write(f"file 'audio/page_{i}.m4a'\n")

        ffmpeg = self._find_ffmpeg()
        full_audio = temp_dir / "full_audio.m4a"
        subprocess.run([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:a", "aac", "-b:a", "192k",
            str(full_audio)
        ], check=True, capture_output=True)

        # 生成各页视频片段
        segments_list = temp_dir / "segments.txt"
        with open(segments_list, "w") as f:
            for slide in slides:
                i = slide["index"]
                slide_img = temp_dir / "slides" / f"slide-{i}.png"
                audio = temp_dir / "audio" / f"page_{i}.m4a"
                dur = durations.get(i, 5.0)
                seg = temp_dir / f"seg_{i}.mp4"

                if slide_img.exists():
                    subprocess.run([
                        ffmpeg, "-y",
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
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(segments_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-movflags", "+faststart",
            str(preview)
        ], check=True, capture_output=True)

        # 烧录字幕
        subtitle_path = output_dir / "05-subtitles.srt"
        video_path = output_dir / "07-video.mp4"
        subprocess.run([
            ffmpeg, "-y",
            "-i", str(preview),
            "-i", str(full_audio),
            "-vf", f"subtitles='{subtitle_path}':force_style='FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Bold=1'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(video_path)
        ], check=True, capture_output=True)

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
