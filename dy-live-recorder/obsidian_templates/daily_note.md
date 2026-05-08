---
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
