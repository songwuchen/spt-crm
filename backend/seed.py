"""DEPRECATED — the canonical seed now lives in ``scripts/seed.py``.

This file used to carry its OWN (hand-maintained) permission list + role model,
which silently drifted out of sync with ``scripts/seed.py`` — e.g. it never had
the 扩展平台 (form/workflow/dashboard) permissions, so any deploy path that ran
``python seed.py`` left roles/menus missing those features.

It is now a thin shim that delegates to the one canonical seed so the two can
never diverge again. It runs in PRODUCTION mode (no demo customers/projects),
matching the historical intent of ``python seed.py`` on a real install.

Prefer calling the canonical seed directly:
    python -m scripts.seed                # dev/demo — includes demo customers/projects
    python -m scripts.seed --production   # production — permissions/roles/admin only
"""
import asyncio
import os
import sys

# Ensure the backend dir is importable so `scripts.seed` resolves regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.seed import seed  # noqa: E402

if __name__ == "__main__":
    asyncio.run(seed(include_demo=False))
