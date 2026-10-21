import type { ReactElement } from "react";

export type Stat = {
  readonly label: string;
  readonly value: string;
  readonly hint: string;
};

export function StatStrip({ stats }: { readonly stats: readonly Stat[] }): ReactElement {
  return (
    <dl className="grid gap-4 sm:grid-cols-3">
      {stats.map((stat) => (
        <div key={stat.label} className="border-l border-slate-200 pl-4">
          <dt className="text-sm text-slate-500">{stat.label}</dt>
          <dd className="mt-1 text-2xl font-semibold text-ink tabular-nums">{stat.value}</dd>
          <dd className="mt-1 text-xs text-slate-500">{stat.hint}</dd>
        </div>
      ))}
    </dl>
  );
}
