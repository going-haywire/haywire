# packages/haywire-app/src/haywire_studio/editors/console_editor.py
"""
ConsoleEditor — scrollable log output panel.

Displays application log messages using NiceGUI's ui.log widget.
Subscribed to the Python root logger via a logging.Handler.
"""

import logging
from typing import TYPE_CHECKING

from nicegui import ui

from haywire.ui.editor.decorator import editor
from haywire.ui.editor.base import BaseEditor

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent


class _LogHandler(logging.Handler):
    """Forwards log records to a NiceGUI ui.log element."""

    def __init__(self, log_element):
        super().__init__()
        self._log = log_element

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._log.push(msg)
        except Exception:
            pass


@editor(
    registry_id='console',
    label='Console',
    icon='terminal',
    default_area='bottom',
    description='Application log output. Captures Python logging messages.',
)
class ConsoleEditor(BaseEditor):
    """
    Renders a scrollable log panel capturing Python log output.

    Uses a logging.Handler attached to the root logger so it receives
    all log messages from the application, regardless of origin.
    """

    def __init__(self):
        self._log_element = None
        self._handler: _LogHandler | None = None

    def render(self, container, context: 'SessionContext') -> None:
        with container:
            self._log_element = ui.log(max_lines=500).classes(
                'w-full h-full font-mono text-xs p-2'
            ).style('background: var(--hw-console-bg); color: var(--hw-console-text);')
        self._handler = _LogHandler(self._log_element)
        self._handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S')
        )
        logging.getLogger().addHandler(self._handler)
        logging.getLogger().info('Console editor connected.')

    def on_context_changed(self, event: 'ContextChangedEvent', context: 'SessionContext') -> None:
        pass  # Console does not react to context changes

    def cleanup(self) -> None:
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None
        self._log_element = None
