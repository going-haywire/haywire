/**
 * Image viewer: shows a StreamingBackend stream or a StillBackend image.
 *
 * stream: reads the multipart MJPEG response with fetch() and shows each JPEG
 *   through an object URL. An <img src> on an endless response keeps the tab's
 *   loading indicator spinning; a fetch() read does not. The fetch is aborted on
 *   unmount so the server sees the viewer leave.
 * still: an <img> on `endpoint?v=version`; the server bumps `version` when the
 *   image changes. Version 0 shows nothing. A click toggles 1:1, which shows the
 *   image at its natural size in a scroll box of the height the fitted view had.
 */

export default {
  template: `
    <div
      ref="box"
      class="hw-image-viewer"
      :class="{ 'hw-image-1to1': oneToOne }"
      :style="containerStyle"
      @click="toggleOneToOne"
    >
      <img ref="img" :src="stillSrc" :style="imageStyle" />
      <div v-if="error" class="hw-image-viewer-error text-xs" style="color: var(--hw-text-muted)">{{ errorMessage }}</div>
    </div>
  `,

  props: {
    endpoint: { type: String, required: true },
    mode: { type: String, default: 'stream' },
    version: { type: Number, default: 0 }
  },

  data() {
    return {
      error: false,
      errorMessage: 'Stream unavailable',
      oneToOne: false,
      fixedHeight: null
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
      const style = {
        position: 'relative',
        width: '100%',
        minHeight: '120px',
        backgroundColor: 'var(--hw-bg-page)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        cursor: this.mode === 'still' ? (this.oneToOne ? 'zoom-out' : 'zoom-in') : 'default'
      }
      if (this.oneToOne) {
        // Block display: a flex box would centre, and so clip, an image larger than it.
        style.display = 'block'
        style.overflow = 'auto'
        style.height = `${this.fixedHeight}px`
      }
      return style
    },

    imageStyle() {
      const hidden = this.error || (this.mode === 'still' && !this.version)
      if (this.oneToOne) {
        return { display: hidden ? 'none' : 'block', maxWidth: 'none', maxHeight: 'none' }
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
    toggleOneToOne() {
      if (this.mode !== 'still' || !this.version) return
      if (!this.oneToOne) this.fixedHeight = this.$refs.box.clientHeight
      this.oneToOne = !this.oneToOne
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

  beforeUnmount() {
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
