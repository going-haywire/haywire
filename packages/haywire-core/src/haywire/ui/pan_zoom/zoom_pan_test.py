from nicegui import ui
import time

from haywire.ui.pan_zoom.zoom_pan_vue import ZoomPanContainer

# from haywire.ui.pan_zoom.mini_map_vue import MinimapCanvas
from haywire.ui.minimap.mini_map_vue import MinimapCanvas


def create_zoom_pan_controls(container: ZoomPanContainer) -> None:
    """Create standard zoom/pan control buttons."""
    with ui.element("div").classes("zoom-pan-controls"):
        ui.button("+", on_click=container.zoom_in).props("round dense").classes("text-xs")
        ui.button("−", on_click=container.zoom_out).props("round dense").classes("text-xs")
        ui.button("⌂", on_click=container.reset_view).props("round dense").classes("text-xs")
        ui.button("⛶", on_click=container.fit_to_content).props("round dense").classes("text-xs")


def create_zoom_pan_info(container: ZoomPanContainer) -> ui.label:
    """Create info display with comprehensive performance metrics
    for current zoom and pan values."""
    info_label = ui.label().classes("zoom-pan-info")

    # Additional performance tracking for the info display
    info_update_times = []
    info_update_count = [0]
    start_time = time.time()

    def update_info(zoom=None, pan_x=None, pan_y=None):
        try:
            current_time = time.time()
            info_update_count[0] += 1

            # Get comprehensive metrics from container
            metrics = container.get_performance_metrics()

            # Use provided values or fall back to container state
            if zoom is None:
                zoom = metrics["current_zoom"]
            if pan_x is None:
                pan_x = metrics["pan_x"]
            if pan_y is None:
                pan_y = metrics["pan_y"]

            zoom_class = container.get_zoom_class_name()

            # Calculate info display FPS (separate from container FPS)
            info_update_times.append(current_time)
            cutoff_time = current_time - 1.0
            info_update_times[:] = [t for t in info_update_times if t > cutoff_time]
            info_fps = len(info_update_times)

            # Calculate uptime
            uptime = current_time - start_time

            # Create comprehensive info text
            info_text = (
                f"Zoom: {zoom:.2f} ({zoom_class}) | "
                f"Pan: ({pan_x:.0f}, {pan_y:.0f}) | "
                f"Container FPS: {metrics['fps']} | "
                f"Info FPS: {info_fps} | "
                f"Updates: {metrics['total_updates']} | "
                f"Uptime: {uptime:.1f}s"
            )

            # Add performance indicators
            if metrics["fps"] > 60:
                info_text += " | ⚡ High Performance"
            elif metrics["fps"] < 10 and metrics["fps"] > 0:
                info_text += " | ⚠️ Low Performance"
            elif metrics["time_since_last_update"] > 1.0:
                info_text += " | 💤 Idle"

            info_label.set_text(info_text)
            info_label.update()
        except Exception as e:
            # Fallback display on error
            error_text = f"Error: {str(e)[:50]}..." if len(str(e)) > 50 else f"Error: {str(e)}"
            info_label.set_text(error_text)
            info_label.update()

    # Store original callbacks
    original_zoom_callback = container.on_zoom_change
    original_pan_callback = container.on_pan_change

    def zoom_callback(zoom):
        update_info(zoom=zoom)
        if original_zoom_callback:
            original_zoom_callback(zoom)

    def pan_callback(x, y):
        update_info(pan_x=x, pan_y=y)
        if original_pan_callback:
            original_pan_callback(x, y)

    # Replace the container's callbacks
    container.on_zoom_change = zoom_callback
    container.on_pan_change = pan_callback

    # Initial update with a small delay to ensure container is ready
    ui.timer(0.1, lambda: update_info(), once=True)

    return info_label


