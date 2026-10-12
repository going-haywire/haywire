<template>
  <span class="hw-keymap-listener" style="display: none"></span>
</template>

<script>
// Page-wide keyboard-shortcut listener.
//
// Tracks the target editor (the last [data-hw-binding] root that took a
// pointerdown), turns key presses into command events for the target's editor
// keymap, and turns the native `paste` event into the editor's paste command.
// Keys typed into a text field stay with the field.
const NATIVE_SELECTOR =
  'input, textarea, select, [contenteditable], .cm-editor, [data-hw-native-keys]';

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
    // Alt+letter on macOS yields a composed glyph (Alt+A -> "å"); the physical key names the combo.
    const physical = /^(?:Key([A-Z])|Digit([0-9]))$/.exec(e.code || '');
    if (e.altKey && physical && key.charCodeAt(0) > 0x7e) key = physical[1] || physical[2];
    key = key.toUpperCase();
  }
  return [...mods, key].join('+');
}

function isNativeTarget(el) {
  return el instanceof Element && el.closest(NATIVE_SELECTOR) !== null;
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
    return { targetBinding: null };
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
    document.addEventListener('pointerdown', this.onPointerDown, true);
    document.addEventListener('keydown', this.onKeyDown, true);
    document.addEventListener('paste', this.onPaste, true);
  },

  unmounted() {
    document.removeEventListener('pointerdown', this.onPointerDown, true);
    document.removeEventListener('keydown', this.onKeyDown, true);
    document.removeEventListener('paste', this.onPaste, true);
  },

  methods: {
    onPointerDown(e) {
      const root = e.target instanceof Element ? e.target.closest('[data-hw-binding]') : null;
      if (!root) return;
      const bindingId = root.dataset.hwBinding;
      if (bindingId === this.targetBinding) return;
      this.targetBinding = bindingId;
      this.$emit('hw-target', { binding_id: bindingId });
    },

    // The target editor's root: the last one clicked while it is still in the page,
    // else the first visible editor root in the fallback slot.
    resolveRoot() {
      if (this.targetBinding !== null) {
        const sel = `[data-hw-binding="${CSS.escape(this.targetBinding)}"]`;
        const current = document.querySelector(sel);
        if (current) return current;
      }
      const slot = `#hw-slot-${CSS.escape(this.fallbackSlot)} [data-hw-binding]`;
      return [...document.querySelectorAll(slot)].find(isVisible) || null;
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
      if (e.repeat || isNativeTarget(document.activeElement)) return;
      const combo = comboFromEvent(e, this.isMac);
      if (combo === null) return;
      const root = this.resolveRoot();
      if (!root) return;
      const map = this.editorMap(root);
      const commandId = map ? map[combo] : undefined;
      if (!commandId) return;
      // A native-event command runs from its browser event (e.g. `paste`), which needs the default.
      const native = (this.keymap && this.keymap.native) || {};
      if (commandId in native) return;
      e.preventDefault();
      this.emitCommand(commandId, root, null, '');
    },

    onPaste(e) {
      if (isNativeTarget(e.target)) return;
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
