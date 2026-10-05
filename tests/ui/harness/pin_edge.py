"""Where a drawn edge meets its pin, as JS for harness tests that check edge geometry.

Every edge end stops at its pin's edge: the pin's centre moved along the pin's
direction vector (``data-pin-dir-x/y``) by half the pin's layout size in that
direction (``offsetWidth``/``offsetHeight``, in the SVG user units edges are
drawn in). ``PIN_EDGE_JS`` declares ``pinEdge(pin, ctm)``, which returns that
point in screen px; ``ctm`` is the screen CTM of the edge SVG or of one of its
paths. Paste it at the top of a script's function body::

    page.evaluate(
        "(sel) => {%s const p = document.querySelector(sel); ... pinEdge(pin, p.getScreenCTM()) }"
        % PIN_EDGE_JS,
        sel,
    )
"""

PIN_EDGE_JS = """
    const pinEdge = (pin, ctm) => {
        const r = pin.getBoundingClientRect();
        const dx = parseFloat(pin.dataset.pinDirX ?? '1');
        const dy = parseFloat(pin.dataset.pinDirY ?? '0');
        const half = (Math.abs(dx) * pin.offsetWidth + Math.abs(dy) * pin.offsetHeight) / 2;
        return {
            x: r.left + r.width / 2 + (ctm.a * dx + ctm.c * dy) * half,
            y: r.top + r.height / 2 + (ctm.b * dx + ctm.d * dy) * half,
        };
    };
"""
