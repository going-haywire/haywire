# haywire/core/tooling/settings.py
"""How Haywire hands work off to the developer's own tools."""

from haywire.barn.builtin.types import STRING
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class ExternalToolsSettings(FrameworkSettings, namespace="tools"):
    """Commands Haywire shells out to.

    "Editor" here means the developer's text editor (VS Code, vim, …); the graph
    editor is unrelated, which is why this lives apart from the canvas/interaction
    settings.
    """

    external_editor_command = setting[STRING](
        "code --goto {file}:{line}",
        label="External Editor Command",
        description=(
            "Command template for opening files externally. "
            "{file} and {line} are substituted. If empty, the per-OS fallback editor list is used."
        ),
        category="tools",
    )
