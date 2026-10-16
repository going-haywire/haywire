#!/bin/zsh
# usage: start.sh <worktree> <logfile>
P=$(cd "$(dirname "$0")" && pwd)
W=$1
mkdir -p $W/.haywire
echo '{"network":{"port":{"value":8191}}}' > $W/.haywire/settings.json
cd $W
GATE_OUT=$P/gate_$(basename $W).json HOME=$P/home UV_CACHE_DIR=$HOME/.cache/uv exec env -u VIRTUAL_ENV $W/.venv/bin/python $P/run_studio.py
