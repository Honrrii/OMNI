# OMNI Stop Conditions

When any of these apply, stop and report the blocker instead of improvising
a way around it. Stopping with a clear report is a correct outcome, not a
failure to complete the task.

- **Dirty overlapping files.** The worktree has uncommitted changes — yours
  or someone else's — in a file your task needs to touch, and it's unclear
  whether those changes are safe to build on, preserve untouched, or are
  abandoned work. Stop and ask, rather than resetting, discarding, or
  silently merging into your own change.
- **Ambiguous ownership of existing changes.** You can't tell whether
  existing uncommitted or unmerged work belongs to the current task, a
  different in-progress task, or is stale. Treat it as someone else's until
  told otherwise.
- **Architectural decision required.** The task cannot be completed within
  the existing shape of the code without a decision that isn't yours to
  make alone (a new module boundary, a new cross-cutting dependency, a
  change to a data shape multiple subsystems read).
- **Requested scope is too broad.** The task as stated cannot be bounded to
  a reviewable, single-producer, single-reviewer unit of work (see
  `production_protocol.md`'s v0.1 constraints). Ask for it to be split
  rather than attempting all of it at once.
- **Acceptance criteria cannot be verified.** The task packet's acceptance
  criteria can't be checked against real command output, a real test, or a
  real artifact — you'd have to assert rather than demonstrate.
- **Required environment is unavailable.** A command, dependency, service,
  or credential the task needs isn't available in the current environment,
  and there's no safe substitute.
- **Protected path would be modified.** The change touches a path matched
  by `omni/autodev/protected_paths.py`'s policy (sandbox, frontend, ML
  model code, ROS export, Visual Bay, mission graph) and the task packet
  didn't explicitly authorize that.
- **New dependency required without justification.** The task can't be
  completed with the standard library and existing in-repo utilities, and
  no justification for a new dependency has been recorded.
- **Two failed repair cycles.** `production_protocol.md` caps repair at two
  cycles. A `CHANGES_REQUIRED` or `BLOCKED` verdict after the second repair
  cycle is a stop condition, not grounds for a third attempt.
- **Evidence contradicts a success claim.** Command output, test results, or
  a generated artifact disagrees with a claim (yours, a packet's, or
  another agent's) that something works or is complete. Trust the evidence,
  report the contradiction, and stop rather than reconciling it silently.
