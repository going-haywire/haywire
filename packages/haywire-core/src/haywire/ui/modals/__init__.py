"""Reusable modal dialogs built on :class:`haywire.ui.components.popup.Popup`."""

from .confirm_modal import confirm_modal
from .diff_modal import DiffSection, diff_modal
from .info_modal import info_modal
from .install_progress_modal import InstallProgressModal, install_progress_modal
from .install_safety_modal import install_safety_modal
from .pick_modal import pick_modal
from .rename_modal import rename_modal
from .save_as_modal import save_as_modal
from .upgrade_impact_modal import upgrade_impact_modal

__all__ = [
    "DiffSection",
    "InstallProgressModal",
    "confirm_modal",
    "diff_modal",
    "info_modal",
    "install_progress_modal",
    "install_safety_modal",
    "pick_modal",
    "rename_modal",
    "save_as_modal",
    "upgrade_impact_modal",
]
