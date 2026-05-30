<template>
  <!-- Overlay / backdrop — v-show (not v-if) keeps slot DOM alive so NiceGUI
       can inject children even before the popup is opened for the first time -->
  <div
    v-show="visible"
    class="hw-popup-overlay"
    :style="overlayStyle"
    @click.self="onOverlayClick"
  >
    <!-- Floating card -->
    <div
      ref="card"
      class="hw-popup-card"
      :class="{ 'hw-popup-dragging': isDragging }"
      :style="cardStyle"
      @click.stop
    >
      <!-- Title bar / drag handle -->
      <div
        v-if="title || closable"
        class="hw-popup-title-bar"
        :class="{ 'hw-popup-not-draggable': !draggable }"
        @mousedown="onTitleMousedown"
      >
        <span v-if="title" class="hw-popup-title-text">{{ title }}</span>
        <div v-else></div>
        <button
          v-if="closable"
          class="hw-popup-close-btn"
          @click.stop="close"
        >✕</button>
      </div>
      <hr v-if="title" class="hw-popup-separator" />

      <!-- Content slot -->
      <div class="hw-popup-content">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'HwPopup',

  props: {
    title:              { type: String,  default: null },
    popupWidth:         { type: String,  default: 'auto' },
    popupHeight:        { type: String,  default: 'auto' },
    closable:           { type: Boolean, default: false },
    backdropClickClose: { type: Boolean, default: false },
    backdropColor:      { type: String,  default: 'var(--hw-bg-overlay)' },
    initialX:           { type: Number,  default: null },
    initialY:           { type: Number,  default: null },
    draggable:          { type: Boolean, default: false },
    clampToViewport:    { type: Boolean, default: false },
    startVisible:       { type: Boolean, default: false },
  },

  data() {
    return {
      visible:     false,
      isDragging:  false,
      currentX:    0,
      currentY:    0,
      dragPositioned: false,
      dragStartMouseX: 0,
      dragStartMouseY: 0,
      dragStartCardX:  0,
      dragStartCardY:  0,
    };
  },

  computed: {
    /** True when the popup was created with explicit x/y coordinates. */
    propsPositioned() {
      return this.initialX !== null && this.initialY !== null;
    },

    /** True when the card should use fixed left/top positioning. */
    isPositioned() {
      return this.dragPositioned || this.propsPositioned;
    },

    overlayStyle() {
      if (!this.visible) {
        // Hidden: must not capture any pointer events
        return { position: 'fixed', inset: '0', zIndex: -1, pointerEvents: 'none' };
      }
      // zIndex 7000/7001 — above Quasar dialogs (default 6000) so haywire
      // modals can layer over any legacy ui.dialog() that still exists in
      // an editor. The long-term direction is to migrate all such dialogs
      // to Popup; until that's done, keep this higher than Quasar's default.
      if (this.propsPositioned) {
        // Originally positioned — transparent overlay, no backdrop
        return {
          position: 'fixed',
          inset: '0',
          zIndex: 7000,
          background: 'transparent',
          pointerEvents: this.backdropClickClose ? 'auto' : 'none',
        };
      }
      // Centred / modal — keep backdrop even after drag-positioning kicks in
      return {
        position: 'fixed',
        inset: '0',
        zIndex: 7000,
        background: this.backdropColor,
        display: this.isPositioned ? 'block' : 'flex',
        alignItems: this.isPositioned ? undefined : 'center',
        justifyContent: this.isPositioned ? undefined : 'center',
        pointerEvents: 'auto',
      };
    },

    cardStyle() {
      const base = {
        width: this.popupWidth,
        height: this.popupHeight,
        maxWidth: '90vw',
        maxHeight: '90vh',
        overflow: 'auto',
        pointerEvents: 'auto',
      };
      if (this.isPositioned) {
        return {
          ...base,
          position: 'fixed',
          left: this.currentX + 'px',
          top:  this.currentY + 'px',
          margin: 0,
          zIndex: 7001,
        };
      }
      return {
        ...base,
        position: 'relative',
        margin: '20px',
        zIndex: 7001,
      };
    },
  },

  mounted() {
    if (this.startVisible) {
      this._initPosition();
      this.visible = true;
    }
    document.addEventListener('mousemove', this.handleDragMove);
    document.addEventListener('mouseup',   this.handleDragUp);
  },

  beforeUnmount() {
    document.removeEventListener('mousemove', this.handleDragMove);
    document.removeEventListener('mouseup',   this.handleDragUp);
  },

  methods: {
    _initPosition() {
      if (this.isPositioned) {
        this.currentX = this.initialX;
        this.currentY = this.initialY;
        if (this.clampToViewport) {
          this._clamp();
        }
      }
    },

    _clamp() {
      const card = this.$refs.card;
      const w = card ? card.offsetWidth  : 300;
      const h = card ? card.offsetHeight : 200;
      this.currentX = Math.max(0, Math.min(this.currentX, window.innerWidth  - w));
      this.currentY = Math.max(0, Math.min(this.currentY, window.innerHeight - h));
    },

    open() {
      if (this.visible) return;
      this._initPosition();
      this.visible = true;
    },

    close() {
      if (!this.visible) return;
      this.visible = false;
      this.isDragging = false;
      this.$emit('popup-close');
    },

    toggle() {
      this.visible ? this.close() : this.open();
    },

    setPosition(x, y) {
      this.currentX = x;
      this.currentY = y;
      if (this.clampToViewport) {
        this._clamp();
      }
    },

    onOverlayClick() {
      if (this.backdropClickClose) {
        this.close();
      }
    },

    onTitleMousedown(e) {
      if (!this.draggable) return;
      if (e.target.closest('button')) return;

      // If the popup was centred (no initial position), capture its current
      // rendered position so that cardStyle switches to fixed positioning
      // and subsequent drag deltas actually move the card.
      if (!this.isPositioned) {
        const card = this.$refs.card;
        if (card) {
          const rect = card.getBoundingClientRect();
          this.currentX = rect.left;
          this.currentY = rect.top;
          this.dragPositioned = true;
        }
      }

      this.isDragging = true;
      this.dragStartMouseX = e.clientX;
      this.dragStartMouseY = e.clientY;
      this.dragStartCardX  = this.currentX;
      this.dragStartCardY  = this.currentY;
      e.preventDefault();
      e.stopPropagation();
    },

    handleDragMove(e) {
      if (!this.isDragging) return;
      const dx = e.clientX - this.dragStartMouseX;
      const dy = e.clientY - this.dragStartMouseY;
      this.currentX = this.dragStartCardX + dx;
      this.currentY = this.dragStartCardY + dy;
      if (this.clampToViewport) {
        this._clamp();
      }
      e.preventDefault();
    },

    handleDragUp(_e) {
      if (!this.isDragging) return;
      this.isDragging = false;
      this.$emit('popup-position-update', { x: this.currentX, y: this.currentY });
    },
  },
};
</script>

