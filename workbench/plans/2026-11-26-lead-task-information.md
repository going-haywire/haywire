# Lead and task: who is told what

| | |
|---|---|
| Status | design round: draft, nothing decided |
| Issue | #264 (T3 sessions aren't told their role or their lead) |
| Inputs | #264; this session's core lead run on 2026-11-25/26 (#241, #242, #243, v0.6.5); the protokol #27 task |

## 1. The channels today

The places an agent learns something, from strongest (always arrives) to weakest (only if someone writes it):

| Channel | Who writes it | Reaches | Holds today |
|---|---|---|---|
| `session-role.sh` (SessionStart) | core hook | every session in a repo with core's `.claude/` | GitHub role: maintainer / contributor |
| `session-place.sh` → `orchestrators/<tool>/session.sh` | core hook, per orchestrator | same | T3: "you are thread `<id>`, use `t3_thread_send`, read `t3-agent.md`", setup wait, `doctor.py`. herdr: address, main folder vs worktree, tab naming, shared-main-folder warning |
| `require-workflow-read.sh` (PreToolUse) | core hook | same | blocks commit / push / `gh pr` until `workflow.md` is read |
| The brief (first message) | the lead, by hand | the task | whatever the lead remembers: issue, branch, lead address, report rule, owner's limits |
| Messages (`t3_thread_send`, `hc send`) | either side, by hand | the other | reports, relayed approvals, answers |
| GitHub (PRs, issues, runs) | anyone | whoever looks | the true state of merges and releases |

The rules for the content exist in `workflow.md` (*Lead and tasks*): the brief holds the issue, branch, acceptance points, report rule and lead address. A task reports *PR opened*, *Live check waiting*, *Ready*, *Blocked*, *Needs a decision* and *Finished*. Only the hooks enforce anything, and they enforce only "read the workflow before git".

## 2. What each side needs from the other

### The task needs, at start

1. **That it is a task**, and of which lead. Today: only in the brief.
2. **The lead's address.** Today: only in the brief. T3 records no parent on `t3_thread_launch`.
3. **The work:** issue URL, branch, acceptance points, and the decisions already made. Today: brief, works when written.
4. **Its limits:**
   - what is public and approved: push? PR? comment? merge never;
   - what needs a decision back: architecture, a public API name, anything the owner reserved.
   
   Today: free text in the brief. This session wrote "commit locally, no push until relayed" by hand, every time.
