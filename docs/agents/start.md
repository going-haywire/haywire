---
serve: product
status: current
doc_template: guide
scope: Read when a person asks you to set them up for Haywire — prerequisites, then a project for a user or the clones for a developer, all the way to a working session
see-also:
  - ../collaboration/workflow.md
  - ../collaboration/second-machine.md
---

# Setting someone up for Haywire

You are an agent, and a person asked you to set them up for Haywire. This page takes you from a
machine with only your harness on it to a working session. Follow it in order.

**What you do and what the person does.** Run every command yourself, explain each step in a
sentence, and check that it worked. A few steps only the person can do: installing software that
needs admin rights, logging in (`gh auth login`), typing a password, creating a token. For each,
give the exact command or click path for their operating system, wait until they say it is
done, then check it yourself. Never ask for a password or a token in the chat.

## 1. Use Haywire, or develop it?

Ask the person which they want:

- **Use Haywire**: build graphs and their own libraries in a project of their own.
- **Develop Haywire**: change core (`going-haywire/haywire`) or one of the organisation's
  libraries (`going-haywire/haybale-*`), as a contributor or the maintainer.

A developer also uses Haywire; you can set up a project for them as well, after their clones.

## 2. Prerequisites, for both

| Tool | Check | If missing, the person installs it |
|---|---|---|
| uv | `uv --version` | macOS, Linux: `curl -LsSf https://astral.sh/uv/install.sh \| sh`; Windows: `winget install --id=astral-sh.uv -e` |
| git | `git --version` | macOS: `xcode-select --install`; Linux: the distribution's package (`sudo apt install git`); Windows: `winget install --id Git.Git -e` |

uv downloads the Python Haywire needs (3.12) by itself; nothing else is required to use Haywire.

## 3a. Use Haywire: a project

1. Ask where the project should live and what it is called. In that folder:

   ```sh
   uvx --python 3.12 --from haywire-studio haywire init <name>
   ```

   It creates the folder `<name>` with one library of the person's own, installs Haywire into
   the project's environment, and writes the files that connect any supported agent harness to it
   (`.mcp.json` and the harness settings beside it: the Farmhand bridge).
2. Start the studio and give the person its address:

   ```sh
   cd <name>
   uv run haywire studio start --browser
   ```

3. Tell the person to open a new agent session **in the project folder**. Claude Code asks once
   whether to trust a new folder; until the person accepts, it also asks before each tool of the
   bridge. There the Farmhand
   bridge connects the session to the studio: the studio's tools appear while it runs, and the
   bridge's instructions list the pages to read for each kind of task. `farmhand_studio_status`
   says why the tools are missing when they are.

Authentication is off by default (the studio answers only on this machine). If the person turns
it on (`uv run haywire auth enable`, in their own terminal), the bridge needs an agent principal
named `farmhand`, which they create once per machine, also in their own terminal:
`uv run haywire user add farmhand --agent --tier edit`.

## 3b. Develop Haywire: the clones

1. **The GitHub CLI**, logged in. Check `gh --version` and `gh auth status`. If it is missing, the
   person installs it ([cli.github.com](https://cli.github.com/)); logging in is theirs:
   `gh auth login`, then `gh auth setup-git`. The workflow's hooks also need `jq`
   (`jq --version`; macOS `brew install jq`, Linux `sudo apt install jq`).
2. **The role.** `gh repo view going-haywire/haywire --json viewerPermission`: `ADMIN`, `MAINTAIN`
   or `WRITE` make a maintainer, anything else a contributor, who works on a fork and needs an
   accepted introduction before a first pull request
   ([the contribution rules](../collaboration/contributing.md)).
3. **One folder for every clone**: the umbrella repository, cloned as `haywire` where the person
   chooses. Core goes inside it under the name `haywire-repo`, where the libraries reach it; the
   umbrella's `bin/umbrella-sync` later builds one environment for the full studio with every
   library cloned on this machine ([its README](https://github.com/going-haywire/umbrella#readme)).

   ```sh
   gh repo clone going-haywire/umbrella haywire
   cd haywire
   gh repo clone going-haywire/haywire haywire-repo                 # a maintainer
   gh repo fork going-haywire/haywire --clone && mv haywire haywire-repo   # a contributor
   cd haywire-repo
   uv sync --all-extras --dev
   ```

4. **Libraries**, only the ones the person works on, beside core:

   ```sh
   gh repo clone going-haywire/haybale-<name>    # (a contributor: gh repo fork … --clone)
   cd haybale-<name>
   uv sync --frozen
   ```

5. **Done.** Each clone's committed files give a session there the workflow, its hooks and the
   Farmhand bridge, with nothing to install. Tell the person to open a new agent session in the
   clone they work on. Its session-start hook names their role, and the bridge lists the workflow
   page, which the hooks want read before the first commit.

An orchestrator (T3 Code, herdr) is optional: its page says how to set it up
([orchestrators](../collaboration/orchestrators/index.md)). A second machine is set up the same
way; [its page](../collaboration/second-machine.md) has the rest.
