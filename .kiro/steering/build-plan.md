---
inclusion: auto
name: build-plan
description: The full Screen to Cart build plan (architecture, request flow, phases, dependencies, model plan, rate limits, risks). Use when creating or updating a spec, planning a phase, deciding where something goes, or checking whether work matches the plan.
---

# Build plan

The full plan lives in the repo and is the source of truth for phases, acceptance criteria ("Done when"), architecture and request flow:

#[[file:docs/screen-to-cart-build-plan.md]]

When working on a phase:
- Use that phase's numbered steps as the starting point for requirements and tasks.
- Use that phase's "Done when" line as acceptance criteria.
- Don't pull work forward from later phases unless asked.
- Keep the spec light (see `engineering.md`): a short task list built from the phase's steps, with requirements and design only for real decisions. Phase 0's spec (~100 requirements, a 740-line design) was too heavy; don't use it as a template.
