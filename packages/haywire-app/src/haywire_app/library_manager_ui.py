"""
NiceGUI-based library management page.

Provides a /libraries route with:
- Installed libraries panel (enable/disable/uninstall)
- Marketplace panel (browse/install from manifest)
"""

from nicegui import ui

from .library_manager import LibraryManager, MarketplaceEntry


# Sample marketplace manifest for mockup purposes
SAMPLE_MARKETPLACE_TOML = '''
[[packages]]
name = "haybale-opencv"
version = "0.2.0"
description = "OpenCV nodes for image processing — filters, transforms, video I/O"
author = "community"
source = "pypi"
install_spec = "haybale-opencv>=0.2.0"
tags = ["image", "video", "opencv"]

[[packages]]
name = "haybale-audio"
version = "0.1.0"
description = "Audio processing nodes — FFT, filters, playback, recording"
author = "community"
source = "git"
install_spec = "git+https://github.com/example/haybale-audio.git"
tags = ["audio", "dsp"]

[[packages]]
name = "haybale-mqtt"
version = "0.3.0"
description = "MQTT client nodes for IoT and messaging"
author = "community"
source = "pypi"
install_spec = "haybale-mqtt>=0.3.0"
tags = ["iot", "mqtt", "network"]

[[packages]]
name = "haybale-osc"
version = "0.2.1"
description = "OSC (Open Sound Control) send/receive nodes"
author = "community"
source = "pypi"
install_spec = "haybale-osc>=0.2.1"
tags = ["osc", "network", "music"]
'''


