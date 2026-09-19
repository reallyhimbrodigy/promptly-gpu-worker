#!/bin/sh
# One production brief from Builder-2's fixture file, as a job: h_brief.sh <id> <s3-source-key> <brief-file>
# The brief travels as a FILE (main --brief-file): quotes and newlines in a production brief would break `sh -c`.
set -u
set -o pipefail
cd "$(dirname "$0")/.." || exit 2
[ $# -eq 3 ] || { echo "usage: h_brief.sh <id> <s3-source-key> <brief-file>"; exit 2; }
BRIEF_ID="$1" BRIEF_KEY="$2" BRIEF_FILE="$3" sh scripts/h_stage.sh brief
