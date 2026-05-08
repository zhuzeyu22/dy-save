import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from jinja2 import Template, TemplateNotFound


class ObsidianClient:
    def __init__(self, config: dict):
        self.config = config.get("obsidian", {})
        self.enabled = self.config.get("enabled", False)
        self.vault_path = self.config.get("vault_path", "")
        self.daily_notes_folder = self.config.get("daily_notes_folder", "Daily")
        self.output_dir = self.config.get("output_dir", "./output")
        self.template_dir = self._get_template_dir()

    def _get_template_dir(self) -> Path:
        script_dir = Path(__file__).parent
        template_dir = script_dir / "obsidian_templates"
        if template_dir.exists():
            return template_dir
        return script_dir / "templates"

    def ensure_folder_exists(self, folder_path: str) -> None:
        path = Path(folder_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    def get_template(self, template_name: str) -> str:
        template_path = self.template_dir / template_name
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        default_template = self._get_default_template()
        template_path.write_text(default_template, encoding="utf-8")
        return default_template

    def _get_default_template(self) -> str:
        return """---
直播时间: {{start_time}} - {{end_time}}
主播: {{anchor_name}}
录音文件: [[{{audio_file}}]]

## 说话者记录

{% for speaker in speakers %}
### {{ speaker.name }} ({{ speaker.utterance_count }} 次发言)

{% for segment in speaker.segments %}
**{{ segment.start_time }} - {{ segment.end_time }}**
> {{ segment.text }}

{% endfor %}
{% endfor %}

## 元数据

- **录制日期**: {{date}}
- **录音时长**: {{duration}}
- **说话者数量**: {{speaker_count}}
- **处理时间**: {{processed_at}}
"""

    def _get_daily_note_path(self, date: str) -> Path:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%m")
        day = date_obj.strftime("%d")
        folder_path = Path(self.vault_path) / self.daily_notes_folder / year / month
        self.ensure_folder_exists(str(folder_path))
        return folder_path / f"{day}.md"

    def _format_duration(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _process_speakers(self, speakers: List[Dict], transcription: List[Dict]) -> List[Dict]:
        if speakers and len(speakers) > 0 and "segments" in speakers[0]:
            return speakers

        processed = {}
        for segment in transcription:
            speaker = segment.get("speaker", "未知说话者")
            if speaker not in processed:
                processed[speaker] = {
                    "name": speaker,
                    "utterance_count": 0,
                    "segments": []
                }
            processed[speaker]["utterance_count"] += 1
            processed[speaker]["segments"].append({
                "start_time": self._format_timestamp(segment.get("start", 0)),
                "end_time": self._format_timestamp(segment.get("end", 0)),
                "text": segment.get("text", "").strip()
            })

        return list(processed.values())

    def _render_template(self, template_content: str, context: Dict) -> str:
        template = Template(template_content)
        return template.render(context)

    def save_daily_note(self, date: str, content: Dict) -> str:
        if not self.enabled:
            raise RuntimeError("Obsidian sync is not enabled in config")

        if not self.vault_path:
            raise ValueError("vault_path is not configured")

        speakers = content.get("speakers", [])
        transcription = content.get("transcription", [])
        processed_speakers = self._process_speakers(speakers, transcription)

        audio_file = content.get("audio_file", "")
        audio_basename = os.path.basename(audio_file) if audio_file else ""
        audio_wiki_link = f"recordings/{audio_basename}"

        duration = content.get("duration", 0)
        duration_formatted = self._format_duration(duration)

        processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "date": date,
            "start_time": content.get("start_time", ""),
            "end_time": content.get("end_time", ""),
            "anchor_name": content.get("anchor_name", ""),
            "audio_file": audio_wiki_link,
            "speakers": processed_speakers,
            "duration": duration_formatted,
            "speaker_count": len(processed_speakers),
            "processed_at": processed_at
        }

        template_content = self.get_template("daily_note.md")
        rendered_content = self._render_template(template_content, context)

        note_path = self._get_daily_note_path(date)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(rendered_content)

        return str(note_path)

    def create_daily_note_from_template(self, date: str, content: Dict, template_name: str = "daily_note.md") -> str:
        if not self.enabled:
            raise RuntimeError("Obsidian sync is not enabled in config")

        if not self.vault_path:
            raise ValueError("vault_path is not configured")

        speakers = content.get("speakers", [])
        transcription = content.get("transcription", [])
        processed_speakers = self._process_speakers(speakers, transcription)

        audio_file = content.get("audio_file", "")
        audio_basename = os.path.basename(audio_file) if audio_file else ""
        audio_wiki_link = f"recordings/{audio_basename}"

        duration = content.get("duration", 0)
        duration_formatted = self._format_duration(duration)

        processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "date": date,
            "start_time": content.get("start_time", ""),
            "end_time": content.get("end_time", ""),
            "anchor_name": content.get("anchor_name", ""),
            "audio_file": audio_wiki_link,
            "speakers": processed_speakers,
            "duration": duration_formatted,
            "speaker_count": len(processed_speakers),
            "processed_at": processed_at
        }

        template_content = self.get_template(template_name)
        rendered_content = self._render_template(template_content, context)

        note_path = self._get_daily_note_path(date)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(rendered_content)

        return str(note_path)
