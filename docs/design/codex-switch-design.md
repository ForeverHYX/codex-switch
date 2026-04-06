# codex-switch Design

## Public Summary

`codex-switch` wraps the existing Codex CLI and chooses the account instance
with the highest remaining quota before forwarding the user's original command.
Each account gets its own isolated runtime home so authentication and instance
state stay separate while the repository working directory stays shared.

## Core Behavior

- a PATH-first `codex` shim intercepts normal `codex ...` launches
- the shim probes each enabled account instance before execution
- quota checks use the Codex CLI's `/status` output
- the best healthy instance is selected by remaining quota, then by stable order
- the selected instance runs the original command without rewriting argv
- unhealthy, unlogged, timed-out, or unparsable instances are skipped

## What Is Shared

- the current repository and working tree
- project-local files such as agent instructions
- global skills and other shared project context

## What Is Isolated

- account authentication state
- instance-specific runtime files and caches
- per-account diagnostic state

## Operational Notes

- the real upstream Codex binary is kept separate from the shim
- stale binary paths can be rediscovered from `PATH`
- public pushes should include only code, tests, and public docs
- local planning docs stay out of public pushes
