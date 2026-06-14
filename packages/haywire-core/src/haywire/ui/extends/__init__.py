"""Element-attaching behavior helpers (aspects), e.g. CodeMirror code intelligence.

Unlike haywire.ui.components.* (self-contained Vue-backed ui.element subclasses),
modules here attach behavior to an existing element they do not own — no .vue,
no render surface; just helpers like attach_code_intelligence().
"""
