#!/usr/bin/env python3
"""
Python Files to Markdown Consolidator
=====================================

This script scans a repository folder for Python files and consolidates them
into a single markdown document with proper formatting and structure.

Usage:
    python consolidate_py_to_md.py [repository_path] [output_file]

Arguments:
    repository_path: Path to the repository folder (default: current directory)
    output_file: Output markdown file name (default: consolidated_code.md)
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import fnmatch


def should_ignore_file(file_path, ignore_patterns):
    """Check if a file should be ignored based on ignore patterns."""
    file_name = os.path.basename(file_path)
    relative_path = str(file_path)

    for pattern in ignore_patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def should_ignore_directory(dir_path, ignore_patterns):
    """Check if a directory should be ignored based on ignore patterns."""
    dir_name = os.path.basename(dir_path)
    relative_path = str(dir_path)

    for pattern in ignore_patterns:
        if fnmatch.fnmatch(dir_name, pattern) or fnmatch.fnmatch(relative_path, pattern):
            return True
    return False


def get_file_info(file_path):
    """Get basic information about a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        total_lines = len(lines)
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith("#")])

        # Extract docstring if present
        docstring = None
        if content.strip().startswith('"""') or content.strip().startswith("'''"):
            quote_type = '"""' if content.strip().startswith('"""') else "'''"
            try:
                start = content.find(quote_type)
                end = content.find(quote_type, start + 3)
                if end != -1:
                    docstring = content[start + 3 : end].strip()
            except Exception as e:
                print(f"Failed to extract docstring from {file_path}: {e}", exc_info=True)

        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "docstring": docstring,
            "content": content,
        }
    except Exception as e:
        return {
            "total_lines": 0,
            "code_lines": 0,
            "docstring": f"Error reading file: {str(e)}",
            "content": f"# Error reading file: {str(e)}",
        }


def scan_repository(repo_path, ignore_patterns):
    """Scan repository for Python files."""
    python_files = []
    repo_path = Path(repo_path)

    for root, dirs, files in os.walk(repo_path):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not should_ignore_directory(os.path.join(root, d), ignore_patterns)]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                if not should_ignore_file(file_path, ignore_patterns):
                    relative_path = file_path.relative_to(repo_path)
                    file_info = get_file_info(file_path)

                    python_files.append(
                        {
                            "path": str(relative_path),
                            "full_path": str(file_path),
                            "name": file,
                            "info": file_info,
                        }
                    )

    return sorted(python_files, key=lambda x: x["path"])