<style>
/* Global (not scoped) — vbuild's scoped attribute injection is unreliable
   for NiceGUI-injected slot children.  All classes use the hw-popup-*
   namespace to avoid collisions.
   Design rules: §8.23 of the Haywire UI Design Guide. */

/* ── Card chrome ────────────────────────────────────────── */
.hw-popup-card {
  background: var(--hw-bg-elevated);
  color: var(--hw-text-body);
  border: 1px solid var(--hw-border-strong);
  border-radius: 8px;                          /* md — §4 radius scale */
  box-shadow: var(--hw-popup-shadow);           /* §8.23 — never hardcoded */
}

.hw-popup-card.hw-popup-dragging {
  opacity: 0.95;
}

/* ── Title bar / drag handle ────────────────────────────── */
.hw-popup-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 4px;
  cursor: move;
  user-select: none;
  color: var(--hw-text-body);
}

.hw-popup-title-bar.hw-popup-not-draggable {
  cursor: default;
}

.hw-popup-title-text {
  font-size: 1.1em;
  font-weight: 600;
  pointer-events: none;
}

/* ── Close button ───────────────────────────────────────── */
.hw-popup-close-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--hw-text-dim);                    /* dim at rest — §1.3 */
  font-size: 1em;
  padding: 2px 6px;
  border-radius: 4px;                           /* sm */
  line-height: 1;
  transition: background 0.15s, color 0.15s;    /* shell tier — §anti-patterns */
}
.hw-popup-close-btn:hover {
  background: var(--hw-bg-hover);
  color: var(--hw-text-body);
}

/* ── Separator ──────────────────────────────────────────── */
.hw-popup-separator {
  margin: 0;
  border: none;
  border-top: 1px solid var(--hw-border-strong);
}

/* ── Content area ───────────────────────────────────────── */
.hw-popup-content {
  padding: 8px;
  user-select: text;
  cursor: auto;
  pointer-events: auto;
}
.hw-popup-content * {
  user-select: text;
}
.hw-popup-content button,
.hw-popup-content .q-btn,
.hw-popup-content .q-item,
.hw-popup-content [role="button"] {
  user-select: none !important;
  cursor: pointer !important;
}
.hw-popup-content input,
.hw-popup-content textarea {
  user-select: text !important;
  cursor: text !important;
}
</style>
