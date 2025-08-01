#!/bin/bash

# This script finds all python files in a specified directory and its subdirectories,
# and combines them into a single markdown file called distilled.md.

# Check if a directory path is provided as the first argument
if [ -z "$1" ]; then
  echo "Error: Please provide the path to the directory you want to distill."
  echo "Usage: $0 <directory_path>"
  exit 1
fi

TARGET_DIR="$1"

# Check if the provided path is actually a directory
if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: Directory '$TARGET_DIR' not found."
  exit 1
fi

# Use the provided directory for the output file
OUTPUT_FILE="$TARGET_DIR/distilled.md"

# Clear the output file if it exists
> "$OUTPUT_FILE"

echo "Processing Python files in '$TARGET_DIR'..."

# Find all .py files, excluding the script itself if it's in the target directory
find "$TARGET_DIR" -type f -name "*.py" | while read -r file; do
  # Get the relative path for the header
  relative_path="${file#$TARGET_DIR/}"
  
  echo "Adding $relative_path to markdown..."

  # Add a header for the file
  echo "---" >> "$OUTPUT_FILE"
  echo "## \`$relative_path\`" >> "$OUTPUT_FILE"
  echo "---" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
  
  # Add the file content in a python code block
  echo "\`\`\`python" >> "$OUTPUT_FILE"
  cat "$file" >> "$OUTPUT_FILE"
  echo "\`\`\`" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
done

echo "✅ All Python files have been distilled into $OUTPUT_FILE"