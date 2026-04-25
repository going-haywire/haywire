# haywire/core/debug/keys.py
"""Shared namespace constants for the debug/logging subsystem.

Imported by BaseLibrary, LoggingConfigurator, and DebugSettingsPanel so that
the debug.library.* key structure is never duplicated as bare strings.
"""

from haywire.core.namespaces import NAMESPACE_LIBRARY_LOG

LIBRARY_LOG_LEVEL_SUFFIX = "log_level"
LIBRARY_LOG_LEVEL_FIELD_METATADATA_KEY = "module_name"


def library_log_key(lib_id: str) -> str:
    """Return the full settings key for a library's log level override.

    Example: library_log_key("haybale_studio") → "debug.library.haybale_studio.log_level"
    """
    return f"{NAMESPACE_LIBRARY_LOG}.{lib_id}.{LIBRARY_LOG_LEVEL_SUFFIX}"


def lib_id_from_key(key: str) -> str | None:
    """Extract lib_id from a debug.library.<lib_id>.log_level key, or None if not matching.

    Example: library_log_key("debug.library.haybale_studio.log_level") → "haybale_studio"
    """
    prefix = NAMESPACE_LIBRARY_LOG + "."
    suffix = "." + LIBRARY_LOG_LEVEL_SUFFIX
    if key.startswith(prefix) and key.endswith(suffix):
        return key[len(prefix) : -len(suffix)]
    return None
