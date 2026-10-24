# 0008. Front-end and visible texts
Status: Accepted
Date: 2026-10-24

## Context
Decided at the start of the project: React and Tailwind, with strict TypeScript and ESLint rules; a panel served by the API itself; the texts impersonal, short and without technical sentences, following the rules of no-ai-slop.

## Decision
- `web/`: React, Vite, Tailwind, TypeScript strict, ESLint and Prettier, built by pnpm; the font Outfit is served from the build, never from a third party.
- The API serves the build: `assets/` and `fonts/` mounted, a file at the top of the build, otherwise `index.html` for any path outside the API.
- Every visible text is French, in `web/src/texts.ts` alone, and follows `docs/writing.md`.
- One address per section, read and written with the History API of the browser (`web/src/state/route.ts`, no router library): `/` (Automatique), `/manuel`, `/en-attente`, `/telechargements`, `/ranger`, `/jellyfin`, `/parametres`; a tab of the settings other than the first adds its slug (`/parametres/sources`, `recherche`, `filtres`, `rangement`, `discord`, `acces`, `journaux`). A change of section or of tab adds an entry to the history; Back and Forward change the view alone, the bar, the header and the frame stay. The links of the sidebar are real links (a new tab opens with the middle click). An unknown address, or one written otherwise (`/parametres/services`, a trailing slash), is replaced by the address of its view, the page Automatique when it has none.
- Mobile first: the classes without a prefix are those of a small screen, `md:` (768 px) brings the layout of a large one; it is the single breakpoint of the layout (`sm:` and `lg:` only spread a grid or a row of fields wider). Under it, a bar at the top (`web/src/components/TopBar.tsx`: the name, the section, the button Menu) opens the sidebar over the page: the focus enters it and stays there, Escape, a click beside it, a link followed or a wider screen close it, the focus goes back to the button, the page under it does not scroll; its links stay the same real links. The frame keeps 1 rem of margin on a small screen, 2.5 rem on a large one.
- A table is a list of cards under `md:`, a table from it (`web/src/components/stacked.ts`): the same cells and the same actions, each one placed in its card by its classes, the headers hidden and a value that does not speak for itself named in the card (`Seeds`, `Depuis`); a checkbox of a column gets its name beside it, the box of a whole selection goes above the list. A long title breaks anywhere in a card, it is cut with an ellipsis in a table.
- A dialog takes the whole screen under `md:`, a centred window from it (`web/src/components/dialog.ts`), a column as tall as its content up to its maximum height (`height: fit-content`: `auto` stretches a modal dialog from the top of the screen to its bottom), as wide as its content between 28rem and 56rem, or, for a dialog made of fields (which have no width of their own), a preferred width that shrinks on a narrow screen; a cut text of a dialog as wide as its content does not count in its width (`contain: inline-size`): its header, its content, the one part that scrolls, and its buttons at the bottom, above the safe area of the screen. The sign-in and the set-up of the first launch take the whole screen too, the buttons of the set-up stay at the bottom while its steps scroll.
- Under `md:`, `web/src/index.css` gives every button, select and field at least 44 px for the finger, every checkbox and radio 20 px, and every field a text of 16 px, under which iOS zooms in on the page at the typing; these rules sit outside the layers of Tailwind, so that no class of a component goes under them, and they leave the switches and the elements read by the screen readers alone. The bar of a selection runs along the bottom of the screen, above its safe area. No page scrolls sideways at 360 px: a long name breaks, a row of fields or of buttons wraps, a strip of tabs too long for the screen scrolls by itself.
- The search (its text, its kind, the work chosen, the releases checked) never goes into the address nor the history: leaving a page of search forgets it, coming back never runs it again; a search opened from En attente or Téléchargements adds the address of its page, then searches.

## Rejected alternatives
- Two renderings of each table, a list for the small screens and a table for the large ones: the data and the actions written twice.
- A desktop-first layout narrowed by `max-*:` classes: every page would carry its large layout and its fixes.
- A separate server for the pages: one more service and a cross-origin API.
- A router library for the addresses: seven sections and the tabs of one need the History API alone.
- The search in the address: the owner wants it forgotten when the page is left.

## Consequences
- The image builds the front-end in a Node stage and holds no Node.
- No address of a section is the name of a file at the top of the build (`index.html`, `favicon.svg`) nor starts with `assets/`, `fonts/` or the prefix of the API: the API answers `index.html` there (`tests/integration/test_pages.py`).
