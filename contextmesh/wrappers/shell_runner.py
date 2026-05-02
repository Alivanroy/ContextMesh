"""Thin subprocess wrapper used by the ``contextmesh run`` command."""
from __future__ import annotations

import os
import subprocess
from typing import List, Tuple


def run_shell_command(command: List[str], *, cwd: str | None = None, timeout: int | None = None) -> Tuple[int, str]:
    """Run *command* and return ``(exit_code, combined_output)``."""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            cwd=cwd or os.getcwd(),
            timeout=timeout,
        )
        return result.returncode, result.stdout or ""
    except FileNotFoundError:
        return 127, f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stdout or "")[-500:] if isinstance(exc.stdout, str) else ""
        return 124, f"Command timed out after {timeout}s\n{tail}"
