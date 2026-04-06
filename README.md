# codex-switch

`codex-switch` is a local wrapper for the Codex CLI. It keeps the normal
`codex` command, but chooses the logged-in account instance with the most
remaining quota before launching the real CLI.

## What it does

- installs a PATH-first `codex` shim
- stores one isolated runtime home per account
- checks account login state with `codex login status`
- probes each account's remaining quota with `/status` before launch
- forwards the original user command unchanged to the selected account
- keeps repository files, project instructions, and shared skills visible to
  every instance

## Install

```bash
python -m pip install -e .
codex-switch install-shim
```

After that, just run `codex`. The first launch asks how many accounts to set up
and walks you through logging each one in with the upstream Codex CLI.

```bash
codex
```

Once setup is done, day-to-day usage stays the same:

```bash
codex "review this branch"
codex exec "make test"
```

## How it works

The first `codex` run triggers setup. `codex-switch` creates one isolated
runtime home per account, runs the upstream login flow for each account in
turn, then stores the real Codex binary path for later launches.

When you later run `codex`, the shim probes each configured account, skips
unhealthy or unlogged ones, and picks the one with the most remaining quota.

## Caveats

- it does not switch accounts in the middle of a running Codex session
- it does not manage upstream Codex upgrades for you
- it depends on the upstream CLI's login/status output staying readable
- all accounts still share the same project working directory

## Public repository rules

- commit source files, tests, and public docs only
- keep local planning docs out of public pushes
- keep local-only agent and skill metadata out of public pushes
