"""Buff API client — talks to the zefoy FastAPI backend."""
import httpx
import database

TIMEOUT = 30.0


def _base() -> str:
    url = database.get_setting("buff_api_url", "").rstrip("/")
    if not url:
        raise ValueError("Chưa cài Buff API URL trong admin panel!")
    return url


# ─── Session / Captcha ───────────────────────────────────────────────────────

def start_session() -> dict:
    """POST /api/start → {session_id, captcha_b64, message}"""
    r = httpx.post(f"{_base()}/api/start", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def refresh_captcha(session_id: str) -> dict:
    """POST /api/refresh_captcha → {captcha_b64}"""
    r = httpx.post(f"{_base()}/api/refresh_captcha",
                   json={"session_id": session_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def solve_captcha(session_id: str, answer: str) -> dict:
    """POST /api/solve → {ok, message, services?}"""
    r = httpx.post(f"{_base()}/api/solve",
                   json={"session_id": session_id, "answer": answer}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_services(session_id: str) -> dict:
    """POST /api/services → {ok, services: [{name, status, available, has_action}]}"""
    r = httpx.post(f"{_base()}/api/services",
                   json={"session_id": session_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def run_buff(session_id: str, service: str, url: str) -> dict:
    """POST /api/run → {ok, amount, message, cooldown, total_sent}"""
    r = httpx.post(f"{_base()}/api/run",
                   json={"session_id": session_id, "service": service, "url": url},
                   timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
