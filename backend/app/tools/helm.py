from __future__ import annotations

import asyncio
import json
import logging

from app import config
from app.models.schemas import ToolResult

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {"get values", "list", "get manifest", "get notes"}


async def _run_helm(args: list[str], timeout: int | None = None) -> tuple[str, str, int]:
    cmd_str = " ".join(args[:2]) if len(args) >= 2 else args[0] if args else ""
    if not any(cmd_str.startswith(allowed) for allowed in ALLOWED_COMMANDS):
        raise PermissionError(f"허용되지 않은 Helm 명령어: {cmd_str}")

    proc = await asyncio.create_subprocess_exec(
        config.HELM_BINARY, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(),
        timeout=timeout or config.COMMAND_TIMEOUT,
    )
    return stdout.decode(), stderr.decode(), proc.returncode or 0


async def get_values(release: str, namespace: str = "default") -> ToolResult:
    try:
        stdout, stderr, rc = await _run_helm(
            ["get", "values", release, "-n", namespace, "-o", "yaml"]
        )
        if rc != 0:
            return ToolResult(tool="helm_get_values", success=False, error=stderr.strip())
        return ToolResult(tool="helm_get_values", success=True, data=stdout)
    except PermissionError as e:
        return ToolResult(tool="helm_get_values", success=False, error=str(e))
    except asyncio.TimeoutError:
        return ToolResult(tool="helm_get_values", success=False, error="Helm 명령 타임아웃")
    except Exception as e:
        return ToolResult(tool="helm_get_values", success=False, error=str(e))


async def list_releases(namespace: str | None = None) -> ToolResult:
    try:
        args = ["list", "-o", "json"]
        if namespace:
            args += ["-n", namespace]
        else:
            args += ["-A"]

        stdout, stderr, rc = await _run_helm(args)
        if rc != 0:
            return ToolResult(tool="helm_list", success=False, error=stderr.strip())
        releases = json.loads(stdout)
        return ToolResult(tool="helm_list", success=True, data=releases)
    except Exception as e:
        return ToolResult(tool="helm_list", success=False, error=str(e))


def generate_upgrade_command(release: str, namespace: str, values_path: str) -> str:
    return f"helm upgrade {release} <CHART> -n {namespace} -f {values_path}"
