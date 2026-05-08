import re
import json
import logging
import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DouyinAPI:
    def __init__(self, cookie: str = ""):
        self.cookie = cookie
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://live.douyin.com/",
        }
        if cookie:
            self.headers["Cookie"] = cookie

    def get_room_id_from_url(self, room_url: str) -> Optional[str]:
        parsed = urlparse(room_url)
        if "live.douyin.com" in parsed.netloc:
            match = re.search(r'/(\d+)', parsed.path)
            if match:
                room_id = match.group(1)
                logger.info(f"从URL提取到room_id: {room_id}")
                return room_id
        
        try:
            response = httpx.get(room_url, headers=self.headers, timeout=10)
            html = response.text
            
            room_id_match = re.search(r'"room_id"\s*:\s*"(\d+)"', html)
            if room_id_match:
                return room_id_match.group(1)
            
            sec_uid_match = re.search(r'"sec_uid"\s*:\s*"([^"]{20,})"', html)
            if sec_uid_match:
                sec_uid = sec_uid_match.group(1)
                logger.info(f"从页面提取到sec_uid: {sec_uid[:30]}...")
                room_id = self.get_room_id_by_sec_uid(sec_uid)
                if room_id:
                    return room_id
            
            url_match = re.search(r'live\.douyin\.com/(\d+)', html)
            if url_match:
                return url_match.group(1)
                
        except Exception as e:
            logger.error(f"获取房间号失败: {e}")
        return None

    def get_room_id_by_sec_uid(self, sec_uid: str) -> Optional[str]:
        try:
            url = "https://api.tiktokv.com/aweme/v1/anchor/room/tab/info/"
            params = {"sec_user_id": sec_uid}
            response = httpx.get(url, headers=self.headers, params=params, timeout=10)
            data = response.json()
            if data.get("status_code") == 0:
                room_info = data.get("anchor_room_list", [{}])[0]
                return str(room_info.get("room_id", ""))
        except Exception as e:
            logger.error(f"通过sec_uid获取房间号失败: {e}")
        return None

    def get_live_status(self, room_id: str) -> Dict[str, Any]:
        try:
            url = "https://live.douyin.com/webcast/webcast/im/fetch/"
            params = {
                "device_platform": "web",
                "aid": "6383",
                "app_name": "douyin_web",
                "room_id": room_id,
            }
            response = httpx.get(url, headers=self.headers, params=params, timeout=10)
            data = response.json()

            if data.get("status_code") == 0:
                room_data = data.get("data", {})
                is_live = room_data.get("is_live", False)
                stream_url = self._parse_stream_url(room_data.get("stream_url", {}))

                return {
                    "is_live": is_live,
                    "room_id": room_id,
                    "stream_url": stream_url,
                    "title": room_data.get("title", ""),
                    "nickname": room_data.get("nickname", ""),
                    "viewer_count": room_data.get("user_count", 0),
                }
        except Exception as e:
            logger.error(f"获取直播状态失败: {e}")

        return {"is_live": False, "room_id": room_id, "stream_url": None}

    def _parse_stream_url(self, stream_data: Dict) -> Optional[str]:
        if not stream_data:
            return None

        flv_url = stream_data.get("live_core_sdk_data", {}).get("pull_data", {}).get("hls_fmp4_url")
        if flv_url:
            return flv_url

        flv_url = stream_data.get("rtmp_pull_url", {}).get("flv")
        if flv_url:
            return flv_url

        for key in ["hls_fmp4_url", "flv_url", "rtmp_url"]:
            url = stream_data.get(key)
            if url:
                return url

        return None

    def get_stream_url(self, room_id: str) -> Optional[str]:
        status = self.get_live_status(room_id)
        if status.get("is_live"):
            return status.get("stream_url")
        return None

    def check_live(self, room_id: str) -> bool:
        status = self.get_live_status(room_id)
        return status.get("is_live", False)
