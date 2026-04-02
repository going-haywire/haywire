<template>
  <div
    ref="root"
    class="number-drag"
    :class="{
      'number-drag--dragging': isDragging,
      'number-drag--editing': isEditing,
      'number-drag--hover': isHovering,
    }"
    @mouseenter="isHovering = true"
    @mouseleave="isHovering = false"
  >
    <!-- Left arrow button -->
    <button
      class="number-drag__arrow number-drag__arrow--left"
      :style="{ opacity: arrowOpacity }"
      @mousedown.prevent="startRepeat(-1)"
      @mouseup.prevent="stopRepeat"
      @mouseleave="stopRepeat"
      tabindex="-1"
    >&#9664;</button>

    <!-- Center: drag zone / display / edit input -->
    <div
      ref="dragZone"
      class="number-drag__center"
      @mousedown.prevent="onMouseDown"
      @dblclick.prevent="enterEditMode"
    >
      <!-- Edit mode input -->
      <input
        v-if="isEditing"
        ref="editInput"
        class="number-drag__input"
        type="text"
        inputmode="decimal"
        :value="editText"
        @input="editText = $event.target.value"
        @keydown.enter.prevent="confirmEdit"
        @keydown.escape.prevent="cancelEdit"
        @blur="confirmEdit"
      />
      <!-- Display mode -->
      <span v-else class="number-drag__display">
        <span v-if="prefix" class="number-drag__affix">{{ prefix }}&nbsp;</span>
        <span>{{ formattedValue }}</span>
        <span v-if="suffix" class="number-drag__affix">&nbsp;{{ suffix }}</span>
      </span>
    </div>

    <!-- Right arrow button -->
    <button
      class="number-drag__arrow number-drag__arrow--right"
      :style="{ opacity: arrowOpacity }"
      @mousedown.prevent="startRepeat(1)"
      @mouseup.prevent="stopRepeat"
      @mouseleave="stopRepeat"
      tabindex="-1"
    >&#9654;</button>
  </div>
</template>

