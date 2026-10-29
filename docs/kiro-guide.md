# Building Screen to Cart with Kiro

This kit sets Kiro up so it follows `docs/screen-to-cart-build-plan.md`. It contains:

```
.kiro/
├── steering/          # persistent project knowledge (10 files)
├── hooks/             # automatic checks and guards (6 files)
├── agents/            # custom agents: plan-reviewer, eval-runner
└── scripts/           # guard and check scripts the hooks call
docs/
├── screen-to-cart-build-plan.md
└── kiro-guide.md      # this file
```

Kiro changes quickly. Everything here was checked against the Kiro docs on October 26, 2026 (IDE 1.x / CLI V3 formats). If something doesn't load, check the docs for that feature first.

---

## 1. Install the kit

1. Create the repo: `mkdir screen-to-cart && cd screen-to-cart && git init`, and add `.env` to `.gitignore` right away (`echo '.env' >> .gitignore`).
2. Unzip this kit into the repo root so `.kiro/` and `docs/` sit at the top level.
3. Make the scripts executable: `chmod +x .kiro/scripts/*`.
4. Open the folder in Kiro and trust the workspace (workspace agents and hooks only load in trusted workspaces).
5. Open the **Steering** section of the Kiro panel and confirm all 10 files appear. Don't click "Generate Steering Docs"; `product.md`, `tech.md` and `structure.md` already exist and are written from the plan.
6. Open the **Agent Hooks** section and confirm the 6 hooks appear.
7. Commit: `git add . && git commit -m "Kiro setup"`.

---

## 2. What each piece does here

### Steering (how Kiro should think about the project)

| File | Mode | Loads when |
|---|---|---|
| `product.md` | always | Every interaction: what Screen to Cart is, non-goals |
| `tech.md` | always | Every interaction: stack, uv/pnpm only, `get_llm(role)`, no secrets |
| `structure.md` | always | Every interaction: folder layout, naming, where new code goes |
| `build-plan.md` | auto | When you're planning, writing specs, or checking work against the plan. Pulls in the full plan via `#[[file:docs/screen-to-cart-build-plan.md]]` |
| `free-tier-budget.md` | auto | When work touches LLM calls, tests, evals or caching |
| `extension.md` | fileMatch `extension/**/*` | When editing extension code: capture rules, permissions |
| `backend-python.md` | fileMatch `backend/**/*.py` | When editing backend code |
| `langgraph-pipeline.md` | fileMatch graph + llm folders | When editing the pipeline: graph shape, state, streaming |
| `testing.md` | fileMatch tests | When editing tests |
| `eval.md` | manual | Only when you type `#eval` |

Why the plan isn't `always`: it's ~500 lines, and loading it into every interaction wastes context. The `auto` file pulls it in when it's relevant, and the file reference means the steering always reads the current version of the plan, so you only ever edit the plan in one place.

### Hooks (what happens automatically)

| Hook | Trigger | What it does |
|---|---|---|
| `format-python` | Agent saves a `backend/**/*.py` file | `ruff format` + `ruff check --fix`; errors go back to the agent |
| `typecheck-extension` | Agent saves an `extension/**/*.ts(x)` file | `tsc --noEmit`; errors go back to the agent |
| `regenerate-api-types` | Agent saves `backend/app/schemas.py` | Agent prompt: regenerate `lib/api-types.ts` and fix callers (uses credits) |
| `guard-secrets` (3 hooks in one file) | Before any file write, file read, or shell command | Blocks the agent from writing, reading or using the shell on real `.env` files, and from writing API keys into any file. `.env.example` stays allowed. Your own edits are never blocked |
| `guard-quota` | Before any shell command | Blocks full eval runs and tests forced into live LLM mode |
| `quick-check` | Agent finishes a turn | ruff + offline pytest + tsc; failures go back to the agent |

How command hooks talk to Kiro: exit code 0 adds stdout to the agent's context; any other exit code sends stderr to the agent as an error, and for Pre Tool Use hooks it also blocks the tool call. That's what makes the guards work.

