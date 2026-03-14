from __future__ import annotations

import logging

from kubernetes import client, config as k8s_config
from kubernetes.client.rest import ApiException

from app import config
from app.models.schemas import ContainerInfo, PodData, ToolResult

logger = logging.getLogger(__name__)

_api: client.CoreV1Api | None = None


def _check_namespace(namespace: str) -> None:
    allowed = config.ALLOWED_NAMESPACES
    if allowed and namespace not in allowed:
        raise PermissionError(f"허용되지 않은 namespace: {namespace}")


def _get_api() -> client.CoreV1Api:
    global _api
    if _api is None:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        _api = client.CoreV1Api()
    return _api


def get_pod_status(pod_name: str, namespace: str = "default") -> ToolResult:
    _check_namespace(namespace)
    try:
        api = _get_api()
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)

        containers = [
            ContainerInfo(
                name=cs.name,
                ready=cs.ready,
                restart_count=cs.restart_count,
                state=_extract_container_state(cs.state),
                last_state=_extract_container_state(cs.last_state),
                resources=_extract_resources(_find_container_spec(pod.spec.containers, cs.name)),
            )
            for cs in (pod.status.container_statuses or [])
        ]

        data = PodData(
            name=pod.metadata.name,
            namespace=pod.metadata.namespace,
            phase=pod.status.phase,
            conditions=[
                {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
                for c in (pod.status.conditions or [])
            ],
            containers=containers,
        )
        return ToolResult(tool="get_pod_status", success=True, data=data.model_dump())
    except ApiException as e:
        return ToolResult(tool="get_pod_status", success=False, error=f"K8s API 오류: {e.status} {e.reason}")
    except Exception as e:
        return ToolResult(tool="get_pod_status", success=False, error=str(e))


def get_pod_logs(
    pod_name: str, namespace: str = "default", tail_lines: int = 80
) -> ToolResult:
    _check_namespace(namespace)
    try:
        api = _get_api()
        logs = api.read_namespaced_pod_log(
            name=pod_name, namespace=namespace, tail_lines=tail_lines,
        )
        return ToolResult(tool="get_pod_logs", success=True, data=logs)
    except ApiException as e:
        return ToolResult(tool="get_pod_logs", success=False, error=f"K8s API 오류: {e.status} {e.reason}")
    except Exception as e:
        return ToolResult(tool="get_pod_logs", success=False, error=str(e))


def get_pod_previous_logs(
    pod_name: str, namespace: str = "default", tail_lines: int = 80
) -> ToolResult:
    _check_namespace(namespace)
    try:
        api = _get_api()
        logs = api.read_namespaced_pod_log(
            name=pod_name, namespace=namespace, tail_lines=tail_lines, previous=True,
        )
        return ToolResult(tool="get_pod_previous_logs", success=True, data=logs)
    except ApiException as e:
        if e.status == 400:
            return ToolResult(tool="get_pod_previous_logs", success=True, data=None)
        return ToolResult(tool="get_pod_previous_logs", success=False, error=f"K8s API 오류: {e.status} {e.reason}")
    except Exception as e:
        return ToolResult(tool="get_pod_previous_logs", success=False, error=str(e))


def get_pod_events(pod_name: str, namespace: str = "default") -> ToolResult:
    _check_namespace(namespace)
    try:
        api = _get_api()
        field = f"involvedObject.name={pod_name}"
        events = api.list_namespaced_event(namespace=namespace, field_selector=field)
        data = [
            {
                "type": ev.type,
                "reason": ev.reason,
                "message": ev.message,
                "source": ev.source.component if ev.source else None,
                "count": ev.count,
                "last_seen": ev.last_timestamp.isoformat() if ev.last_timestamp else None,
            }
            for ev in events.items
        ]
        return ToolResult(tool="get_pod_events", success=True, data=data)
    except ApiException as e:
        return ToolResult(tool="get_pod_events", success=False, error=f"K8s API 오류: {e.status} {e.reason}")
    except Exception as e:
        return ToolResult(tool="get_pod_events", success=False, error=str(e))


def _extract_container_state(state) -> dict:
    if state is None:
        return {"status": "unknown"}
    if state.running:
        return {
            "status": "running",
            "started_at": state.running.started_at.isoformat() if state.running.started_at else None,
        }
    if state.waiting:
        return {"status": "waiting", "reason": state.waiting.reason, "message": state.waiting.message}
    if state.terminated:
        return {
            "status": "terminated",
            "reason": state.terminated.reason,
            "exit_code": state.terminated.exit_code,
            "finished_at": state.terminated.finished_at.isoformat() if state.terminated.finished_at else None,
        }
    return {"status": "unknown"}


def _find_container_spec(specs, name: str):
    for s in specs or []:
        if s.name == name:
            return s
    return None


def _extract_resources(spec) -> dict:
    if spec is None or spec.resources is None:
        return {"limits": {}, "requests": {}}
    return {
        "limits": dict(spec.resources.limits or {}),
        "requests": dict(spec.resources.requests or {}),
    }
