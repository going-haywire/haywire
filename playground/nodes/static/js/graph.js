// Node Graph Editor JavaScript utilities

class GraphInteraction {
    constructor() {
        this.isDragging = false;
        this.dragNode = null;
        this.dragOffset = { x: 0, y: 0 };
        this.isConnecting = false;
        this.connectionStart = null;
        this.tempConnection = null;
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // Mouse event handlers for drag and drop
        document.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // Prevent context menu on canvas
        document.addEventListener('contextmenu', (e) => {
            if (e.target.classList.contains('graph-canvas')) {
                e.preventDefault();
            }
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }
    
    handleMouseDown(e) {
        // Check if clicking on a node
        const nodeCard = e.target.closest('.node-card');
        if (nodeCard) {
            this.startNodeDrag(e, nodeCard);
            return;
        }
        
        // Check if clicking on a port
        const port = e.target.closest('.port');
        if (port) {
            this.startConnection(e, port);
            return;
        }
    }
    
    handleMouseMove(e) {
        if (this.isDragging && this.dragNode) {
            this.updateNodePosition(e);
        } else if (this.isConnecting) {
            this.updateTempConnection(e);
        }
    }
    
    handleMouseUp(e) {
        if (this.isDragging) {
            this.endNodeDrag();
        } else if (this.isConnecting) {
            this.endConnection(e);
        }
    }
    
    handleKeyDown(e) {
        // Delete selected nodes
        if (e.key === 'Delete' || e.key === 'Backspace') {
            this.deleteSelectedNodes();
        }
        
        // Select all nodes
        if (e.ctrlKey && e.key === 'a') {
            e.preventDefault();
            this.selectAllNodes();
        }
        
        // Copy nodes
        if (e.ctrlKey && e.key === 'c') {
            this.copySelectedNodes();
        }
        
        // Paste nodes
        if (e.ctrlKey && e.key === 'v') {
            this.pasteNodes();
        }
    }
    
    startNodeDrag(e, nodeCard) {
        this.isDragging = true;
        this.dragNode = nodeCard;
        
        const rect = nodeCard.getBoundingClientRect();
        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
        
        nodeCard.style.zIndex = '1000';
        document.body.style.cursor = 'grabbing';
    }
    
    updateNodePosition(e) {
        if (!this.dragNode) return;
        
        const canvas = document.querySelector('.graph-canvas');
        const canvasRect = canvas.getBoundingClientRect();
        
        const x = e.clientX - canvasRect.left - this.dragOffset.x;
        const y = e.clientY - canvasRect.top - this.dragOffset.y;
        
        this.dragNode.style.left = `${Math.max(0, x)}px`;
        this.dragNode.style.top = `${Math.max(0, y)}px`;
    }
    
    endNodeDrag() {
        if (this.dragNode) {
            this.dragNode.style.zIndex = '';
            this.dragNode = null;
        }
        
        this.isDragging = false;
        document.body.style.cursor = '';
    }
    
    startConnection(e, port) {
        this.isConnecting = true;
        this.connectionStart = port;
        
        // Create temporary connection line
        this.createTempConnection(e);
    }
    
    createTempConnection(e) {
        const svg = document.querySelector('.connection-svg');
        if (!svg) return;
        
        this.tempConnection = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        this.tempConnection.setAttribute('stroke', '#1976d2');
        this.tempConnection.setAttribute('stroke-width', '2');
        this.tempConnection.setAttribute('stroke-dasharray', '5,5');
        
        const startRect = this.connectionStart.getBoundingClientRect();
        const svgRect = svg.getBoundingClientRect();
        
        const startX = startRect.left + startRect.width / 2 - svgRect.left;
        const startY = startRect.top + startRect.height / 2 - svgRect.top;
        
        this.tempConnection.setAttribute('x1', startX);
        this.tempConnection.setAttribute('y1', startY);
        this.tempConnection.setAttribute('x2', startX);
        this.tempConnection.setAttribute('y2', startY);
        
        svg.appendChild(this.tempConnection);
    }
    
    updateTempConnection(e) {
        if (!this.tempConnection) return;
        
        const svg = document.querySelector('.connection-svg');
        const svgRect = svg.getBoundingClientRect();
        
        const endX = e.clientX - svgRect.left;
        const endY = e.clientY - svgRect.top;
        
        this.tempConnection.setAttribute('x2', endX);
        this.tempConnection.setAttribute('y2', endY);
    }
    
    endConnection(e) {
        // Remove temporary connection
        if (this.tempConnection) {
            this.tempConnection.remove();
            this.tempConnection = null;
        }
        
        // Check if dropping on a valid port
        const targetPort = e.target.closest('.port');
        if (targetPort && targetPort !== this.connectionStart) {
            this.createConnection(this.connectionStart, targetPort);
        }
        
        this.isConnecting = false;
        this.connectionStart = null;
    }
    
    createConnection(sourcePort, targetPort) {
        // Validate connection (implement your validation logic)
        const sourceIsOutput = sourcePort.classList.contains('output-port');
        const targetIsInput = targetPort.classList.contains('input-port');
        
        if (sourceIsOutput && targetIsInput) {
            // Valid connection - notify the application
            const sourcePortId = sourcePort.getAttribute('data-port-id');
            const targetPortId = targetPort.getAttribute('data-port-id');
            
            // Trigger a custom event that the Python backend can listen to
            window.dispatchEvent(new CustomEvent('createConnection', {
                detail: { sourcePortId, targetPortId }
            }));
        }
    }
    
    deleteSelectedNodes() {
        const selectedNodes = document.querySelectorAll('.node-card.selected');
        selectedNodes.forEach(node => {
            // Trigger deletion event
            window.dispatchEvent(new CustomEvent('deleteNode', {
                detail: { nodeId: node.getAttribute('data-node-id') }
            }));
        });
    }
    
    selectAllNodes() {
        const nodes = document.querySelectorAll('.node-card');
        nodes.forEach(node => node.classList.add('selected'));
    }
    
    copySelectedNodes() {
        // Implement copy functionality
        console.log('Copy not implemented');
    }
    
    pasteNodes() {
        // Implement paste functionality
        console.log('Paste not implemented');
    }
}

// Utility functions for graph manipulation
class GraphUtils {
    static getNodeBounds(nodeElement) {
        const rect = nodeElement.getBoundingClientRect();
        const canvas = document.querySelector('.graph-canvas');
        const canvasRect = canvas.getBoundingClientRect();
        
        return {
            x: rect.left - canvasRect.left,
            y: rect.top - canvasRect.top,
            width: rect.width,
            height: rect.height
        };
    }
    
    static getPortPosition(portElement) {
        const rect = portElement.getBoundingClientRect();
        const canvas = document.querySelector('.graph-canvas');
        const canvasRect = canvas.getBoundingClientRect();
        
        return {
            x: rect.left + rect.width / 2 - canvasRect.left,
            y: rect.top + rect.height / 2 - canvasRect.top
        };
    }
    
    static createCurvedPath(start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const controlOffset = Math.abs(dx) * 0.5;
        
        return `M ${start.x} ${start.y} C ${start.x + controlOffset} ${start.y} ${end.x - controlOffset} ${end.y} ${end.x} ${end.y}`;
    }
    
    static snapToGrid(value, gridSize = 20) {
        return Math.round(value / gridSize) * gridSize;
    }
}

// Initialize graph interaction when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.graphInteraction = new GraphInteraction();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GraphInteraction, GraphUtils };
}
