import type { ReactElement } from "react";

import { setValue, useSettings, valueOf } from "../../state/settings";
import { texts } from "../../texts";
import { ArrowDownIcon, ArrowUpIcon } from "../icons";

type Props = {
  readonly label: string;
  readonly settingKey: string;
  /** Les valeurs ordonnées, dans leur ordre par défaut. */
  readonly options: readonly string[];
  readonly nameOf: (value: string) => string;
};

/** L'ordre enregistré : chaque valeur une fois ; sinon l'ordre par défaut. */
function orderOf(value: unknown, options: readonly string[]): readonly string[] {
  if (
    Array.isArray(value) &&
    value.length === options.length &&
    options.every((option) => (value as readonly unknown[]).includes(option))
  ) {
    return value as readonly string[];
  }
  return options;
}

/** Une liste ordonnée d'un réglage : chaque ligne monte ou descend d'un cran. */
export function OrderField({ label, settingKey, options, nameOf }: Props): ReactElement {
  const settings = useSettings();
  const order = orderOf(valueOf(settings, settingKey), options);
  const saved = orderOf(settings.saved?.values[settingKey], options);
  const changed = order.join() !== saved.join();

  function move(index: number, step: number): void {
    const next = [...order];
    const [moved] = next.splice(index, 1);
    if (moved !== undefined) {
      next.splice(index + step, 0, moved);
      setValue(settingKey, next);
    }
  }

  return (
    <fieldset className="space-y-1.5">
      <legend className="text-sm font-medium">{label}</legend>
      <ol className={`divide-y divide-slate-100 rounded-lg border ${changed ? "border-accent" : "border-slate-200"}`}>
        {order.map((value, index) => (
          <li key={value} className="flex items-center gap-2 px-3 py-1.5 text-sm">
            <span className="w-5 text-xs text-slate-400 tabular-nums">{index + 1}</span>
            <span className="min-w-0 flex-1 truncate">{nameOf(value)}</span>
            <button
              type="button"
              disabled={index === 0}
              onClick={() => {
                move(index, -1);
              }}
              aria-label={texts.titleOrder.up(nameOf(value))}
              className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30"
            >
              <ArrowUpIcon />
            </button>
            <button
              type="button"
              disabled={index === order.length - 1}
              onClick={() => {
                move(index, 1);
              }}
              aria-label={texts.titleOrder.down(nameOf(value))}
              className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100 disabled:opacity-30"
            >
              <ArrowDownIcon />
            </button>
          </li>
        ))}
      </ol>
    </fieldset>
  );
}
