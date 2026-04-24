# CLAUDE.md

## Project AI Operating Manual

This repository uses a structured AI-assisted development workflow.
Follow this file exactly unless the human explicitly overrides it.

---

## 0. Core Principles

1. OpenSpec is the canonical source of truth for:
   - requirements
   - specs
   - design decisions
   - task breakdown
   - change history

2. No meaningful feature implementation should begin unless there is an active OpenSpec change
   or the human explicitly asks for a tiny spike / prototype / bugfix without full ceremony.

3. Use the right tool for the right layer:
   - gstack = challenge the idea, sharpen scope, validate readiness, QA, ship
   - OpenSpec = formalize and track requirements/design/tasks
   - Compound Engineering = execution planning, review, compounding knowledge
   - Superpowers = implementation discipline, TDD, debugging, task-by-task execution

4. Prefer small, reviewable increments over large speculative rewrites.

5. Never silently invent product requirements.
   If something is unclear:
   - ask
   - or document the assumption explicitly in OpenSpec / plan output

6. Never claim work is complete without verification.

---

## 1. Tool Ownership

### 1.1 OpenSpec owns
Use OpenSpec for:
- proposing changes
- maintaining specs
- design docs
- task lists
- verification
- archiving completed changes

Primary commands:
- `/opsx:propose`
- `/opsx:new`
- `/opsx:continue`
- `/opsx:ff`
- `/opsx:verify`
- `/opsx:sync`
- `/opsx:archive`

Rules:
- All durable requirements must end up in `openspec/`
- If code and spec disagree, raise the mismatch explicitly
- Before closing a feature, run verification
- After completion, archive the change

### 1.2 gstack owns
Use gstack for:
- idea pressure-testing
- product scope compression/expansion
- engineering plan challenge
- test / QA on staging
- ship readiness

Primary commands:
- `/office-hours`
- `/plan-ceo-review`
- `/plan-eng-review`
- `/plan-design-review` when UI matters
- `/qa`
- `/ship`

Rules:
- Use `/office-hours` at the beginning of ambiguous or important features
- Use `/plan-ceo-review` when scope, ambition, or MVP boundary is unclear
- Use `/plan-eng-review` before implementation for non-trivial features
- Use `/qa` against staging or preview URLs before calling work done
- Use `/ship` for final PR/release preparation

### 1.3 Compound Engineering owns
Use Compound Engineering for:
- brainstorming implementation approaches
- turning a feature/design into an execution plan
- structured work execution
- multi-agent code review
- documenting learnings

Primary commands:
- `/ce:brainstorm`
- `/ce:plan`
- `/ce:work`
- `/ce:review`
- `/ce:compound`

Rules:
- Read OpenSpec docs first before making a plan
- Plans should be executable, incremental, and test-aware
- Use `/ce:review` before merge for substantial changes
- Use `/ce:compound` after merge or after major findings

### 1.4 Superpowers owns
Use Superpowers for:
- writing concrete implementation plans
- TDD
- systematic debugging
- subagent-driven execution
- disciplined completion checks

Preferred skills:
- `superpowers:writing-plans`
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `superpowers:subagent-driven-development`
- `superpowers:verification-before-completion` if available

Rules:
- For implementation, prefer Superpowers skills over ad hoc coding
- For new behavior, write failing tests first whenever practical
- For bugs, do root-cause analysis before patching
- Never fix a bug without either:
  - a reproducer
  - a failing test
  - or a documented reason that a test is impossible

---

## 2. Default Workflow

For any non-trivial feature, follow this order:

1. Clarify the request
2. Run gstack discovery/review as needed
3. Create or update OpenSpec change
4. Use Compound Engineering to create an execution plan
5. Use Superpowers to implement in small steps
6. Use Compound Engineering to review code
7. Use gstack QA on a running environment if relevant
8. Run OpenSpec verification
9. Prepare PR / ship
10. Archive OpenSpec change
11. Compound learnings

Canonical sequence:

- `/office-hours`
- `/plan-ceo-review`
- `/plan-eng-review`
- `/opsx:propose <change-name>`
- `/ce:plan`
- `Use superpowers:writing-plans`
- `Use superpowers:test-driven-development`
- `Use superpowers:subagent-driven-development`
- `/ce:review`
- `/qa <preview-or-staging-url>`
- `/opsx:verify <change-name>`
- `/ship`
- `/ce:compound`
- `/opsx:archive <change-name>`

Not every task needs every step.
Use the lightweight mode for:
- tiny bugfixes
- copy changes
- safe refactors
- ultra-local code edits

But still:
- inspect context
- write/adjust tests when appropriate
- verify before completion

---

## 3. Complexity Routing Rules

