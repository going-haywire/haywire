<template>
  <teleport to="body">
    <!-- Context Menu Overlay -->
    <div 
      v-if="showMenu"
      class="context-menu-overlay"
      @click="hideMenu"
      @contextmenu.prevent="hideMenu"
    >
      <!-- Context Menu -->
      <div 
        class="context-menu"
        :style="menuStyle"
        @click.stop
      >
        <div class="context-menu-header">
          <span class="menu-title">{{ menuTitle }}</span>
          <button class="close-button" @click="hideMenu">×</button>
        </div>
        
        <div class="context-menu-content">
          <!-- Node Creation Menu (for canvas) -->
          <div v-if="menuType === 'canvas'" class="menu-section">
            <div class="menu-section-title">Create Node</div>
            <div 
              v-for="nodeType in availableNodes" 
              :key="nodeType"
              class="menu-item"
              @click="createNode(nodeType)"
            >
              <i class="menu-icon">+</i>
              {{ getNodeDisplayName(nodeType) }}
            </div>
          </div>
          
          <!-- Node Menu (for nodes) -->
          <div v-if="menuType === 'node'" class="menu-section">
            <div class="menu-item" @click="duplicateNode">
              <i class="menu-icon">📋</i>
              Duplicate
            </div>
            <div class="menu-item" @click="copyNode">
              <i class="menu-icon">📄</i>
              Copy
            </div>
            <div class="menu-separator"></div>
            <div class="menu-item danger" @click="deleteNode">
              <i class="menu-icon">🗑️</i>
              Delete
            </div>
          </div>
          
          <!-- Connection Menu (for connections) -->
          <div v-if="menuType === 'connection'" class="menu-section">
            <div class="menu-item" @click="inspectConnection">
              <i class="menu-icon">🔍</i>
              Inspect
            </div>
            <div class="menu-separator"></div>
            <div class="menu-item danger" @click="deleteConnection">
              <i class="menu-icon">🗑️</i>
              Delete Connection
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: 'ContextMenu',
  
  props: {
    availableNodes: { type: Array, default: () => [] }
  },
  
  data() {
    return {
      showMenu: false,
      menuType: '', // 'canvas', 'node', 'connection'
      menuX: 0,
      menuY: 0,
      targetElement: null,
      targetData: null
    };
  },
  
  computed: {
    menuTitle() {
      switch(this.menuType) {
        case 'canvas': return 'Canvas Menu';
        case 'node': return 'Node Menu';
        case 'connection': return 'Connection Menu';
        default: return 'Context Menu';
      }
    },
    
    menuStyle() {
      return {
        left: `${this.menuX}px`,
        top: `${this.menuY}px`,
        position: 'fixed',
        zIndex: 10000,
        // Remove transform to prevent interference with fixed positioning
        // transform: 'translate(0, 0)' // Ensure no additional transforms
      };
    }
  },
  
  mounted() {
    // Listen for context menu events from the parent
    this.$el.addEventListener('show-context-menu', this.handleShowContextMenu);
    document.addEventListener('keydown', this.handleKeydown);
  },
  
  beforeDestroy() {
    this.$el.removeEventListener('show-context-menu', this.handleShowContextMenu);
    document.removeEventListener('keydown', this.handleKeydown);
  },
  
  methods: {
    handleShowContextMenu(event) {
      const { menuType, x, y, targetElement, targetData } = event.detail;
      this.showContextMenu(menuType, x, y, targetElement, targetData);
    },
    
    handleKeydown(event) {
      if (event.key === 'Escape' && this.showMenu) {
        this.hideMenu();
      }
    },
    
    showContextMenu(menuType, x, y, targetElement = null, targetData = null) {
      this.menuType = menuType;
      // Add small offset to position menu near but not exactly on cursor
      this.menuX = x + 2;
      this.menuY = y + 2;
      this.targetElement = targetElement;
      this.targetData = targetData;
      this.showMenu = true;
      
      console.log(`Showing ${menuType} context menu at (${x}, ${y}) -> offset to (${this.menuX}, ${this.menuY})`);
      
      // Ensure menu doesn't go off-screen
      this.$nextTick(() => {
        // With teleport, we need to query the document instead of $el
        const menu = document.querySelector('.context-menu');
        if (menu) {
          const rect = menu.getBoundingClientRect();
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;
          
          let adjustedX = this.menuX;
          let adjustedY = this.menuY;
          
          // Adjust horizontal position if menu would go off right edge
          if (rect.right > viewportWidth) {
            adjustedX = viewportWidth - rect.width - 10;
          }
          
          // Adjust vertical position if menu would go off bottom edge
          if (rect.bottom > viewportHeight) {
            adjustedY = viewportHeight - rect.height - 10;
          }
          
          // Ensure menu doesn't go off left or top edges
          if (adjustedX < 10) adjustedX = 10;
          if (adjustedY < 10) adjustedY = 10;
          
          // Update positions if they were adjusted
          if (adjustedX !== this.menuX || adjustedY !== this.menuY) {
            this.menuX = adjustedX;
            this.menuY = adjustedY;
            console.log(`Adjusted menu position to (${adjustedX}, ${adjustedY})`);
          }
        }
      });
    },
    
    hideMenu() {
      this.showMenu = false;
      this.menuType = '';
      this.targetElement = null;
      this.targetData = null;
    },
    
    getNodeDisplayName(nodeType) {
      // Extract readable name from node type
      const parts = nodeType.split(':');
      if (parts.length > 1) {
        return parts[parts.length - 1].replace(/\./g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      }
      return nodeType;
    },
    
    // Canvas Actions
    createNode(nodeType) {
      this.$emit('createNode', {
        nodeType: nodeType,
        x: this.targetData?.x || this.menuX,
        y: this.targetData?.y || this.menuY
      });
      this.hideMenu();
    },
    
    // Node Actions
    duplicateNode() {
      this.$emit('duplicateNode', {
        nodeId: this.targetData?.nodeId,
        element: this.targetElement
      });
      this.hideMenu();
    },
    
    copyNode() {
      this.$emit('copyNode', {
        nodeId: this.targetData?.nodeId,
        element: this.targetElement
      });
      this.hideMenu();
    },
    
    deleteNode() {
      this.$emit('deleteNode', {
        nodeId: this.targetData?.nodeId,
        element: this.targetElement
      });
      this.hideMenu();
    },
    
    // Connection Actions
    inspectConnection() {
      this.$emit('inspectConnection', {
        connectionId: this.targetData?.connectionId,
        element: this.targetElement
      });
      this.hideMenu();
    },
    
    deleteConnection() {
      this.$emit('deleteConnection', {
        connectionId: this.targetData?.connectionId,
        element: this.targetElement
      });
      this.hideMenu();
    }
  }
}
</script>

