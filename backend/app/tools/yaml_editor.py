from __future__ import annotations

import difflib
import fnmatch
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from app import config
from app.models.schemas import ToolResult, YamlModification

logger = logging.getLogger(__name__)

_yaml = YAML()
_yaml.preserve_quotes = True


def load_yaml(text: str) -> dict:
    return _yaml.load(StringIO(text)) or {}


def dump_yaml(data: dict) -> str:
    stream = StringIO()
    _yaml.dump(data, stream)
    return stream.getvalue()


def is_path_allowed(path: str) -> bool:
    """수정 경로가 화이트리스트에 포함되는지 확인한다."""
    allowed = config.ALLOWED_MODIFY_PATHS
    if allowed is None:
        allowed = config.DEFAULT_MODIFY_PATHS

    for pattern in allowed:
        if pattern == path:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if path == prefix or path.startswith(prefix + "."):
                return True
            continue
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def apply_modification(yaml_text: str, modification: YamlModification) -> ToolResult:
    if not is_path_allowed(modification.path):
        return ToolResult(
            tool="yaml_modify",
            success=False,
            error=f"수정이 허용되지 않은 경로입니다: {modification.path}",
        )

    try:
        data = load_yaml(yaml_text)
        keys = modification.path.split(".")
        target = data
        for key in keys[:-1]:
            if key not in target:
                return ToolResult(
                    tool="yaml_modify",
                    success=False,
                    error=f"경로를 찾을 수 없음: {modification.path}",
                )
            target = target[key]

        final_key = keys[-1]
        old_value = target.get(final_key, "<없음>")
        target[final_key] = modification.value

        new_text = dump_yaml(data)
        return ToolResult(
            tool="yaml_modify",
            success=True,
            data={
                "modified_yaml": new_text,
                "changed_field": modification.path,
                "old_value": old_value,
                "new_value": modification.value,
            },
        )
    except Exception as e:
        return ToolResult(tool="yaml_modify", success=False, error=str(e))


def generate_diff(original: str, modified: str) -> str:
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile="original-values.yaml",
        tofile="modified-values.yaml",
    )
    return "".join(diff)


def save_values(release: str, yaml_text: str, original_text: str | None = None) -> ToolResult:
    try:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{release}-values-{timestamp}.yaml"
        filepath = config.OUTPUTS_DIR / filename
        filepath.write_text(yaml_text, encoding="utf-8")

        backup_path = None
        if original_text:
            backup_name = f"{release}-values-{timestamp}.backup.yaml"
            backup_filepath = config.OUTPUTS_DIR / backup_name
            backup_filepath.write_text(original_text, encoding="utf-8")
            backup_path = str(backup_filepath)
            logger.info("백업 저장: %s", backup_path)

        return ToolResult(
            tool="yaml_save",
            success=True,
            data={
                "path": str(filepath),
                "filename": filename,
                "backup_path": backup_path,
            },
        )
    except Exception as e:
        return ToolResult(tool="yaml_save", success=False, error=str(e))
