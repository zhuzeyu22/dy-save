import os
import gc
import logging
from typing import List, Dict, Optional

try:
    from faster_whisper import WhisperModel
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    def __init__(self, config: dict):
        self.config = config.get("whisper", {})
        self.model_size = self.config.get("model_size", "base")
        self.device = self.config.get("device", "auto")
        self.language = self.config.get("language", "zh")
        self.batch_size = self.config.get("batch_size", 16)
        self.segment_length = self.config.get("segment_length", 30)
        self.model = None
        self._load_model()

    def _load_model(self):
        if not TORCH_AVAILABLE:
            logger.warning("faster-whisper未安装，跳过模型加载")
            return
            
        try:
            compute_type = "float16" if self.device == "cuda" else "int8"
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type,
            )
            logger.info(f"Whisper模型加载成功: {self.model_size}, 设备: {self.device}")
        except Exception as e:
            logger.error(f"加载Whisper模型失败: {e}")
            raise

    def transcribe(self, audio_path: str) -> Dict:
        if not os.path.exists(audio_path):
            logger.error(f"音频文件不存在: {audio_path}")
            return {"segments": [], "language": self.language, "duration": 0.0, "error": "文件不存在"}

        try:
            duration = self._get_audio_duration(audio_path)
            logger.info(f"开始转录: {audio_path}, 时长: {duration:.2f}秒")

            if duration > self.segment_length * 60:
                segments = self._transcribe_long_audio(audio_path)
            else:
                segments = self._transcribe_segment(audio_path)

            result = {
                "segments": segments,
                "language": self.language,
                "duration": duration,
            }
            logger.info(f"转录完成: {audio_path}, 片段数: {len(segments)}")
            return result

        except Exception as e:
            logger.error(f"转录失败: {audio_path}, 错误: {e}")
            return {"segments": [], "language": self.language, "duration": 0.0, "error": str(e)}

    def _transcribe_segment(self, audio_path: str) -> List[Dict]:
        segments, info = self.model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        results = []
        for segment in segments:
            results.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })

        return results

    def _transcribe_long_audio(self, audio_path: str) -> List[Dict]:
        segments, info = self.model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            segment_length=self.segment_length,
        )

        results = []
        for segment in segments:
            results.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip()
            })
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        return results

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception:
            try:
                import wave
                with wave.open(audio_path, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    return frames / float(rate)
            except Exception:
                return 0.0

    def transcribe_batch(self, audio_files: List[str]) -> List[Dict]:
        results = []
        for audio_file in audio_files:
            logger.info(f"批量处理: {audio_file} ({audio_files.index(audio_file) + 1}/{len(audio_files)})")
            result = self.transcribe(audio_file)
            results.append(result)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        return results

    def get_model_info(self) -> Dict:
        return {
            "model_size": self.model_size,
            "device": self.device,
            "language": self.language,
            "batch_size": self.batch_size,
            "segment_length": self.segment_length,
        }

    def __del__(self):
        if self.model is not None:
            del self.model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
