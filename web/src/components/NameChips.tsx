import type { ReactElement } from "react";

import { texts } from "../texts";
import type { AltTitle } from "../types";
import { CheckIcon } from "./icons";

type Props = {
  readonly titles: readonly AltTitle[];
  readonly enabled: ReadonlySet<string>;
  readonly onToggle: (title: string) => void;
};

export function NameChips({ titles, enabled, onToggle }: Props): ReactElement {
  return (
    <fieldset className="rounded-xl border border-slate-200 bg-surface px-4 py-4 md:px-5">
      <legend className="sr-only">{texts.works.names}</legend>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold text-ink" aria-hidden="true">
          {texts.works.names}
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {titles.map((alt) => {
          const on = enabled.has(alt.title);
          return (
            <label
              key={alt.title}
              className={`flex min-h-11 max-w-full cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-sm has-focus-visible:ring-2 has-focus-visible:ring-accent-ring md:min-h-0 ${
                on ? "border-accent bg-accent-soft text-accent-text" : "border-slate-200 text-slate-500 line-through"
              }`}
            >
              <input
                type="checkbox"
                checked={on}
                onChange={() => {
                  onToggle(alt.title);
                }}
                className="sr-only"
              />
              {on ? <CheckIcon className="size-3.5" /> : null}
              <span className="min-w-0 wrap-anywhere">{alt.title}</span>
              <span className="text-xs opacity-60">{alt.language}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
