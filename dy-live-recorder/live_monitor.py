import time
import logging
from datetime import datetime
from typing import Optional, Callable
from douyin_api import DouyinAPI

logger = logging.getLogger(__name__)


class LiveMonitor:
    def __init__(
        self,
        config: dict,
        on_live_start: Optional[Callable] = None,
        on_live_end: Optional[Callable] = None
    ):
        self.config = config
        self.douyin = DouyinAPI(config.get("douyin", {}).get("cookie", ""))

        room_url = config.get("douyin", {}).get("room_url", "")
        self.room_id = room_url if room_url.isdigit() else self.douyin.get_room_id_from_url(room_url)

        if not self.room_id:
            raise ValueError("无法获取房间ID，请检查配置")

        self.check_interval = config.get("douyin", {}).get("check_interval", 300)
        self.username = config.get("douyin", {}).get("username", "")

        self.on_live_start = on_live_start
        self.on_live_end = on_live_end

        self._is_live = False
        self._live_start_time: Optional[datetime] = None
        self._running = False

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def live_start_time(self) -> Optional[datetime]:
        return self._live_start_time

    def check_live_status(self) -> dict:
        try:
            status = self.douyin.get_live_status(self.room_id)
            return status
        except Exception as e:
            logger.error(f"检查直播状态失败: {e}")
            return {"is_live": False, "error": str(e)}

    def start_monitoring(self):
        logger.info(f"开始监控主播: {self.username} (房间号: {self.room_id})")
        logger.info(f"检测间隔: {self.check_interval} 秒")
        self._running = True

        while self._running:
            try:
                status = self.check_live_status()

                if status.get("is_live"):
                    if not self._is_live:
                        self._live_start_time = datetime.now()
                        logger.info(f"🎬 检测到直播开始! 时间: {self._live_start_time}")
                        if self.on_live_start:
                            self.on_live_start(status)
                else:
                    if self._is_live:
                        logger.info("📴 直播已结束")
                        if self.on_live_end:
                            self.on_live_end()
                    else:
                        logger.debug("💤 待机中...")

                self._is_live = status.get("is_live", False)

            except Exception as e:
                logger.error(f"监控异常: {e}")

            if self._running:
                time.sleep(self.check_interval)

        logger.info("监控已停止")

    def stop_monitoring(self):
        logger.info("正在停止监控...")
        self._running = False

    def get_stream_url(self) -> Optional[str]:
        if self._is_live:
            return self.douyin.get_stream_url(self.room_id)
        return None
