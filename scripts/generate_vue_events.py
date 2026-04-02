#!/usr/bin/env python3
import sys
from pathlib import Path
from haywire.ui.components.graph.generators import VueEventGenerator

# Add the src directory to Python path
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))


def main():
    """Generate Vue event constants"""
    print("Generating Vue event constants...")

    vue_code = VueEventGenerator.generate_event_constants()

    # Output to the editor_v1 directory
    output_dir = project_root / "src" / "haywire" / "ui" / "components" / "graph_canvas" / "generated"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / "graph_events.js"
    with open(output_file, "w") as f:
        f.write(vue_code)

    print("✅ Vue event constants generated successfully!")
    print(f"📁 File: {output_file}")


if __name__ == "__main__":
    main()
