#!/usr/bin/env python3
"""
抖音直播录音系统 - 主程序

功能：
- 24小时监控抖音主播"智慧的大聪明"的直播状态
- 直播时自动录制音频
- 直播结束后进行语音转文本
- 根据音色区分不同说话者
- 自动同步到Obsidian笔记库
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import yaml

from live_monitor import LiveMonitor
from audio_recorder import AudioRecorder
from whisper_transcriber import WhisperTranscriber
from speaker_diarization import SpeakerDiarization
from transcription_merger import TranscriptionMerger
from obsidian_client import ObsidianClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DouyinLiveRecorder:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self._setup_logging()

        self.recorder: Optional[AudioRecorder] = None
        self.transcriber: Optional[WhisperTranscriber] = None
        self.diarization: Optional[SpeakerDiarization] = None
        self.obsidian: Optional[ObsidianClient] = None
        self.monitor: Optional[LiveMonitor] = None

        self._is_running = False
        self._current_recording_start: Optional[datetime] = None
        self._pending_processing = []
        self._processing_thread: Optional[threading.Thread] = None

        self._setup_signal_handlers()

    def _load_config(self, config_path: str) -> dict:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    def _setup_logging(self):
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO"))
        log_file = log_config.get("file", "./dy_monitor.log")

        logging.getLogger().setLevel(log_level)

        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(log_level)
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logging.getLogger().addHandler(file_handler)

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logger.info(f"收到退出信号 {signum}，正在优雅退出...")
        self.stop()

    def initialize(self):
        logger.info("=" * 60)
        logger.info("抖音直播录音系统初始化中...")
        logger.info("=" * 60)

        try:
            self._init_audio_recorder()
            self._init_transcriber()
            self._init_diarization()
            self._init_obsidian()
            self._init_monitor()

            logger.info("=" * 60)
            logger.info("所有组件初始化完成！")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def _init_audio_recorder(self):
        logger.info("初始化音频录制器...")
        self.recorder = AudioRecorder(self.config)
        logger.info("音频录制器初始化完成")

    def _init_transcriber(self):
        logger.info("初始化语音转文本模型...")
        whisper_config = self.config.get("whisper", {})
        if not whisper_config.get("model_size"):
            logger.warning("Whisper配置为空，跳过初始化")
            return

        try:
            self.transcriber = WhisperTranscriber(self.config)
            logger.info(f"语音转文本模型初始化完成: {self.transcriber.get_model_info()}")
        except Exception as e:
            logger.warning(f"语音转文本初始化失败: {e}")
            self.transcriber = None

    def _init_diarization(self):
        logger.info("初始化说话者识别模型...")
        diar_config = self.config.get("diarization", {})
        if not diar_config.get("model_name"):
            logger.warning("说话者识别配置为空，跳过初始化")
            return

        try:
            diar_config["hf_token"] = os.getenv("HF_TOKEN", diar_config.get("hf_token"))
            self.diarization = SpeakerDiarization(diar_config)
            logger.info("说话者识别模型初始化完成")
        except Exception as e:
            logger.warning(f"说话者识别初始化失败: {e}")
            self.diarization = None

    def _init_obsidian(self):
        obsidian_config = self.config.get("obsidian", {})
        if not obsidian_config.get("enabled"):
            logger.info("Obsidian同步未启用")
            return

        try:
            self.obsidian = ObsidianClient(self.config)
            logger.info(f"Obsidian客户端初始化完成: {obsidian_config.get('vault_path')}")
        except Exception as e:
            logger.warning(f"Obsidian初始化失败: {e}")
            self.obsidian = None

    def _init_monitor(self):
        logger.info("初始化直播监控器...")

        def on_live_start(status: dict):
            self._handle_live_start(status)

        def on_live_end():
            self._handle_live_end()

        self.monitor = LiveMonitor(self.config, on_live_start, on_live_end)
        logger.info("直播监控器初始化完成")

    def _handle_live_start(self, status: dict):
        logger.info("=" * 60)
        logger.info("🎬 检测到直播开始！")
        logger.info(f"   房间ID: {status.get('room_id')}")
        logger.info(f"   标题: {status.get('title', 'N/A')}")
        logger.info(f"   观众数: {status.get('viewer_count', 0)}")
        logger.info("=" * 60)

        stream_url = status.get("stream_url")
        if not stream_url:
            logger.error("无法获取直播流地址")
            return

        self._current_recording_start = datetime.now()
        date_str = self._current_recording_start.strftime("%Y%m%d_%H%M%S")
        output_prefix = f"live_{date_str}"

        success = self.recorder.start_recording(stream_url, output_prefix)
        if success:
            logger.info(f"开始录制: {output_prefix}")
        else:
            logger.error("录制启动失败")

    def _handle_live_end(self):
        logger.info("=" * 60)
        logger.info("📴 直播已结束")
        logger.info("=" * 60)

        if self.recorder and self.recorder.is_recording():
            chunks = self.recorder.stop_recording()

            if chunks:
                recording_info = {
                    "chunks": chunks,
                    "start_time": self._current_recording_start,
                    "end_time": datetime.now()
                }
                self._pending_processing.append(recording_info)
                logger.info(f"录制完成，等待处理: {len(chunks)} 个分片")

                self._start_processing_thread()

        self._current_recording_start = None

    def _start_processing_thread(self):
        if self._processing_thread and self._processing_thread.is_alive():
            logger.info("处理线程已在运行中")
            return

        self._processing_thread = threading.Thread(target=self._process_recordings, daemon=True)
        self._processing_thread.start()

    def _process_recordings(self):
        while self._pending_processing:
            recording = self._pending_processing.pop(0)
            self._process_single_recording(recording)

    def _process_single_recording(self, recording: dict):
        chunks = recording.get("chunks", [])
        start_time = recording.get("start_time")
        end_time = recording.get("end_time")

        if not chunks:
            return

        logger.info("=" * 60)
        logger.info("开始处理录音...")
        logger.info("=" * 60)

        output_dir = Path(self.config.get("record", {}).get("output_dir", "./recordings"))
        date_prefix = start_time.strftime("%Y%m%d_%H%M%S")
        merged_file = output_dir / f"{date_prefix}_merged.wav"

        merged_path = self.recorder.merge_chunks(str(merged_file))
        if not merged_path:
            logger.error("合并音频失败")
            return

        transcription_result = self._transcribe_audio(merged_path)
        if not transcription_result or not transcription_result.get("segments"):
            logger.error("语音转文本失败或结果为空")
            return

        diarization_result = self._identify_speakers(merged_path)
        if not diarization_result:
            diarization_result = {"segments": [], "speakers": []}

        merged_result = self._merge_results(transcription_result, diarization_result)

        self._save_to_obsidian(
            merged_result,
            merged_path,
            start_time,
            end_time
        )

        self._export_results(merged_result, merged_path)

        logger.info("=" * 60)
        logger.info("处理完成！")
        logger.info("=" * 60)

    def _transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        if not self.transcriber:
            logger.warning("语音转文本模型未初始化")
            return None

        try:
            logger.info(f"开始语音转文本: {audio_path}")
            result = self.transcriber.transcribe(audio_path)
            logger.info(f"转录完成: {len(result.get('segments', []))} 个片段")
            return result
        except Exception as e:
            logger.error(f"语音转文本失败: {e}")
            return None

    def _identify_speakers(self, audio_path: str) -> Optional[Dict]:
        if not self.diarization:
            logger.warning("说话者识别模型未初始化")
            return None

        try:
            logger.info(f"开始说话者识别: {audio_path}")
            result = self.diarization.identify(audio_path)
            logger.info(f"说话者识别完成: {len(result.get('speakers', []))} 个说话者")
            return result
        except Exception as e:
            logger.error(f"说话者识别失败: {e}")
            return None

    def _merge_results(self, transcription: Dict, diarization: Dict) -> Dict:
        merger = TranscriptionMerger(overlap_threshold=0.5)

        speaker_labels = {}
        speakers = diarization.get("speakers", [])
        if len(speakers) >= 2:
            speaker_labels = {
                speakers[0]: "主播",
                speakers[1]: "观众"
            }

        if speaker_labels:
            result = merger.merge_with_custom_labels(transcription, diarization, speaker_labels)
        else:
            result = merger.merge(transcription, diarization)

        return result

    def _save_to_obsidian(
        self,
        merged_result: Dict,
        audio_path: str,
        start_time: datetime,
        end_time: datetime
    ):
        if not self.obsidian:
            logger.info("Obsidian同步未启用，跳过")
            return

        try:
            date_str = start_time.strftime("%Y-%m-%d")
            start_time_str = start_time.strftime("%H:%M")
            end_time_str = end_time.strftime("%H:%M")

            content = {
                "start_time": start_time_str,
                "end_time": end_time_str,
                "anchor_name": self.config.get("douyin", {}).get("username", "智慧的大聪明"),
                "audio_file": str(audio_path),
                "transcription": merged_result.get("segments", []),
                "speakers": merged_result.get("speakers", {}),
                "duration": merged_result.get("duration", 0)
            }

            note_path = self.obsidian.save_daily_note(date_str, content)
            logger.info(f"已同步到Obsidian: {note_path}")

        except Exception as e:
            logger.error(f"Obsidian同步失败: {e}")

    def _export_results(self, merged_result: Dict, audio_path: str):
        output_dir = Path(self.config.get("obsidian", {}).get("output_dir", "./output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_name = Path(audio_path).stem
        json_path = output_dir / f"{audio_name}.json"
        txt_path = output_dir / f"{audio_name}.txt"
        srt_path = output_dir / f"{audio_name}.srt"

        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(merged_result, f, indent=2, ensure_ascii=False)
            logger.info(f"JSON结果已保存: {json_path}")

            TranscriptionMerger.export_to_text(merged_result, str(txt_path))
            TranscriptionMerger.export_to_srt(merged_result, str(srt_path))

        except Exception as e:
            logger.error(f"导出结果失败: {e}")

    def start(self):
        logger.info("=" * 60)
        logger.info("启动抖音直播录音系统")
        logger.info(f"监控主播: {self.config.get('douyin', {}).get('username', '智慧的大聪明')}")
        logger.info("按 Ctrl+C 优雅退出")
        logger.info("=" * 60)

        self._is_running = True

        try:
            self.monitor.start_monitoring()
        except KeyboardInterrupt:
            logger.info("收到键盘中断")
        finally:
            self.stop()

    def stop(self):
        logger.info("正在停止系统...")

        self._is_running = False

        if self.monitor:
            self.monitor.stop_monitoring()

        if self.recorder and self.recorder.is_recording():
            logger.info("正在停止当前录制...")
            chunks = self.recorder.stop_recording()
            if chunks and self._current_recording_start:
                recording_info = {
                    "chunks": chunks,
                    "start_time": self._current_recording_start,
                    "end_time": datetime.now()
                }
                self._pending_processing.append(recording_info)

        if self._pending_processing:
            logger.info(f"还有 {len(self._pending_processing)} 个录音待处理")
            self._process_recordings()

        logger.info("系统已停止")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="抖音直播录音系统")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    args = parser.parse_args()

    try:
        app = DouyinLiveRecorder(args.config)

        if not app.initialize():
            logger.error("初始化失败，程序退出")
            sys.exit(1)

        app.start()

    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