File hooks only fire on changes the agent makes, not your own edits.

**You own `.env`.** Hooks only run on the agent's tool calls, so editing `.env` yourself is never blocked. The guard covers all three ways the agent could reach the file: the write tool, the read tool (so your keys never end up in the agent's context), and the shell (`cat .env`, `echo KEY=... >> .env`, `sed -i`, `source .env`, `cp .env.example .env`). When the agent needs a new setting, it adds the name to `.env.example` and `app/config.py` and tells you what to set. Also make sure `.env` is in `.gitignore`.

If `quick-check` slows you down in Phase 0–1, set `"enabled": false` in `.kiro/hooks/quick-check.json` and turn it back on in Phase 2.

### Custom agents

| Agent | Use it for |
|---|---|
| `plan-reviewer` | After finishing a spec or a chunk of tasks: read-only review of the diff against the phase's "Done when", the spec, and the steering rules |
| `eval-runner` | From Phase 2 on: runs the dev-subset eval, compares with the last run, writes `SUMMARY.md` |

Custom agents don't load steering automatically, which is why both list steering files in `resources`. Select one as the session agent in the chat, or ask the main agent to delegate to it as a sub-agent.

---

## 3. The build loop: one spec per phase

Specs are Kiro's core feature and the main way to make it follow the plan. Each spec produces `requirements.md`, `design.md` and `tasks.md` under `.kiro/specs/<name>/`, and Kiro tracks task progress as it implements.

For each phase:

1. **Start the spec.** In the Kiro panel, click `+` under Specs (or choose Spec in chat) → Feature → **Requirements-First**. Paste the phase prompt from section 4.
2. **Review requirements.** Use the floating **Review** button to comment on exact passages. Check that the acceptance criteria match the phase's "Done when". Run **Analyze Requirements** to catch gaps and contradictions before design.
3. **Review design.** Check it against section 3 of the plan (architecture and request flow) and the steering rules. This is where you catch "it decided to use pip" or "it put the transcript fetch in the backend."
4. **Review tasks.** Each task should be small enough to review in one sitting. Ask Kiro to split any task that touches more than ~3 files.
5. **Run tasks.** Run them one at a time at first so you learn the code. Later, "run all tasks" lets Kiro run independent tasks in parallel waves.
6. **Review with the plan-reviewer agent.** Switch to `plan-reviewer` and say: "Review the working tree against Phase N and the `phase-N-...` spec."
7. **Check "Done when" yourself,** then commit and tag: `git tag phase-N-done`.

Use a **Quick Spec** for Phase 0, since it's well understood and doesn't need approval gates. Use a **Bugfix Spec** whenever something breaks in a way that isn't a one-line fix.

---

## 4. Spec prompts for each phase

Paste these when you create each spec. They point Kiro at the plan rather than restating it.

**Phase 0 — Setup (Quick Spec)**
> Create the spec `phase-0-setup` for Phase 0 of docs/screen-to-cart-build-plan.md. Follow sections 4 and 5 exactly: uv project named screen-to-cart-backend with the CPU-only torch index, the listed runtime/dev/eval dependencies, the WXT React extension named screen-to-cart-extension, docker-compose with pgvector/pgvector:pg16, `.env.example` from section 5, FastAPI `/health`, the `get_llm(role)` provider factory, and Langfuse setup in `app/observability.py`. Acceptance criteria: the Phase 0 "Done when" line. I'll fill in `.env` myself.

**Phase 1 — Capture**
> Create the spec `phase-1-capture` for Phase 1 of docs/screen-to-cart-build-plan.md, following the request flow in section 3 (steps 1–6) and the permissions table. Include: the hotkey and side panel trigger, pause at t, `GET /lookup` before capture, hiding YouTube's controls, three captures at t, t−0.5s and t−1.0s by seeking back with ≥0.5s spacing, OffscreenCanvas cropping with devicePixelRatio, transcript fetched in the browser, and backend sharpest-frame selection. Add a task early on to test whether `captureVisibleTab` works from a side panel button click after navigating to a new video. Acceptance criteria: the Phase 1 "Done when" line.

