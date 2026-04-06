# codex-switch

`codex-switch` is a local wrapper for the Codex CLI. It keeps the normal
`codex` command, but chooses the logged-in account instance with the most
remaining quota before launching the real CLI.

## What it does

- installs a PATH-first `codex` shim
- stores one isolated runtime home per account
- probes each account with `codex login status` before launch
- forwards the original user command unchanged to the selected account
- keeps repository files, project instructions, and shared skills visible to
  every instance

## Install

```bash
codex-switch init --instance-count 2 --real-codex-path "$(which codex)"
codex-switch install-shim
```

If you already have the shim installed, day-to-day usage stays the same:

```bash
codex "review this branch"
codex exec "make test"
```

## How it works

The first `codex` run triggers setup. `codex-switch` creates one isolated
runtime home per account, runs the upstream login flow for each account, then
stores the real Codex binary path for later launches.

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
