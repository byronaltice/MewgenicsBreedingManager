# Verification Mode

A subagent enters **verification mode** when its dispatch prompt is shaped as a verification request rather than an open investigation. Any of the three subagent types (`defect-ghidra`, `defect-blob-walker`, `defect-text-resources`) may be dispatched this way — verification mode is a prompt shape, not a separate subagent type.

## Trigger shape

The dispatch prompt names:
- A single specific claim, quoted verbatim.
- The artifact it concerns: function/offset/address, save-blob offset (with relativity), GON path/file:line, or audit artifact path.
- An explicit request for a verdict in the format below.

If the dispatch is not shaped this way, you are in normal task mode — follow `return_contract.md` instead.

## Behavior in verification mode

- Do **not** synthesize new directions, propose follow-ups, or surface unrelated findings.
- Re-derive the cited result independently using the same tool that produced it (re-decompile via MCP, re-run the relevant script, re-grep the corpus). **Do not trust the original report's quoted lines** — fetch them yourself.
- Compare your reading to the verbatim claim *at the specific level of detail in the claim*: the offset, line, value, or symbol named.
- Identity-claim discipline (`investigation_rules.md` §2, ≥2 independent lines) still applies — your verdict is itself an identity claim about the artifact.

## Return shape (overrides the standard contract)

Output exactly these sections, nothing else:

### Verdict
One of: `CONFIRM` / `CONTRADICT` / `INCONCLUSIVE`.

### Evidence
≤5 lines quoted verbatim from the artifact, each with an address / file:line / offset citation. No paraphrasing.

### Disagreement
Required if verdict is `CONTRADICT` or `INCONCLUSIVE`; omit if `CONFIRM`.

> Original claim: `<quoted X>`. My reading: `<quoted Y>`. Specific divergence at `<address / file:line / offset>`.

## Length cap

200 words total, excluding the ≤5 quoted evidence lines.

## What to omit

In verification mode, do **not** include `Method`, `Confidence`, `Open follow-ups`, or `Artifacts written`. The standard return contract is intentionally bypassed to keep verifier output minimal — the orchestrator only needs the verdict and the citations that ground it.

## Out of scope

If your re-derivation surfaces an obviously-related question, drop it. At most, append a single plain-text line after the disagreement block — no "follow-up directions," no "recommended next steps." Direction selection remains the orchestrator's job.
