# Setting up a second machine

A second machine (for example a Linux box on the home network) runs its own sessions,
tests and studio, on its own clone. It shares nothing with the first machine but GitHub:
work moves between them only through pushed branches.

## Tools

- git, [uv](https://docs.astral.sh/uv/), the [GitHub CLI](https://cli.github.com/),
  Claude Code (logged in), and Node.js (`npx` starts the Farmhand proxy from `.mcp.json`).
- `gh auth login`, then `gh auth setup-git`: git pushes over HTTPS with the same login.
- Optionally, the orchestrator you use on the first machine, set up to reach this one, to
  run its sessions from one place: its file in [orchestrators/](orchestrators/) says how.

## The main checkout

```sh
gh repo clone going-haywire/haywire haywire-repo
cd haywire-repo
uv sync --all-extras --dev
uv run playwright install --with-deps chromium    # browser tests
```

On Linux, raise the file-watch limit once, or the test suite runs out of inotify
instances (CI does the same):

```sh
echo fs.inotify.max_user_instances=8192 | sudo tee /etc/sysctl.d/90-inotify.conf
sudo sysctl --system
```

`~/.haywire` (global settings, security document, model caches, volumes) starts empty on
this machine; nothing is copied from the first.

## The other libraries (optional)

Only when this machine works on or runs libraries from other repositories (spandrel,
visiongraph, stream, …). Clone the umbrella as the folder that holds the repositories,
`haywire-repo` and each library this machine needs inside it, then build the umbrella;
its `README.md` lists the steps:

```sh
gh repo clone going-haywire/umbrella haywire && cd haywire
gh repo clone going-haywire/haywire haywire-repo
gh repo clone going-haywire/haybale-spandrel      # only the libraries this machine needs
bin/umbrella-sync                                  # the umbrella: every library here, editable
```

The umbrella's `pyproject.toml`, `uv.lock` and `haywire.code-workspace` are this machine's
own, written by `umbrella-sync` from the repositories cloned here and not tracked, so the
two machines may clone different libraries.

`haywire-repo` keeps its own environment for its tests. Models and devices (GPU, webcam,
OAK-D) are this machine's own: a model downloads again here, and a node that needs a
device works only if the device is attached here.

## Reaching the studio from the first machine

A studio listens on `127.0.0.1` only. Reach it through an SSH tunnel; the browser then
talks to `localhost`, which is a secure context, so the clipboard works:

```sh
ssh -N -L 8125:127.0.0.1:8125 <linux-host>     # then open http://localhost:8125
```

Use the port the worktree's studio runs on (`.haywire/settings.json`, `network.port`).

To open the studio to the network instead, follow
[docs/guides/security.md](https://github.com/going-haywire/haywire/blob/master/docs/guides/security.md).
