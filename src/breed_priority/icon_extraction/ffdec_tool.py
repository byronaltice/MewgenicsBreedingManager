"""Discovery and validation for JPEXS Free Flash Decompiler (FFDEC) + Java.

The Mewgenics Breeding Manager shells out to FFDEC's CLI to rasterize ability
sprite frames out of ``ability_icons.swf``. FFDEC is a Java jar; the operator
must have a JRE/JDK installed. This module locates both.

No Qt imports — pure stdlib so the icon_extraction package stays standalone.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from typing import Optional

from .. import app_settings


# ── Default search locations ──────────────────────────────────────────────────

_DEFAULT_FFDEC_JAR_PATHS = (
    r"C:\Program Files\FFDec\ffdec.jar",
    r"C:\Program Files (x86)\FFDec\ffdec.jar",
    # Last-resort fallback: the PoC dir the operator already has set up.
    r"C:\Users\Byron\AppData\Local\Temp\ffdec-poc\ffdec.jar",
)

_MICROSOFT_JDK_GLOB = r"C:\Program Files\Microsoft\jdk-*\bin\java.exe"
_ECLIPSE_JDK_GLOB = r"C:\Program Files\Eclipse Adoptium\jdk-*\bin\java.exe"
_JAVA_EXE_NAME = "java.exe"
_VALIDATE_TIMEOUT_SECS = 15


# ── Java discovery ────────────────────────────────────────────────────────────

def find_java() -> Optional[str]:
    """Return the absolute path to a usable ``java`` executable, or None."""
    saved = app_settings.get_java_exe_path()
    if saved and os.path.isfile(saved):
        return saved

    on_path = shutil.which("java")
    if on_path:
        return on_path

    for pattern in (_MICROSOFT_JDK_GLOB, _ECLIPSE_JDK_GLOB):
        matches = sorted(glob.glob(pattern), reverse=True)  # newest version first
        for candidate in matches:
            if os.path.isfile(candidate):
                return candidate

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = os.path.join(java_home, "bin", _JAVA_EXE_NAME)
        if os.path.isfile(candidate):
            return candidate

    return None


# ── FFDEC discovery ───────────────────────────────────────────────────────────

def find_ffdec() -> Optional[str]:
    """Return the absolute path to ``ffdec.jar`` if available, else None."""
    saved = app_settings.get_ffdec_jar_path()
    if saved and os.path.isfile(saved):
        return saved

    for candidate in _DEFAULT_FFDEC_JAR_PATHS:
        if os.path.isfile(candidate):
            return candidate

    return None


# ── Validation ────────────────────────────────────────────────────────────────

def validate(java_exe: str, ffdec_jar: str) -> tuple[bool, str]:
    """Run ``java -jar ffdec.jar -help`` to confirm both binaries work."""
    if not java_exe or not os.path.isfile(java_exe):
        return False, f"Java executable not found: {java_exe!r}"
    if not ffdec_jar or not os.path.isfile(ffdec_jar):
        return False, f"FFDEC jar not found: {ffdec_jar!r}"
    try:
        completed = subprocess.run(
            [java_exe, "-jar", ffdec_jar, "-help"],
            capture_output=True,
            timeout=_VALIDATE_TIMEOUT_SECS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "FFDEC -help command timed out."
    except OSError as exc:
        return False, f"Could not launch Java: {exc}"
    out = (completed.stdout or b"") + (completed.stderr or b"")
    if b"JPEXS" in out or b"ffdec" in out.lower():
        return True, ""
    return False, "FFDEC did not respond as expected to -help."
