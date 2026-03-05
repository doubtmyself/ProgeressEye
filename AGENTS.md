# ProgressEye Agent Operating Rules

## Session Entry (Mandatory)

1. Always start by reading `docs/INDEX.md`.
2. Then read the platform index based on task scope:
   - PC: `docs/pc-agent/INDEX.md`
   - Mobile: `docs/mobile-app/INDEX.md`
   - Backend: `docs/backend/INDEX.md`

## Documentation Policy (Mandatory)

1. `docs/` is the only official documentation source.
2. Do not create or maintain `README.md` files as documentation sources.
3. If new information is needed, add or split documents under `docs/` and update relevant index files.

## Update Discipline

1. Any feature/policy change must update:
   - Relevant `docs/*/topics/*.md`
   - Relevant platform `docs/*/INDEX.md`
   - `docs/privacy-policy-ko.md` when account/privacy policy changes
2. Keep links/path references valid after edits.


Karpathy Guidelines
Behavioral guidelines to reduce common LLM coding mistakes, derived from Andrej Karpathy's observations on LLM coding pitfalls.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]