<template>
  <span class="hw-keymap-listener" style="display: none"></span>
</template>

<script>
// Page-wide keyboard-shortcut listener.
//
// Tracks the active slot (the last [data-hw-slot] that took a pointerdown and
// shows an editor) and, inside it, the target editor (the last [data-hw-binding]
// root clicked); writes the active slot to <html data-hw-active-slot>, where the
// shell CSS lights its bars and no server redraw can reach it. Turns key presses
// into command events for the target's editor keymap, and the native `paste`
// event into the editor's paste command.
// Keys typed into a text field stay with the field, except the commands marked
// `in_text_fields`; keys pressed inside a dialog, a Popup or a [data-hw-native-keys]
// subtree stay with the page.
const TEXT_FIELD_SELECTOR = 'input, textarea, select, [contenteditable], .cm-editor';
const NATIVE_KEYS_SELECTOR = '[data-hw-native-keys]';
const NATIVE_SELECTOR = `${TEXT_FIELD_SELECTOR}, ${NATIVE_KEYS_SELECTOR}`;

const MODIFIER_KEYS = new Set(['Control', 'Meta', 'Alt', 'Shift', 'AltGraph', 'CapsLock', 'OS']);

// Canonical order, matching haywire.core.signals.keys.normalize_combo.
function comboFromEvent(e, isMac) {
  if (MODIFIER_KEYS.has(e.key)) return null;
  const mods = [];
  if (isMac ? e.metaKey : e.ctrlKey) mods.push('Mod');
  if (isMac && e.ctrlKey) mods.push('Ctrl');
  if (e.altKey) mods.push('Alt');
  if (e.shiftKey) mods.push('Shift');
  let key = e.key;
  if (key === ' ') {
    key = 'Space';
  } else if (key.length === 1) {
    // Option+letter on macOS composes a glyph (Option+A -> "å") and a non-Latin layout types its own
    // letter under Ctrl/Cmd (Ctrl+C -> "с"); the physical key names those combos. Ctrl+Alt outside
    // macOS is AltGr, whose composed character is the key itself.
    const physical = /^(?:Key([A-Z])|Digit([0-9]))$/.exec(e.code || '');
    const composed = key.charCodeAt(0) > 0x7e;
    const byPhysical = (isMac && e.altKey) || ((e.ctrlKey || e.metaKey) && !e.altKey);
    if (physical && composed && byPhysical) key = physical[1] || physical[2];
    key = key.toUpperCase();
  }
  return [...mods, key].join('+');
}

function isNativeTarget(el) {
  return el instanceof Element && el.closest(NATIVE_SELECTOR) !== null;
}

// An open dialog or Popup sits over the editors, so keys pressed in it never act on the editor behind.
function isInDialog(el) {
  return el instanceof Element && el.closest('.q-dialog, .hw-popup-overlay') !== null;
}

// A subtree marked data-hw-native-keys keeps every key, `in_text_fields` commands too.
function keepsAllKeys(el) {
  return el instanceof Element && el.closest(NATIVE_KEYS_SELECTOR) !== null;
}

function keepsNativeKeys(target) {
  const active = document.activeElement;
  return isNativeTarget(active) || isInDialog(active) || isInDialog(target);
}

// Ask a focused input or textarea to commit its value ahead of the command; the websocket keeps
// the order. `hw-commit` goes out synchronously, where a Quasar field's own blur event is deferred
// and cancelled by the refocus. The blur and refocus still commit a native-blur field. A code
// editor streams every change and keeps its caret, so it is left alone.
function commitField(el) {
  if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return;
  el.dispatchEvent(new CustomEvent('hw-commit', { bubbles: true }));
  el.blur();
  el.focus();
}

function isVisible(el) {
  return el.offsetParent !== null;
}

