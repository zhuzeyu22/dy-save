"""
Transcription Merger Module

将 Whisper 转录结果与 pyannote 说话者识别结果合并，
基于时间戳对齐，为每个转录片段分配说话者标签。
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class TranscriptionMerger:
    """
    说话者标注与语音转录整合器

    将 Whisper 的转录结果与 pyannote 的声纹识别结果合并，
    输出统一的结构化数据。
    """

    def __init__(self, overlap_threshold: float = 0.5):
        """
        初始化合并器

        Args:
            overlap_threshold: 重叠阈值，默认 0.5 (50%)，
                              表示转录片段与说话者片段重叠超过50%时分配该说话者
        """
        self.overlap_threshold = overlap_threshold
        logger.info(f"TranscriptionMerger 初始化完成，重叠阈值: {overlap_threshold * 100}%")

    def merge(self, transcription_result: Dict, diarization_result: Dict) -> Dict:
        """
        合并转录结果与说话者识别结果

        Args:
            transcription_result: Whisper 输出结果
                {
                    "segments": [{"start": float, "end": float, "text": str}, ...],
                    "language": str,
                    "duration": float
                }
            diarization_result: pyannote 输出结果
                {
                    "segments": [{"start": float, "end": float, "speaker": str}, ...],
                    "speakers": [str, ...]
                }

        Returns:
            合并后的结果
            {
                "segments": [{"start": float, "end": float, "text": str, "speaker": str}, ...],
                "speakers": {"speaker_name": {"segments": int, "total_duration": float}, ...},
                "language": str,
                "duration": float
            }
        """
        transcription_segments = transcription_result.get("segments", [])
        diarization_segments = diarization_result.get("segments", [])

        logger.info(f"开始合并: 转录片段数={len(transcription_segments)}, "
                    f"说话者片段数={len(diarization_segments)}")

        if not transcription_segments:
            logger.warning("转录结果为空")
            return self._create_empty_result(transcription_result)

        if not diarization_segments:
            logger.warning("说话者识别结果为空，所有片段标记为'未知'")
            return self._merge_with_unknown(transcription_result)

        merged_segments = []
        diarization_segments_sorted = sorted(diarization_segments, key=lambda x: x["start"])

        for trans_seg in transcription_segments:
            speaker = self._find_speaker_for_segment(
                trans_seg, diarization_segments_sorted
            )
            merged_seg = {
                "start": trans_seg["start"],
                "end": trans_seg["end"],
                "text": trans_seg.get("text", ""),
                "speaker": speaker
            }
            merged_segments.append(merged_seg)

            logger.debug(f"  片段 [{trans_seg['start']:.2f}s - {trans_seg['end']:.2f}s] "
                         f"-> 说话者: {speaker}")

        speakers_stats = self._calculate_speaker_stats(merged_segments)
        self._log_merge_summary(merged_segments, speakers_stats)

        result = {
            "segments": merged_segments,
            "speakers": speakers_stats,
            "language": transcription_result.get("language", "unknown"),
            "duration": transcription_result.get("duration", 0.0)
        }

        logger.info(f"合并完成: 共 {len(merged_segments)} 个片段, {len(speakers_stats)} 个说话者")
        return result

    def _find_speaker_for_segment(
        self,
        trans_segment: Dict,
        diarization_segments: List[Dict]
    ) -> str:
        """
        为转录片段找到对应的说话者

        查找与该转录片段有最大重叠的说话者片段，
        如果重叠比例超过阈值，则分配该说话者。

        Args:
            trans_segment: 转录片段 {"start": float, "end": float, ...}
            diarization_segments: 排序后的说话者片段列表

        Returns:
            说话者标签，未找到匹配时返回 "未知"
        """
        trans_start = trans_segment["start"]
        trans_end = trans_segment["end"]
        trans_duration = trans_end - trans_start

        if trans_duration <= 0:
            return "未知"

        best_overlap = 0.0
        best_speaker = "未知"

        for diar_seg in diarization_segments:
            diar_start = diar_seg["start"]
            diar_end = diar_seg["end"]
            diar_speaker = diar_seg.get("speaker", "未知")

            overlap_start = max(trans_start, diar_start)
            overlap_end = min(trans_end, diar_end)
            overlap_duration = max(0, overlap_end - overlap_start)

            if overlap_duration > best_overlap:
                best_overlap = overlap_duration
                best_speaker = diar_speaker

        overlap_ratio = best_overlap / trans_duration

        if overlap_ratio >= self.overlap_threshold:
            logger.debug(f"    重叠比例: {overlap_ratio:.2%}, 说话者: {best_speaker}")
            return best_speaker
        else:
            logger.debug(f"    重叠比例不足: {overlap_ratio:.2%} < {self.overlap_threshold:.2%}, 标记为'未知'")
            return "未知"

    def _calculate_speaker_stats(self, merged_segments: List[Dict]) -> Dict:
        """
        计算每个说话者的统计数据

        Args:
            merged_segments: 合并后的片段列表

        Returns:
            说话者统计 {"speaker_name": {"segments": int, "total_duration": float}, ...}
        """
        speaker_data = defaultdict(lambda: {"segments": 0, "total_duration": 0.0})

        for seg in merged_segments:
            speaker = seg.get("speaker", "未知")
            duration = seg["end"] - seg["start"]

            speaker_data[speaker]["segments"] += 1
            speaker_data[speaker]["total_duration"] += duration

        stats = {}
        for speaker, data in sorted(speaker_data.items()):
            stats[speaker] = {
                "segments": data["segments"],
                "total_duration": round(data["total_duration"], 2)
            }

        return stats

    def _log_merge_summary(
        self,
        merged_segments: List[Dict],
        speaker_stats: Dict
    ) -> None:
        """
        输出合并摘要日志

        Args:
            merged_segments: 合并后的片段列表
            speaker_stats: 说话者统计
        """
        logger.info("=" * 50)
        logger.info("说话者标注统计:")
        for speaker, stats in speaker_stats.items():
            logger.info(f"  {speaker}: {stats['segments']} 个片段, "
                        f"总时长 {stats['total_duration']:.2f}秒")

        unknown_count = sum(
            1 for seg in merged_segments if seg["speaker"] == "未知"
        )
        if unknown_count > 0:
            logger.warning(f"  未知说话者片段: {unknown_count} 个")
        logger.info("=" * 50)

    def _create_empty_result(self, transcription_result: Dict) -> Dict:
        """
        创建空结果（转录为空时）

        Args:
            transcription_result: 原始转录结果

        Returns:
            空的结果字典
        """
        return {
            "segments": [],
            "speakers": {},
            "language": transcription_result.get("language", "unknown"),
            "duration": transcription_result.get("duration", 0.0)
        }

    def _merge_with_unknown(self, transcription_result: Dict) -> Dict:
        """
        处理说话者识别结果为空的情况

        Args:
            transcription_result: 原始转录结果

        Returns:
            所有片段标记为"未知"的结果
        """
        transcription_segments = transcription_result.get("segments", [])

        merged_segments = [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg.get("text", ""),
                "speaker": "未知"
            }
            for seg in transcription_segments
        ]

        speaker_stats = self._calculate_speaker_stats(merged_segments)

        return {
            "segments": merged_segments,
            "speakers": speaker_stats,
            "language": transcription_result.get("language", "unknown"),
            "duration": transcription_result.get("duration", 0.0)
        }

    def merge_with_custom_labels(
        self,
        transcription_result: Dict,
        diarization_result: Dict,
        speaker_labels: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        使用自定义标签合并结果

        Args:
            transcription_result: Whisper 输出结果
            diarization_result: pyannote 输出结果
            speaker_labels: 自定义说话者标签映射 {"SPEAKER_00": "主播", "SPEAKER_01": "观众", ...}

        Returns:
            合并后的结果，说话者使用自定义标签
        """
        if speaker_labels is None:
            speaker_labels = {}

        result = self.merge(transcription_result, diarization_result)

        for seg in result["segments"]:
            original_speaker = seg["speaker"]
            seg["speaker"] = speaker_labels.get(original_speaker, original_speaker)

        new_speakers = {}
        for original_name, label in speaker_labels.items():
            if original_name in result["speakers"]:
                new_speakers[label] = result["speakers"][original_name]

        result["speakers"] = new_speakers

        return result

    @staticmethod
    def export_to_srt(merged_result: Dict, srt_path: str) -> None:
        """
        导出合并结果为 SRT 字幕格式

        Args:
            merged_result: merge() 返回的结果
            srt_path: 输出 SRT 文件路径
        """
        segments = merged_result.get("segments", [])

        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(segments, start=1):
                start_time = TranscriptionMerger._format_srt_time(seg["start"])
                end_time = TranscriptionMerger._format_srt_time(seg["end"])
                speaker = seg.get("speaker", "未知")

                f.write(f"{idx}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"[{speaker}] {seg.get('text', '')}\n")
                f.write("\n")

        logger.info(f"SRT 字幕已导出: {srt_path}")

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """
        将秒数格式化为 SRT 时间格式 (HH:MM:SS,mmm)

        Args:
            seconds: 秒数

        Returns:
            SRT 时间格式字符串
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def export_to_text(merged_result: Dict, txt_path: str) -> None:
        """
        导出合并结果为纯文本格式

        Args:
            merged_result: merge() 返回的结果
            txt_path: 输出文本文件路径
        """
        segments = merged_result.get("segments", [])

        with open(txt_path, "w", encoding="utf-8") as f:
            for seg in segments:
                speaker = seg.get("speaker", "未知")
                text = seg.get("text", "")
                f.write(f"[{speaker}] {text}\n")

        logger.info(f"文本已导出: {txt_path}")


def load_sample_data() -> Tuple[Dict, Dict]:
    """
    加载示例数据用于测试

    Returns:
        (transcription_result, diarization_result)
    """
    transcription_sample = {
        "segments": [
            {"start": 0.0, "end": 3.5, "text": "大家好，欢迎来到我的直播间"},
            {"start": 3.8, "end": 8.2, "text": "今天我们来聊聊最近的话题"},
            {"start": 8.5, "end": 12.0, "text": "主播说得太有道理了"},
            {"start": 12.3, "end": 18.0, "text": "观众朋友们有什么问题可以提问"},
            {"start": 18.5, "end": 22.0, "text": "感谢这位观众的建议"},
            {"start": 22.5, "end": 28.0, "text": "我们继续聊下一个话题"},
        ],
        "language": "zh",
        "duration": 28.0
    }

    diarization_sample = {
        "segments": [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00", "confidence": 0.95},
            {"start": 5.2, "end": 10.0, "speaker": "SPEAKER_01", "confidence": 0.92},
            {"start": 10.3, "end": 15.0, "speaker": "SPEAKER_00", "confidence": 0.94},
            {"start": 15.2, "end": 20.0, "speaker": "SPEAKER_01", "confidence": 0.91},
            {"start": 20.2, "end": 28.0, "speaker": "SPEAKER_00", "confidence": 0.96},
        ],
        "speakers": ["SPEAKER_00", "SPEAKER_01"]
    }

    return transcription_sample, diarization_sample


if __name__ == "__main__":
    import json
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="转录与说话者识别结果合并工具")
    parser.add_argument(
        "--transcription",
        "-t",
        help="转录结果 JSON 文件路径"
    )
    parser.add_argument(
        "--diarization",
        "-d",
        help="说话者识别结果 JSON 文件路径"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="输出 JSON 文件路径 (可选)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="重叠阈值，默认 0.5 (50%%)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="使用示例数据进行演示"
    )

    args = parser.parse_args()

    merger = TranscriptionMerger(overlap_threshold=args.threshold)

    if args.demo:
        transcription, diarization = load_sample_data()
        print("=" * 50)
        print("示例数据 - 转录结果:")
        print(json.dumps(transcription, indent=2, ensure_ascii=False))
        print("\n示例数据 - 说话者识别结果:")
        print(json.dumps(diarization, indent=2, ensure_ascii=False))
    elif args.transcription and args.diarization:
        with open(args.transcription, "r", encoding="utf-8") as f:
            transcription = json.load(f)
        with open(args.diarization, "r", encoding="utf-8") as f:
            diarization = json.load(f)
    else:
        parser.print_help()
        print("\n使用 --demo 参数运行示例演示")
        exit(0)

    result = merger.merge(transcription, diarization)

    print("\n合并结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {args.output}")
