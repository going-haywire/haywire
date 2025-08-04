
from .elements import Outlet, Inlet

# Example showing how pipes would work with multi-value inlets
class Pipe:
    """Example pipe class for data propagation"""
    def __init__(self, source_outlet: Outlet, target_inlet: Inlet, pipe_id: str):
        self.source_outlet = source_outlet
        self.target_inlet = target_inlet
        self.pipe_id = pipe_id
        
        # Add this pipe to outlet's pipe list
        source_outlet.pipes.append(self)
    
    def propagate(self, value: Any):
        """Propagate value through pipe using polymorphic DataField interface"""
        # The DataField subclass will handle the logic based on its type
        # ScalarField ignores source_id, MultiField uses it
        self.target_inlet.set_value_from_source(self.pipe_id, value)    


    def disconnect(self):
        """Disconnect the pipe using polymorphic DataField interface"""
        # Remove from outlet's pipes
        self.source_outlet.pipes.remove(self)
        
        # Remove source using polymorphic interface
        # ScalarField will clear its value, MultiField will remove the specific source
        self.target_inlet.remove_source(self.pipe_id)
        
        # Update connection status based on remaining sources
        # Use polymorphic has_sources method
        self.target_inlet.is_connected = self.target_inlet.data.has_sources() if self.target_inlet.data else False
