/**
 * Image viewer: shows a StreamingBackend stream or a StillBackend image.
 *
 * stream: reads the multipart MJPEG response with fetch() and shows each JPEG
 *   through an object URL. An <img src> on an endless response keeps the tab's
 *   loading indicator spinning; a fetch() read does not. The fetch is aborted on
 *   unmount so the server sees the viewer leave.
 * still: an <img> on `endpoint?v=version`; the server bumps `version` when the
 *   image changes. Version 0 shows nothing. A click makes the view `enlarge` times
 *   wider, as tall as the image's aspect ratio needs, and shows the image `zoom`
 *   times the view's width in a scroll box; each new image reshapes the view.
 *   Dragging inside it pans, a click without a drag goes back.
 */

const WIDTH_VAR = '--hw-widget-min-width'  // the node's width floor, see haywire.ui.widget.sizing
const DRAG_SLOP = 4  // px a press may move and still count as a click

export default {
  template: `
    <div
      ref="box"
      class="hw-image-viewer"
      :style="containerStyle"
      @click="toggleEnlarged"
    >
      <div
        v-if="enlarged"
        ref="scroll"
        data-interactive="true"
        :style="scrollStyle"
        @mousedown="startPan"
      >
        <img :src="stillSrc" :style="imageStyle" draggable="false" @load="onEnlargedLoad" />
      </div>
      <img v-else ref="img" :src="stillSrc" :style="imageStyle" />
      <div v-if="error" class="hw-image-viewer-error text-xs" style="color: var(--hw-text-muted)">{{ errorMessage }}</div>
    </div>
  `,

  props: {
    endpoint: { type: String, required: true },
    mode: { type: String, default: 'stream' },
    version: { type: Number, default: 0 },
    enlarge: { type: Number, default: 2 },
    zoom: { type: Number, default: 2 }
  },

  data() {
    return {
      error: false,
      errorMessage: 'Stream unavailable',
      enlarged: false,
      viewWidth: 0,
      viewHeight: 0,
      imageWidth: 0,
      panning: false
    }
  },

  computed: {
    stillSrc() {
      if (this.mode !== 'still' || !this.version) return undefined
      return `${this.endpoint}?v=${this.version}`
    },

    containerStyle() {
      // min-height gives intrinsic size: a percentage height has nothing to resolve
      // against before the host node has measured once.
      return {
        position: 'relative',
        width: '100%',
        minHeight: '120px',
        backgroundColor: 'var(--hw-bg-page)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        cursor: this.mode === 'still' ? (this.enlarged ? 'zoom-out' : 'zoom-in') : 'default'
      }
    },

    scrollStyle() {
      // The scroll box is a child: on the root, the host's `flex: 1` would override the
      // fixed height and the node would grow to the image's natural height.
      // Block display: a flex box would centre, and so clip, an image larger than it.
      return {
        display: 'block',
        overflow: 'auto',
        flex: '0 0 auto',
        width: `${this.viewWidth}px`,
        height: `${this.viewHeight}px`,
        cursor: this.panning ? 'grabbing' : 'grab'
      }
    },

    imageStyle() {
      const hidden = this.error || (this.mode === 'still' && !this.version)
      if (this.enlarged) {
        return {
          display: hidden ? 'none' : 'block',
          width: `${this.imageWidth}px`,
          height: 'auto',
          maxWidth: 'none',
          maxHeight: 'none',
          userSelect: 'none'
        }
      }
      // flex: 1 1 auto with min sizes 0: the <img> is a replaced flex item whose
      // flex-basis is its natural size, and only this lets object-fit scale it down.
      return {
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        minWidth: '0',
        minHeight: '0',
        maxWidth: '100%',
        maxHeight: '100%',
        objectFit: 'contain',
        display: hidden ? 'none' : 'block'
      }
    }
  },

  methods: {
    toggleEnlarged() {
      if (this._dragged) {
        this._dragged = false  // the click that ends a pan
        return
      }
      if (this.mode !== 'still' || !this.version) return
      if (this.enlarged) {
        this._restoreWidthFloor()
        this.enlarged = false
        return
      }
      const box = this.$refs.box
      const img = this.$refs.img
      this.viewWidth = Math.round(box.clientWidth * this.enlarge)
      if (img && img.naturalWidth) {
        this._fitView(img.naturalWidth, img.naturalHeight)
      } else {
        this.viewHeight = Math.round(box.clientHeight * this.enlarge)
        this.imageWidth = Math.round(this.viewWidth * this.zoom)
      }
      this._raiseWidthFloor(this.viewWidth)
      this.enlarged = true
      this.$nextTick(() => this._centre())
    },

    /** Shape the enlarged view after the image: its width stays, its height follows the aspect ratio. */
    _fitView(naturalWidth, naturalHeight) {
      this.viewHeight = Math.round((this.viewWidth * naturalHeight) / naturalWidth)
      this.imageWidth = Math.round(this.viewWidth * this.zoom)
    },

    /** A new image arrived while enlarged: take its shape and look at its centre. */
    onEnlargedLoad(event) {
      const img = event.target
      if (!img.naturalWidth) return
      this._fitView(img.naturalWidth, img.naturalHeight)
      this.$nextTick(() => this._centre())
    },

    /** Raise the node's width floor so the card grows to the enlarged view. */
    _raiseWidthFloor(px) {
      const host = this.$el.closest('.widget-container') || this.$el
      this._floorHost = host
      this._savedFloor = host.style.getPropertyValue(WIDTH_VAR)
      host.style.setProperty(WIDTH_VAR, `${px}px`)
    },

    _restoreWidthFloor() {
      const host = this._floorHost
      if (!host) return
      if (this._savedFloor) host.style.setProperty(WIDTH_VAR, this._savedFloor)
      else host.style.removeProperty(WIDTH_VAR)
      this._floorHost = null
    },

    _centre() {
      const scroll = this.$refs.scroll
      if (!scroll) return
      scroll.scrollLeft = (scroll.scrollWidth - scroll.clientWidth) / 2
      scroll.scrollTop = (scroll.scrollHeight - scroll.clientHeight) / 2
    },

    /** Pan the enlarged view by dragging; the canvas leaves data-interactive presses alone. */
    startPan(event) {
      if (event.button !== 0) return
      const scroll = this.$refs.scroll
      const startX = event.clientX
      const startY = event.clientY
      const left = scroll.scrollLeft
      const top = scroll.scrollTop
      this._dragged = false
      const move = (e) => {
        const dx = e.clientX - startX
        const dy = e.clientY - startY
        if (!this._dragged && Math.hypot(dx, dy) < DRAG_SLOP) return
        this._dragged = true
        this.panning = true
        scroll.scrollLeft = left - dx
        scroll.scrollTop = top - dy
      }
      const up = () => {
        window.removeEventListener('mousemove', move)
        window.removeEventListener('mouseup', up)
        this.panning = false
      }
      window.addEventListener('mousemove', move)
      window.addEventListener('mouseup', up)
      event.preventDefault()
    },

    /** Open the MJPEG stream and show its frames; reconnect after 1 s until unmounted. */
    async _startStream() {
      while (!this._stopped) {
        this._abort = new AbortController()
        try {
          const response = await fetch(this.endpoint, { signal: this._abort.signal })
          if (!response.ok || !response.body) {
            throw new Error(`HTTP ${response.status}`)
          }
          this.error = false
          await this._consume(response.body.getReader())
        } catch (e) {
          if (this._stopped || e.name === 'AbortError') return
          this.error = true
          console.error('Image viewer: stream error', e)
        }
        if (this._stopped) return
        await new Promise(r => setTimeout(r, 1000))
      }
    },

    /**
     * Read multipart parts of the form
     *   --frame\r\nContent-Type: image/jpeg\r\nContent-Length: N\r\n\r\n<N bytes>\r\n
     * and hand each JPEG to _showFrame().
     */
    async _consume(reader) {
      const decoder = new TextDecoder('latin1')
      let buf = new Uint8Array(0)

      const append = (chunk) => {
        const next = new Uint8Array(buf.length + chunk.length)
        next.set(buf, 0)
        next.set(chunk, buf.length)
        buf = next
      }

      const indexOf = (needle, from) => {
        outer: for (let i = from; i <= buf.length - needle.length; i++) {
          for (let j = 0; j < needle.length; j++) {
            if (buf[i + j] !== needle[j]) continue outer
          }
          return i
        }
        return -1
      }

      const SEP = [13, 10, 13, 10]

      while (true) {
        if (this._stopped) {
          await reader.cancel().catch(() => {})
          return
        }
        const headerEnd = indexOf(SEP, 0)
        if (headerEnd === -1) {
          const { done, value } = await reader.read()
          if (done) return
          append(value)
          continue
        }
        const headerText = decoder.decode(buf.subarray(0, headerEnd))
        const match = /Content-Length:\s*(\d+)/i.exec(headerText)
        if (!match) {
          buf = buf.subarray(headerEnd + SEP.length)  // garbage before a boundary: resync
          continue
        }
        const length = parseInt(match[1], 10)
        const bodyStart = headerEnd + SEP.length
        while (buf.length < bodyStart + length) {
          if (this._stopped) {
            await reader.cancel().catch(() => {})
            return
          }
          const { done, value } = await reader.read()
          if (done) return
          append(value)
        }
        this._showFrame(buf.subarray(bodyStart, bodyStart + length))
        let nextStart = bodyStart + length
        if (buf[nextStart] === 13 && buf[nextStart + 1] === 10) nextStart += 2
        buf = buf.slice(nextStart)
      }
    },

    /** Show one JPEG through an object URL, revoking the previous one after the next paint. */
    _showFrame(bytes) {
      const img = this.$refs.img
      if (!img) return
      const url = URL.createObjectURL(new Blob([bytes.slice()], { type: 'image/jpeg' }))
      const previous = this._objectUrl
      img.src = url
      this._objectUrl = url
      this.error = false
      if (previous) requestAnimationFrame(() => URL.revokeObjectURL(previous))
    }
  },

  mounted() {
    this._stopped = false
    this._abort = null
    this._objectUrl = null
    if (this.mode === 'stream') this._startStream()
  },

  updated() {
    // A server update re-applies the element's style, and with it the declared width floor.
    if (this.enlarged && this._floorHost) this._floorHost.style.setProperty(WIDTH_VAR, `${this.viewWidth}px`)
  },

  beforeUnmount() {
    this._restoreWidthFloor()
    this._stopped = true
    if (this._abort) {
      this._abort.abort()
      this._abort = null
    }
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl)
      this._objectUrl = null
    }
  }
}
