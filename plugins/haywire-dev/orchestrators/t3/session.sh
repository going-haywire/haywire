#!/bin/bash
# T3 Code's slot (ADR 0090), run by hooks/session-place.sh at session start: prints that the
# agent runs in a T3 thread and where the T3 how-to is. Prints nothing outside T3.

[ "$CLAUDE_CODE_ENTRYPOINT" = "t3-code" ] || [ -n "$T3CODE_THREAD_ID" ] || exit 0

echo "You run in T3 Code${T3CODE_THREAD_ID:+ as thread \`$T3CODE_THREAD_ID\`}. Message another thread with \`t3_thread_send\` (it arrives as its next input); refer to a thread by its title, the branch for a task. Lead and tasks in T3: \`orchestrators/t3.md\` in the haywire-workflow skill."
exit 0
