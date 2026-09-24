"""Writing new components into a library: which libraries may receive them, what
would be written, the write itself, and whether the result registered.

Every function here is free of UI calls, so the New Node wizard, Promote to
Macro and Farmhand's authoring tools share one pipeline.
"""

from .deps import linked_additions, undeclared_imports
from .node_clone import (
    NodeFields,
    NodePlan,
    class_name_refusal,
    default_fields,
    is_clone_source,
    link_libraries,
    list_clone_sources,
    module_stem,
    plan_node,
    suggest_class_name,
    write_node,
)
from .registration import DEFAULT_TIMEOUT_S, RegistrationOutcome, RegistrationWatch
from .targets import AuthoringTarget, authoring_targets

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "AuthoringTarget",
    "NodeFields",
    "NodePlan",
    "RegistrationOutcome",
    "RegistrationWatch",
    "authoring_targets",
    "class_name_refusal",
    "default_fields",
    "is_clone_source",
    "link_libraries",
    "linked_additions",
    "list_clone_sources",
    "module_stem",
    "plan_node",
    "suggest_class_name",
    "undeclared_imports",
    "write_node",
]
