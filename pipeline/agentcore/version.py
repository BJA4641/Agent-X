"""agentcore/version.py — v5.9.8 REQ-VERSION-1: ONE version constant.

Why this exists
---------------
The platform carried THREE independent version numbers:
  1. workers/runner.py         VERSION = "5.9.7"
  2. web/app/api/version/route.ts  WEB_VERSION = "5.9.4"   (hardcoded, never bumped)
  3. ops.heartbeat job payload  — frozen at whichever boot started that chain

The banner reads (1) via worker_health and (2) directly, so after deploying
5.9.7 it still displayed "5.9.4" — correctly, because nobody had ever bumped the
web constant. Three sources of truth means the version display can never be
trusted, which makes deploy verification impossible.

Now: repo-root `version.json` is the only place a version is written. Python
reads it here; the web layer imports the same JSON. Bump one file, everything
agrees.
"""
from __future__ import annotations
import json
import os

_FALLBACK = "5.9.8"


# Canonical file lives in web/ so the Next.js build can always resolve it
# (a repo-root file would be outside the Vercel root directory and break the
# build). Python is the flexible reader, so Python does the searching.
_CANDIDATES = ("../../../web/version.json", "../../web/version.json",
               "../../../version.json", "../../version.json", "../version.json")


def _read() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in _CANDIDATES:
        path = os.path.normpath(os.path.join(here, rel))
        try:
            with open(path, "r", encoding="utf-8") as fh:
                v = (json.load(fh) or {}).get("version")
                if v:
                    return str(v)
        except Exception:
            continue
    return _FALLBACK


VERSION = _read()
__version__ = VERSION
