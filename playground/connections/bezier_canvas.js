// bezier_canvas.js - Interactive Image pattern implementation
export default {
  template: `
    <div class="bezier-canvas-container" 
         style="position: relative;"
         :style="{ width: width + 'px', height: height + 'px' }">
      
      <!-- Background slot - always receives events -->
      <div class="bezier-background" 
           style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 1;">
        <slot name="background"></slot>
      </div>
      
      <!-- SVG canvas for curves - pointer events handled per element -->
      <svg 
        ref="svg"
        :width="width" 
        :height="height" 
        class="bezier-canvas"
        style="position: absolute; top: 0; left: 0; z-index: 2; pointer-events: none;"
      >
        
        <!-- Render all curves -->
        <g v-for="(curve, index) in curves" :key="curve.id">
          <!-- Control lines (when control points are shown) -->
          <g v-if="curve.showControlPoints">
            <line 
              :x1="curve.startPoint.x" 
              :y1="curve.startPoint.y" 
              :x2="curve.controlPoint1.x" 
              :y2="curve.controlPoint1.y"
              stroke="#94a3b8" 
              stroke-width="1" 
              stroke-dasharray="5,5"
              style="pointer-events: none;"
            />
            <line 
              :x1="curve.endPoint.x" 
              :y1="curve.endPoint.y" 
              :x2="curve.controlPoint2.x" 
              :y2="curve.controlPoint2.y"
              stroke="#94a3b8" 
              stroke-width="1" 
              stroke-dasharray="5,5"
              style="pointer-events: none;"
            />
          </g>
          
          <!-- Main Bézier curve -->
          <path
            :d="getCurvePathData(curve)"
            :stroke="curve.strokeColor"
            :stroke-width="curve.strokeWidth"
            fill="none"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="bezier-path"
            :class="{ 'curve-selected': selectedCurveId === curve.id }"
            style="pointer-events: stroke; cursor: pointer;"
            @pointerdown="(e) => onCurvePointerDown(e, curve.id)"
          />
          
          <!-- Start point -->
          <circle
            :cx="curve.startPoint.x"
            :cy="curve.startPoint.y"
            r="6"
            fill="#3b82f6"
            stroke="#1e40af"
            stroke-width="2"
            class="start-point"
            style="pointer-events: all; cursor: grab;"
            @pointerdown="(e) => onPointPointerDown(e, curve.id, 'start')"
          />
          
          <!-- End point -->
          <circle
            :cx="curve.endPoint.x"
            :cy="curve.endPoint.y"
            r="6"
            fill="#3b82f6"
            stroke="#1e40af"
            stroke-width="2"
            class="end-point"
            style="pointer-events: all; cursor: grab;"
            @pointerdown="(e) => onPointPointerDown(e, curve.id, 'end')"
          />
          
          <!-- Control points (when shown) -->
          <g v-if="curve.showControlPoints">
            <!-- Control point 1 -->
            <circle
              :cx="curve.controlPoint1.x"
              :cy="curve.controlPoint1.y"
              r="6"
              fill="#94a3b8"
              stroke="#475569"
              stroke-width="2"
              class="control-point"
              style="pointer-events: all; cursor: grab;"
              @pointerdown="(e) => onPointPointerDown(e, curve.id, 'control1')"
            />
            
            <!-- Control point 2 -->
            <circle
              :cx="curve.controlPoint2.x"
              :cy="curve.controlPoint2.y"
              r="6"
              fill="#94a3b8"
              stroke="#475569"
              stroke-width="2"
              class="control-point"
              style="pointer-events: all; cursor: grab;"
              @pointerdown="(e) => onPointPointerDown(e, curve.id, 'control2')"
            />
          </g>
          
          <!-- Point labels (when shown) -->
          <text v-if="curve.showControlPoints && showLabels" 
                :x="curve.startPoint.x + 10" 
                :y="curve.startPoint.y - 10" 
                font-size="10" 
                fill="#3b82f6"
                style="pointer-events: none; user-select: none;">S</text>
          <text v-if="curve.showControlPoints && showLabels" 
                :x="curve.endPoint.x + 10" 
                :y="curve.endPoint.y - 10" 
                font-size="10" 
                fill="#3b82f6"
                style="pointer-events: none; user-select: none;">E</text>
          <text v-if="curve.showControlPoints && showLabels" 
                :x="curve.controlPoint1.x - 15" 
                :y="curve.controlPoint1.y - 15" 
                font-size="10" 
                fill="#94a3b8"
                style="pointer-events: none; user-select: none;">C1</text>
          <text v-if="curve.showControlPoints && showLabels" 
                :x="curve.controlPoint2.x - 15" 
                :y="curve.controlPoint2.y - 15" 
                font-size="10" 
                fill="#94a3b8"
                style="pointer-events: none; user-select: none;">C2</text>
        </g>
      </svg>

    <!-- Foreground slot - always receives events -->
      <div class="bezier-foreground" 
           style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 10;">
        <slot name="foreground"></slot>
      </div>
 
    </div>
  `,
  
  props: {
    curves: {
      type: Array,
      default: () => []
    },
    width: {
      type: Number,
      default: 600
    },
    height: {
      type: Number,
      default: 400
    },
    selectedCurveId: {
      type: String,
      default: null
    },
    showLabels: {
      type: Boolean,
      default: false
    }
  },
  
  data() {
    return {
      isDragging: false,
      dragTarget: null,
      dragCurveId: null,
      dragOffset: { x: 0, y: 0 },
      initialPointerPosition: { x: 0, y: 0 },
      hasPointerCapture: false
    };
  },
  
  mounted() {
    // Add global pointer event listeners
    document.addEventListener('pointermove', this.onPointerMove);
    document.addEventListener('pointerup', this.onPointerUp);
    
    console.log('BezierCanvas mounted with curves:', this.curves);
  },
  
  beforeUnmount() {
    // Clean up event listeners
    document.removeEventListener('pointermove', this.onPointerMove);
    document.removeEventListener('pointerup', this.onPointerUp);
  },
  
  methods: {
    getCurvePathData(curve) {
      return `M ${curve.startPoint.x},${curve.startPoint.y} C ${curve.controlPoint1.x},${curve.controlPoint1.y} ${curve.controlPoint2.x},${curve.controlPoint2.y} ${curve.endPoint.x},${curve.endPoint.y}`;
    },
    
    // Get SVG coordinates from pointer event
    getSVGCoordinates(event) {
      const svg = this.$refs.svg;
      if (!svg) return { x: 0, y: 0 };
      
      const rect = svg.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
    },
       
    // Curve pointer down - emit curve click
    onCurvePointerDown(event, curveId) {
      event.preventDefault();
      event.stopPropagation();
      
      const coords = this.getSVGCoordinates(event);
      console.log('Curve clicked:', curveId, 'at:', coords);
      
      this.$emit('mouse', {
        mouse_event_type: 'curve_click',
        image_x: coords.x,
        image_y: coords.y,
        curveId: curveId,
        button: event.button,
        buttons: event.buttons,
        altKey: event.altKey,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey
      });
    },
    
    // Point pointer down - start drag operation
    onPointPointerDown(event, curveId, pointType) {
      event.preventDefault();
      event.stopPropagation();
      
      // Capture pointer to this element for reliable drag handling
      event.target.setPointerCapture(event.pointerId);
      this.hasPointerCapture = true;
      
      this.isDragging = true;
      this.dragTarget = pointType;
      this.dragCurveId = curveId;
      
      const coords = this.getSVGCoordinates(event);
      this.initialPointerPosition = coords;
      
      // Find the current point position to calculate offset
      const curve = this.curves.find(c => c.id === curveId);
      if (curve) {
        let pointPosition;
        switch (pointType) {
          case 'start':
            pointPosition = curve.startPoint;
            break;
          case 'end':
            pointPosition = curve.endPoint;
            break;
          case 'control1':
            pointPosition = curve.controlPoint1;
            break;
          case 'control2':
            pointPosition = curve.controlPoint2;
            break;
        }
        
        this.dragOffset = {
          x: coords.x - pointPosition.x,
          y: coords.y - pointPosition.y
        };
      }
      
      console.log('Start dragging:', pointType, 'of curve:', curveId, 'at:', coords);
      
      // Emit drag start event
      this.$emit('mouse', {
        mouse_event_type: 'drag_start',
        image_x: coords.x,
        image_y: coords.y,
        curveId: curveId,
        pointType: pointType,
        button: event.button,
        buttons: event.buttons,
        altKey: event.altKey,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey
      });
    },
    
    // Global pointer move handler
    onPointerMove(event) {
      if (!this.isDragging || !this.dragTarget || !this.dragCurveId) return;
      
      const coords = this.getSVGCoordinates(event);
      
      // Calculate new position accounting for drag offset
      const newPosition = {
        x: Math.max(0, Math.min(this.width, coords.x - this.dragOffset.x)),
        y: Math.max(0, Math.min(this.height, coords.y - this.dragOffset.y))
      };
      
      // Emit point drag event
      this.$emit('mouse', {
        mouse_event_type: 'point_drag',
        image_x: newPosition.x,
        image_y: newPosition.y,
        curveId: this.dragCurveId,
        pointType: this.dragTarget,
        button: event.button,
        buttons: event.buttons,
        altKey: event.altKey,
        ctrlKey: event.ctrlKey,
        metaKey: event.metaKey,
        shiftKey: event.shiftKey
      });
    },
    
    // Global pointer up handler
    onPointerUp(event) {
      if (this.isDragging) {
        const coords = this.getSVGCoordinates(event);
        
        console.log('End dragging:', this.dragTarget, 'of curve:', this.dragCurveId, 'at:', coords);
        
        // Emit drag end event
        this.$emit('mouse', {
          mouse_event_type: 'drag_end',
          image_x: coords.x,
          image_y: coords.y,
          curveId: this.dragCurveId,
          pointType: this.dragTarget,
          button: event.button,
          buttons: event.buttons,
          altKey: event.altKey,
          ctrlKey: event.ctrlKey,
          metaKey: event.metaKey,
          shiftKey: event.shiftKey
        });
        
        // Reset drag state
        this.isDragging = false;
        this.dragTarget = null;
        this.dragCurveId = null;
        this.dragOffset = { x: 0, y: 0 };
        this.hasPointerCapture = false;
      }
    }
  }
};
