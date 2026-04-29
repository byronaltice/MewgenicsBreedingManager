---
name: clean-work
description: Remove all Codex/ worktrees and branches except the current one. Use when finished with a session to clean up stale worktrees.
allowed-tools: Bash(git *)
---

Clean up all stale `Codex/` worktrees and branches, keeping only the one currently in use.

## Steps

1. Identify the current worktree and branch:
   ```
   git worktree list
   git branch --show-current
   ```

2. From the repo root, list all `Codex/` worktrees and remove each one that is NOT the current worktree:
   ```
   git worktree list --porcelain
   ```
   For each worktree whose branch matches `Codex/` but is NOT the current branch:
   ```
   git worktree remove --force <worktree-path>
   ```

3. After removing worktrees, prune the worktree metadata:
   ```
   git worktree prune
   ```

4. Delete all local `Codex/` branches except the current branch:
   ```
   git branch --list 'Codex/*'
   ```
   For each branch that is NOT the current branch:
   ```
   git branch -D <branch-name>
   ```

5. Report a summary of what was removed (worktrees and branches), and what was kept.

## Important rules

- NEVER remove the worktree or branch you are currently operating in.
- NEVER touch `main`, feature branches, or any non-`Codex/` branch.
- If a worktree has uncommitted changes, warn the user and skip it rather than force-removing silently. Ask whether to proceed.
- Run all git commands from the repo root: `%USERPROFILE%\gitprojects\MewgenicsBreedingManager`
