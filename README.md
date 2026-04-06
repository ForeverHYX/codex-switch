# codex-switch

`codex-switch` is a local wrapper for the Codex CLI. It keeps one shared project
workspace, but routes each `codex ...` invocation to the logged-in account
instance with the most remaining quota.

## What v1 does

- keeps the normal `codex` entrypoint through a PATH-first shim
- stores one isolated runtime home per account
- probes each account with `/status` before launch
- skips unhealthy, unlogged, or failing instances
- forwards the original user command unchanged to the selected account
- keeps repository context, skills, and project files shared across instances

## What v1 does not do

- switch accounts in the middle of a running Codex session
- manage upstream Codex upgrades for you
- guarantee that `/status` output never changes
- merge or synchronize account histories

## Public repository rules

- commit source files, tests, and public docs only
- keep local planning docs out of public pushes
- keep local-only agent and skill metadata out of public pushes

## Release checklist

- [ ] tests pass locally
- [ ] the public design doc reflects the latest approved behavior
- [ ] staged files exclude local-only planning metadata
- [ ] public pushes include only code, tests, and public docs

## Public design

See [docs/design/codex-switch-design.md](docs/design/codex-switch-design.md) for the public summary of the approved behavior.
