---
name: The canvas fit lands after goto_ready
description: A canvas centres itself through a server round trip that can land after goto_ready and after the transform has held still for two frames, so geometry read then is pre-fit. Harness canvases stamp data-hw-fit-done; wait_for_canvas_settled waits for it.
type: project
---

# The canvas fit lands after `goto_ready`

When a canvas mounts, the client reports it ready, the server answers with
`ZoomPan.center_on_content`, and `fitToContent` fits two frames after it is called. On a
slow server that whole round trip can land after `nav.goto_ready` has returned, and after
the pan/zoom transform has already held still for two frames at its unfitted value
(`matrix(1,0,0,1,0,0)`). A test that reads pin positions or clicks coordinates then works
on the pre-fit canvas, and every pin moves under it a moment later.

A stable transform is therefore not a settled canvas. Harness canvases mounted through
`routes._centre_when_ready` carry `data-hw-fit-pending` and get `data-hw-fit-done` two frames
after the fit was requested; `nav.wait_for_canvas_settled` waits for that stamp before it
watches the transform. A route that skips centring (`/graph-detail-culled`) removes the
pending marker. A page built on a real `GraphEditor` carries no marker, so the helper
falls back to transform stability alone there.

Uniform CPU load does not reproduce this; delaying the harness server's event handling does.
