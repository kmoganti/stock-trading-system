"""
Simple in-memory progress tracker for long-running operations like signal generation.
Thread-safe for single-process async apps. Not persisted.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_lock = asyncio.Lock()

_STATE: Dict[str, Any] = {
    "in_progress": False,
    "task": None,           # e.g., "intraday", "historic", "live"
    "phase": None,          # e.g., "initializing", "scanning", "persisting"
    "current_symbol": None,
    "processed": 0,
    "total": 0,
    "started_at": None,
    "last_update": None,
}


def _utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


async def start(task: str, total: int, phase: str = "initializing") -> None:
    """Initialize progress state for a task."""
    async with _lock:
        now = datetime.now(timezone.utc)
        _STATE.update({
            "in_progress": True,
            "task": task,
            "phase": phase,
            "current_symbol": None,
            "processed": 0,
            "total": int(total) if total is not None else 0,
            "started_at": now,
            "last_update": now,
        })


async def update(current_symbol: Optional[str] = None, processed: Optional[int] = None, phase: Optional[str] = None) -> None:
    """Update current progress information."""
    async with _lock:
        if not _STATE.get("in_progress"):
            return
        if current_symbol is not None:
            _STATE["current_symbol"] = current_symbol
        if processed is not None:
            _STATE["processed"] = int(processed)
        if phase is not None:
            _STATE["phase"] = phase
        _STATE["last_update"] = datetime.now(timezone.utc)


async def finish() -> None:
    """Mark current task as finished."""
    async with _lock:
        _STATE.update({
            "in_progress": False,
            "phase": "completed",
            "current_symbol": None,
            "processed": _STATE.get("total", 0),
            "last_update": datetime.now(timezone.utc),
        })


async def clear() -> None:
    """Clear progress state completely."""
    async with _lock:
        for k in list(_STATE.keys()):
            _STATE[k] = None
        _STATE.update({
            "in_progress": False,
            "processed": 0,
            "total": 0,
        })


async def get_state() -> Dict[str, Any]:
    async with _lock:
        total = _STATE.get("total") or 0
        processed = min(_STATE.get("processed") or 0, total) if total else (_STATE.get("processed") or 0)
        pct = 0
        if total:
            try:
                pct = int((processed / total) * 100)
            except ZeroDivisionError:
                pct = 0
        return {
            "in_progress": bool(_STATE.get("in_progress")),
            "task": _STATE.get("task"),
            "phase": _STATE.get("phase"),
            "current_symbol": _STATE.get("current_symbol"),
            "processed": processed,
            "total": total,
            "percentage": pct,
            "started_at": _utc_iso(_STATE.get("started_at")),
            "last_update": _utc_iso(_STATE.get("last_update")),
        }