### 3.1 Tiny task
Examples:
- typo
- text label
- small styling tweak
- narrow bugfix with obvious root cause

Default flow:
1. inspect local context
2. optionally create a lightweight note, no full OpenSpec required
3. use `superpowers:test-driven-development` if behavior changes
4. verify locally
5. summarize changes clearly

### 3.2 Medium task
Examples:
- new API endpoint
- form workflow
- CRUD surface
- auth/permissions adjustment
- moderate refactor

Default flow:
1. `/plan-eng-review`
2. `/opsx:propose <change-name>` or update existing change
3. `/ce:plan`
4. `superpowers:writing-plans`
5. `superpowers:test-driven-development`
6. `/ce:review`
7. `/opsx:verify`

### 3.3 Large / risky task
Examples:
- new product area
- cross-cutting data model changes
- billing
- auth
- migrations
- infrastructure changes
- user-facing workflow redesign

Default flow:
1. `/office-hours`
2. `/plan-ceo-review`
3. `/plan-eng-review`
4. `/plan-design-review` if UI/UX is central
5. `/opsx:propose <change-name>`
6. `/ce:plan`
7. `superpowers:writing-plans`
8. implement in phases
9. `/ce:review`
10. `/qa <url>`
11. `/opsx:verify`
12. `/ship`
13. `/ce:compound`
14. `/opsx:archive`

---

## 4. Mandatory Behavioral Rules for Claude

### 4.1 Before coding
Before writing code for any non-trivial change:
- inspect the relevant files
- inspect tests
- inspect config and boundaries
- check whether an OpenSpec change already exists
- avoid re-planning from scratch if there is already an accepted spec/design

### 4.2 During planning
When planning:
- prefer concrete file-level plans
- identify risks
- identify migrations
- identify rollback strategy
- identify tests
- identify what can be deferred

### 4.3 During implementation
During implementation:
- work in small chunks
- explain intent briefly before major edits
- preserve unrelated code
- avoid broad rewrites unless explicitly requested
- do not silently change APIs or behavior beyond scope

### 4.4 During debugging
For bugs:
- first reproduce
- identify the true root cause
- add or update a failing test where practical
- fix minimally
- verify the specific regression and nearby risks

### 4.5 Before marking complete
Before saying "done" or equivalent:
- run relevant tests
- run lint/typecheck if applicable
- confirm acceptance criteria
- list any remaining risks or follow-ups
- if applicable, verify against OpenSpec

Do not say something is complete if:
- tests are skipped without explanation
- known issues remain unstated
- spec mismatches remain unresolved

---

## 5. OpenSpec Rules

### 5.1 Canonical paths
Use these as the source of truth:
- `openspec/specs/`
- `openspec/changes/`
- `openspec/archive/` if present
- `docs/solutions/` — documented solutions to past problems (bugs, best practices, workflow patterns), organized by category with YAML frontmatter (module, tags, problem_type)

### 5.2 Naming
Change names should be:
- short
- descriptive
- kebab-case

Examples:
- `taskflow-v1`
- `add-team-invites`
- `improve-search-ranking`

### 5.3 Required artifacts for significant changes
For medium and large changes, ensure these exist when appropriate:
- `proposal.md`
- `design.md`
- `tasks.md`
- relevant spec deltas

### 5.4 Spec discipline
If a request conflicts with existing specs:
- call out the conflict
- propose a spec update
- do not silently drift implementation away from documented behavior

---

## 6. Planning Output Standard

Whenever producing a plan, structure it like this:

### Objective
What is being changed and why?

### Scope
What is included?
What is explicitly excluded?

### Constraints
Technical, product, timeline, compatibility, migration, security constraints.

### Files / Systems Affected
List likely files, modules, services, database tables, jobs, routes, UI surfaces.

### Risks
List failure modes, edge cases, compatibility concerns, security/privacy risks.

### Implementation Steps
A numbered sequence of small, executable tasks.

### Test Plan
Unit, integration, e2e, manual QA as appropriate.

### Rollback / Recovery
How to back out safely if deployment fails.

### Demo / Verification
What should be shown to prove the feature works.

---

## 7. Implementation Standard

When implementing, prefer this execution style:

1. restate the task briefly
2. inspect relevant code
3. create a small plan
4. write or update failing tests first when practical
5. implement minimal passing change
6. refactor if needed
7. run verification
8. summarize what changed and any residual risks

For multi-step work, stop after each meaningful checkpoint and report:
- what was completed
- what remains
- whether assumptions changed

---

## 8. Testing Standard

### 8.1 General
Prefer real behavior over heavy mocking.
Tests should validate behavior, not implementation trivia.

### 8.2 Required checks when relevant
Run as applicable:
- unit tests
- integration tests
- e2e tests
- lint
- typecheck
- build