<style>
/* Context Menu Styles - Not scoped to work with teleport */
.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.1);
  z-index: 9999;
}

.context-menu {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  border: 1px solid #e0e0e0;
  min-width: 200px;
  max-width: 300px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
}

.context-menu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px 8px 16px;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
  border-radius: 8px 8px 0 0;
}

.menu-title {
  font-weight: 600;
  color: #333;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.close-button {
  background: none;
  border: none;
  font-size: 18px;
  color: #666;
  cursor: pointer;
  padding: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button:hover {
  background: #e0e0e0;
  color: #333;
}

.context-menu-content {
  padding: 8px 0;
}

.menu-section {
  margin-bottom: 4px;
}

.menu-section:last-child {
  margin-bottom: 0;
}

.menu-section-title {
  padding: 8px 16px 4px 16px;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.15s ease;
  color: #333;
}

.menu-item:hover {
  background: #f0f7ff;
  color: #1976d2;
}

.menu-item.danger {
  color: #d32f2f;
}

.menu-item.danger:hover {
  background: #ffebee;
  color: #c62828;
}

.menu-icon {
  margin-right: 12px;
  font-size: 16px;
  width: 20px;
  text-align: center;
  font-style: normal;
}

.menu-separator {
  height: 1px;
  background: #e0e0e0;
  margin: 4px 0;
}

/* Animation */
.context-menu {
  animation: menuFadeIn 0.15s ease-out;
}

@keyframes menuFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
