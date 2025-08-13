#!/usr/bin/env python3
"""
Launch script for the Haywire Undo/Redo Test Application.

This script sets up the Python path and launches the test application
with proper error handling and development settings.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    # Import and run the test application
    from test_undo_app import main
    
    print("Starting Haywire Undo/Redo Test Application...")
    print("Features included:")
    print("  ✓ Pan/Zoom node editor")
    print("  ✓ Undo/Redo system")
    print("  ✓ Node creation and manipulation")
    print("  ✓ Interactive graph operations")
    print("  ✓ Real-time statistics")
    print("  ✓ Hot reload notifications")
    print()
    print("Opening application in browser...")
    
    main()
    
except ImportError as e:
    print(f"Import Error: {e}")
    print("Make sure all required dependencies are installed:")
    print("  pip install nicegui")
    print("  pip install watchdog")  # For file watching if needed
    sys.exit(1)
    
except Exception as e:
    print(f"Error starting application: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