**Phase 2 — Identify**
> Create the spec `phase-2-identify` for Phase 2 of docs/screen-to-cart-build-plan.md. Use the model plan and rate-limit rules from section 2 and the free-tier-budget steering. Include the ProductCandidate schema, Tier 1 on qwen/qwen3.8-27b with JSON mode, Tier 2 on openai/gpt-oss-120b only below the confidence threshold, the per-model token bucket, record/replay mode, the identify cache, and the eval labels format. Acceptance criteria: the Phase 2 "Done when" line.

**Phase 3 — Retrieve**
> Create the spec `phase-3-retrieve` for Phase 3 of docs/screen-to-cart-build-plan.md: the retailer base interface and Listing schema, eBay Browse and Best Buy adapters with respx tests, LangGraph wiring with Send fan-out for the top candidate only and the `operator.add` reducer, and the 24h retailer cache. Follow the langgraph-pipeline steering. Acceptance criteria: the Phase 3 "Done when" line.

**Phase 4 — Resolve and verify**
> Create the spec `phase-4-resolve` for Phase 4 of docs/screen-to-cart-build-plan.md: dedupe (GTIN/UPC/MPN, then rapidfuzz), SigLIP rerank with embeddings in pgvector, price breakdown with estimated tax, accessory filtering, rule-first check_quality, and the refine loop capped at 2 attempts with a test proving the cap. Acceptance criteria: the Phase 4 "Done when" line.

**Phase 5 — UX and trust**
> Create the spec `phase-5-ux` for Phase 5 of docs/screen-to-cart-build-plan.md: SSE streaming of node updates to the side panel, candidate chips that search on click, the product card and price breakdown, "why this match" evidence, sponsorship detection as a parallel branch from START, and the structured error states from the backend-python steering. Acceptance criteria: the Phase 5 "Done when" line.

**Phase 6 — Evaluate and ship**
> Create the spec `phase-6-eval-ship` for Phase 6 of docs/screen-to-cart-build-plan.md. Include #eval. Cover the eval runner with Langfuse datasets and scores, ablations, threshold tuning, deployment, and Chrome Web Store publishing. Full 200-item runs are tasks for me to start manually, spread over several days. Acceptance criteria: the Phase 6 "Done when" line.

---

## 5. Day-to-day habits

- **Start each session by naming the phase:** "We're in Phase 3, spec phase-3-retrieve, task 4." Kiro then pulls in the right auto steering and spec.
- **Keep the plan current.** When you change a decision, update `docs/screen-to-cart-build-plan.md` first, then ask Kiro to update the affected spec. Steering reads the plan by reference, so it updates automatically.
- **Add steering when you correct Kiro twice.** If you correct the same mistake twice, it belongs in a steering file.
- **Use AGENTS.md for folder-level notes** if you prefer them next to the code (e.g. `extension/AGENTS.md`). They're always included and don't support inclusion modes, so keep them short.
- **Rewind instead of arguing.** If a task goes off the rails, use checkpoints to roll back and re-prompt with a clearer instruction rather than asking Kiro to undo its own changes.
- **Watch credits.** Agent-action hooks (`regenerate-api-types`) and workflows cost credits; command hooks don't.

---

## 6. Optional extras

- **Workflows** (opt-in, uses more tokens): good for Phase 6 or a big refactor. Enable them under Workspace Configuration → Workflows. The bundled `investigate` recipe is useful for read-only questions like "how does the refine loop decide to stop?", and `feature-pipeline` runs requirements → design → implementation → independent review → validation in the background. Keep "Use workflows" on **Only when asked** while you're learning the codebase.
- **MCP servers** in `.kiro/settings/mcp.json`: a Postgres MCP server lets Kiro inspect your dev database (cache rows, embeddings) directly. Scope it to the dev database only.
- **Powers** bundle MCP tools and skills and load only when relevant. Browse kiro.dev/powers for anything matching your stack before adding raw MCP servers.
