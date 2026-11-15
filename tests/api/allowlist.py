"""The internal imports each migrated library in ``barn/`` still has (ADR 0084).

``module:name`` per import, sorted. ``test_internal_imports.py`` compares the
lists with the code. A list only shrinks: a name leaves it when the library
stops using it or when the name enters the Author API.
"""

INTERNAL_IMPORTS: dict[str, list[str]] = {
    "haybale-audio": [],
    "haybale-core": [],
    "haybale-example": [],
    "haybale-haystack": [
        "haywire.core.di.config:get_library_system",
        "haywire.core.di.context:get_node_factory",
        "haywire.core.di.context:get_workspace_root",
        "haywire.core.execution.compile_result:CompileResult",
        "haywire.core.execution.flow_metrics:FlowMeterSampler",
        "haywire.core.execution.flow_metrics:FlowReading",
        "haywire.core.execution.flow_metrics:MeterReading",
        "haywire.core.execution.flow_metrics:Severity",
        "haywire.core.execution.interpreter:Interpreter",
        "haywire.core.graph.editor:Editor",
        "haywire.core.graph.scheduler:LoopScheduler",
        "haywire.core.graph.types:ChangeReason",
        "haywire.core.graph.validation:ValidationResult",
        "haywire.core.macro.promote:macro_document",
        "haywire.core.macro.source:count_placements",
        "haywire.core.macro.source:macro_edit_refusal",
        "haywire.core.macro.source:macro_source_path",
        "haywire.core.macro.source:macro_template",
        "haywire.core.macro.source:modified_instance_origin",
        "haywire.core.macro.source:origin_label",
        "haywire.core.node.factory:NodeFactory",
        "haywire.core.session:IAppState",
        "haywire.core.signals:GraphSaved",
        "haywire.core.state:LibraryStateContainer",
        "haywire.core.workspace:default_save_dir",
        "haywire.ui.components.popup:Popup",
        "haywire.ui.modals:pick_modal",
        "haywire.ui.modals:rename_modal",
    ],
    "haybale-image": [],
    "haybale-models": [],
}
