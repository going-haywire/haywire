## Testing Recommendations

### Unit Tests
- [ ] Test callback registration/unregistration
- [ ] Test callback invocation on reload/add/remove
- [ ] Test error isolation between callbacks
- [ ] Test registry subscriber chains

### Integration Tests
- [ ] Test NodeFactory hot reload flow
- [ ] Test NodeRenderFactory cache clearing
- [ ] Test CustomType → Node cascade reload
- [ ] Test error recovery and rollback


## Edge Testing Checklist

- [ ] UIEdge creation on connection add
- [ ] UIEdge cleanup on connection remove
- [ ] Visual state calculation (VALID/WARNING/INVALID)
- [ ] Sync event emission to Vue
- [ ] Vue handler updates SVG attributes
- [ ] CSS classes applied correctly
- [ ] Context menu displays metrics
- [ ] Hot reload triggers visual update
- [ ] Manual testing: Create connection between nodes
- [ ] Manual testing: Trigger adapter hot reload
- [ ] Manual testing: Verify color changes
- [ ] Manual testing: Right-click connection for context menu
- [ ] Manual testing: Verify metrics display
