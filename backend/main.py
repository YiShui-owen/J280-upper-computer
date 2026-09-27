from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

app = FastAPI(title="J280 Showcase Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FIELD_RE = re.compile(r"([A-Z]+)=([0-9A-F]+)")
SIGNED_32 = {"A", "AD", "ENC", "TH", "THD", "U", "PT", "PE"}
SIGNED_16 = {"DC", "DA", "PU", "AU"}
MODE_NAMES = {0: "IDLE", 1: "ZERO", 2: "SWING", 3: "BALANCE", 4: "FAULT"}


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Missing config: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def signed_hex(v: str, bits: int) -> int:
    n = int(v, 16)
    sign = 1 << (bits - 1)
    return n - (1 << bits) if n & sign else n


def q20_rad_to_deg(raw: int) -> float:
    return raw * 180.0 / math.pi / 1048576.0


def q15_to_pct(raw: int) -> float:
    return raw * 100.0 / 32768.0


def parse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("T="):
        return None
    items = dict(FIELD_RE.findall(line))
    if not items or "T" not in items:
        return None

    raw: dict[str, int] = {}
    for k, v in items.items():
        try:
            if k in SIGNED_32:
                raw[k] = signed_hex(v, 32)
            elif k in SIGNED_16:
                raw[k] = signed_hex(v, 16)
            else:
                raw[k] = int(v, 16)
        except Exception:
            continue

    mode = raw.get("M", -1)
    cm = raw.get("CM", 0)
    lim_packed = raw.get("LIM", 0)
    data = {
        "source": "tuner-log",
        "fpga_time_ms": raw.get("T", 0),
        "mode": mode,
        "mode_name": MODE_NAMES.get(mode, "UNKNOWN"),
        "fault": raw.get("F", 0),
        "saturation": bool(raw.get("S", 0)),
        "angle_deg": round(q20_rad_to_deg(raw.get("A", 0)), 4),
        "angle_velocity_deg_s": round(q20_rad_to_deg(raw.get("AD", 0)), 3),
        "encoder": raw.get("ENC", 0),
        "arm_angle_deg": round(q20_rad_to_deg(raw.get("TH", 0)), 3),
        "arm_velocity_deg_s": round(q20_rad_to_deg(raw.get("THD", 0)), 3),
        "control_raw_percent": round(q15_to_pct(raw.get("U", 0)), 2),
        "duty_command_percent": round(q15_to_pct(raw.get("DC", 0)), 2),
        "duty_actual_percent": round(q15_to_pct(raw.get("DA", 0)), 2),
        "alpha_ref_deg": round(raw.get("PU", 0) * 360.0 / 4096.0, 3),
        "position_target": raw.get("PT", 0),
        "position_error": raw.get("PE", 0),
        "angle_output_percent": round(q15_to_pct(raw.get("AU", 0)), 2),
        "akp": raw.get("AKP", 0),
        "akd": raw.get("AKD", 0),
        "pkp": raw.get("PKP", 0),
        "pki": raw.get("PKI", 0),
        "pkd": raw.get("PKD", 0),
        "revision": raw.get("REV", 0),
        "pwm_limit_percent": raw.get("PWM", 0),
        "ref_limit_raw": (lim_packed >> 8) & 0xFF if "LIM" in raw else 42,
        "deadzone_percent": lim_packed & 0x0F if "LIM" in raw else 0,
        "d_deadband_q2": (lim_packed >> 4) & 0x07 if "LIM" in raw else 0,
        "control_mode": cm & 0x3,
        "control_mode_name": "TRUE CASCADE" if (cm & 0x3) == 1 else "ANGLE ONLY",
        "d_filter": round(((cm >> 2) & 0x1FFF) / 4096.0, 4) if cm else 0.1848,
        "received_at": time.time(),
    }
    return data


class Command(BaseModel):
    command: str


class ConfigUpdate(BaseModel):
    tuner_project_dir: str


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.latest: dict[str, Any] = {}
        self.samples: deque[dict[str, Any]] = deque(maxlen=240)
        self.last_log_path: str | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    def cfg(self) -> dict[str, Any]:
        return load_config()

    def project_dir(self) -> Path:
        cfg = self.cfg()
        return Path(cfg["tuner_project_dir"])

    def latest_log(self) -> Path | None:
        cfg = self.cfg()
        d = self.project_dir()
        if not d.exists():
            return None
        logs = list(d.glob(cfg.get("log_glob", "v512_1ms_10ms_home_m29_v2_*.log")))
        return max(logs, key=lambda p: p.stat().st_mtime) if logs else None

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead = []
        text_payload = json.dumps(payload, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send_text(text_payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def loop(self) -> None:
        self._running = True
        current: Path | None = None
        fp = None
        position = 0
        while self._running:
            try:
                log = self.latest_log()
                if log is None:
                    self.last_error = f"未找到 tuner 日志，请确认 tuner 正在运行：{self.project_dir()}"
                    await asyncio.sleep(0.5)
                    continue
                if current != log:
                    if fp:
                        fp.close()
                    current = log
                    self.last_log_path = str(log)
                    fp = log.open("r", encoding="ascii", errors="ignore")
                    fp.seek(0, os.SEEK_END)
                    position = fp.tell()

                assert fp is not None
                line = fp.readline()
                if not line:
                    # Handle file truncation/recreation.
                    try:
                        size = current.stat().st_size
                        if size < position:
                            fp.seek(0)
                            position = 0
                    except Exception:
                        pass
                    await asyncio.sleep(0.02)
                    continue
                position = fp.tell()
                parsed = parse_line(line.strip())
                if parsed:
                    self.latest = parsed
                    self.samples.append(parsed)
                    self.last_error = None
                    await self.broadcast({"type": "telemetry", "data": parsed})
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_error = str(e)
                await asyncio.sleep(0.5)
        if fp:
            fp.close()

    async def start(self) -> None:
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

hub = Hub()


@app.on_event("startup")
async def startup() -> None:
    await hub.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await hub.stop()


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "J280 Showcase Backend", "version": "1.0.0"}


@app.get("/health")
def health() -> dict[str, Any]:
    latest_age = None
    if hub.latest.get("received_at"):
        latest_age = time.time() - hub.latest["received_at"]
    return {
        "ok": hub.last_error is None and latest_age is not None and latest_age < 2.0,
        "project_dir": str(hub.project_dir()),
        "log": hub.last_log_path,
        "last_error": hub.last_error,
        "latest_age_s": latest_age,
        "latest": hub.latest,
    }


@app.get("/snapshot")
def snapshot() -> dict[str, Any]:
    return {"latest": hub.latest, "history": list(hub.samples), "error": hub.last_error}


@app.post("/command")
def command(body: Command) -> dict[str, Any]:
    cmd = body.command.strip().upper()
    allowed = {
        "START", "STOP", "PROBE=+", "PROBE=-", "PROBE=0",
        "PROBEAMP=1", "PROBEAMP=2", "PROBEAMP=4", "PROBEAMP=12",
        "MODE=CASCADE",
    }
    parameter_prefixes = ("AKP=", "AKD=", "PKP=", "PKD=", "PKI=", "PWM=", "REF=")
    if cmd not in allowed and not cmd.startswith(parameter_prefixes):
        raise HTTPException(400, f"Unsupported command: {cmd}")
    cfg = load_config()
    mailbox = hub.project_dir() / cfg.get("mailbox_name", "v512_1ms_10ms_remote_cmd.txt")
    if not mailbox.parent.exists():
        raise HTTPException(404, f"Tuner project dir not found: {mailbox.parent}")
    mailbox.parent.mkdir(parents=True, exist_ok=True)
    with mailbox.open("a", encoding="ascii", newline="\n") as f:
        f.write(cmd + "\n")
    return {"ok": True, "command": cmd, "mailbox": str(mailbox)}


@app.post("/config")
def update_config(body: ConfigUpdate) -> dict[str, Any]:
    cfg = load_config()
    cfg["tuner_project_dir"] = body.tuner_project_dir
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    hub.last_error = None
    hub.last_log_path = None
    return {"ok": True, "config": cfg}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    hub.clients.add(ws)
    try:
        if hub.latest:
            await ws.send_json({"type": "telemetry", "data": hub.latest})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.clients.discard(ws)
    except Exception:
        hub.clients.discard(ws)
