# haywire/core/tooling/settings.py
"""How Haywire hands work off to the developer's own tools."""

from haywire.barn.builtin.types import STRING
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class ExternalToolsSettings(FrameworkSettings, namespace="tools"):
    """Commands Haywire shells out to.

    "Editor" here means the developer's text editor (VS Code, vim, …), NOT the
    graph editor — the two are unrelated, which is why this does not live
    beside the canvas/interaction settings. Fields are named from the tool's
    point of view (``editor_command``), so the namespace supplies the
    "external" half.
    """

    editor_command = setting[STRING](
        "code --goto {file}:{line}",
        label="External Editor Command",
        description=(
            "Command template for opening files externally. "
            "{file} and {line} are substituted. If empty, the per-OS fallback editor list is used."
        ),
        category="tools",
    )
