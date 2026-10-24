# 0001. Documents: a README, pages in docs/, living ADRs
Status: Accepted
Date: 2026-10-21

## Context
Decided at the start of the project: the rules of an earlier project of the same owner, adapted to shelfdrop. Rules and commands must stay apart from descriptions, and another session must be able to resume the work from the repository alone.

## Decision
- `CLAUDE.md` holds the rules and the commands; `docs/` holds the descriptions and the contracts, in English: for the users, `installation.md`, `configuration.md`, `api.md`, `how-it-works.md`, `mcp-client.md` and the ADRs in `docs/adr/`; for the agents, `docs/agents/` (`development.md`, `writing.md`, `verified-facts.md`). `README.md` says what shelfdrop is, how to start it and where each page is; `CONTRIBUTING.md` how a human contributor sets up, tests and commits (decided on 2026-10-24: the repository reads as a project, the pages written for the agents apart).
- The docs change with the code, in the same commit. An ADR states what is decided today on its subject and is updated in place; a decision no code implements yet waits outside the repository, with the plan of its feature.
- `docs/agents/writing.md` is in English but its examples, which are French texts.

## Rejected alternatives
- Everything in `CLAUDE.md`: rules and descriptions mixed, and a file too long to be read whole.
- The plan of the project in the repository: it describes features no code implements.

## Consequences
- Reviewing a change includes its docs; no tool checks them.
