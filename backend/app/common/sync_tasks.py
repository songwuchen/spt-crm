"""In-memory progress store for long-running sync tasks.

Scope: single backend process. If the backend restarts, running tasks
are lost — callers must retry. For the DingTalk sync use case this is
acceptable because the underlying operation is idempotent.

Each task holds: status (running|completed|failed), phase, processed/total,
result (on completion), error (on failure), timestamps.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional

# tenant_id -> currently running task_id (so the UI can reconnect after a refresh)
_active_by_tenant: dict[str, str] = {}

# task_id -> task record
_tasks: dict[str, dict[str, Any]] = {}

_lock = asyncio.Lock()

# Cap retained tasks so a long-lived process doesn't leak memory.
_MAX_TASKS = 200


def _gc_locked() -> None:
    if len(_tasks) <= _MAX_TASKS:
        return
    # Drop the oldest finished tasks first
    finished = [
        (t["finished_at"] or t["started_at"], tid)
        for tid, t in _tasks.items()
        if t["status"] != "running"
    ]
    finished.sort()
    for _, tid in finished[: len(_tasks) - _MAX_TASKS]:
        _tasks.pop(tid, None)


async def create_task(tenant_id: str, kind: str) -> str:
    task_id = uuid.uuid4().hex
    async with _lock:
        _tasks[task_id] = {
            "id": task_id,
            "tenant_id": tenant_id,
            "kind": kind,
            "status": "running",
            "phase": "starting",
            "processed": 0,
            "total": 0,
            "result": None,
            "error": None,
            "started_at": time.time(),
            "finished_at": None,
        }
        _active_by_tenant[tenant_id] = task_id
        _gc_locked()
    return task_id


async def update_progress(task_id: str, phase: str, processed: int, total: int) -> None:
    async with _lock:
        t = _tasks.get(task_id)
        if t and t["status"] == "running":
            t["phase"] = phase
            t["processed"] = processed
            t["total"] = total


async def finish_task(task_id: str, result: Any) -> None:
    async with _lock:
        t = _tasks.get(task_id)
        if not t:
            return
        t["status"] = "completed"
        t["result"] = result
        t["finished_at"] = time.time()
        if _active_by_tenant.get(t["tenant_id"]) == task_id:
            _active_by_tenant.pop(t["tenant_id"], None)


async def fail_task(task_id: str, error: str) -> None:
    async with _lock:
        t = _tasks.get(task_id)
        if not t:
            return
        t["status"] = "failed"
        t["error"] = error
        t["finished_at"] = time.time()
        if _active_by_tenant.get(t["tenant_id"]) == task_id:
            _active_by_tenant.pop(t["tenant_id"], None)


def get_task(task_id: str) -> Optional[dict[str, Any]]:
    t = _tasks.get(task_id)
    if not t:
        return None
    # Return a shallow copy so callers can't mutate the store
    return dict(t)


def get_active_for_tenant(tenant_id: str, kind: Optional[str] = None) -> Optional[str]:
    tid = _active_by_tenant.get(tenant_id)
    if not tid:
        return None
    t = _tasks.get(tid)
    if not t or t["status"] != "running":
        return None
    if kind and t["kind"] != kind:
        return None
    return tid
