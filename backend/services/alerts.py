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
    is_new = key not in alerts
    alerts[key] = {
        "level": level,
        "message": message,
        "instructions": instructions,
        "since": alerts[key]["since"] if not is_new else datetime.utcnow().isoformat(),
    }
    p = _alerts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(alerts, indent=2))

    # Push to Telegram only on the state transition (not present -> present),
    # so a failure that keeps retrying doesn't spam a message every attempt.
    # Silent dashboard banners get missed for days — this is the actual fix
    # for that (see .claude/specs — recurring "why is there no data" incidents).
    if is_new:
        import services.telegram as tg  # lazy import — avoid any import-cycle risk
        icon = {"error": "\U0001F534", "warning": "⚠️"}.get(level, "ℹ️")
        text = f"{icon} {message}"
        if instructions:
            text += f"\n{instructions}"
        tg.send(text)


def clear_alert(key: str) -> None:
    alerts = get_alerts()
    if key not in alerts:
        return
    since = alerts[key].get("since")
    alerts.pop(key)
    _alerts_path().write_text(json.dumps(alerts, indent=2))

    import services.telegram as tg
    duration = ""
    if since:
        try:
            mins = (datetime.utcnow() - datetime.fromisoformat(since)).total_seconds() / 60
            duration = f" (was down {mins:.0f} min)" if mins >= 1 else ""
        except ValueError:
            pass
    tg.send(f"✅ Resolved: {key}{duration}")
