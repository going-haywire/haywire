# Setting up a second machine

A second machine (for example a Linux box on the home network) runs its own sessions,
tests and studio, on its own clone. It shares nothing with the first machine but GitHub:
work moves between them only through pushed branches.

## Tools

- git, [uv](https://docs.astral.sh/uv/), the [GitHub CLI](https://cli.github.com/),
  Claude Code (logged in), and Node.js (`npx` starts the Farmhand proxy from `.mcp.json`).
- `gh auth login`, then `gh auth setup-git`: git pushes over HTTPS with the same login.
- [herdr](https://herdr.dev/guide/) on the machine, added to the first machine's herdr
  under *Settings → Machines* (its host from `~/.ssh/config`), to run its sessions from
  one place.

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

## The sibling libraries (optional)

Only when this machine works on or runs `haybale-spandrel` or `haybale-visiongraph`.
Clone each next to `haywire-repo`, link it into `barn/` and install it editable:

```sh
gh repo clone going-haywire/haybale-spandrel ../haybale-spandrel
ln -s "$(realpath ../haybale-spandrel/barn/haybale-spandrel)" barn/haybale-spandrel
uv pip install -e barn/haybale-spandrel
```

`scripts/worktree_setup.py` copies these links into every worktree. Their models and
devices (GPU, webcam, OAK-D) are this machine's own: a model downloads again here, and a
node that needs a device works only if the device is attached here.

## Reaching the studio from the first machine

A studio listens on `127.0.0.1` only. Reach it through an SSH tunnel; the browser then
talks to `localhost`, which is a secure context, so the clipboard works:

```sh
ssh -N -L 8125:127.0.0.1:8125 <linux-host>     # then open http://localhost:8125
```

Use the port the worktree's studio runs on (`.haywire/settings.json`, `network.port`).

Opening the studio to the network instead takes, in this order, since exposure refuses
without login and TLS (`docs/adr/0026-studio-network-exposure.md`): an admin user
(`haywire user add`), `haywire auth enable`, `haywire ssl setup`, then
`haywire network expose --ranges <cidr>`. `haywire security status` shows the result.
