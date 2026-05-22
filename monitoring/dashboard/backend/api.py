"""FastAPI backend for ACE Mission Control dashboard."""

import asyncio
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

_DASHBOARD_PORT = int(os.getenv("DASHBOARD_API_PORT", "8000"))

app = FastAPI(title="ACE Mission Control API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_connected_clients: list[WebSocket] = []


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/api/state")
async def get_state():
    from monitoring.dashboard.backend.state import get_state, sync_from_portfolio
    sync_from_portfolio()
    return get_state()


@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.post("/api/kill-switch/activate")
async def activate_kill_switch():
    try:
        from risk.risk_gate import activate_kill_switch
        activate_kill_switch("Dashboard manual trigger")
        from monitoring.dashboard.backend.state import update, add_log
        update({"kill_switch_active": True})
        add_log("WARN", "Kill switch ACTIVATED via dashboard")
        return {"ok": True, "kill_switch_active": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/kill-switch/deactivate")
async def deactivate_kill_switch():
    try:
        from risk.risk_gate import deactivate_kill_switch
        deactivate_kill_switch()
        from monitoring.dashboard.backend.state import update, add_log
        update({"kill_switch_active": False})
        add_log("INFO", "Kill switch DEACTIVATED via dashboard")
        return {"ok": True, "kill_switch_active": False}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/log")
async def get_log():
    from monitoring.dashboard.backend.state import get_state
    return {"entries": get_state()["mission_log"]}


# ---------------------------------------------------------------------------
# WebSocket — pushes full state every 2 seconds
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connected_clients.append(websocket)
    try:
        while True:
            from monitoring.dashboard.backend.state import get_state, sync_from_portfolio
            sync_from_portfolio()
            state = get_state()
            await websocket.send_text(json.dumps(state, default=str))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in _connected_clients:
            _connected_clients.remove(websocket)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    from monitoring.dashboard.backend.state import update, add_log
    update({"status": "running", "uptime_start": datetime.now(timezone.utc).isoformat()})
    add_log("INFO", "ACE Mission Control dashboard started")