### 8.3 Bugfix policy
For bugfixes:
- add a reproducing test whenever feasible
- if no automated test is feasible, document the manual repro and validation steps

### 8.4 No fake confidence
Never claim:
- "fixed"
- "works"
- "fully done"

unless there is actual verification evidence.

---

## 9. Review Standard

Use review at two levels:

### 9.1 Self-review
Before external review:
- inspect diff
- remove dead code
- remove accidental debug output
- verify naming
- verify comments/docs
- verify test coverage around changes

### 9.2 Compound Engineering review
Use `/ce:review` for:
- security-sensitive changes
- auth / billing / migrations
- shared abstractions
- non-trivial refactors
- any PR large enough to hide subtle defects

Capture findings clearly:
- must-fix
- should-fix
- follow-up later

---

## 10. QA Standard

For user-facing changes:
- prefer testing on preview / staging
- use `/qa <url>` when available
- test the happy path and at least key edge cases
- verify permissions and failure states, not only success states

Minimum QA checklist for UI flows:
- load page
- empty/loading/error states
- form validation
- permission boundaries
- persistence after refresh
- mobile/responsive sanity if relevant

---

## 11. Communication Style

When responding:
- be concise but complete
- prefer bullets over long prose
- state assumptions explicitly
- distinguish facts from suggestions
- do not bury risks

When blocked:
- say exactly what is blocked
- say what was checked
- propose the next best action

When there are multiple reasonable options:
- present a recommendation
- give 1–2 alternatives
- explain tradeoffs briefly

---

## 12. Repo Safety Rules

Do not:
- delete large sections of code without reason
- rewrite unrelated files opportunistically
- change environment or deployment config casually
- introduce new dependencies without justification
- run destructive commands unless explicitly requested

For migrations / dangerous changes:
- explain risk first
- prefer reversible steps
- include rollback notes

---

## 13. Branch / PR Rules

For significant work:
- keep changes scoped
- prefer one feature per PR
- include tests
- include spec references
- summarize user impact and risk

PR summary should include:
- what changed
- why
- how it was verified
- screenshots or demo notes if UI changed
- follow-ups if any

---

## 14. Recommended Command Playbooks

### 14.1 New feature
1. `/office-hours`
2. `/plan-ceo-review`
3. `/plan-eng-review`
4. `/opsx:propose <change-name>`
5. `/ce:plan`
6. `Use superpowers:writing-plans`
7. `Use superpowers:test-driven-development`
8. `Use superpowers:subagent-driven-development`
9. `/ce:review`
10. `/qa <url>`
11. `/opsx:verify <change-name>`
12. `/ship`
13. `/ce:compound`
14. `/opsx:archive <change-name>`

### 14.2 Bugfix
1. reproduce bug
2. `Use superpowers:systematic-debugging`
3. add failing test if practical
4. implement minimal fix
5. run focused verification
6. if behavior/spec changed, update OpenSpec
7. `/ce:review` if the area is risky

### 14.3 Refactor
1. inspect boundaries and current tests
2. `/plan-eng-review` if broad refactor
3. ensure behavior is locked by tests
4. refactor in small steps
5. `/ce:review`
6. verify no behavior drift

### 14.4 UI iteration
1. `/office-hours` if requirements unclear
2. `/plan-design-review`
3. update OpenSpec if behavior changes
4. implement incrementally
5. preview and `/qa <url>`
6. summarize UX tradeoffs

---

## 15. Fast Decision Heuristics

If unsure which tool to use:

- "What problem should we solve?" -> gstack
- "What exactly did we decide?" -> OpenSpec
- "How should we execute this cleanly?" -> Compound Engineering
- "How do we implement/debug this correctly?" -> Superpowers

If multiple tools seem applicable:
- use the one that owns the current layer
- do not duplicate artifacts unnecessarily

---

## 16. Completion Checklist

Before final completion, verify:

- [ ] Request understood
- [ ] Scope controlled
- [ ] Relevant OpenSpec change exists or explicit exception documented
- [ ] Plan created for non-trivial work
- [ ] Tests added/updated as needed
- [ ] Code verified
- [ ] Review completed for risky work
- [ ] QA completed for user-facing work
- [ ] Spec verified
- [ ] Remaining risks/follow-ups documented

---

## 17. If the Human Gives Direct Instructions

Human instructions override this file.

However, if the human asks for something risky, unclear, or in conflict with existing specs:
- comply as far as possible
- but explicitly warn about the risk, assumption, or conflict

---

## 18. Preferred Working Attitude

Be rigorous, practical, and calm.

Optimize for:
- correctness
- clarity
- maintainability
- reversible changes
- transparent reasoning
- compounding repository quality over time