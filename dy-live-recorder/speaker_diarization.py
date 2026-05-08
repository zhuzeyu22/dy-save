"""
Speaker Diarization Module

使用 pyannote.audio 进行说话者识别，支持配置最少/最多说话人数，
输出每个音频片段的说话者标签，并为每个说话者分配稳定的唯一标识符。
"""

import os
import logging
from typing import List, Dict, Optional, Union
from pathlib import Path
from collections import defaultdict
import torch

from pyannote.audio import Pipeline
from pyannote.core import Segment, Annotation

logger = logging.getLogger(__name__)


class SpeakerDiarization:
    """
    说话者识别类，使用 pyannote.audio 进行声纹识别
    """

    def __init__(self, config: dict):
        """
        初始化说话者识别器

        Args:
            config: 配置字典，包含以下键:
                - model_name: 模型名称，默认 "pyannote/speaker-diarization-3.1"
                - min_speakers: 最少说话人数，默认 1
                - max_speakers: 最多说话人数，默认 10
                - cache_dir: 模型缓存目录，默认 ~/.cache/huggingface
                - hf_token: HuggingFace 访问令牌
        """
        self.config = config
        self.model_name = config.get("model_name", "pyannote/speaker-diarization-3.1")
        self.min_speakers = config.get("min_speakers", 1)
        self.max_speakers = config.get("max_speakers", 10)
        self.cache_dir = config.get("cache_dir", os.path.expanduser("~/.cache/huggingface"))
        self.hf_token = config.get("hf_token", os.getenv("HF_TOKEN"))

        self.pipeline = None
        self._init_cache_dir()
        self._init_pipeline()

    def _init_cache_dir(self) -> None:
        """创建模型缓存目录"""
        cache_path = Path(self.cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"模型缓存目录: {self.cache_dir}")

    def _init_pipeline(self) -> None:
        """初始化 pyannote 说话者识别流水线"""
        if not self.hf_token:
            logger.warning(
                "未提供 HuggingFace 访问令牌 (HF_TOKEN)，"
                "请设置环境变量或在配置中指定 hf_token"
            )
            logger.warning(
                "访问 https://huggingface.co/pyannote/speaker-diarization"
                " 获取访问令牌并同意用户协议"
            )
            return

        try:
            logger.info(f"正在加载说话者识别模型: {self.model_name}")
            logger.info(f"配置参数: min_speakers={self.min_speakers}, max_speakers={self.max_speakers}")

            self.pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=self.hf_token
            )

            if torch.cuda.is_available():
                self.pipeline.to(torch.device("cuda"))
                logger.info("模型已加载到 GPU")
            else:
                logger.info("模型已加载到 CPU")

            logger.info("说话者识别模型初始化成功")

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def _check_pipeline(self) -> None:
        """检查流水线是否已初始化"""
        if self.pipeline is None:
            raise RuntimeError(
                "说话者识别流水线未初始化。"
                "请确保提供了有效的 HuggingFace 访问令牌 (HF_TOKEN)。"
                "访问 https://huggingface.co/pyannote/speaker-diarization 获取令牌。"
            )

    def _normalize_speaker_labels(self, annotation: Annotation) -> Annotation:
        """
        标准化说话者标签，将原始标签映射为 SPEAKER_00, SPEAKER_01 等格式

        Args:
            annotation: pyannote 的 Annotation 对象

        Returns:
            标准化后的 Annotation 对象
        """
        speaker_mapping = {}
        sorted_speakers = sorted(annotation.labels())

        for idx, original_label in enumerate(sorted_speakers):
            new_label = f"SPEAKER_{idx:02d}"
            speaker_mapping[original_label] = new_label

        normalized = Annotation()
        for segment, track, label in annotation.itertracks(yield_label=True):
            normalized[segment, track] = speaker_mapping.get(label, label)

        return normalized

    def identify(self, audio_path: str) -> Dict:
        """
        识别单个音频文件中的说话者

        Args:
            audio_path: 音频文件路径

        Returns:
            包含 segments 和 speakers 的字典:
            {
                "segments": [
                    {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00", "confidence": 0.95},
                    ...
                ],
                "speakers": ["SPEAKER_00", "SPEAKER_01", ...]
            }
        """
        self._check_pipeline()

        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info(f"开始处理音频文件: {audio_path}")

        try:
            diarization = self.pipeline(
                audio_path,
                min_speakers=self.min_speakers,
                max_speakers=self.max_speakers
            )

            segments = []
            seen_speakers = set()

            for segment in diarization.itertracks(yield_label=True):
                turn, _, speaker = segment
                start = round(turn.start, 2)
                end = round(turn.end, 2)

                confidence = 1.0

                segment_info = {
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "confidence": confidence
                }
                segments.append(segment_info)
                seen_speakers.add(speaker)

                logger.debug(
                    f"  片段: [{start:.2f}s - {end:.2f}s] "
                    f"说话者: {speaker} (置信度: {confidence:.2f})"
                )

            sorted_speakers = sorted(list(seen_speakers))
            speaker_mapping = {sp: f"SPEAKER_{idx:02d}" for idx, sp in enumerate(sorted_speakers)}

            for seg in segments:
                seg["speaker"] = speaker_mapping.get(seg["speaker"], seg["speaker"])

            result = {
                "segments": segments,
                "speakers": sorted(set(seg["speaker"] for seg in segments))
            }

            logger.info(
                f"处理完成: 检测到 {len(result['speakers'])} 个说话者, "
                f"{len(segments)} 个音频片段"
            )

            return result

        except Exception as e:
            logger.error(f"处理音频文件失败: {e}")
            raise

    def identify_batch(self, audio_files: List[str]) -> List[Dict]:
        """
        批量识别多个音频文件中的说话者

        Args:
            audio_files: 音频文件路径列表

        Returns:
            每个音频文件的识别结果列表
        """
        results = []

        for audio_path in audio_files:
            try:
                result = self.identify(audio_path)
                result["audio_path"] = audio_path
                results.append(result)
            except Exception as e:
                logger.error(f"处理 {audio_path} 失败: {e}")
                results.append({
                    "audio_path": audio_path,
                    "segments": [],
                    "speakers": [],
                    "error": str(e)
                })

        return results

    def identify_with_merged_speakers(
        self,
        audio_files: List[str],
        speaker_mapping: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        合并多个音频文件的说话者识别结果，统一分配说话者ID

        Args:
            audio_files: 音频文件路径列表
            speaker_mapping: 可选的说话者映射字典，用于跨音频文件匹配说话者

        Returns:
            {
                "results": [...],  # 每个文件的识别结果
                "global_speaker_mapping": {...},  # 全局说话者映射
                "total_speakers": int,  # 总说话人数
                "total_segments": int   # 总片段数
            }
        """
        if speaker_mapping is None:
            speaker_mapping = {}

        global_speaker_counter = len(speaker_mapping)
        results = []

        for audio_path in audio_files:
            try:
                result = self.identify(audio_path)
                file_speakers = set(result["speakers"])

                for speaker in file_speakers:
                    if speaker not in speaker_mapping:
                        new_id = f"SPEAKER_{global_speaker_counter:02d}"
                        speaker_mapping[speaker] = new_id
                        global_speaker_counter += 1
                        logger.info(f"新说话者 {speaker} -> {new_id}")

                for segment in result["segments"]:
                    segment["speaker"] = speaker_mapping.get(
                        segment["speaker"], segment["speaker"]
                    )
                result["speakers"] = sorted(
                    set(speaker_mapping.get(sp, sp) for sp in result["speakers"])
                )

                result["audio_path"] = audio_path
                results.append(result)

            except Exception as e:
                logger.error(f"处理 {audio_path} 失败: {e}")
                results.append({
                    "audio_path": audio_path,
                    "segments": [],
                    "speakers": [],
                    "error": str(e)
                })

        total_segments = sum(len(r.get("segments", [])) for r in results)

        return {
            "results": results,
            "global_speaker_mapping": speaker_mapping,
            "total_speakers": global_speaker_counter,
            "total_segments": total_segments
        }

    @staticmethod
    def extract_audio_segments(
        segments: List[Dict],
        speaker: Optional[str] = None
    ) -> List[Dict]:
        """
        从识别结果中提取特定说话者的音频片段

        Args:
            segments: 识别结果中的 segments 列表
            speaker: 可选的说话者标签过滤

        Returns:
            过滤后的片段列表
        """
        if speaker is None:
            return segments
        return [seg for seg in segments if seg.get("speaker") == speaker]

    @staticmethod
    def merge_consecutive_segments(segments: List[Dict]) -> List[Dict]:
        """
        合并连续的相同说话者片段

        Args:
            segments: 识别结果中的 segments 列表

        Returns:
            合并后的片段列表
        """
        if not segments:
            return []

        sorted_segments = sorted(segments, key=lambda x: x["start"])
        merged = []

        current = dict(sorted_segments[0])

        for seg in sorted_segments[1:]:
            if (seg["speaker"] == current["speaker"] and
                    abs(seg["start"] - current["end"]) < 0.1):
                current["end"] = seg["end"]
                current["confidence"] = (
                    current.get("confidence", 1.0) + seg.get("confidence", 1.0)
                ) / 2
            else:
                merged.append(current)
                current = dict(seg)

        merged.append(current)
        return merged


def load_config_from_yaml(config_path: str) -> dict:
    """
    从 YAML 文件加载说话者识别配置

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("diarization", {})


if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="说话者识别工具")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出 JSON 文件路径 (可选)"
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="合并连续的相同说话者片段"
    )

    args = parser.parse_args()

    config = load_config_from_yaml(args.config)
    config["hf_token"] = os.getenv("HF_TOKEN")

    diarization = SpeakerDiarization(config)

    result = diarization.identify(args.audio_file)

    if args.merge:
        result["segments"] = SpeakerDiarization.merge_consecutive_segments(
            result["segments"]
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {args.output}")
