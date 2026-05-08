import os
import sys
import signal
import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum


class RecordingState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


class AudioRecorder:
    """
    抖音直播音频录制器
    支持 FLV/HLS 流录制，WAV格式输出，自动分片
    """

    def __init__(self, config: dict):
        self.logger = logging.getLogger(__name__)
        self.config = config.get("record", {})

        self.sample_rate = self.config.get("sample_rate", 16000)
        self.channels = self.config.get("channels", 1)
        self.format = self.config.get("format", "wav")
        self.chunk_duration = self.config.get("chunk_duration", 1800)
        self.output_dir = Path(self.config.get("output_dir", "./recordings"))
        self.retry_interval = self.config.get("retry_interval", 30)
        self.max_retry = self.config.get("max_retry", 10)

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._state = RecordingState.IDLE
        self._process: Optional[subprocess.Popen] = None
        self._chunks: List[str] = []
        self._current_chunk: Optional[str] = None
        self._chunk_start_time: Optional[datetime] = None
        self._chunk_index = 0
        self._stream_url: Optional[str] = None
        self._output_prefix: Optional[str] = None
        self._session_start_time: Optional[datetime] = None
        self._retry_count = 0
        self._is_merging = False
        self._chunk_lock = threading.Lock()
        self._state_lock = threading.Lock()

        self._chunk_timer: Optional[threading.Timer] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.logger.info(f"收到信号 {signum}，准备优雅退出...")
        self._stop_event.set()
        self.stop_recording()

    def _get_ffmpeg_command(self, stream_url: str, output_path: str) -> List[str]:
        cmd = [
            "ffmpeg",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", stream_url,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-f", self.format,
            "-t", str(self.chunk_duration),
            "-y",
            output_path
        ]
        return cmd

    def _generate_output_path(self, output_prefix: str, part_index: int) -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        start_time_str = self._session_start_time.strftime("%H%M%S") if self._session_start_time else "000000"
        filename = f"{date_str}_{start_time_str}_part{part_index}.wav"
        return str(self.output_dir / f"{output_prefix}_{filename}")

    def _start_ffmpeg_process(self) -> bool:
        if not self._stream_url:
            self.logger.error("流URL未设置")
            return False

        self._chunk_index += 1
        output_path = self._generate_output_path(self._output_prefix, self._chunk_index)
        self._current_chunk = output_path
        self._chunk_start_time = datetime.now()

        cmd = self._get_ffmpeg_command(self._stream_url, output_path)
        self.logger.info(f"启动 ffmpeg: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            return True
        except Exception as e:
            self.logger.error(f"启动 ffmpeg 失败: {e}")
            return False

    def _monitor_process(self):
        while not self._stop_event.is_set():
            with self._state_lock:
                if self._state != RecordingState.RECORDING:
                    break

            if self._process is None:
                break

            return_code = self._process.poll()

            if return_code is not None:
                if return_code == 0:
                    self.logger.info("分片录制完成（正常结束）")
                    self._handle_chunk_complete()
                else:
                    self.logger.warning(f"ffmpeg 进程异常退出，返回码: {return_code}")
                    stderr = self._process.stderr.read().decode('utf-8', errors='ignore') if self._process.stderr else ""
                    self.logger.debug(f"ffmpeg stderr: {stderr[:500]}")
                    self._handle_chunk_complete()

            time.sleep(0.5)

    def _handle_chunk_complete(self):
        with self._chunk_lock:
            if self._current_chunk and os.path.exists(self._current_chunk):
                file_size = os.path.getsize(self._current_chunk)
                if file_size > 0:
                    self._chunks.append(self._current_chunk)
                    self.logger.info(f"保存分片: {self._current_chunk} ({file_size} bytes)")
                else:
                    self.logger.warning(f"分片文件为空，跳过: {self._current_chunk}")
                    try:
                        os.remove(self._current_chunk)
                    except:
                        pass
            self._current_chunk = None

        if self._state == RecordingState.RECORDING and not self._stop_event.is_set():
            self.logger.info("开始下一分片录制...")
            self._start_ffmpeg_process()

    def _scheduled_chunk_rotation(self):
        if self._state == RecordingState.RECORDING and self._process:
            self.logger.info("分片定时器触发，切换分片...")
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                else:
                    self._process.terminate()
            except Exception as e:
                self.logger.warning(f"终止进程时出错: {e}")

    def start_recording(self, stream_url: str, output_prefix: str) -> bool:
        """
        开始录制
        :param stream_url: 直播流地址 (FLV/HLS)
        :param output_prefix: 输出文件前缀
        :return: 是否成功开始录制
        """
        with self._state_lock:
            if self._state == RecordingState.RECORDING:
                self.logger.warning("已经在录制中")
                return False

            self._stream_url = stream_url
            self._output_prefix = output_prefix
            self._session_start_time = datetime.now()
            self._chunk_index = 0
            self._chunks = []
            self._retry_count = 0
            self._stop_event.clear()

            if not self._start_ffmpeg_process():
                self._state = RecordingState.IDLE
                return False

            self._state = RecordingState.RECORDING
            self.logger.info(f"开始录制: {stream_url}")

        self._chunk_timer = threading.Timer(self.chunk_duration, self._scheduled_chunk_rotation)
        self._chunk_timer.daemon = True
        self._chunk_timer.start()

        self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
        self._monitor_thread.start()

        return True

    def stop_recording(self) -> List[str]:
        """
        停止录制
        :return: 分片文件列表
        """
        with self._state_lock:
            if self._state == RecordingState.IDLE:
                self.logger.info("当前未在录制")
                return list(self._chunks)

            self.logger.info("正在停止录制...")
            self._state = RecordingState.STOPPING

        if self._chunk_timer:
            self._chunk_timer.cancel()
            self._chunk_timer = None

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        if self._process:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                else:
                    self._process.terminate()
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning("ffmpeg 未响应，强制终止")
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                else:
                    self._process.kill()
            except Exception as e:
                self.logger.error(f"终止 ffmpeg 时出错: {e}")
            finally:
                self._handle_chunk_complete()
                self._process = None

        with self._state_lock:
            self._state = RecordingState.IDLE

        self.logger.info(f"录制结束，共 {len(self._chunks)} 个分片")
        return list(self._chunks)

    def pause_recording(self) -> bool:
        """暂停录制"""
        with self._state_lock:
            if self._state != RecordingState.RECORDING:
                self.logger.warning("当前不在录制状态，无法暂停")
                return False

            if self._chunk_timer:
                self._chunk_timer.cancel()

            if self._process:
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self._process.pid), signal.SIGSTOP)
                    else:
                        os.kill(self._process.pid, signal.SIGSTOP)
                    self._state = RecordingState.PAUSED
                    self.logger.info("录制已暂停")
                    return True
                except Exception as e:
                    self.logger.error(f"暂停失败: {e}")
                    return False
        return False

    def resume_recording(self) -> bool:
        """恢复录制"""
        with self._state_lock:
            if self._state != RecordingState.PAUSED:
                self.logger.warning("当前未在暂停状态，无法恢复")
                return False

            if self._process:
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self._process.pid), signal.SIGCONT)
                    else:
                        os.kill(self._process.pid, signal.SIGCONT)
                    self._state = RecordingState.RECORDING
                    self.logger.info("录制已恢复")

                    elapsed = (datetime.now() - self._chunk_start_time).total_seconds() if self._chunk_start_time else 0
                    remaining = max(1, self.chunk_duration - elapsed)
                    self._chunk_timer = threading.Timer(remaining, self._scheduled_chunk_rotation)
                    self._chunk_timer.daemon = True
                    self._chunk_timer.start()

                    return True
                except Exception as e:
                    self.logger.error(f"恢复失败: {e}")
                    return False
        return False

    def get_chunks(self) -> List[str]:
        """获取当前分片列表"""
        with self._chunk_lock:
            return list(self._chunks)

    def merge_chunks(self, output_file: str) -> str:
        """
        合并所有分片为一个文件
        :param output_file: 输出文件路径
        :return: 合并后的文件路径
        """
        with self._chunk_lock:
            chunks = list(self._chunks)

        if not chunks:
            self.logger.warning("没有分片文件需要合并")
            return ""

        if self._is_merging:
            self.logger.warning("合并操作正在进行中")
            return ""

        self._is_merging = True

        try:
            if len(chunks) == 1:
                self.logger.info(f"只有一个分片，直接复制: {chunks[0]}")
                import shutil
                shutil.copy2(chunks[0], output_file)
                return output_file

            self.logger.info(f"开始合并 {len(chunks)} 个分片...")

            concat_list = self.output_dir / "concat_list.txt"
            with open(concat_list, 'w') as f:
                for chunk in chunks:
                    f.write(f"file '{chunk}'\n")

            merge_cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                "-y",
                output_file
            ]

            self.logger.info(f"执行合并命令: {' '.join(merge_cmd)}")
            result = subprocess.run(
                merge_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )

            try:
                os.remove(concat_list)
            except:
                pass

            if result.returncode == 0:
                self.logger.info(f"合并完成: {output_file}")
                return output_file
            else:
                self.logger.error(f"合并失败: {result.stderr.decode('utf-8', errors='ignore')}")
                return ""

        except subprocess.TimeoutExpired:
            self.logger.error("合并超时")
            return ""
        except Exception as e:
            self.logger.error(f"合并出错: {e}")
            return ""
        finally:
            self._is_merging = False

    def is_recording(self) -> bool:
        """检查是否正在录制"""
        with self._state_lock:
            return self._state == RecordingState.RECORDING

    def get_state(self) -> RecordingState:
        """获取当前状态"""
        with self._state_lock:
            return self._state

    def get_status(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        with self._state_lock:
            state = self._state
        with self._chunk_lock:
            chunks = list(self._chunks)

        status = {
            "state": state.value,
            "is_recording": state == RecordingState.RECORDING,
            "chunks_count": len(chunks),
            "current_chunk": self._current_chunk,
            "chunk_index": self._chunk_index,
            "session_start": self._session_start_time.isoformat() if self._session_start_time else None,
            "chunk_start": self._chunk_start_time.isoformat() if self._chunk_start_time else None,
            "stream_url": self._stream_url,
            "retry_count": self._retry_count,
        }

        if self._current_chunk and os.path.exists(self._current_chunk):
            status["current_chunk_size"] = os.path.getsize(self._current_chunk)
        else:
            status["current_chunk_size"] = 0

        return status


def test_recorder():
    """测试录制器功能"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    config = {
        "record": {
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav",
            "chunk_duration": 10,
            "output_dir": "./test_recordings",
            "retry_interval": 5,
            "max_retry": 3
        }
    }

    recorder = AudioRecorder(config)
    print(f"初始状态: {recorder.is_recording()}")

    stream_url = "https://test.streams.example/live/test.flv"
    print(f"测试流URL: {stream_url}")

    print(f"开始录制测试...")
    success = recorder.start_recording(stream_url, "test_live")
    print(f"录制开始: {success}")

    if success:
        for i in range(3):
            time.sleep(1)
            status = recorder.get_status()
            print(f"状态: {status}")

        print("停止录制...")
        chunks = recorder.stop_recording()
        print(f"分片列表: {chunks}")

    import shutil
    try:
        shutil.rmtree("./test_recordings")
        print("清理测试目录完成")
    except:
        pass


if __name__ == "__main__":
    test_recorder()
