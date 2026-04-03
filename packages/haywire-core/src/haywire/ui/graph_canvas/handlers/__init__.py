"""
Canvas event handler objects for GraphCanvasManager.

Each module provides a focused handler class that owns the state and
dependencies relevant to one concern:

- interaction.py   — drag events, edge click
- selection.py     — selection state, clipboard (copy/paste)
- visual_layer.py  — node/edge visual registry, graph sync
- context_menu.py  — context menu routing via IContextMenuProvider
"""