def main():
    @ui.page("/")
    def main_page():
        ui.label("NiceGUI Zoom/Pan Container Demo").classes("text-2xl font-bold mb-4")

        def on_zoom_change(zoom):
            pass

        def on_pan_change(x, y):
            pass

        # Main layout with left panel and zoom container
        with ui.row().classes("w-full gap-4").style("height: 80vh;"):
            # Right side with zoom container (create first so we can reference it)
            with (
                ui.card().classes("flex-grow").style("height: 100%; display: flex; flex-direction: column;")
            ):
                ui.label("Zoomable Content Area").classes("text-lg mb-2 flex-shrink-0")

                # Create the zoom/pan container
                zoom_container = (
                    ZoomPanContainer(
                        initial_zoom=1.0,
                        on_zoom_change=on_zoom_change,
                        on_pan_change=on_pan_change,
                    )
                    .classes("w-full flex-grow border-2 border-gray-300")
                    .style("height: 100%;")
                )

                # LOD-based visibility rules

                # Mark your containers with these classes in Python:
                # - .lod-container-top: Always visible (main containers)
                # - .lod-container-parent: Visible from low zoom up
                # - .lod-container-child: Visible from medium zoom up
                # - .lod-detail: Visible only at high zoom

                # Add content to the container
                with zoom_container:
                    with ui.grid(columns=50).classes("gap-6 p-8") as grid:
                        grid.classes("right-[2000px] bottom-[2000px] relative")
                        for i in range(1000):
                            with ui.card().classes(
                                "w-32 h-32 bg-blue-100 flex flex-col "
                                "items-center justify-center zoom-pan-lod0 node-card"
                            ):
                                with ui.column():
                                    # Drag handle (should be draggable, not pan the view)
                                    with ui.row().classes("drag-handle w-full justify-center mb-1"):
                                        ui.icon("drag_indicator").classes("text-grey-6 text-xs")
                                    ui.label(f"Item {i + 1}").classes(
                                        "text-center text-sm mb-2 zoom-pan-lod1"
                                    )
                                    ui.input(value="some text").props("clearable outlined").classes(
                                        "text-xs zoom-pan-lod2"
                                    ).style("cursor: text; pointer-events: auto;")
                                    # Add a port-like element
                                    with ui.row().classes("justify-center mt-1"):
                                        ui.icon("fiber_manual_record").classes(
                                            "port output-port w-3 h-3 bg-red-500 rounded-full"
                                        ).style("cursor: crosshair;")

                # Add controls
                create_zoom_pan_controls(zoom_container)
                create_zoom_pan_info(zoom_container)

                MinimapCanvas(zoom_container, width=200, position="top-right", visible=True)

            # Left panel with controls and documentation (create after zoom_container)
            with (
                ui.card()
                .classes("w-80 flex-shrink-0")
                .style("height: 100%; display: flex; flex-direction: column;")
            ):
                ui.label("Controls & Info").classes("text-xl font-bold mb-4")

                # Additional demo controls
                with ui.column().classes("gap-2 mb-6"):
                    ui.label("Demo Controls").classes("text-lg font-semibold mb-2")
                    ui.button("Zoom to 2x", on_click=lambda: zoom_container.set_zoom(2.0)).classes("w-full")
                    ui.button("Pan to (100, 50)", on_click=lambda: zoom_container.set_pan(100, 50)).classes(
                        "w-full"
                    )
                    ui.button("Reset View", on_click=zoom_container.reset_view).classes("w-full")
                    ui.button("Fit Content", on_click=zoom_container.fit_to_content).classes("w-full")

                    # Performance controls
                    ui.separator()
                    ui.label("Performance").classes("text-md font-semibold mb-2")
                    ui.button(
                        "Show Performance Summary",
                        on_click=lambda: ui.notify(
                            zoom_container.get_performance_summary(), type="info", timeout=10000
                        ),
                    ).classes("w-full")
                    ui.button(
                        "Reset Performance Metrics",
                        on_click=lambda: (
                            zoom_container.reset_performance_metrics(),
                            ui.notify("Performance metrics reset", type="positive"),
                        ),
                    ).classes("w-full")

                # Controls documentation
                with ui.column().classes("flex-grow"):
                    ui.label("Keyboard & Mouse Controls").classes("text-lg font-semibold mb-2")
                    ui.markdown("""
                        **Mouse Controls:**
                        - **Mouse wheel**: Zoom in/out
                        - **Click and drag**: Pan around

                        **Keyboard Shortcuts:**
                        - **+ key**: Zoom in
                        - **- key**: Zoom out  
                        - **0 key**: Reset view

                        **Button Controls:**
                        - Use the control buttons for programmatic control
                        - Corner buttons: +/- zoom, home, fit content
                    """).classes("text-sm")

    ui.run(
        title="Container PanZoom Implementation", favicon="🔗", dark=False, show=True, reload=True, port=8090
    )


# Example usage and demo
if __name__ in {"__main__", "__mp_main__"}:
    main()
