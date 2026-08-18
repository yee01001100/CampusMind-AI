# Python dependency ownership

Day 0 keeps the root `pyproject.toml` stable so parallel agents do not create merge conflicts.

- Agent 1 only edits `requirements/agent-1.txt`.
- Agent 2 only edits `requirements/agent-2.txt`.
- Agent 3 only edits `requirements/agent-3.txt`.
- Agent 4 manages dependencies only in `apps/web/package.json`.
- Agent 0 installs all three Python requirement files, resolves version conflicts, and consolidates final runtime dependencies into `pyproject.toml`.

Do not place credentials, local paths, or unverified dependency versions in these files.
