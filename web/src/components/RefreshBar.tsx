import type { ReactElement, ReactNode } from "react";

import { texts } from "../texts";
import { formatClock } from "../utils/format";
import { Spinner } from "./Skeletons";

export const liveIntervals: readonly number[] = [2, 5, 10, 30];

type Props = {
  readonly updatedAt: Date;
  readonly refreshing: boolean;
  readonly onRefresh: () => void;
  /** Le temps réel, quand la page le propose. */
  readonly live?: {
    readonly on: boolean;
    readonly every: number;
    readonly onToggle: (on: boolean) => void;
    readonly onEvery: (seconds: number) => void;
  };
  readonly children?: ReactNode;
};

export function RefreshBar({ updatedAt, refreshing, onRefresh, live, children }: Props): ReactElement {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        disabled={refreshing}
        onClick={onRefresh}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-surface px-3 py-1.5 text-sm hover:bg-slate-50 disabled:cursor-wait disabled:opacity-80"
      >
        {refreshing ? (
          <Spinner className="size-3.5" />
        ) : (
          <svg
            viewBox="0 0 24 24"
            className="size-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            aria-hidden="true"
          >
            <path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        {refreshing ? texts.refresh.refreshing : texts.refresh.refresh}
      </button>
      {live === undefined ? null : (
        <>
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm md:min-h-0">
            <input
              type="checkbox"
              role="switch"
              checked={live.on}
              onChange={(event) => {
                live.onToggle(event.target.checked);
              }}
              className="peer sr-only"
            />
            <span className="relative h-5 w-9 rounded-full bg-slate-200 transition peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-ring after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-4" />
            {texts.refresh.live}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="sr-only">{texts.refresh.every}</span>
            <select
              value={live.every}
              disabled={!live.on}
              onChange={(event) => {
                live.onEvery(Number(event.target.value));
              }}
              className="rounded-lg border border-slate-200 bg-surface px-2 py-1 text-sm disabled:opacity-50"
            >
              {liveIntervals.map((seconds) => (
                <option key={seconds} value={seconds}>
                  {texts.refresh.seconds(seconds)}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      {children}
      <span className="ml-auto flex items-center gap-2 text-xs text-slate-500 tabular-nums" aria-live="polite">
        {live?.on === true ? (
          <>
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
            </span>
            {`${texts.refresh.liveEvery(live.every)} · `}
          </>
        ) : null}
        {texts.refresh.updatedAt(formatClock(updatedAt))}
      </span>
    </div>
  );
}
