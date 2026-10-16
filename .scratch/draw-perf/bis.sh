#!/bin/zsh
P=$(cd "$(dirname "$0")" && pwd)
PY=/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/.venv/bin/python
sha=$1; g=10x512n_5x448e
git -C $P/c2 checkout -q --detach $sha || exit 1
pkill -f run_studio.py; sleep 2; rm -f $P/gate_c2.json
(nohup $P/start.sh $P/c2 > $P/c2.log 2>&1 &)
for i in {1..60}; do sleep 1; grep -q "ready to go" $P/c2.log && break; done
sleep 3; cd $P
$PY setup.py $g
$PY measure.py $sha timing 3 $g $P/gate_c2.json 2>&1 | grep -v "^found" | sed -E 's/"B_ms.*//' | cut -c1-200
pkill -f run_studio.py; sleep 2
