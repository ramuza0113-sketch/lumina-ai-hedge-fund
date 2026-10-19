"""
Lumina Capital - X (Twitter) Publisher Helper
Provides tweet length calculation, trimming, and optional posting.
"""
import os
import re
import json
import sqlite3
from typing import Optional, Dict, Any, List

class XPublisher:
    """
    X (Twitter) Integration Helper for Lumina Capital
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None
    ):
        try:
            from core.state_manager import get_x_credentials
            creds = get_x_credentials()
        except Exception:
            creds = {}
        self.api_key = (api_key or creds.get("api_key", os.getenv("X_API_KEY", ""))).strip()
        self.api_secret = (api_secret or creds.get("api_secret", os.getenv("X_API_SECRET", ""))).strip()
        self.access_token = (access_token or creds.get("access_token", os.getenv("X_ACCESS_TOKEN", ""))).strip()
        self.access_token_secret = (access_token_secret or creds.get("access_token_secret", os.getenv("X_ACCESS_TOKEN_SECRET", ""))).strip()
        self.init_post_history_db()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.access_token and self.access_token_secret)

    @staticmethod
    def get_history_db_path() -> str:
        app_data_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'LuminaAI')
        os.makedirs(app_data_dir, exist_ok=True)
        return os.path.join(app_data_dir, 'lumina_history.db')

    @classmethod
    def init_post_history_db(cls):
        try:
            db_path = cls.get_history_db_path()
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS autonomous_post_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at DATETIME,
                    genre TEXT,
                    content TEXT,
                    tweet_id TEXT,
                    status TEXT,
                    post_type TEXT,
                    error_msg TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except Exception:
            pass

    @staticmethod
    def get_twitter_weighted_length(text: str) -> int:
        if not text:
            return 0
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        text_without_urls = re.sub(url_pattern, '', text)
        weight = len(urls) * 23
        for ch in text_without_urls:
            if ord(ch) <= 0x7F:
                weight += 1
            else:
                weight += 2
        return weight

    @classmethod
    def get_twitter_char_count(cls, text: str) -> int:
        weight = cls.get_twitter_weighted_length(text)
        return (weight + 1) // 2

    @classmethod
    def _smart_trim_tweet(cls, text: str, max_weight: int = 280) -> str:
        if cls.get_twitter_weighted_length(text) <= max_weight:
            return text
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        url_len = len(urls) * 23
        avail = max_weight - url_len - 6
        if avail <= 0:
            return text[:130] + "..."
        cur_weight = 0
        trimmed_chars = []
        for ch in text:
            w = 1 if ord(ch) <= 0x7F else 2
            if cur_weight + w > avail:
                break
            cur_weight += w
            trimmed_chars.append(ch)
        return "".join(trimmed_chars) + "..."

    def post_tweet(self, text: str, media_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if not self.is_configured():
            return {"status": "error", "message": "X API credentials not configured."}
        try:
            from requests_oauthlib import OAuth1Session
            oauth = OAuth1Session(
                self.api_key,
                client_secret=self.api_secret,
                resource_owner_key=self.access_token,
                resource_owner_secret=self.access_token_secret
            )
            payload = {"text": text}
            if media_ids:
                payload["media"] = {"media_ids": media_ids}
            res = oauth.post("https://api.twitter.com/2/tweets", json=payload)
            if res.status_code in (200, 201):
                data = res.json()
                tweet_id = data.get("data", {}).get("id")
                return {"status": "success", "tweet_id": tweet_id}
            else:
                return {"status": "error", "message": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
