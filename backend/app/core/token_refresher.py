import asyncio
import base64
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
import httpx

from app.config import settings
from app.core.logger import logger

# Official Web Player Fail-Safe Fallback Token
DEFAULT_DEVELOPER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IldlYlBsYXlLaWQifQ.eyJpc3MiOiJBTVBXZWJQbGF5IiwiaWF0IjoxNzg2NjMyOTI0LCJleHAiOjE3OTI2ODA5MjQsInJvb3RfaHR0cHNfb3JpZ2luIjpbImFwcGxlLmNvbSJdfQ.hBgj61sZf-y7bmuvT-joXAUAcf7TVJ51732xnH5vFkLHOmsQHxVqGMYUuI4h8c0-RX3fRY3moylhLW8fewFJyw"

JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9-_=]{20,}\.[A-Za-z0-9-_=]{20,}\.[A-Za-z0-9-_=]{20,}")
JS_ASSET_PATTERN = re.compile(r"/(?:assets|web-player)/[^\"'\s<>]+\.js")


def parse_jwt_expiry(token: str) -> Optional[int]:
    """Extracts the 'exp' unix timestamp from a JWT token string."""
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Pad base64 if needed
        padding = len(payload_b64) % 4
        if padding:
            payload_b64 += "=" * (4 - padding)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8", errors="replace")
        payload = json.loads(payload_json)
        return payload.get("exp")
    except Exception:
        return None


class AppleMusicTokenManager:
    """
    Manages the lifecycle, periodic inspection, dynamic extraction,
    and automatic caching/refresh of Apple Music Developer Tokens.
    """

    def __init__(self, am_dir: Optional[Path] = None):
        self.am_dir = am_dir or settings.APPLE_MUSIC_DIR
        self.cache_file = self.am_dir / ".token_cache"
        self.config_file = self.am_dir / "config.yaml"
        self._lock = asyncio.Lock()
        self._memory_token: Optional[str] = None
        self._memory_exp: Optional[int] = None
        self._last_read_time: float = 0.0

    def get_cached_token(self) -> Tuple[Optional[str], Optional[int], float]:
        """
        Reads token from cache file or config.yaml.
        Uses in-memory 5-minute TTL caching to avoid frequent disk I/O.
        Returns (token, exp_timestamp, remaining_days).
        """
        now_ts = int(time.time())
        if self._memory_token and (time.time() - self._last_read_time < 300.0):
            remaining_days = ((self._memory_exp - now_ts) / 86400.0) if self._memory_exp else 0.0
            return self._memory_token, self._memory_exp, remaining_days

        token = None
        if self.cache_file.exists():
            try:
                token = self.cache_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        if not token and self.config_file.exists():
            try:
                content = self.config_file.read_text(encoding="utf-8", errors="replace")
                match = re.search(r'authorization-token:\s*["\']?([^"\'\r\n]+)["\']?', content)
                if match:
                    val = match.group(1).strip()
                    if val and val != "your-authorization-token" and JWT_PATTERN.match(val):
                        token = val
            except Exception:
                pass

        if not token:
            token = DEFAULT_DEVELOPER_TOKEN

        exp = parse_jwt_expiry(token)
        self._memory_token = token
        self._memory_exp = exp
        self._last_read_time = time.time()

        remaining_days = ((exp - now_ts) / 86400.0) if exp else 0.0
        return token, exp, remaining_days


    async def fetch_latest_token_online(self) -> Optional[str]:
        """Dynamically scrapes the latest active Developer Token from Apple Music Web Player JS assets."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=12.0) as client:
                # 1. Fetch browse page
                resp = await client.get("https://music.apple.com/us/browse")
                if resp.status_code != 200:
                    resp = await client.get("https://music.apple.com")
                if resp.status_code != 200:
                    return None

                html = resp.text

                # 2. Check direct HTML match
                html_matches = JWT_PATTERN.findall(html)
                for candidate in html_matches:
                    exp = parse_jwt_expiry(candidate)
                    if exp and exp > int(time.time()) + 86400:
                        return candidate

                # 3. Locate JS bundles
                js_files = JS_ASSET_PATTERN.findall(html)
                if not js_files:
                    return None

                # Prioritize index/player scripts
                prioritized = [js for js in js_files if any(k in js.lower() for k in ("index", "main", "player"))]
                others = [js for js in js_files if js not in prioritized]
                candidates = prioritized + others

                for js in candidates[:8]:
                    js_url = js if js.startswith("http") else ("https://music.apple.com" + js)
                    try:
                        js_resp = await client.get(js_url)
                        if js_resp.status_code == 200:
                            tokens = JWT_PATTERN.findall(js_resp.text)
                            for t in tokens:
                                exp = parse_jwt_expiry(t)
                                if exp and exp > int(time.time()) + 86400:
                                    return t
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"[TokenManager] 在线抓取 Apple Music Token 失败 (可回退): {str(e)}")

        return None

    async def update_token(self, new_token: str) -> None:
        """Saves new token to .token_cache and updates config.yaml."""
        async with self._lock:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.cache_file.write_text(new_token.strip(), encoding="utf-8")
            except Exception as e:
                logger.warning(f"[TokenManager] 写入 .token_cache 失败: {str(e)}")

            if self.config_file.exists():
                try:
                    content = self.config_file.read_text(encoding="utf-8", errors="replace")
                    if "authorization-token:" in content:
                        new_content = re.sub(
                            r'authorization-token:\s*["\']?[^"\'\r\n]*["\']?',
                            f'authorization-token: "{new_token.strip()}"',
                            content
                        )
                        self.config_file.write_text(new_content, encoding="utf-8")
                except Exception as e:
                    logger.warning(f"[TokenManager] 更新 config.yaml 中的 authorization-token 失败: {str(e)}")

    async def ensure_valid_token(self) -> str:
        """
        Ensures a valid token exists. If the current token is missing or has
        less than 30 days remaining, attempts an automatic dynamic online refresh.
        """
        curr_token, exp, remaining_days = self.get_cached_token()

        if exp and remaining_days > 30.0:
            exp_date = datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d")
            logger.debug(f"[TokenManager] 当前 Apple Music Token 充足 (剩余 {remaining_days:.1f} 天, 有效期至 {exp_date})")
            return curr_token

        logger.info(f"[TokenManager] Apple Music Token 需更新 (剩余 {remaining_days:.1f} 天)，正在自动获取最新凭据...")
        new_token = await self.fetch_latest_token_online()
        if new_token:
            new_exp = parse_jwt_expiry(new_token)
            new_days = ((new_exp - int(time.time())) / 86400.0) if new_exp else 0.0
            new_date = datetime.fromtimestamp(new_exp, tz=timezone.utc).strftime("%Y-%m-%d") if new_exp else "未知"
            await self.update_token(new_token)
            logger.info(f"[TokenManager] ✅ Apple Music Token 自动刷新成功！新凭据有效期至: {new_date} (剩余 {new_days:.1f} 天)")
            return new_token
        else:
            logger.warning(f"[TokenManager] 无法在线获取新 Token，继续使用现有/内置回退 Token (剩余 {remaining_days:.1f} 天)")
            return curr_token or DEFAULT_DEVELOPER_TOKEN


token_manager = AppleMusicTokenManager()