def generate_markdown(python_files, repo_path, output_file):
    """Generate markdown document from Python files."""

    # Calculate statistics
    total_files = len(python_files)
    total_lines = sum(f["info"]["total_lines"] for f in python_files)
    total_code_lines = sum(f["info"]["code_lines"] for f in python_files)

    markdown_content = f"""# Repository Code Documentation

**Repository:** `{os.path.basename(repo_path)}`  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Output File:** `{output_file}`

## Summary

- **Total Python Files:** {total_files}
- **Total Lines:** {total_lines:,}
- **Code Lines:** {total_code_lines:,}
- **Comment/Blank Lines:** {total_lines - total_code_lines:,}

## File Structure

```
{os.path.basename(repo_path)}/
"""

    # Add file tree
    for file_data in python_files:
        path_parts = Path(file_data["path"]).parts
        indent = "  " * (len(path_parts) - 1)
        markdown_content += f"{indent}├── {path_parts[-1]} ({file_data['info']['total_lines']} lines)\n"

    markdown_content += "```\n\n"

    # Add detailed file contents
    markdown_content += "## File Contents\n\n"

    for i, file_data in enumerate(python_files, 1):
        file_info = file_data["info"]

        markdown_content += f"### {i}. `{file_data['path']}`\n\n"

        # File statistics
        markdown_content += f"- **Lines:** {file_info['total_lines']}\n"
        markdown_content += f"- **Code Lines:** {file_info['code_lines']}\n"

        # Add docstring if present
        if file_info["docstring"] and file_info["docstring"] != "":
            markdown_content += f"- **Description:** {file_info['docstring']}\n"

        markdown_content += "\n"

        # Add the actual code
        markdown_content += "```python\n"
        markdown_content += file_info["content"]
        if not file_info["content"].endswith("\n"):
            markdown_content += "\n"
        markdown_content += "```\n\n"

        # Add separator for readability
        if i < len(python_files):
            markdown_content += "---\n\n"

    # Add footer
    markdown_content += f"""
---

*This documentation was automatically generated from the Python files in `{repo_path}` 
on {datetime.now().strftime("%Y-%m-%d at %H:%M:%S")}.*
"""

    return markdown_content


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate Python files from a repository into a markdown document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python consolidate_py_to_md.py /path/to/repo
    python consolidate_py_to_md.py ./my_project output.md
    python consolidate_py_to_md.py /home/user/code --ignore "test_*" "__pycache__"
        """,
    )

    parser.add_argument(
        "repository_path", nargs="?", default=None, help="Path to the repository folder (required)"
    )

    parser.add_argument(
        "output_file",
        nargs="?",
        default="consolidated_code.md",
        help="Output markdown file name (default: consolidated_code.md)",
    )

    parser.add_argument(
        "--ignore",
        nargs="*",
        default=[
            "__pycache__",
            "*.pyc",
            ".git",
            ".pytest_cache",
            "venv",
            "env",
            ".venv",
            "node_modules",
            ".DS_Store",
        ],
        help="Patterns to ignore (default: common build/cache directories)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Show help if no repository path is provided
    if args.repository_path is None:
        parser.print_help()
        print("\n" + "=" * 60)
        print("📁 PYTHON TO MARKDOWN CONSOLIDATOR")
        print("=" * 60)
        print("This tool scans a repository for Python files and creates")
        print("a consolidated markdown documentation file.")
        print("\n🚀 Quick Start:")
        print("  python consolidate_py_to_md.py /path/to/your/repo")
        print("\n📋 Common Usage Examples:")
        print("  python consolidate_py_to_md.py ./my_project")
        print("  python consolidate_py_to_md.py /home/user/code/myapp docs.md")
        print("  python consolidate_py_to_md.py ./src --ignore 'test_*' --verbose")
        print("\n💡 Tips:")
        print("  • The script automatically ignores common build directories")
        print("  • Use --verbose to see which files are being processed")
        print("  • Output file defaults to 'consolidated_code.md'")
        print("  • Relative paths are resolved from current directory")
        print("\n" + "=" * 60)
        sys.exit(0)

    repo_path = os.path.abspath(args.repository_path)

    # Validate repository path
    if not os.path.isdir(repo_path):
        print(f"Error: Repository path '{repo_path}' does not exist or is not a directory.")
        sys.exit(1)

    if args.verbose:
        print(f"Scanning repository: {repo_path}")
        print(f"Output file: {args.output_file}")
        print(f"Ignore patterns: {args.ignore}")
        print()

    # Scan for Python files
    python_files = scan_repository(repo_path, args.ignore)

    if not python_files:
        print("No Python files found in the repository.")
        sys.exit(0)

    if args.verbose:
        print(f"Found {len(python_files)} Python files:")
        for file_data in python_files:
            print(f"  - {file_data['path']} ({file_data['info']['total_lines']} lines)")
        print()

    # Generate markdown
    print("Generating markdown document...")
    markdown_content = generate_markdown(python_files, repo_path, args.output_file)

    # Write to file
    try:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"✅ Successfully created '{args.output_file}'")
        print(
            f"📊 Processed {len(python_files)} files with "
            f"{sum(f['info']['total_lines'] for f in python_files):,} total lines"
        )

    except Exception as e:
        print(f"❌ Error writing to file: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
