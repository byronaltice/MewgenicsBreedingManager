# subagents/ Index

Resources supporting the multi-agent investigation workflow. Sub-agents are spawned by the orchestrator (per `.claude/commands/advisor-strategy.md`) to work on a specific hypothesis in isolation; files here give them the context they need without loading the full investigation history.

Agent definitions (identity, tools, model, system prompt) live at `.claude/agents/<name>.md`. The system prompts there reference the briefings in this directory by path.

## Contents

| Subdirectory | Purpose |
|---|---|
| `_shared/` | Cross-agent rules: return contract (incl. `[PIVOTAL]` flag), closed-leads/identity discipline, verification mode (subagent-facing) and verification policy (orchestrator-facing). Read by every agent before starting any task. Verification mode is a prompt-shape used to second-source pivotal claims, not a separate subagent type. |
| `ghidra/` | Briefing for `defect-ghidra` subagent (Ghidra MCP decompile/analysis, read-only). |
| `blob-walker/` | Briefing for `defect-blob-walker` subagent (write/run Python investigation scripts; scoped Bash + Write). |
| `text-resources/` | Briefing for `defect-text-resources` subagent (search/analyze gpak text corpus, read-only). |

## Adding a new subagent

1. Create `<name>/briefing.md` and `<name>/example_prompts.md` in this directory, following the existing structure.
2. Create `.claude/agents/<name>.md` with frontmatter (`name`, `description`, `tools`, `model`) and a short system prompt that references `_shared/investigation_rules.md`, `_shared/return_contract.md`, the new briefing, and `findings/ruled_out_leads.md`.
3. Update this index.
