#!/bin/sh
# PRE-TOOL GATE: preview_timeline is WITHHELD until the edit exists.
#
# A PREFERENCE IS NOT A PROPERTY — this lane's own rule, earned when the prompt
# said "do not orchestrate" and the agent orchestrated anyway. The prompt asks
# the agent not to preview before it has finished placing; this REFUSES.
#
# MEASURED on run-1789522875: three preview_timeline calls, two of them before
# the edit was finished, 124 seconds of thinking across them — more than the
# whole 90-second budget for the job.
#
# /work/DONE is the legitimate unlock and there is no exploit in writing it:
# writing DONE is what triggers the render, so an agent that writes it early
# gets exactly what previewing early was trying to get, by the intended route.
if [ -f /work/DONE ]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
else
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"preview_timeline is WITHHELD until you have finished placing. Write /work/DONE — that renders the edit and sends you the frames as pictures, with the acceptance criteria for every placement. Previewing now would show you a timeline you have not finished building, and costs a model turn to see it."}}'
fi
