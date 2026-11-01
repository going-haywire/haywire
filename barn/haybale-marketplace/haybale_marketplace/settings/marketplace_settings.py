"""MarketplaceSettings — library-wide settings for installing libraries."""

from haywire.barn.builtin.types import CHOICES
from haywire.core.settings import LibrarySettings, setting, settings

#: Suggested ``--torch-backend`` values; any other value uv accepts can be typed in.
TORCH_BACKENDS = (
    "auto",
    "cpu",
    "cu118",
    "cu126",
    "cu128",
    "cu129",
    "cu130",
    "cu132",
    "rocm6.4",
    "rocm7.0",
    "rocm7.1",
    "rocm7.2",
    "xpu",
)


@settings(namespace="marketplace", label="Marketplace", description="How libraries are installed")
class MarketplaceSettings(LibrarySettings):
    """Settings for installing libraries into this project's environment."""

    torch_backend = setting[CHOICES](
        "auto",
        label="PyTorch backend",
        description=(
            "Which PyTorch build installs fetch: auto (detect this machine's GPU), cpu, "
            "or a CUDA/ROCm version; type another version and press Enter"
        ),
        widget_config={"options": list(TORCH_BACKENDS), "new_value_mode": "add-unique"},
    )
