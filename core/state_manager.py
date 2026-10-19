import os
import json

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")

def load_app_settings():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "fred_api_key": os.getenv("FRED_API_KEY", ""),
        "fmp_api_key": os.getenv("FMP_API_KEY", "")
    }

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

