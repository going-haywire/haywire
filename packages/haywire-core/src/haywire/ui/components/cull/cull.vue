<template>
  <div class="hw-node-cull" :style="cullStyle">
    <!-- The whole point. NiceGUI hands a slot to Vue as a FUNCTION; withholding
         it means renderRecursively never descends into this node's subtree, so
         the page's full-tree render walk skips ~84 elements per culled node. -->
    <slot v-if="shown" />
  </div>
</template>

<script>
export default {
  data() {
    return {
      shown: true,
      // Layout size remembered at cull time, so the placeholder keeps the
      // node's footprint and nothing around it reflows. offsetWidth/Height,
      // not getBoundingClientRect: the latter is multiplied by canvas zoom.
      w: 0,
      h: 0,
    };
  },

  computed: {
    cullStyle() {
      return this.shown ? '' : `width:${this.w}px;height:${this.h}px;`;
    },
  },

  mounted() {
    // Same handle pattern as pan.vue's `_zoomPanControls`: the canvas drives
    // culling entirely client-side, so a pan costs no websocket traffic.
    this.$el._hwCull = {
      setVisible: (v) => this.setVisible(v),
      isVisible: () => this.shown,
    };
  },

  beforeUnmount() {
    delete this.$el._hwCull;
  },

  methods: {
    setVisible(v) {
      const next = !!v;
      if (next === this.shown) return;
      if (!next) {
        this.w = this.$el.offsetWidth;
        this.h = this.$el.offsetHeight;
      }
      this.shown = next;
    },
  },
};
</script>
