# Engineering principles

Screen to Cart is a solo portfolio project. Build the simplest thing that meets the current phase's "Done when" line, and make it easy to read.

## Scope
- Build only what the current phase needs. No code for later phases, no "in case we need it" options, flags, abstractions or error types.
- Add an abstraction only when there are two real users of it. One retailer adapter doesn't need a plugin system.
- Handle errors that can actually happen and that the user would see. Don't add error paths for things the library already handles or that can't happen yet.
- If a task looks like it needs more than about 200 lines of new code, stop and say so before building it.
- Prefer the library's defaults. Don't wrap a library just to rename it.

## Clean code
- Code should explain itself. Use clear names for functions, variables and types so a reader rarely needs a comment.
- Write comments only for the "why": a non-obvious decision, a workaround, an external constraint (rate limits, Chrome API limits). Never restate what the code does.
- Docstrings: one line for public functions whose purpose isn't obvious from the name and signature. No docstrings on private helpers or obvious code.
- Keep functions short and doing one thing. Prefer early returns over nested `if`s.
- No dead code, no commented-out code, no TODOs without a phase number.
- Follow the existing style of the file you're editing.

## Tests
- Test behavior that could break and would matter: pipeline nodes, retailer adapters, matching and ranking logic, the refine-loop cap, frame selection.
- Use a few clear examples per behavior (typically 1–4 cases). No generated 100-case parametrized tests and no property-based tests unless the logic is actually tricky (e.g. dedupe).
- Don't test library behavior (pydantic validation, settings source order, FastAPI routing), file contents (README, `.env.example`), or one-line wrappers.
- Name tests `test_<unit>_<behavior>`.

## Specs and planning
- A phase spec starts from the build plan's numbered steps and "Done when" line. Keep it short: requirements and design only where there's a real decision to record, and a task list of about 5–12 tasks.
- Don't restate the build plan or steering rules in the spec; reference them.
- Checkpoints run the existing checks (`pytest`, `ruff`, `mypy`, `pnpm build`). Don't add new verification steps for things the tools already guarantee.

## Commits
- Commit after each top-level task, without asking.
- Subject only, in Conventional Commits form: `<type>(<scope>): <summary>`, under 60 characters. Add a body only when a decision isn't obvious from the diff, and then one or two short lines.