class LibraryManagerPage:
    """NiceGUI page for library management."""

    def __init__(self, library_manager: LibraryManager):
        self.manager = library_manager
        self._installed_container = None
        self._marketplace_container = None
        self._status_label = None

    def create_page(self):
        """Build the /libraries page UI."""
        with ui.column().classes('w-full max-w-5xl mx-auto p-6 gap-6'):
            # Header
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Library Manager').classes('text-2xl font-bold')
                with ui.row().classes('gap-2'):
                    ui.button(
                        'Back to Editor',
                        icon='arrow_back',
                        on_click=lambda: ui.navigate.to('/'),
                    ).props('flat')
                    ui.button(
                        'Refresh',
                        icon='refresh',
                        on_click=self._refresh_all,
                    ).props('flat')

            self._status_label = ui.label('').classes(
                'text-sm text-gray-500'
            )

            # Two-column layout
            with ui.row().classes('w-full gap-6'):
                # Installed libraries
                with ui.card().classes('flex-1'):
                    ui.label('Installed Libraries').classes(
                        'text-lg font-bold mb-4'
                    )
                    self._installed_container = ui.column().classes(
                        'w-full gap-2'
                    )
                    self._render_installed()

                # Marketplace
                with ui.card().classes('flex-1'):
                    ui.label('Marketplace').classes(
                        'text-lg font-bold mb-4'
                    )
                    self._marketplace_container = ui.column().classes(
                        'w-full gap-2'
                    )
                    self._render_marketplace()

    def _set_status(self, message: str, msg_type: str = 'info'):
        """Update the status bar."""
        if self._status_label:
            self._status_label.text = message
        color_map = {
            'info': 'info',
            'success': 'positive',
            'error': 'negative',
            'warning': 'warning',
        }
        ui.notify(message, type=color_map.get(msg_type, 'info'))

    def _refresh_all(self):
        """Refresh both panels."""
        self._render_installed()
        self._render_marketplace()
        self._set_status('Refreshed')

    def _render_library_card(
        self,
        name: str,
        version: str,
        description: str,
        author: str,
        tags: list[str],
        badge_text: str,
        badge_color: str,
        actions_builder,
    ):
        """Render a library card with consistent layout.

        Args:
            name: Display name / label.
            version: Version string.
            description: One-line description.
            author: Author name (shown if non-empty).
            tags: List of tag strings.
            badge_text: Text for the source/type badge.
            badge_color: Color for the badge.
            actions_builder: Callable that emits action buttons
                into the current UI context.
        """
        with ui.card().classes('w-full p-3'):
            # Title row: name + version + badge ... actions on the right
            with ui.row().classes(
                'w-full items-center justify-between'
            ):
                with ui.row().classes('items-center gap-2'):
                    ui.label(name).classes('font-medium')
                    if version:
                        ui.label(f'v{version}').classes(
                            'text-xs text-gray-400'
                        )
                    ui.badge(
                        badge_text,
                        color=badge_color,
                    ).props('outline')

                # Action buttons aligned right
                with ui.row().classes('gap-1'):
                    actions_builder()

            # Description
            if description:
                ui.label(description).classes(
                    'text-sm text-gray-600'
                )

            # Metadata row
            if author:
                ui.label(f'By {author}').classes(
                    'text-xs text-gray-400'
                )

            # Tags
            if tags:
                with ui.row().classes('gap-1 mt-1'):
                    for tag in tags:
                        ui.badge(tag).props('outline color=grey')

    def _render_installed(self):
        """Render the installed libraries list."""
        if not self._installed_container:
            return

        self._installed_container.clear()
        libraries = self.manager.list_installed()

        with self._installed_container:
            if not libraries:
                ui.label('No libraries discovered').classes(
                    'text-gray-500 italic'
                )
                return

            ui.label(f'{len(libraries)} libraries found').classes(
                'text-sm text-gray-500 mb-2'
            )

            for lib in sorted(libraries, key=lambda x: x.label):
                # Badge shows install type
                type_colors = {
                    'EDITABLE': 'purple',
                    'REGULAR': 'blue',
                    'FOLDER': 'teal',
                }
                badge_color = type_colors.get(lib.install_type, 'grey')

                def make_actions(lib=lib):
                    if lib.enabled:
                        ui.button(
                            'Disable',
                            icon='pause',
                            on_click=lambda lid=lib.library_id: (
                                self._disable_library(lid)
                            ),
                        ).props('size=sm color=orange flat')
                    else:
                        ui.button(
                            'Enable',
                            icon='play_arrow',
                            on_click=lambda lid=lib.library_id: (
                                self._enable_library(lid)
                            ),
                        ).props('size=sm color=green flat')

                    if lib.install_type in ('REGULAR', 'EDITABLE'):
                        ui.button(
                            icon='delete',
                            on_click=lambda lid=lib.library_id, ln=lib.label: (
                                self._confirm_uninstall(lid, ln)
                            ),
                        ).props('size=sm color=red flat round')

                self._render_library_card(
                    name=lib.label,
                    version=lib.version,
                    description=lib.description,
                    author=lib.author,
                    tags=lib.tags,
                    badge_text=lib.install_type.lower(),
                    badge_color=badge_color,
                    actions_builder=make_actions,
                )

    def _render_marketplace(self):
        """Render the marketplace panel with sample packages."""
        if not self._marketplace_container:
            return

        self._marketplace_container.clear()

        # Parse sample manifest
        import toml as toml_lib
        data = toml_lib.loads(SAMPLE_MARKETPLACE_TOML)
        packages = [
            MarketplaceEntry(**pkg) for pkg in data.get('packages', [])
        ]

        # Get installed library names for comparison
        installed_names = {
            lib.library_id for lib in self.manager.list_installed()
        }

        with self._marketplace_container:
            ui.label(
                'Browse available haybale libraries'
            ).classes('text-sm text-gray-500 mb-2')

            ui.input(
                placeholder='Search packages...',
            ).classes('w-full mb-3').props('dense clearable')

            for pkg in packages:
                pkg_id = pkg.name.replace('haybale-', '')
                is_installed = pkg_id in installed_names or (
                    pkg.name in installed_names
                )

                source_color = (
                    'blue' if pkg.source == 'pypi' else 'purple'
                )

                def make_actions(
                    pkg=pkg, is_installed=is_installed
                ):
                    if is_installed:
                        ui.label('Installed').classes(
                            'text-green-500 text-sm font-medium'
                        )
                    else:
                        ui.button(
                            'Install',
                            icon='download',
                            on_click=lambda spec=pkg.install_spec, n=pkg.name: (
                                self._install_package(spec, n)
                            ),
                        ).props('size=sm color=primary')

                self._render_library_card(
                    name=pkg.name,
                    version=pkg.version,
                    description=pkg.description,
                    author=pkg.author,
                    tags=pkg.tags,
                    badge_text=pkg.source,
                    badge_color=source_color,
                    actions_builder=make_actions,
                )

    def _enable_library(self, library_id: str):
        """Enable a library and refresh."""
        self.manager.registry.enable_library(library_id)
        self._set_status(f"Enabled: {library_id}", 'success')
        self._render_installed()

    def _disable_library(self, library_id: str):
        """Disable a library and refresh."""
        self.manager.registry.disable_library(library_id)
        self._set_status(f"Disabled: {library_id}", 'warning')
        self._render_installed()

    def _confirm_uninstall(self, library_id: str, label: str):
        """Show confirmation dialog before uninstalling."""
        with ui.dialog() as dialog, ui.card():
            ui.label(f'Uninstall {label}?').classes('text-lg font-bold')
            ui.label(
                'This will disable the library and remove it from '
                'the venv. Any graph nodes using this library will '
                'show as errors.'
            ).classes('text-gray-600 mb-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Uninstall',
                    on_click=lambda: (
                        self._do_uninstall(library_id, label),
                        dialog.close(),
                    ),
                ).props('color=negative')
        dialog.open()

    def _do_uninstall(self, library_id: str, label: str):
        """Perform the uninstall."""
        success, message = self.manager.uninstall(library_id)
        if success:
            self._set_status(f"Uninstalled: {label}", 'success')
        else:
            self._set_status(message, 'error')
        self._refresh_all()

    def _install_package(self, install_spec: str, name: str):
        """Install a package from the marketplace."""
        self._set_status(f"Installing {name}...", 'info')

        success, message = self.manager.install(install_spec)
        if success:
            self._set_status(f"Installed: {name}", 'success')
        else:
            self._set_status(message, 'error')
        self._refresh_all()
