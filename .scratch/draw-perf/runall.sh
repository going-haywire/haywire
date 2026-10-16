#!/bin/zsh
# usage: runall.sh <cN> <graph> <runs>
P=$(cd "$(dirname "$0")" && pwd)
PY=/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/.venv/bin/python
c=$1; g=$2; n=$3
pkill -f run_studio.py; sleep 2
rm -f $P/gate_$c.json
(nohup $P/start.sh $P/$c > $P/$c.log 2>&1 &)
for i in {1..60}; do sleep 1; grep -q "ready to go" $P/$c.log && break; done
sleep 3
cd $P
$PY setup.py $g
echo "== $c warmup"; $PY measure.py $c timing 1 $g $P/gate_$c.json
echo "== $c timing"; $PY measure.py $c timing $n $g $P/gate_$c.json
echo "== $c lookups"; $PY measure.py $c lookups 2 $g $P/gate_$c.json
pkill -f run_studio.py; sleep 2
