import os
import json

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
_DOTENV_LOADED = False


def _ensure_dotenv_loaded():
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=False)
        return
    except Exception:
        pass
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def load_app_settings():
    _ensure_dotenv_loaded()
    saved = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    saved = data
        except Exception:
            saved = {}

    gem_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or saved.get("google_api_key")
        or saved.get("gemini_api_key")
        or ""
    )
    merged = dict(saved)
    merged.update({
        "google_api_key": gem_key,
        "gemini_api_key": gem_key,
        "openai_api_key": os.getenv("OPENAI_API_KEY") or saved.get("openai_api_key", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY") or saved.get("anthropic_api_key", ""),
        "fred_api_key": os.getenv("FRED_API_KEY") or saved.get("fred_api_key", ""),
        "fmp_api_key": os.getenv("FMP_API_KEY") or saved.get("fmp_api_key", ""),
    })
    return merged

def save_app_settings(settings):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

def get_stock_report_scheduler_settings():
    return {"enabled": False, "frequency": "once_daily_2000"}

def save_stock_report_scheduler_settings(settings):
    pass

def get_discord_settings():
    settings = load_app_settings()
    return settings.get("discord_settings", {
        "enabled": False,
        "bot_token": os.getenv("DISCORD_BOT_TOKEN", ""),
        "channel_id": os.getenv("DISCORD_CHANNEL_ID", ""),
        "webhook_url": os.getenv("DISCORD_WEBHOOK_URL", "")
    })

def save_discord_settings(discord_settings):
    settings = load_app_settings()
    settings["discord_settings"] = discord_settings
    save_app_settings(settings)

def get_note_settings():
    settings = load_app_settings()
    return settings.get("note_settings", {
        "email": os.getenv("NOTE_EMAIL", ""),
        "password": os.getenv("NOTE_PASSWORD", ""),
        "creator_url": os.getenv("NOTE_CREATOR_URL", "")
    })

def save_note_settings(note_settings):
    settings = load_app_settings()
    settings["note_settings"] = note_settings
    save_app_settings(settings)

def get_x_credentials():
    settings = load_app_settings()
    return settings.get("x_credentials", {
        "api_key": os.getenv("X_API_KEY", ""),
        "api_secret": os.getenv("X_API_SECRET", ""),
        "access_token": os.getenv("X_ACCESS_TOKEN", ""),
        "access_token_secret": os.getenv("X_ACCESS_TOKEN_SECRET", "")
    })

def save_x_credentials(creds):
    settings = load_app_settings()
    settings["x_credentials"] = creds
    save_app_settings(settings)

