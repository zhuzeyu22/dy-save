# Checklist - 抖音直播录音系统

## 环境配置
- [x] config.yaml 文件存在且包含所有必需配置项
- [ ] 所有Python依赖已安装（ffmpeg, faster-whisper, pyannote-audio等）
- [ ] Obsidian Vault路径已配置且可访问

## 抖音监控
- [x] 能成功获取主播"智慧的大聪明"的房间信息
- [x] 直播状态检测逻辑正确（开播/未开播）
- [x] 监控循环能正常切换待机/录制状态

## 音频录制
- [x] 能获取有效的直播流地址
- [x] ffmpeg录制进程正常运行
- [x] 分片文件按30分钟自动分割
- [x] 录制结束能正确合并分片
- [x] 断线后能自动重连继续录制

## 语音识别
- [ ] Whisper模型加载成功
- [x] 转录输出包含时间戳
- [ ] 转录结果准确度符合预期
- [x] 批量处理大文件无内存溢出

## 声纹识别
- [ ] pyannote模型加载成功
- [x] 能区分至少2个说话者
- [x] 说话者标签与音频片段正确对应
- [x] 说话者ID在多段音频中保持一致

## Obsidian同步
- [x] 能成功连接Obsidian Vault
- [x] 每日笔记按日期正确创建
- [x] 笔记包含直播时间段信息
- [x] 各说话者发言记录格式正确
- [x] 原始音频文件链接有效

## 主程序
- [x] 程序能正常启动
- [x] 日志输出清晰可读
- [x] 能优雅处理Ctrl+C退出
- [x] 异常情况下资源正确释放
- [ ] 24小时连续运行稳定

## 功能验证
- [ ] 单人直播场景正常工作
- [x] 多人连麦场景说话者区分正确
- [x] 直播结束后自动触发转录和归档

---

## 已完成的功能模块

### 代码文件清单
- `dy_monitor.py` - 主程序入口
- `douyin_api.py` - 抖音API客户端
- `live_monitor.py` - 直播监控模块
- `audio_recorder.py` - 音频录制模块
- `whisper_transcriber.py` - 语音识别模块
- `speaker_diarization.py` - 声纹识别模块
- `transcription_merger.py` - 结果整合模块
- `obsidian_client.py` - Obsidian客户端
- `config.yaml` - 配置文件
- `requirements.txt` - 依赖清单
- `start.sh` - 启动脚本
- `obsidian_templates/daily_note.md` - 笔记模板
