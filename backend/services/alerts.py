import json
import os
from datetime import datetime
from pathlib import Path


def _data_dir() -> Path:
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/jobs.db")
    db_path = db_url.split("///", 1)[-1]
    return Path(db_path).parent


def _alerts_path() -> Path:
    return _data_dir() / "alerts.json"


def get_alerts() -> dict:
    try:
        return json.loads(_alerts_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def set_alert(key: str, level: str, message: str, instructions: str = "") -> None:
    alerts = get_alerts()
    alerts[key] = {
        "level": level,
        "message": message,
        "instructions": instructions,
        "since": datetime.utcnow().isoformat(),
    }
    p = _alerts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(alerts, indent=2))


def clear_alert(key: str) -> None:
    alerts = get_alerts()
    if key not in alerts:
        return
    alerts.pop(key)
    _alerts_path().write_text(json.dumps(alerts, indent=2))