5. **Which steps are the lead's:** merge, release, `finish` under T3, and filing issues. Today: in the docs, but a task that hasn't read `t3-agent.md` improvises (#27 ran `share`).

### The task needs, during the work

6. **Relayed owner decisions and approvals**, with their scope. Today: messages; they work. Scope is free text ("push + PR only").

### The lead needs, from the task

7. **Each state change, pushed before the turn ends**: *PR opened*, *Ready*, *Blocked*, *Needs a decision*. Today: works only when the brief said so. T3 settles a thread at every turn end, so a silent stop looks like done (#264).
8. **What the owner told the task directly.** This session: the owner asked the #243 task for the wrap option and picked hover-tip option (b) in the task's thread. The task reported both; nothing asks it to.
9. **A Ready report that can go straight to the owner**: URL, head SHA, checks with the run URL, the live-check table or why there was none, open points, a draft PR. This session's tasks did this well once the brief asked for it.

### The lead needs, from the world

10. **Merges and releases it didn't make.** This session: #254 merged and v0.6.4 shipped outside the lead's knowledge. The lead found out only at `/release` Step 0, and its own reports to the owner were stale by then.
11. **Its own role.** The core lead here learned it was "lead" only from the umbrella's first message. The hook said maintainer and T3 thread, but not lead.

## 3. Gaps, in one line each

- G1. No session is told *lead* or *task* (only herdr hints at main folder vs worktree).
- G2. A task's lead address lives only in the brief.
- G3. The brief has no template, so limits and report rules are re-typed and can be forgotten.
- G4. Nothing makes a task send a report before its turn ends.
- G5. An approval's scope is free text; nothing records what was approved.
- G6. A task isn't asked to forward what the owner told it directly.
- G7. The lead isn't told about merges or releases it didn't make.
- G8. Nested leads (umbrella → core lead → task) aren't described: who reports to whom, and whose approval counts.
- G9. Library release from a task: `workflow.md` and `share` disagree (#264, point 5).

## 4. Options

### A. Where the role and the lead's address come from (G1, G2, G8)

- **A1. The hook derives the role from the place.** A main folder is a lead, a worktree is a task. The lead's address stays in the brief. Cheap, but a worktree session still can't find a lead the brief omits.
- **A2. A1 plus a recorded parent.** The lead passes `delegatedFrom` on `t3_thread_launch` (T3 stores it), and the hook prints "your lead is `<thread>`" when the thread has one. Needs a check that the hook can read it (T3 env or API); herdr would need its own.
- **A3. A1 plus a lead file.** `worktree_setup.py` takes `--lead <address>` and writes it into the worktree's git folder (next to `haywire-setup-done`). The hook prints it. Works the same for T3 and herdr, and survives a thin brief.

*Recommendation: A3.* It's one mechanism for every orchestrator, in files core already owns. For nested leads (G8), the lead file names the direct lead only; the umbrella is that lead's lead.

### B. The brief (G3, G5)

- **B1. A checklist in `workflow.md`** that the lead hook prints in a main folder. Still hand-typed.
- **B2. A brief template**, `dev/templates/brief.md`, with fixed sections:
  - Issue
  - Branch
  - Acceptance
  - Decided
  - **Approved** (none / push+PR / …)
  - Reserved for the owner
  - Report to
  - Read first
  
  The lead fills it in.
- **B3. B2 plus a script** (`brief.py`) that fills in the issue, branch, lead address and default limits, and starts the task through the orchestrator's slot.

*Recommendation: B2 now, B3 when a second orchestrator needs it.* The **Approved** line is G5: the task reads its scope from one place, and the lead updates it with a message that names the line.

### C. Reports that can't be lost (G4, G6)

- **C1. A rule in `t3-agent.md` and `herdr-agent.md`**: send the report before ending the turn, and forward anything the owner told you directly.
- **C2. C1 plus a Stop hook in a worktree**: when the turn ends and the session sent no message to its lead since the last state change, the hook asks it to (or, with no lead known, to tell the user). Needs a way to tell from the hook that a message was sent (a marker written by a PostToolUse hook on `t3_thread_send` / `hc send`).

*Recommendation: C1 at once; C2 if C1 alone fails again.*

### D. The lead's view of the world (G7)

- **D1. The lead re-reads state before every report to the owner**: `tasks.py`, `gh pr list --state merged` since its last look, the last tag. A rule plus a habit.
- **D2. `tasks.py --since <sha>`** also prints merges and tags on `master` since that commit. The lead keeps the commit it last reported from.
- **D3. A rule that whoever merges or releases outside a lead tells that lead.**

*Recommendation: D2 plus D1 as the rule.* D3 depends on people remembering, which is the problem itself.

### E. Library release from a task (G9)

- **E1.** Releases are the lead's, from the main folder; `workflow.md` drops "runs in the task's worktree too".
- **E2.** `share` accepts a branch at the default branch's tip; the docs stay as they are.

*Recommendation: E1.* It matches "the lead orders merges, releases and cleanup".

## 5. Owner decisions

1. **A:** A1, A2 or **A3**?
2. **B:** B1, **B2** or B3? And the template's sections: anything to add or drop?
3. **C:** **C1 now**, C2 later?
4. **D:** **D2 + D1**? Or is D3 enough for how you work?
5. **E:** **E1** or E2?
6. **G8:** in the umbrella → core lead → task chain, does the core lead act as a task of the umbrella (reports to it), as a peer (as with a second machine), or does it depend on who started it?
7. **The umbrella folder:** give it a `.claude/settings.json` that runs core's hooks, or keep it outside the hooks and document it?
8. **Your UX issues:** add them here, as further sections.

## 5a. Decided (owner, 2026-11-26)

### G1. Decisions live in the task's thread

1. **The task asks.** In its own thread, it writes the options and its recommendation, and ends with the lead's link. In the same turn, it sends the lead one line: the question, its recommendation and its own link.
2. **The lead marks it.** It puts `? ` in front of the task's title, marks it unread, and gives the owner the one line and the link. To remind the owner, it lists "Waiting on you: <link> – one line" per task.
3. **The owner answers in the task.** That answer is the owner's word for that task, approvals included. Nothing is relayed.
4. **The task resumes.** It sends the lead "Decided: … (approved: …)" and ends its reply with the lead's link. The lead drops the `? `.

Only the lead names and marks threads; a task never renames itself (G3). Every task carries its lead's link (`t3-thread://v2/<environment>/<thread id>`) from its brief or the lead file (A3).

### Choices (owner, 2026-11-26)

- **A3:** lead file. `worktree_setup.py --lead <link>` writes it, and the session-start hook prints it.
- **B2:** brief template.
- **C1:** the report-before-turn-end rule.
- **D2:** `tasks.py --since`, with D1 as the rule.
- **E1:** library releases stay with the lead.
- **F, the relationship is set by the owner's words at creation:**
  - *"spin up a task"*: the current thread is the lead, and the new thread is its task. It gets the lead file and the `<lead tag> › <branch>` name.
  - *"spin up a thread"*: the new thread is a peer. It gets no lead file, a lead-style name of its own (`<tag> ◆ lead`), and the other thread's link in its first message, for messages only.
  - So the role comes from the lead file, not from the folder: a lead file means a task, none means a lead or peer. A worktree session without a lead file asks the user once.

### G2. Thread names

| Thread | Title |
|---|---|
| Lead | `<tag> ◆ lead` (`core ◆ lead`, `umb ◆ lead`, `protokol ◆ lead`; `core@<machine> ◆ lead` on a second machine) |
| Task | `<lead tag> › <branch>` (`core › fix/haystack-reassembly-stop-broadcast`) |
| Waiting on the owner | `? ` in front, set and cleared by the task |

The project already names the repository, so a title doesn't repeat it. The tag says which lead a task follows, even in a library project where the umbrella and the library lead both start tasks.

### G3. What T3 offers (checked 2026-11-26)

Three test threads, `core › test/delegated-from`, `test/waiting-one` and `test/waiting-two`:

| What | Result |
|---|---|
| Sidebar grouping | by project (one per repository, plus the umbrella) |
| Title | free text; any agent can rename any thread (`t3_thread_update`) |
| `delegatedFrom` on `t3_thread_launch` | accepted, but nothing visible: `parentThreadId` and `relationshipToParent` stay null, and the task sees no marker. So the lead's link must be in the brief (or the lead file). |
| Task renames itself to `? …` | worked once, failed once: `waiting-one` replaced its title with `? Name the test cat`, then "restored" it to `Name the test cat`. Hence the lead does the naming (G1). |
| Task marks itself unread | fails during its own turn ("no completed run"); works from the lead once the task's turn has ended |
| Settle at turn end | not reliable either way: the test worktree threads stayed unsettled, while the protokol #27 task settled. Don't depend on it. |
| Task → lead message, owner → task answer, task → lead "Decided" | worked in all three, including two tasks waiting at once |
| Links back to the lead at the end of a reply | worked (to be confirmed by the owner in the sidebar) |

## 6. Tests and checks (once decided)

- Hook output: shell tests for `session.sh` in a main folder, in a worktree with a lead file, and in a worktree without one (A3).
- `worktree_setup.py --lead`: unit test that the file is written and read back.
- `tasks.py --since`: unit test with a fake `git log` / tag list.
- Docs: `workflow.md`, `t3-agent.md`, `herdr-agent.md` and the brief template, all in one PR.
