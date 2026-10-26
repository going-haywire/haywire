<template>
  <span class="hw-access-gate" style="display: none"></span>
</template>

<script>
// Page-wide level-mode gate for canvas cards and panels.
//
// isGated(el) is the one definition of "this element does not take input in the
// level mode in force"; the <style> block below says the same for pointer input,
// and the focusin listener blurs a gated element as it takes keyboard focus.
// Keep the two in step: test_access_gate.py::test_css_and_isGated_agree.
//
// Nested stamps: the strictest one around el decides, so an inner stamp can only tighten.
//
//   canvas: el inside a card (.ui-node-slot) under a [data-hw-level-mode] root;
//           required = strictest [data-hw-requires] from el up to the slot, unstamped = 'edit'.
//   panel:  el inside [data-hw-mode-scope="session"]; gated only when a
//           [data-hw-requires] ancestor (or el) ranks above <html data-hw-session-mode>.
const RANK = { view: 0, operate: 1, edit: 2 };

// A value outside the three ranks needs more than edit, as an unstamped card element does.
function requiredRank(value) {
  return value in RANK ? RANK[value] : RANK.edit;
}

function canvasGated(el) {
  const slot = el.parentElement ? el.parentElement.closest('.ui-node-slot') : null;
  if (!slot) return null;
  const root = slot.closest('[data-hw-level-mode]');
  if (!root) return null;
  const mode = root.dataset.hwLevelMode;
  if (!(mode in RANK)) return false;
  let required = null;
  for (let node = el.closest('[data-hw-requires]'); node && slot.contains(node);
       node = node.parentElement ? node.parentElement.closest('[data-hw-requires]') : null) {
    required = Math.max(required ?? RANK.view, requiredRank(node.dataset.hwRequires));
  }
  return (required ?? RANK.edit) > RANK[mode];
}

function panelGated(el) {
  const scope = el.closest('[data-hw-mode-scope="session"]');
  if (!scope) return false;
  const mode = document.documentElement.dataset.hwSessionMode || 'view';
  if (!(mode in RANK)) return false;
  // Only stamps inside the scope count; an unknown stamp gates nothing here.
  for (let node = el.closest('[data-hw-requires]'); node && node !== scope && scope.contains(node);
       node = node.parentElement ? node.parentElement.closest('[data-hw-requires]') : null) {
    const required = node.dataset.hwRequires;
    if (required in RANK && RANK[required] > RANK[mode]) return true;
  }
  return false;
}

function isGated(el) {
  if (!(el instanceof Element)) return false;
  const canvas = canvasGated(el);
  return canvas === null ? panelGated(el) : canvas;
}

function blurIfGated(el) {
  if (el instanceof HTMLElement && isGated(el)) el.blur();
}

export default {
  name: 'AccessGate',

  props: {
    sessionMode: { type: String, default: 'view' },
  },

  watch: {
    sessionMode(mode) {
      this.writeSessionMode(mode);
    },
  },

  mounted() {
    window.hwAccess = { isGated };
    this.writeSessionMode(this.sessionMode);
    document.addEventListener('focusin', this.onFocusIn, true);
    // A canvas lock flips its root's attribute, never this component's props.
    this.levelObserver = new MutationObserver(() => blurIfGated(document.activeElement));
    this.levelObserver.observe(document.body, {
      attributes: true,
      attributeFilter: ['data-hw-level-mode'],
      subtree: true,
    });
  },

  unmounted() {
    document.removeEventListener('focusin', this.onFocusIn, true);
    this.levelObserver.disconnect();
  },

  methods: {
    writeSessionMode(mode) {
      document.documentElement.dataset.hwSessionMode = mode;
      blurIfGated(document.activeElement);
    },

    onFocusIn(e) {
      blurIfGated(e.target);
    },
  },
};
</script>

<style>
/* Canvas cards. Below edit, card content takes no pointer input, except
 * [data-hw-requires="view"] elements in every mode and [data-hw-requires="operate"]
 * ones in operate; unstamped content counts as edit. Keyed on .ui-node-slot
 * descendants so the card root and the slot keep taking presses (a double-click on
 * the card body still enters); pins sit inside the slot and are gated too.
 * !important plus the extra selectors out-specify .connection-pin's rule in
 * canvas.vue. The gate never matches inside an exempt subtree that holds no stricter
 * stamp, so a widget's own pointer-events rules (a disabled widget's none) stay in force. */
[data-hw-level-mode="view"] .ui-node-slot *:not([data-hw-requires="view"]):not([data-hw-requires="view"] *),
[data-hw-level-mode="operate"] .ui-node-slot *:not([data-hw-requires="view"]):not([data-hw-requires="view"] *):not([data-hw-requires="operate"]):not([data-hw-requires="operate"] *) {
    pointer-events: none !important;
}
/* pointer-events inherits, so an exempt root would take the gated ancestors'
 * none; :where() gives it auto at zero specificity, so its own rules still win. */
:where([data-hw-level-mode="view"] .ui-node-slot [data-hw-requires="view"],
       [data-hw-level-mode="operate"] .ui-node-slot [data-hw-requires="view"],
       [data-hw-level-mode="operate"] .ui-node-slot [data-hw-requires="operate"]) { pointer-events: auto; }
/* A stricter (or unknown) stamp nested in an exempt one is gated again: nesting only tightens. */
[data-hw-level-mode="view"] .ui-node-slot [data-hw-requires]:not([data-hw-requires="view"]),
[data-hw-level-mode="view"] .ui-node-slot [data-hw-requires]:not([data-hw-requires="view"]) *,
[data-hw-level-mode="operate"] .ui-node-slot [data-hw-requires]:not([data-hw-requires="view"]):not([data-hw-requires="operate"]),
[data-hw-level-mode="operate"] .ui-node-slot [data-hw-requires]:not([data-hw-requires="view"]):not([data-hw-requires="operate"]) * {
    pointer-events: none !important;
}

/* Panels under [data-hw-mode-scope="session"]: only stamped writers are gated,
 * greyed as a disabled input (design guide 2.11). No session mode counts as view. */
:is(html[data-hw-session-mode="view"], html:not([data-hw-session-mode])) [data-hw-mode-scope="session"] :is([data-hw-requires="operate"], [data-hw-requires="edit"]),
html[data-hw-session-mode="operate"] [data-hw-mode-scope="session"] [data-hw-requires="edit"] {
    opacity: 0.5;
    pointer-events: none !important;
}
:is(html[data-hw-session-mode="view"], html:not([data-hw-session-mode])) [data-hw-mode-scope="session"] :is([data-hw-requires="operate"], [data-hw-requires="edit"]) *,
html[data-hw-session-mode="operate"] [data-hw-mode-scope="session"] [data-hw-requires="edit"] * {
    pointer-events: none !important;
}
</style>
