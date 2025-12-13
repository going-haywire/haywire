#!/bin/bash

# This script finds all files with a specified extension in a directory and its subdirectories,
# and combines them into a single markdown file.

# Check if all required arguments are provided
if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
  echo "Error: Missing required arguments."
  echo "Usage: $0 <source_directory> <file_extension> <output_markdown_file>"
  echo ""
  echo "Arguments:"
  echo "  source_directory     - Path to the directory containing files to distill"
  echo "  file_extension       - File extension to search for (e.g., py, md, js)"
  echo "  output_markdown_file - Path to the output markdown file"
  echo ""
  echo "Example:"
  echo "  $0 ./src py ./docs/distilled.md"
  exit 1
fi

TARGET_DIR="$1"
FILE_EXTENSION="$2"
OUTPUT_FILE="$3"

# Check if the provided path is actually a directory
if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: Directory '$TARGET_DIR' not found."
  exit 1
fi

# Create output directory if it doesn't exist
OUTPUT_DIR=$(dirname "$OUTPUT_FILE")
if [ ! -d "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi

# Clear the output file if it exists
> "$OUTPUT_FILE"

echo "Processing .$FILE_EXTENSION files in '$TARGET_DIR'..."
echo "Output will be written to '$OUTPUT_FILE'"

# Find all files with the specified extension
find "$TARGET_DIR" -type f -name "*.$FILE_EXTENSION" | while read -r file; do
  # Get the relative path for the header
  relative_path="${file#$TARGET_DIR/}"
  
  echo "Adding $relative_path to markdown..."

  # Add a header for the file
  echo "---" >> "$OUTPUT_FILE"
  echo "## \`$relative_path\`" >> "$OUTPUT_FILE"
  echo "---" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
  
  # Add the file content in a code block with the appropriate language
  echo "\`\`\`$FILE_EXTENSION" >> "$OUTPUT_FILE"
  cat "$file" >> "$OUTPUT_FILE"
  echo "\`\`\`" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
done

echo "✅ All .$FILE_EXTENSION files have been distilled into $OUTPUT_FILE"