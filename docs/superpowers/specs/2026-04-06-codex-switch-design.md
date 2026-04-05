# codex-switch Design

Date: 2026-04-06
Status: approved for planning

## Goal

Build a local CLI wrapper that lets the user keep typing `codex` normally while
`codex-switch` selects the logged-in Codex account instance with the most
remaining quota before launching the real Codex CLI.

The first version targets these constraints:

- The user keeps the normal `codex` command entrypoint.
- The first `codex` run triggers an initialization wizard automatically.
- Multiple account instances are created and logged in separately.
- Project context, skills, repository files, and in-repo `AGENT.md` remain
  shared because every selected instance still runs in the same project
  directory.
- Account auth and instance-local state are isolated.
- Every instance shares the same real `codex` binary version.
- Routing happens once before launch; no in-session failover in v1.
- Unhealthy or unlogged instances are skipped.
- Ties are broken by fixed instance order.

## Recommended approach

Use a front-of-PATH wrapper named `codex` that forwards to one real Codex CLI
binary while choosing among multiple isolated account instances.

This design deliberately avoids copying multiple real Codex binaries. Each
instance is instead represented by its own runtime root directory, keeping auth
and local state separate while letting all instances share the same installed
Codex version and the same project-level context.

## Architecture

The CLI is split into four focused modules.

### 1. Wrapper

The wrapper owns the user-facing `codex` entrypoint. It:

- detects whether `codex-switch` has been initialized
- runs the bootstrap wizard on first use
- decides which instance should handle the current command
- forwards the original arguments to the real Codex binary unchanged

### 2. Instance manager

The instance manager owns instance lifecycle and metadata. It:

- creates isolated instance runtime roots
- reads and writes instance metadata
- lists known instances
- checks whether an instance is logged in
- exposes health status for diagnostics

### 3. Quota probe

The quota probe runs the target instance's quota/status check and converts the
result into a normalized score that the router can compare.

Probe failures, missing auth, malformed output, and timeouts are treated as
instance-local failures. Those instances are skipped unless all instances fail.

### 4. Bootstrap wizard

The wizard handles first-run setup. It:

- locates the real `codex` binary
- asks how many account instances to create
- creates each instance runtime root
- launches per-instance login
- writes the persistent global config
- validates that the wrapper is actually reachable through PATH

## Runtime model

`codex-switch` keeps its own state under `~/.codex-switch/`:

```text
~/.codex-switch/
  config.json
  bin/
    codex
  instances/
    acct-001/
      home/
      meta.json
    acct-002/
      home/
      meta.json
  logs/
    probe.log
```

Global config stores:

- real Codex binary path
- ordered instance list
- routing policy
- wrapper installation metadata

Each instance directory stores only instance-scoped runtime state and metadata.
Project files, skills, and repository context are not copied.

## Isolation strategy

The selected instance launches the real `codex` binary with an instance-specific
runtime environment rooted at that instance's directory.

The design target is:

- shared project working directory
- shared repository context
- shared skills visibility
- isolated auth/session state
- isolated instance-local state

The implementation should prefer environment-based runtime isolation over
copying the Codex binary. If the Codex CLI does not fully respect the runtime
directory overrides needed for clean auth isolation, the fallback may involve a
more explicit per-instance wrapper, but still against a single shared real
binary version.

## Command routing

All user `codex ...` invocations pass through the wrapper.

Routing rules for v1:

- if not initialized, start the wizard immediately
- for normal execution commands, probe all instances and select the best one
- for account management commands such as login/logout, route through
  `codex-switch` management flows instead of forwarding blindly
- preserve the user's original arguments when forwarding to the selected real
  Codex process

`codex-switch` should also expose explicit management commands for maintenance:

- `codex-switch init`
- `codex-switch list`
- `codex-switch login <instance>`
- `codex-switch doctor`
- `codex-switch uninstall`

These commands exist for setup and recovery; day-to-day usage remains `codex`.

## Initialization flow

The first bare or normal `codex` invocation performs lazy initialization:

1. locate and verify the real `codex` binary
2. ask for the number of account instances
3. create an isolated runtime root for each instance
4. run login for each instance in turn
5. allow retry, skip, or abort on login failure
6. persist global configuration
7. verify wrapper installation and PATH precedence

## Login model

`codex-switch` does not implement authentication itself. For each instance it
launches the real `codex login` flow inside that instance's isolated runtime
environment, allowing browser-based authorization to remain owned by the
official CLI while keeping credentials separated per instance.

## Quota probing and routing policy

Before launching a normal command, the wrapper probes every known instance in
parallel.

Probe behavior:

- run the instance-scoped quota/status command
- parse the remaining quota into a comparable numeric value
- skip instances that are unlogged, malformed, timed out, or otherwise failed

Selection policy for v1:

- choose the available instance with the largest remaining quota
- if multiple instances tie, use fixed instance order
- if all instances fail, exit with a clear action-oriented error

The parser must be implemented as a dedicated module because the status output
format may change across Codex CLI versions.

## Version management

All instances share one real Codex binary path. `codex-switch` does not manage
Codex upgrades itself.

Expected behavior:

- initialization records the current real binary path
- each launch verifies that the path still exists and is executable
- if the stored path is stale, `codex-switch` attempts to rediscover `codex`
  from PATH and updates its config
- if rediscovery fails, the command exits with guidance to repair the upstream
  Codex installation

This keeps every instance on the same Codex version and avoids upgrade drift
between per-account copies.

## Error handling

The first version should classify and report these errors clearly:

### Real Codex unavailable

The stored real binary path is missing, not executable, or no longer resolves.
The wrapper should attempt rediscovery before failing.

### Instance not logged in

The instance auth state is missing or invalid. That instance is skipped unless
every instance is unavailable.

### Quota probe failed

The status command timed out, changed format, or returned unusable data. That
instance is skipped and the failure is logged for diagnosis.

### Wrapper installation broken

The PATH order does not actually route `codex` to the `codex-switch` wrapper.
Initialization and doctor commands should detect and explain the required fix.

## Testing strategy

At minimum, the project should cover:

- unit tests for config persistence
- unit tests for routing and tie breaking
- unit tests for quota parsing
- integration tests with a mock `codex` executable that simulates:
  - logged in vs not logged in instances
  - different quota values
  - malformed or failing status output
  - stale real binary path recovery

Manual acceptance checks should verify:

- first `codex` use enters the wizard
- multiple accounts can be logged in separately
- project context remains shared
- a bad instance is skipped cleanly
- upgrading the real Codex binary does not require rebuilding instances

## Suggested repository structure

```text
codex-switch/
  README.md
  AGENT.md
  docs/
    superpowers/
      specs/
        2026-04-06-codex-switch-design.md
  src/
    codex_switch/
      cli.py
      wrapper.py
      config.py
      instances.py
      probe.py
      routing.py
      doctor.py
  tests/
    test_config.py
    test_routing.py
    test_probe.py
    test_integration_wrapper.py
  pyproject.toml
```

Python is the recommended implementation language for v1 because it is well
suited for local CLI tools, subprocess management, directory isolation, and
testability.

## README scope for v1

The README should promise only the following:

- `codex-switch` wraps `codex` and chooses the logged-in instance with the most
  remaining quota
- first use triggers an initialization wizard
- all instances share the same real Codex installation and the same project
  context
- v1 performs pre-launch routing only
- the tool depends on a locally working Codex CLI and browser-based login
- changes in upstream status output may require `codex-switch` updates

## Out of scope for v1

- in-session automatic failover
- distributed or multi-machine state sync
- direct management of Codex upgrades
- hard guarantees about quota parser stability across all future Codex versions
