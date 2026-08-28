#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hotpatch: 生产卡补充选单允许草稿 + 合同流水号/图纸号反查。"""
from __future__ import annotations

from pathlib import Path

import paramiko

PWD = "Ruolin2025"
HOST, USER = "192.168.1.205", "swc"
SUDO = f"echo {PWD} | sudo -S"
ROOT = Path(r"G:\ruolin-a\spt-crm")
LOCAL = ROOT / "backend/app/domains/lowcode/pricing_checklist_fields.py"
CONTAINERS = ["spt-crm-backend-1", "spt-crm-worker-1", "spt-crm-reminder-1"]


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    sftp = c.open_sftp()
    sftp.put(str(LOCAL), "/tmp/pricing_checklist_fields.py")
    sftp.close()

    def run(cmd: str, timeout: int = 120) -> None:
        print(">>", cmd.replace(PWD, "***")[:200], flush=True)
        _, o, e = c.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        print(out, flush=True)
        if err.strip():
            print("STDERR:", err, flush=True)
        if o.channel.recv_exit_status() != 0:
            raise SystemExit(f"failed: {cmd}")

    for name in CONTAINERS:
        run(f"{SUDO} docker cp /tmp/pricing_checklist_fields.py {name}:/app/app/domains/lowcode/pricing_checklist_fields.py")
        run(f"{SUDO} docker restart {name}")

    print("waiting backend...", flush=True)
    import time
    time.sleep(8)
    run(f"{SUDO} docker exec spt-crm-backend-1 python backend/scripts/_probe_wmgf_pickable_205.py 2>/dev/null || true")
    c.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
