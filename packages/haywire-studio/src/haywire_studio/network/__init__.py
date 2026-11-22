"""Studio networking: peer filtering, TLS material, host names, and the listening port."""

# The setting itself is declared by haybale-studio; the app reads it by key.
from __future__ import annotations

STUDIO_PORT_KEY = "network.port"
DEFAULT_STUDIO_PORT = 8124
