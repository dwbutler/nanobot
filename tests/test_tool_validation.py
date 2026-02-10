from typing import Any
from pathlib import Path

import pytest

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.filesystem import _resolve_path
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import _validate_url


class SampleTool(Tool):
    @property
    def name(self) -> str:
        return "sample"

    @property
    def description(self) -> str:
        return "sample tool"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2},
                "count": {"type": "integer", "minimum": 1, "maximum": 10},
                "mode": {"type": "string", "enum": ["fast", "full"]},
                "meta": {
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string"},
                        "flags": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["tag"],
                },
            },
            "required": ["query", "count"],
        }

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


def test_validate_params_missing_required() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi"})
    assert "missing required count" in "; ".join(errors)


def test_validate_params_type_and_range() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi", "count": 0})
    assert any("count must be >= 1" in e for e in errors)

    errors = tool.validate_params({"query": "hi", "count": "2"})
    assert any("count should be integer" in e for e in errors)


def test_validate_params_enum_and_min_length() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "h", "count": 2, "mode": "slow"})
    assert any("query must be at least 2 chars" in e for e in errors)
    assert any("mode must be one of" in e for e in errors)


def test_validate_params_nested_object_and_array() -> None:
    tool = SampleTool()
    errors = tool.validate_params(
        {
            "query": "hi",
            "count": 2,
            "meta": {"flags": [1, "ok"]},
        }
    )
    assert any("missing required meta.tag" in e for e in errors)
    assert any("meta.flags[0] should be string" in e for e in errors)


def test_validate_params_ignores_unknown_fields() -> None:
    tool = SampleTool()
    errors = tool.validate_params({"query": "hi", "count": 2, "extra": "x"})
    assert errors == []


async def test_registry_returns_validation_error() -> None:
    reg = ToolRegistry()
    reg.register(SampleTool())
    result = await reg.execute("sample", {"query": "hi"})
    assert "Invalid parameters" in result


def test_filesystem_blocks_prefix_bypass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    sibling = tmp_path / "workspace_evil"
    workspace.mkdir()
    sibling.mkdir()

    inside = workspace / "safe.txt"
    outside = sibling / "escape.txt"

    assert _resolve_path(str(inside), workspace) == inside.resolve()

    with pytest.raises(PermissionError):
        _resolve_path(str(outside), workspace)


@pytest.mark.asyncio
async def test_exec_blocks_outside_working_dir_when_restricted(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()

    tool = ExecTool(working_dir=str(workspace), restrict_to_workspace=True, timeout=1)
    result = await tool.execute("pwd", working_dir=str(outside))
    assert "working_dir outside workspace" in result


@pytest.mark.asyncio
async def test_exec_blocks_absolute_paths_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    tool = ExecTool(working_dir=str(workspace), restrict_to_workspace=True, timeout=1)
    result = await tool.execute("cat /etc/passwd")
    assert "path outside workspace" in result


@pytest.mark.asyncio
async def test_exec_blocks_sudo_by_default(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    tool = ExecTool(working_dir=str(workspace), timeout=1)
    result = await tool.execute("sudo ls")
    assert "dangerous pattern" in result


@pytest.mark.asyncio
async def test_exec_allow_patterns_enforced(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    tool = ExecTool(
        working_dir=str(workspace),
        timeout=1,
        allow_patterns=[r"^echo\b"],
    )
    result = await tool.execute("ls")
    assert "not in allowlist" in result


def test_web_validate_blocks_local_and_private_urls() -> None:
    ok, _ = _validate_url("https://127.0.0.1")
    assert ok is False

    ok, _ = _validate_url("http://localhost")
    assert ok is False

    ok, _ = _validate_url("http://169.254.169.254/latest/meta-data")
    assert ok is False
