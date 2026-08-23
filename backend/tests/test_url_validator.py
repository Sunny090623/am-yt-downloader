import pytest
from app.core.url_validator import validate_and_sanitize_youtube_url

def test_valid_standard_youtube_url():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=tracking123&feature=share"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is True
    assert sanitized == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert err is None

def test_valid_short_youtube_url():
    url = "https://youtu.be/dQw4w9WgXcQ?t=42"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is True
    assert sanitized == "https://youtu.be/dQw4w9WgXcQ?t=42"
    assert err is None

def test_valid_shorts_url():
    url = "https://www.youtube.com/shorts/abc123XYZ"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is True
    assert sanitized == "https://www.youtube.com/shorts/abc123XYZ"
    assert err is None

def test_valid_music_youtube_url():
    url = "https://music.youtube.com/watch?v=track12345"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is True
    assert sanitized == "https://www.youtube.com/watch?v=track12345"
    assert err is None

def test_valid_mobile_youtube_url():
    url = "http://m.youtube.com/watch?v=mobile123"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is True
    assert sanitized == "https://www.youtube.com/watch?v=mobile123"
    assert err is None

def test_reject_non_youtube_url():
    url = "https://www.bilibili.com/video/BV1xx411c7mD"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    assert is_valid is False
    assert sanitized is None
    assert "不支持的域名" in err

def test_reject_shell_injection_attempt():
    url = "https://www.youtube.com/watch?v=123; rm -rf /"
    is_valid, sanitized, err = validate_and_sanitize_youtube_url(url)
    # The URL validator sanitizes the video ID to prevent command injection characters
    assert is_valid is True
    assert ";" not in sanitized
    assert " " not in sanitized

def test_reject_empty_or_invalid_scheme():
    is_valid, _, err = validate_and_sanitize_youtube_url("")
    assert is_valid is False

    is_valid, _, err = validate_and_sanitize_youtube_url("ftp://youtube.com/watch?v=123")
    assert is_valid is False
    assert "仅支持 http / https" in err
