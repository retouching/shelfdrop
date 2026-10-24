import { useId, useState, type KeyboardEvent, type ReactElement } from "react";

import { languageLabel, sourceName } from "../api/works";
import { useSettings, valueOf } from "../state/settings";
import { texts } from "../texts";
import { languageOrderOf, sortProposals, type TitleProposal } from "../utils/titles";
import { ChevronDownIcon } from "./icons";
import { field } from "./fields";

type Props = {
  readonly label: string;
  readonly value: string;
  readonly onChange: (value: string) => void;
  /** Les noms connus de l'œuvre. */
  readonly names: readonly TitleProposal[];
  /** Le nom retenu d'office : en tête de la liste. */
  readonly chosen: string;
  /** Classes de plus du champ (une bordure de champ modifié). */
  readonly className?: string;
};

/** « FR · MangaUpdates, Kitsu » : la langue d'un nom et ses sources, deux au plus. */
export function proposalMeta(name: TitleProposal): string {
  const shown = name.sources.slice(0, 2).map(sourceName).join(", ");
  const more = name.sources.length > 2 ? ` ${texts.titleField.more(name.sources.length - 2)}` : "";
  return [languageLabel(name.language), shown + more].filter((part) => part !== "").join(" · ");
}

/** Un titre libre, avec les noms connus proposés (langue et source) : une liste déroulante au clavier
 * (flèches, Entrée, Échap) et au doigt. */
export function TitleField({ label, value, onChange, names, chosen, className = "" }: Props): ReactElement {
  const id = useId();
  const listId = `${id}-list`;
  const settings = useSettings();
  const languages = languageOrderOf(valueOf(settings, "search.language_order"));
  const all = sortProposals(names, chosen, languages);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const [active, setActive] = useState(-1);
  const needle = (filter ?? "").trim().toLowerCase();
  const shown = needle === "" ? all : all.filter((name) => name.title.toLowerCase().includes(needle));
  const expanded = open && shown.length > 0;
  const chosenKey = chosen.trim().toLowerCase();

  function pick(name: TitleProposal): void {
    onChange(name.title);
    setOpen(false);
    setFilter(null);
    setActive(-1);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!expanded) {
        setOpen(true);
        setFilter(null);
        setActive(event.key === "ArrowDown" ? 0 : all.length - 1);
        return;
      }
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + shown.length) % shown.length);
    } else if (event.key === "Enter" && expanded && active >= 0 && active < shown.length) {
      event.preventDefault();
      const name = shown[active];
      if (name !== undefined) {
        pick(name);
      }
    } else if (event.key === "Escape" && expanded) {
      // Ferme la liste sans fermer la fenêtre.
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      setActive(-1);
    }
  }

  return (
    <div className="relative space-y-1.5">
      <label htmlFor={`${id}-input`} className="block text-sm font-medium">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={`${id}-input`}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-activedescendant={expanded && active >= 0 ? `${id}-option-${String(active)}` : undefined}
          autoComplete="off"
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setFilter(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onKeyDown={onKeyDown}
          onBlur={() => {
            setOpen(false);
            setActive(-1);
          }}
          className={`${field} ${className}`}
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label={texts.titleField.proposals}
          aria-expanded={expanded}
          aria-controls={listId}
          disabled={all.length === 0}
          onMouseDown={(event) => {
            // Garde le champ actif : la liste ne se ferme pas avant le clic.
            event.preventDefault();
          }}
          onClick={() => {
            setFilter(null);
            setActive(-1);
            setOpen((current) => !current);
            document.getElementById(`${id}-input`)?.focus();
          }}
          className="shrink-0 rounded-lg border border-slate-200 px-2.5 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
        >
          <ChevronDownIcon className="size-4" />
        </button>
      </div>
      <div
        id={listId}
        role="listbox"
        aria-label={texts.titleField.proposals}
        hidden={!expanded}
        className="absolute inset-x-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-200 bg-surface py-1 shadow-lg"
      >
        {shown.map((name, index) => {
          const meta = proposalMeta(name);
          const isDefault = name.title.toLowerCase() === chosenKey;
          return (
            // eslint-disable-next-line jsx-a11y/click-events-have-key-events -- the keyboard is the combobox's (arrows, Enter), the options never take the focus
            <div
              key={name.title}
              id={`${id}-option-${String(index)}`}
              role="option"
              tabIndex={-1}
              aria-selected={index === active}
              onMouseDown={(event) => {
                event.preventDefault();
              }}
              onClick={() => {
                pick(name);
              }}
              className={`cursor-pointer px-3 py-2 text-sm ${index === active ? "bg-accent-soft" : "hover:bg-slate-50"}`}
            >
              <span className="block wrap-anywhere text-ink">{name.title}</span>
              {meta === "" && !isDefault ? null : (
                <span className="block text-xs text-slate-500">
                  {[meta, isDefault ? texts.titleField.chosen : ""].filter((part) => part !== "").join(" · ")}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
