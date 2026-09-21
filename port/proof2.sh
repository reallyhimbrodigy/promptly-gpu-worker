#!/bin/sh
# PROOF 2 for one ported_mg component, end to end and never by eye.
#
#   port/proof2.sh <Name>
#
# 1. persist_registered.py lifts the code ChatCut stored out of the session
#    transcript — tool_result ONLY, never the tool_use that carried what we sent.
# 2. the contract-shaped source is materialised from chatcut_registry.json.
# 3. registered_diff.mjs classifies the pair and sets the exit code.
#
# Exit 0 only on IDENTICAL or injection-only STRIPPED. Anything else is a
# finding, including an ABSENT read-back, which exits 2 rather than diffing
# against a file that is not there.
set -e
N="$1"
[ -n "$N" ] || { echo "usage: port/proof2.sh <Name>"; exit 2; }
D=${PROOF2_DIR:-/tmp/b2reg}
mkdir -p "$D"
python3 port/persist_registered.py "$N" "$D/$N.registered.jsx"
python3 -c "
import json,sys
n=sys.argv[1]
r=json.load(open('chatcut_registry.json'))['components']
if n not in r:
    print('  ABSENT — %r is not in chatcut_registry.json components' % n); sys.exit(2)
c=r[n]['code']; open(sys.argv[2],'w').write(c)
print('  source %d chars from chatcut_registry.json' % len(c))
" "$N" "$D/$N.source.jsx"
node port/registered_diff.mjs "$N" "$D/$N.registered.jsx" "$D/$N.source.jsx"
