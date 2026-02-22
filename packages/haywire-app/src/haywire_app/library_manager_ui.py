"""
NiceGUI-based library management page.

Provides a /libraries route with:
- Installed libraries panel (enable/disable/uninstall)
- Marketplace panel (browse/install from manifest)
"""

import asyncio

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
source_url = "https://github.com/example/haybale-opencv"

[[packages]]
name = "haybale-audio"
version = "0.1.0"
description = "Audio processing nodes — FFT, filters, playback, recording"
author = "community"
source = "git"
install_spec = "git+https://github.com/example/haybale-audio.git"
tags = ["audio", "dsp"]
source_url = "https://github.com/example/haybale-audio"

[[packages]]
name = "haybale-mqtt"
version = "0.3.0"
description = "MQTT client nodes for IoT and messaging"
author = "community"
source = "pypi"
install_spec = "haybale-mqtt>=0.3.0"
tags = ["iot", "mqtt", "network"]
source_url = "https://github.com/example/haybale-mqtt"

[[packages]]
name = "haybale-osc"
version = "0.2.1"
description = "OSC (Open Sound Control) send/receive nodes"
author = "community"
source = "pypi"
install_spec = "haybale-osc>=0.2.1"
tags = ["osc", "network", "music"]
source_url = "https://github.com/example/haybale-osc"
'''


class LibraryManagerPage:
    """NiceGUI page for library management."""

    def __init__(self, library_manager: LibraryManager, marketplace_path: str | None = None):
        self.manager = library_manager
        self.marketplace_path = marketplace_path
        self._installed_container = None
        self._marketplace_container = None
        self._status_label = None
        # Maps package/library name → card element for in-card log injection
        self._marketplace_cards: dict[str, ui.card] = {}
        self._installed_cards: dict[str, ui.card] = {}

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
                with ui.card().classes('flex-1 min-w-0'):
                    ui.label('Installed Libraries').classes(
                        'text-lg font-bold mb-4'
                    )
                    self._installed_container = ui.column().classes(
                        'w-full gap-2'
                    )
                    self._render_installed()

                # Marketplace
                with ui.card().classes('flex-1 min-w-0'):
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
    ) -> ui.card:
        """Render a library card with consistent layout.

        Returns the card element so callers can inject content (e.g. log panels).
        """
        with ui.card().classes('w-full p-3 overflow-hidden') as card:
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
        return card

    def _render_installed(self):
        """Render the installed libraries list."""
        if not self._installed_container:
            return

        self._installed_container.clear()
        self._installed_cards.clear()
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

                card = self._render_library_card(
                    name=lib.label,
                    version=lib.version,
                    description=lib.description,
                    author=lib.author,
                    tags=lib.tags,
                    badge_text=lib.install_type.lower(),
                    badge_color=badge_color,
                    actions_builder=make_actions,
                )
                self._installed_cards[lib.library_id] = card

    def _render_marketplace(self):
        """Render the marketplace panel with packages from manifest."""
        if not self._marketplace_container:
            return

        self._marketplace_container.clear()
        self._marketplace_cards.clear()

        # Load from project marketplace file if available, else use sample
        if self.marketplace_path:
            packages = self.manager.load_marketplace(self.marketplace_path)
        else:
            import toml as toml_lib
            data = toml_lib.loads(SAMPLE_MARKETPLACE_TOML)
            packages = [
                MarketplaceEntry(**pkg) for pkg in data.get('packages', [])
            ]

        # Build lookup sets for installed detection (case-insensitive)
        installed_libs = self.manager.list_installed()
        installed_ids = {lib.library_id.lower() for lib in installed_libs}
        installed_dist_names = {
            lib.distribution_name.lower()
            for lib in installed_libs if lib.distribution_name
        }

        with self._marketplace_container:
            ui.label(
                'Browse available haybale libraries'
            ).classes('text-sm text-gray-500 mb-2')

            ui.input(
                placeholder='Search packages...',
            ).classes('w-full mb-3').props('dense clearable')

            for pkg in packages:
                # Check by library ID (strip haybale- prefix) and distribution name
                pkg_id = pkg.name.replace('haybale-', '').lower()
                is_installed = (
                    pkg_id in installed_ids
                    or pkg.name.lower() in installed_ids
                    or pkg.name.lower() in installed_dist_names
                )

                # Check installed version (fast — no network call)
                installed_version = (
                    self.manager.get_installed_version(pkg.name)
                    if is_installed else None
                )
                try:
                    from packaging.version import Version
                    update_available = (
                        is_installed
                        and installed_version is not None
                        and pkg.version
                        and Version(pkg.version) > Version(installed_version)
                    )
                except Exception:
                    update_available = False

                source_color = (
                    'blue' if pkg.source == 'pypi' else 'purple'
                )

                def make_actions(
                    pkg=pkg,
                    is_installed=is_installed,
                    installed_version=installed_version,
                    update_available=update_available,
                ):
                    if is_installed:
                        # Show installed version badge
                        if installed_version:
                            badge_color = 'orange' if update_available else 'green'
                            badge_label = (
                                f'v{installed_version} — update available'
                                if update_available
                                else f'v{installed_version} installed'
                            )
                            ui.badge(badge_label, color=badge_color).props(
                                'outline'
                            ).classes('text-xs')

                        # VS Code-style split uninstall button
                        with ui.row().classes('gap-0 items-center'):
                            ui.button(
                                'Uninstall',
                                on_click=lambda lid=pkg_id, ln=pkg.name: (
                                    self._confirm_uninstall_marketplace(lid, ln)
                                ),
                            ).props('size=sm color=negative flat')
                            with ui.button(icon='arrow_drop_down').props(
                                'size=sm color=negative flat'
                            ):
                                with ui.menu():
                                    if update_available:
                                        ui.menu_item(
                                            f'Update to v{pkg.version}',
                                            on_click=lambda e, spec=pkg.install_spec, n=pkg.name: (
                                                self._install_package(spec, n, e.sender)
                                            ),
                                        )
                                    ui.menu_item(
                                        'Install specific version…',
                                        on_click=lambda p=pkg: (
                                            self._open_version_picker(p)
                                        ),
                                    )
                                    ui.separator()
                                    ui.menu_item(
                                        'Uninstall permanently',
                                        on_click=lambda lid=pkg_id, ln=pkg.name: (
                                            self._confirm_uninstall_marketplace(lid, ln)
                                        ),
                                    )
                    else:
                        ui.button(
                            'Install',
                            icon='download',
                            on_click=lambda e, spec=pkg.install_spec, n=pkg.name: (
                                self._install_package(spec, n, e.sender)
                            ),
                        ).props('size=sm color=primary')

                card = self._render_library_card(
                    name=pkg.name,
                    version=pkg.version,
                    description=pkg.description,
                    author=pkg.author,
                    tags=pkg.tags,
                    badge_text=pkg.source,
                    badge_color=source_color,
                    actions_builder=make_actions,
                )
                self._marketplace_cards[pkg.name] = card

    def _enable_library(self, library_id: str):
        """Enable a library and refresh."""
        self.manager.enable_library(library_id)
        self._set_status(f"Enabled: {library_id}", 'success')
        self._render_installed()

    def _disable_library(self, library_id: str):
        """Disable a library and refresh."""
        self.manager.disable_library(library_id)
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

            async def confirm_and_uninstall():
                dialog.close()
                await self._do_uninstall(library_id, label)

            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close)
                ui.button(
                    'Uninstall',
                    on_click=confirm_and_uninstall,
                ).props('color=negative')
        dialog.open()

    @staticmethod
    def _create_log_in_card(card: ui.card, title: str) -> ui.log:
        """Append an expandable log panel inside an existing card."""
        with card:
            with ui.expansion(
                title, icon='terminal', value=True,
            ).classes('w-full min-w-0'):
                log = ui.log(max_lines=50).classes('w-full h-32')
        return log

    async def _do_uninstall(self, library_id: str, label: str):
        """Perform the uninstall with streaming log output."""
        self._set_status(f"Uninstalling {label}...", 'info')

        card = self._installed_cards.get(library_id)
        if card:
            log = self._create_log_in_card(card, f'Uninstalling {label}...')
        else:
            log = None

        def on_output(line: str):
            if log:
                log.push(line)

        success, message = await self.manager.uninstall_streaming(
            library_id, on_output,
        )

        if success:
            if log:
                log.push(f'--- {label} uninstalled successfully ---')
            self._set_status(f"Uninstalled: {label}", 'success')
        else:
            if log:
                log.push(f'--- ERROR: {message} ---')
            self._set_status(message, 'error')

        self._refresh_all()

    def _confirm_uninstall_marketplace(self, library_id: str, label: str):
        """Uninstall a library that was installed via the marketplace panel."""
        # Resolve the actual library_id from the installed registry
        installed = self.manager.list_installed()
        pkg_id = library_id.replace('haybale-', '').lower()
        matched = next(
            (lib for lib in installed
             if lib.library_id.lower() == pkg_id
             or lib.distribution_name.lower() == label.lower()),
            None,
        )
        if matched:
            self._confirm_uninstall(matched.library_id, matched.label)
        else:
            self._set_status(f"Could not find installed entry for '{label}'", 'error')

    def _open_version_picker(self, pkg: MarketplaceEntry):
        """Open a dialog that fetches available versions and lets the user pick one."""
        with ui.dialog() as dialog, ui.card().classes('min-w-80'):
            ui.label(f'Install specific version — {pkg.name}').classes(
                'text-lg font-bold mb-2'
            )
            version_select = ui.select(
                options=['Loading…'],
                value='Loading…',
                label='Version',
            ).classes('w-full').props('dense')
            status = ui.label('Fetching versions…').classes('text-xs text-gray-400')

            async def load_versions():
                versions = await self.manager.fetch_versions(pkg)
                if versions:
                    version_select.options = versions
                    version_select.value = versions[0]
                    status.text = f'{len(versions)} versions available'
                else:
                    version_select.options = ['(unavailable)']
                    version_select.value = '(unavailable)'
                    status.text = 'Could not fetch version list'

            async def install_selected(e):
                selected = version_select.value
                if not selected or selected in ('Loading…', '(unavailable)'):
                    return
                dialog.close()
                spec = self.manager.build_versioned_spec(pkg, selected)
                # Find install button stub — pass None since we have no button ref here
                await self._install_package(spec, pkg.name, None)

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button(
                    'Install', on_click=install_selected,
                ).props('color=primary')

        dialog.open()
        asyncio.ensure_future(load_versions())

    async def _install_package(
        self, install_spec: str, name: str, button: ui.button | None,
    ):
        """Install a package from the marketplace with streaming log."""
        if button:
            button.disable()
            button.props('loading')
        self._set_status(f"Installing {name}...", 'info')

        card = self._marketplace_cards.get(name)
        if card:
            log = self._create_log_in_card(card, f'Installing {name}...')
        else:
            log = None

        def on_output(line: str):
            if log:
                log.push(line)

        success, message = await self.manager.install_streaming(
            install_spec, on_output,
        )

        if success:
            if log:
                log.push(f'--- {name} installed successfully ---')
            self._set_status(f"Installed: {name}", 'success')
        else:
            if log:
                log.push(f'--- ERROR: {message} ---')
            self._set_status(message, 'error')

        self._refresh_all()