<script>
export default {
  name: 'NumberDrag',

  props: {
    modelValue:  { type: Number, default: 0 },
    min:         { type: Number, default: -Infinity },
    max:         { type: Number, default:  Infinity },
    step:        { type: Number, default: 0.1 },
    precision:   { type: Number, default: -1 },   // -1 = auto
    prefix:      { type: String, default: '' },
    suffix:      { type: String, default: '' },
    sensitivity: { type: Number, default: 1.0 },   // drag px per step
  },

  data() {
    return {
      isHovering: false,
      isDragging: false,
      isEditing: false,
      editText: '',
    };
  },

  computed: {
    formattedValue() {
      const p = Math.max(this.effectivePrecision, this.valuePrecision);
      return this.modelValue.toFixed(p);
    },
    effectivePrecision() {
      if (this.precision >= 0) return this.precision;
      // auto: derive from step
      const s = this.step.toString();
      const dot = s.indexOf('.');
      return dot < 0 ? 0 : s.length - dot - 1;
    },
    valuePrecision() {
      // derive decimal places from the actual stored value
      // use toPrecision(10) to strip floating-point noise before counting
      const s = parseFloat(this.modelValue.toPrecision(10)).toString();
      const dot = s.indexOf('.');
      return dot < 0 ? 0 : s.length - dot - 1;
    },
    arrowOpacity() {
      if (this.isDragging) return 0.6;
      if (this.isHovering) return 0.6;
      return 0;
    },
  },

  methods: {
    // ── Arrow repeat ──────────────────────────────────
    startRepeat(dir) {
      this.nudge(dir);
      this._repeatTimer = setTimeout(() => {
        this._repeatInterval = setInterval(() => this.nudge(dir), 60);
      }, 400);
    },
    stopRepeat() {
      clearTimeout(this._repeatTimer);
      clearInterval(this._repeatInterval);
      this._repeatTimer = null;
      this._repeatInterval = null;
    },
    nudge(dir) {
      this.setValue(this.modelValue + dir * this.step);
    },
    countDecimals(num) {
      if (Number.isInteger(num)) return 0;
      const str = num.toString();
      const decimalPart = str.split('.')[1];
      return decimalPart ? decimalPart.length : 0;
    },

    // ── Drag ──────────────────────────────────────────
    onMouseDown(e) {
      this._startX = e.clientX;
      this._startValue = this.modelValue;
      this._startPrecision = this.valuePrecision;
      const baseStep = 1 / Math.pow(10, this.countDecimals(this._startValue));
      const rect = this.$refs.root.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;  // 0 (left) → 1 (right)
      // 5 zones: [0,0.2) *100  [0.2,0.4) *10  [0.4,0.6) *1  [0.6,0.8) *0.1  [0.8,1] *0.01
      const zone = Math.min(2, Math.floor(pos * 3));
      const multiplier = Math.pow(10, 1 - zone);         // 10, 1, 0.1
      this._dragStep = baseStep * multiplier;
      // precision = decimals needed to represent this step cleanly
      this._dragPrecision = Math.max(0, this.countDecimals(this._startValue) - (1 - zone));
      this._moved = false;
      document.addEventListener('mousemove', this.onMouseMove);
      document.addEventListener('mouseup', this.onMouseUp);
      document.addEventListener('mouseleave', this.onMouseLeave);
      if (!document.getElementById('number-drag-cursor-style')) {
        const style = document.createElement('style');
        style.id = 'number-drag-cursor-style';
        style.textContent = '* { cursor: none !important; }';
        document.head.appendChild(style);
      }
    },
    onMouseMove(e) {
      const dx = e.clientX - this._startX;
      if (!this._moved && Math.abs(dx) < 3) return;       // dead-zone
      this._moved = true;
      if (!this.isDragging) this.isDragging = true;

      const pxPerStep = Math.max(1, 4 / this.sensitivity);  // pixels needed per step
      const steps = Math.round(dx / pxPerStep);
      const raw = parseFloat((this._startValue + steps * this._dragStep).toFixed(this._dragPrecision));
      const clamped = Math.min(this.max, Math.max(this.min, raw));

      // Rebase origin when clamped so dragging back responds immediately
      if (clamped !== raw) {
        this._startX = e.clientX;
        this._startValue = clamped;
      }

      if (clamped !== this.modelValue) {
        this.$emit('update:modelValue', clamped);
      }
    },
    onMouseUp() {
      document.removeEventListener('mousemove', this.onMouseMove);
      document.removeEventListener('mouseup', this.onMouseUp);
      document.removeEventListener('mouseleave', this.onMouseLeave);
      const style = document.getElementById('number-drag-cursor-style');
      if (style) style.remove();
      this.isDragging = false;
      // if no drag happened, treat as single click → edit mode
      if (!this._moved) {
        this.enterEditMode();
      }
    },

    // ── Edit mode ─────────────────────────────────────
    enterEditMode() {
      this.editText = this.formattedValue;
      this.isEditing = true;
      this.$nextTick(() => {
        const inp = this.$refs.editInput;
        if (inp) { inp.focus(); inp.select(); }
      });
    },
    confirmEdit() {
      if (!this.isEditing) return;
      const parsed = parseFloat(this.editText);
      if (!isNaN(parsed)) {
        const clamped = Math.min(this.max, Math.max(this.min, parsed));
        if (clamped !== this.modelValue) {
          this.$emit('update:modelValue', clamped);
        }
      }
      this.isEditing = false;
    },
    cancelEdit() {
      this.isEditing = false;
    },
    onMouseLeave() {
      this.onMouseUp();
    },

    // ── Value helpers ─────────────────────────────────
    setValue(raw) {
      const clamped = Math.min(this.max, Math.max(this.min, raw));
      if (clamped !== this.modelValue) {
        this.$emit('update:modelValue', clamped);
      }
    },
  },

  beforeUnmount() {
    this.stopRepeat();
    document.removeEventListener('mousemove', this.onMouseMove);
    document.removeEventListener('mouseup', this.onMouseUp);
    document.removeEventListener('mouseleave', this.onMouseLeave);
    const style = document.getElementById('number-drag-cursor-style');
    if (style) style.remove();
  },
};
</script>

<style>
.number-drag {
  display: flex;
  align-items: center;
  height: var(--hw-compact-field-h, 26px);
  border-radius: 4px;
  background: var(--hw-bg-input, rgba(255, 255, 255, 0.06));
  border: 1px solid var(--hw-border, rgba(255, 255, 255, 0.10));
  overflow: hidden;
  user-select: none;
  font-size: 12px;
  color: inherit;
  transition: background 0.15s, border-color 0.15s;
}
.number-drag--hover {
  border-color: var(--hw-border-strong, rgba(255, 255, 255, 0.25));
}
.number-drag--dragging,
.number-drag--editing {
  background: var(--hw-bg-elevated, rgba(255, 255, 255, 0.12));
  border-color: var(--hw-accent, #4f8ef7);
}

/* ── Arrow buttons ─────────────────────────────── */
.number-drag__arrow {
  flex: 0 0 20px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 8px;
  padding: 0;
  transition: opacity 0.15s, background 0.1s;
}
.number-drag__arrow:hover {
  opacity: 1 !important;
  background: var(--hw-bg-elevated, rgba(255, 255, 255, 0.08));
}
.number-drag__arrow:active {
  background: var(--hw-accent-active, rgba(255, 255, 255, 0.15));
  color: var(--hw-text-on-accent, #fff);
}

/* ── Center area ───────────────────────────────── */
.number-drag__center {
  flex: 1 1 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ew-resize;
  min-width: 0;
  padding: 0 2px;
}
.number-drag--editing .number-drag__center {
  cursor: text;
}
.number-drag--dragging .number-drag__center {
  cursor: ew-resize;
}

.number-drag__display {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  pointer-events: none;
}
.number-drag__affix {
  opacity: 0.5;
}

/* ── Edit input ────────────────────────────────── */
.number-drag__input {
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: center;
  padding: 0 4px;
}
</style>
