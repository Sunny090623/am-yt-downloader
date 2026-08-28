import re
import urllib.parse
from typing import Tuple, Optional

YOUTUBE_VALID_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "gaming.youtube.com",
    "youtu.be"
}

# YouTube video IDs are 11 characters base64url or alphanumeric with _ -
SAFE_VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SAFE_LIST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

def sanitize_id(raw_id: str) -> Optional[str]:
    """Ensures extracted ID contains only safe alphanumeric/dash characters."""
    if not raw_id:
        return None
    # Strip any dangerous shell characters, spaces, semicolons
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id.strip())
    return cleaned if cleaned else None

def validate_and_sanitize_youtube_url(raw_url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates that a URL is a structured, valid YouTube URL and sanitizes tracking parameters.
    Returns: (is_valid: bool, sanitized_url: Optional[str], error_message: Optional[str])
    """
    if not raw_url or not isinstance(raw_url, str):
        return False, None, "URL 不能为空"
    
    raw_url = raw_url.strip()
    if not raw_url:
        return False, None, "URL 不能为空"
    
    # Check if a scheme is present
    if "://" in raw_url:
        scheme_prefix = raw_url.split("://", 1)[0].lower()
        if scheme_prefix not in ("http", "https"):
            return False, None, f"仅支持 http / https 协议，不支持 '{scheme_prefix}'"
    else:
        # Prepend scheme if missing (e.g. user pasted www.youtube.com/...)
        raw_url = "https://" + raw_url
    
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except Exception:
        return False, None, "无法解析 URL 格式"
    
    if parsed.scheme.lower() not in ("http", "https"):
        return False, None, "仅支持 http / https 协议"
    
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, None, "无效的 URL 域名"
    
    # Check against whitelist
    if hostname not in YOUTUBE_VALID_HOSTS:
        if not hostname.endswith(".youtube.com"):
            return False, None, f"不支持的域名: {hostname}。目前仅支持 YouTube 链接"
    
    path = parsed.path
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    
    # Case 1: youtu.be/<video_id>
    if hostname == "youtu.be":
        raw_id = path.lstrip("/").split("/")[0] if path.lstrip("/") else None
        video_id = sanitize_id(raw_id)
        if not video_id:
            return False, None, "无效的 youtu.be 短链接，缺少视频 ID"
        
        sanitized = f"https://youtu.be/{video_id}"
        if "t" in query_params:
            time_val = sanitize_id(query_params["t"][0])
            if time_val:
                sanitized += f"?t={time_val}"
        return True, sanitized, None
    
    # Case 2: youtube.com/watch?v=<video_id>
    if path == "/watch" or path.startswith("/watch/"):
        video_id_list = query_params.get("v")
        if not video_id_list or not video_id_list[0]:
            return False, None, "YouTube 链接缺少视频参数 (v)"
        video_id = sanitize_id(video_id_list[0])
        if not video_id:
            return False, None, "无效的视频 ID 参数"
        sanitized = f"https://www.youtube.com/watch?v={video_id}"
        if "list" in query_params:
            list_id = sanitize_id(query_params["list"][0])
            if list_id:
                sanitized += f"&list={list_id}"
        return True, sanitized, None
    
    # Case 3: /shorts/<video_id>
    if path.startswith("/shorts/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[1]:
            video_id = sanitize_id(parts[1])
            if video_id:
                return True, f"https://www.youtube.com/shorts/{video_id}", None
        return False, None, "无效的 YouTube Shorts 链接"
    
    # Case 4: /embed/<video_id>, /v/<video_id>, /live/<video_id>
    for prefix in ("/embed/", "/v/", "/live/"):
        if path.startswith(prefix):
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[1]:
                video_id = sanitize_id(parts[1])
                if video_id:
                    return True, f"https://www.youtube.com{prefix}{video_id}", None
            return False, None, f"无效的 YouTube 路径: {path}"
            
    # Case 5: /playlist?list=<list_id>
    if path == "/playlist" and "list" in query_params:
        list_id = sanitize_id(query_params["list"][0])
        if list_id:
            return True, f"https://www.youtube.com/playlist?list={list_id}", None

    # Fallback: if it's on youtube.com and has a non-empty path
    if path and path != "/":
        clean_url = urllib.parse.urlunparse((
            "https",
            "www.youtube.com",
            parsed.path,
            "",
            parsed.query,
            ""
        ))
        return True, clean_url, None

    return False, None, "未能识别有效的 YouTube 视频或歌单路径"


APPLE_MUSIC_VALID_HOSTS = {
    "music.apple.com",
    "beta.music.apple.com",
    "classical.music.apple.com"
}

def validate_and_sanitize_apple_music_url(raw_url: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Validates and categorizes an Apple Music URL.
    Returns: (is_valid: bool, sanitized_url: Optional[str], media_type: Optional[str], error_message: Optional[str])
    where media_type is 'song' or 'album'.
    """
    if not raw_url or not isinstance(raw_url, str):
        return False, None, None, "URL 不能为空"
    
    raw_url = raw_url.strip()
    if not raw_url:
        return False, None, None, "URL 不能为空"
    
    if "://" in raw_url:
        scheme_prefix = raw_url.split("://", 1)[0].lower()
        if scheme_prefix not in ("http", "https"):
            return False, None, None, f"仅支持 http / https 协议，不支持 '{scheme_prefix}'"
    else:
        raw_url = "https://" + raw_url
        
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except Exception:
        return False, None, None, "无法解析 URL 格式"
        
    hostname = (parsed.hostname or "").lower()
    if hostname not in APPLE_MUSIC_VALID_HOSTS:
        return False, None, None, f"不支持的域名: {hostname}。仅支持 Apple Music 链接 (music.apple.com)"
        
    path = parsed.path
    query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    
    # Check if song URL: /song/ or /album/... with ?i=
    if "/song/" in path:
        clean_path = re.sub(r"[^a-zA-Z0-9_\-\./]", "", path)
        if ".." in clean_path:
            return False, None, None, "检测到非法的路径遍历字符"
        sanitized = f"https://music.apple.com{clean_path}"
        return True, sanitized, "song", None
        
    if "/album/" in path:
        clean_path = re.sub(r"[^a-zA-Z0-9_\-\./]", "", path)
        if ".." in clean_path:
            return False, None, None, "检测到非法的路径遍历字符"
        if "i" in query_params and query_params["i"] and query_params["i"][0]:
            clean_i = sanitize_id(query_params["i"][0])
            if clean_i:
                sanitized = f"https://music.apple.com{clean_path}?i={clean_i}"
                return True, sanitized, "song", None
        
        sanitized = f"https://music.apple.com{clean_path}"
        return True, sanitized, "album", None
        
    return False, None, None, "无法识别的 Apple Music 链接类型，仅支持单曲 (Song) 或专辑 (Album)"