export default {
  name: 'KeymapListener',

  props: {
    keymap: { type: Object, default: () => ({ editors: {}, native: {} }) },
    fallbackSlot: { type: String, default: 'edit' },
    platform: { type: String, default: 'auto' },
  },

  data() {
    return { targetBinding: null, activeSlot: null };
  },

  computed: {
    isMac() {
      if (this.platform === 'auto') return (navigator.platform || '').startsWith('Mac');
      return this.platform === 'mac';
    },
  },

  mounted() {
    // Shortcut hints render both spellings; the shell CSS hides the one this flag rules out.
    document.documentElement.dataset.hwPlatform = this.isMac ? 'mac' : 'other';
    // Folding or closing the active slot's editor resizes it; the highlight then moves to the fallback.
    this.slotObserver = new ResizeObserver(() => this.checkActiveSlot());
    // A slot clicked while it shows no editor (a collapsed rail) becomes active once one appears.
    this.pendingSlot = null;
    this.pendingObserver = new ResizeObserver(() => this.checkPendingSlot());
    this.setActiveSlot(this.fallbackSlot);
    document.addEventListener('pointerdown', this.onPointerDown, true);
    document.addEventListener('keydown', this.onKeyDown, true);
    document.addEventListener('paste', this.onPaste, true);
  },

  unmounted() {
    this.slotObserver.disconnect();
    this.pendingObserver.disconnect();
    document.removeEventListener('pointerdown', this.onPointerDown, true);
    document.removeEventListener('keydown', this.onKeyDown, true);
    document.removeEventListener('paste', this.onPaste, true);
  },

  methods: {
    setActiveSlot(name) {
      this.activeSlot = name;
      document.documentElement.dataset.hwActiveSlot = name;
      this.slotObserver.disconnect();
      const slotEl = this.slotElement(name);
      if (!slotEl) return;
      this.slotObserver.observe(slotEl);
      slotEl.querySelectorAll('[data-hw-binding]').forEach((root) => this.slotObserver.observe(root));
    },

    checkActiveSlot() {
      if (this.activeSlot === this.fallbackSlot) return;
      if (!this.firstVisibleRoot(this.slotElement(this.activeSlot))) this.setActiveSlot(this.fallbackSlot);
    },

    setPendingSlot(slotEl) {
      this.pendingSlot = slotEl.dataset.hwSlot;
      this.pendingObserver.observe(slotEl);
    },

    clearPendingSlot() {
      this.pendingSlot = null;
      this.pendingObserver.disconnect();
    },

    checkPendingSlot() {
      if (this.pendingSlot === null) return;
      if (!this.firstVisibleRoot(this.slotElement(this.pendingSlot))) return;
      const name = this.pendingSlot;
      this.clearPendingSlot();
      this.setActiveSlot(name);
    },

    retarget(root) {
      const bindingId = root.dataset.hwBinding;
      if (bindingId === this.targetBinding) return;
      this.targetBinding = bindingId;
      this.$emit('hw-target', { binding_id: bindingId });
    },

    slotElement(name) {
      return document.querySelector(`[data-hw-slot="${CSS.escape(name)}"]`);
    },

    firstVisibleRoot(slotEl) {
      return slotEl ? [...slotEl.querySelectorAll('[data-hw-binding]')].find(isVisible) || null : null;
    },

    // A pointer-down in a slot that shows an editor makes it the active slot; one on an editor
    // root also makes that editor the target. A bar click leaves the target to the next key.
    // A slot that shows none yet becomes active if one appears before the next pointer-down.
    onPointerDown(e) {
      if (!(e.target instanceof Element)) return;
      this.clearPendingSlot();
      const slotEl = e.target.closest('[data-hw-slot]');
      if (!slotEl) return;
      const hit = e.target.closest('[data-hw-binding]');
      if (!hit && !this.firstVisibleRoot(slotEl)) {
        this.setPendingSlot(slotEl);
        return;
      }
      this.setActiveSlot(slotEl.dataset.hwSlot);
      if (hit) this.retarget(hit);
    },

    // The target editor's root: the last one clicked while it is still visible in the active slot,
    // else the slot's first visible root, else the fallback slot's, which then becomes active.
    // A root other than the last target becomes the target.
    resolveRoot() {
      const slotEl = this.slotElement(this.activeSlot);
      if (slotEl && this.targetBinding !== null) {
        const current = slotEl.querySelector(`[data-hw-binding="${CSS.escape(this.targetBinding)}"]`);
        if (current && isVisible(current)) return current;
      }
      let root = this.firstVisibleRoot(slotEl);
      if (!root) {
        root = this.firstVisibleRoot(this.slotElement(this.fallbackSlot));
        if (root) this.setActiveSlot(this.fallbackSlot);
      }
      if (root) this.retarget(root);
      return root;
    },

    editorMap(root) {
      const editors = (this.keymap && this.keymap.editors) || {};
      return editors[root.dataset.hwEditor] || null;
    },

    emitCommand(commandId, root, position, text) {
      this.$emit('hw-command', {
        command_id: commandId,
        binding_id: root.dataset.hwBinding,
        position,
        text,
      });
    },

    onKeyDown(e) {
      if (e.repeat) return;
      const active = document.activeElement;
      if (isInDialog(active) || isInDialog(e.target)) return;
      if (keepsAllKeys(active)) return;
      const inField = isNativeTarget(active);
      const combo = comboFromEvent(e, this.isMac);
      if (combo === null) return;
      const root = this.resolveRoot();
      if (!root) return;
      const map = this.editorMap(root);
      const commandId = map ? map[combo] : undefined;
      if (!commandId) return;
      // In a text field only the commands marked `in_text_fields` act; every other key stays the field's.
      const textFieldCommands = (this.keymap && this.keymap.text_fields) || [];
      if (inField && !textFieldCommands.includes(commandId)) return;
      // A native-event command runs from its browser event (e.g. `paste`), which needs the default.
      const native = (this.keymap && this.keymap.native) || {};
      if (commandId in native) return;
      e.preventDefault();
      if (inField) commitField(active);
      this.emitCommand(commandId, root, null, '');
    },

    onPaste(e) {
      if (isNativeTarget(e.target) || keepsNativeKeys(e.target)) return;
      const root = this.resolveRoot();
      if (!root) return;
      const map = this.editorMap(root);
      if (!map) return;
      const native = (this.keymap && this.keymap.native) || {};
      const claimed = new Set(Object.values(map));
      const commandId = Object.keys(native).find((id) => native[id] === 'paste' && claimed.has(id));
      if (!commandId) return;
      e.preventDefault();
      const text = e.clipboardData ? e.clipboardData.getData('text/plain') : '';
      const hook = [...root.querySelectorAll('[data-hw-pointer-local]')].find(isVisible);
      const local = hook && typeof hook.hwPointerLocal === 'function' ? hook.hwPointerLocal() : null;
      this.emitCommand(commandId, root, local || null, text);
    },
  },
};
</script>
