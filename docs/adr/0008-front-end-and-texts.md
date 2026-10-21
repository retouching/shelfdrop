# 0008. Front-end and visible texts
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user: React and Tailwind, with strict TypeScript and ESLint rules; a panel at `shelfdrop.maigo.party`; the texts impersonal, short and without technical sentences, following the rules of no-ai-slop.

## Decision
- `web/`: React, Vite, Tailwind, TypeScript strict, ESLint and Prettier, built by pnpm; the font Outfit is served from the build, never from a third party.
- The API serves the build: `assets/` and `fonts/` mounted, a file at the top of the build, otherwise `index.html` for any path outside the API.
- Every visible text is French, in `web/src/texts.ts` alone, and follows `docs/writing.md`.

## Rejected alternatives
- A separate server for the pages: one more service and a cross-origin API.

## Consequences
- The image builds the front-end in a Node stage and holds no Node.
