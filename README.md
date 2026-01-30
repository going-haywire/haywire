# Haywire node system

The following draft is created by Martin Fröhlich (aka maybites) and released under [CC-BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/). (c) 2025

Haywire is a Blueprint inspired node system that follows the principle of an execution flow system.

Notable open source projects that realize something similar but with different use cases in mind:

* [Floppy](https://github.com/JLuebben/Floppy) based on python
* [Box](https://github.com/p-ranav/box) based on python
* [CablesGL](https://cables.gl/) based on javascript

## Getting Started

### Prerequisites

- Python 3.11+
- Compatible cameras or video files
- Network connectivity for multi-node setups

### Installation

1. **Clone the repository:**
   ```sh
   git clone <repository-url>
   cd <repository-foldername>
   ```

2. **Install dependencies (Python 3.11+ required):**
   ```sh
   pip install uv # if not already installed
   uv sync
   ```

   Or for development:
   ```sh
   uv sync --dev
   ```

3. **Just update dependencies after editing toml:**
   ```sh
   uv sync
   ```

### Development

Using Visual Studio Code as the developement IDE, Haywire allows to jump directly to the source and correct line number, if VS Code is added to your PATH:

* macOS: Open VS Code → Cmd+Shift+P → Type "Shell Command: Install 'code' command in PATH"
* Windows: During installation, check "Add to PATH" or reinstall
* Linux: Usually automatic, or sudo ln -s /usr/share/code/bin/code /usr/local/bin/code