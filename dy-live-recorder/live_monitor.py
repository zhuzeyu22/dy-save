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
        self.unique_id = None
        
        if room_url:
            if room_url.isdigit():
                self.room_id = room_url
                logger.info(f"使用房间号: {self.room_id}")
            else:
                self.room_id = self.douyin.get_room_id_from_url(room_url)
                if not self.room_id:
                    import re
                    match = re.search(r'/([a-zA-Z0-9_]+)/?', room_url.split('live.douyin.com')[-1] if 'live.douyin.com' in room_url else room_url)
                    if match:
                        self.unique_id = match.group(1).strip('/')
                        logger.info(f"未获取到房间号，使用抖音号监控: {self.unique_id}")
                        self.room_id = None
                    else:
                        raise ValueError("无法解析房间URL，请检查配置")
                else:
                    logger.info(f"获取到房间号: {self.room_id}")
        else:
            raise ValueError("room_url未配置")

        self.check_interval = config.get("douyin", {}).get("check_interval", 300)
        self.username = config.get("douyin", {}).get("username", "")

        self.on_live_start = on_live_start
        self.on_live_end = on_live_end

        self._is_live = False
        self._live_start_time: Optional[datetime] = None
        self._running = False

    def _get_room_id_for_user(self) -> Optional[str]:
        if self.unique_id:
            user_info = self.douyin.get_user_by_unique_id(self.unique_id)
            if user_info and user_info.get("room_id"):
                return str(user_info["room_id"])
        return None

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def live_start_time(self) -> Optional[datetime]:
        return self._live_start_time

    def check_live_status(self) -> dict:
        try:
            room_id = self.room_id
            if not room_id and self.unique_id:
                room_id = self._get_room_id_for_user()
                if room_id:
                    logger.info(f"通过抖音号获取到房间号: {room_id}")
            
            if not room_id:
                logger.warning("无法获取房间号，等待下次检测...")
                return {"is_live": False, "room_id": None, "stream_url": None, "waiting_for_room": True}
            
            status = self.douyin.get_live_status(room_id)
            status["waiting_for_room"] = False
            return status
        except Exception as e:
            logger.error(f"检查直播状态失败: {e}")
            return {"is_live": False, "error": str(e)}

    def start_monitoring(self):
        monitor_target = self.username or self.unique_id or self.room_id or "未知主播"
        logger.info(f"开始监控主播: {monitor_target}")
        logger.info(f"检测间隔: {self.check_interval} 秒")
        if self.unique_id:
            logger.info(f"监控方式: 通过抖音号 '{self.unique_id}' 检测")
        self._running = True

        while self._running:
            try:
                status = self.check_live_status()

                if status.get("waiting_for_room"):
                    logger.info("💤 主播未开播，持续监控中...")

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
