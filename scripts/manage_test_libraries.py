#!/usr/bin/env python3
"""
Interactive CLI tool to install/uninstall test libraries in the Haywire repository.
"""

import subprocess
import sys
from pathlib import Path

# Get the project root directory
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Define the libraries
LIBRARIES = {
    '1': {
        'name': 'haybale-core',
        'path': PROJECT_ROOT / 'libraries' / 'haybale-core',
        'description': 'Core library with essential types, nodes, widgets, and renderers'
    },
    '2': {
        'name': 'haybale-example',
        'path': PROJECT_ROOT / 'libraries' / 'haybale-example',
        'description': 'Example library with custom nodes, widgets, and renderers'
    },
    '3': {
        'name': 'haybale-visiongraph',
        'path': PROJECT_ROOT / 'libraries' / 'haybale-visiongraph',
        'description': 'Visiongraph library for Haywire'
    },
    '4': {
        'name': 'haybale-TEST_A',
        'path': PROJECT_ROOT / 'libraries' / 'haybale-TEST_A',
        'description': 'Test library A'
    },
    '5': {
        'name': 'haybale-TEST_B',
        'path': PROJECT_ROOT / 'libraries' / 'haybale-TEST_B',
        'description': 'Test library B'
    }
}


def run_command(cmd, description):
    """Run a command and display the result."""
    print(f"\n{description}...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 70)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print(f"✅ {description} - Success!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed!")
        print(f"Error: {e.stderr}")
        return False


def check_installation_status(package_name):
    """Check if a package is installed and whether it's editable."""
    try:
        # Check if installed
        result = subprocess.run(
            ['uv', 'pip', 'show', package_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return "Not installed"
        
        # Check if editable
        result_editable = subprocess.run(
            ['uv', 'pip', 'list', '--editable'],
            capture_output=True,
            text=True
        )
        
        if package_name in result_editable.stdout:
            return "Installed (editable)"
        else:
            return "Installed (regular)"
            
    except Exception as e:
        return f"Error checking: {e}"


def show_status():
    """Display installation status of all libraries."""
    print("\n" + "=" * 70)
    print("LIBRARY INSTALLATION STATUS")
    print("=" * 70)
    
    for key, lib in LIBRARIES.items():
        status = check_installation_status(lib['name'])
        status_icon = "✅" if "Installed" in status else "❌"
        print(f"{status_icon} [{key}] {lib['name']}: {status}")
        print(f"    {lib['description']}")
        print(f"    Path: {lib['path']}")
        print()


def install_library(lib_info, editable=True):
    """Install a library."""
    if not lib_info['path'].exists():
        print(f"❌ Error: Library path does not exist: {lib_info['path']}")
        return False
    
    if editable:
        cmd = ['uv', 'pip', 'install', '-e', str(lib_info['path'])]
        description = f"Installing {lib_info['name']} (editable mode with hot-reload)"
    else:
        cmd = ['uv', 'pip', 'install', str(lib_info['path'])]
        description = f"Installing {lib_info['name']} (regular mode)"
    
    return run_command(cmd, description)


def uninstall_library(lib_info):
    """Uninstall a library."""
    cmd = ['uv', 'pip', 'uninstall', lib_info['name']]
    description = f"Uninstalling {lib_info['name']}"
    return run_command(cmd, description)


def install_menu():
    """Show install menu and handle installation."""
    print("\n" + "=" * 70)
    print("INSTALL LIBRARIES")
    print("=" * 70)
    print("Select libraries to install (separate with commas, e.g., 1,2,3):")
    print()
    
    for key, lib in LIBRARIES.items():
        status = check_installation_status(lib['name'])
        print(f"  [{key}] {lib['name']} - {status}")
    
    print("  [a] Install all")
    print("  [b] Back to main menu")
    print()
    
    choice = input("Your choice: ").strip().lower()
    
    if choice == 'b':
        return
    
    # Ask about installation mode
    print("\nInstallation mode:")
    print("  [1] Editable (recommended for development, enables hot-reload)")
    print("  [2] Regular (production mode)")
    mode = input("Your choice [1]: ").strip() or '1'
    editable = mode == '1'
    
    # Determine which libraries to install
    if choice == 'a':
        libs_to_install = list(LIBRARIES.keys())
    else:
        libs_to_install = [k.strip() for k in choice.split(',')]
    
    # Install selected libraries
    for key in libs_to_install:
        if key in LIBRARIES:
            install_library(LIBRARIES[key], editable)
        else:
            print(f"❌ Invalid choice: {key}")
    
    input("\nPress Enter to continue...")


def uninstall_menu():
    """Show uninstall menu and handle uninstallation."""
    print("\n" + "=" * 70)
    print("UNINSTALL LIBRARIES")
    print("=" * 70)
    print("Select libraries to uninstall (separate with commas, e.g., 1,2,3):")
    print()
    
    for key, lib in LIBRARIES.items():
        status = check_installation_status(lib['name'])
        print(f"  [{key}] {lib['name']} - {status}")
    
    print("  [a] Uninstall all")
    print("  [b] Back to main menu")
    print()
    
    choice = input("Your choice: ").strip().lower()
    
    if choice == 'b':
        return
    
    # Determine which libraries to uninstall
    if choice == 'a':
        libs_to_uninstall = list(LIBRARIES.keys())
    else:
        libs_to_uninstall = [k.strip() for k in choice.split(',')]
    
    # Confirm
    print("\n⚠️  You are about to uninstall:")
    for key in libs_to_uninstall:
        if key in LIBRARIES:
            print(f"  - {LIBRARIES[key]['name']}")
    
    confirm = input("\nContinue? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        input("\nPress Enter to continue...")
        return
    
    # Uninstall selected libraries
    for key in libs_to_uninstall:
        if key in LIBRARIES:
            uninstall_library(LIBRARIES[key])
        else:
            print(f"❌ Invalid choice: {key}")
    
    input("\nPress Enter to continue...")


def main_menu():
    """Display main menu and handle user choice."""
    while True:
        print("\n" + "=" * 70)
        print("HAYWIRE TEST LIBRARIES MANAGER")
        print("=" * 70)
        print()
        print("  [1] Show installation status")
        print("  [2] Install libraries")
        print("  [3] Uninstall libraries")
        print("  [4] Reinstall (uninstall + install editable)")
        print("  [q] Quit")
        print()
        
        choice = input("Your choice: ").strip().lower()
        
        if choice == '1':
            show_status()
            input("\nPress Enter to continue...")
        elif choice == '2':
            install_menu()
        elif choice == '3':
            uninstall_menu()
        elif choice == '4':
            print("\n" + "=" * 70)
            print("REINSTALL ALL LIBRARIES")
            print("=" * 70)
            confirm = input(
                "This will uninstall and reinstall all libraries. Continue? [y/N]: "
            ).strip().lower()
            if confirm == 'y':
                for key, lib in LIBRARIES.items():
                    print(f"\n--- Processing {lib['name']} ---")
                    uninstall_library(lib)
                    install_library(lib, editable=True)
                print("\n✅ All libraries reinstalled!")
            else:
                print("Cancelled.")
            input("\nPress Enter to continue...")
        elif choice == 'q':
            print("\nGoodbye!")
            sys.exit(0)
        else:
            print("❌ Invalid choice. Please try again.")
            input("\nPress Enter to continue...")


if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
        sys.exit(0)
