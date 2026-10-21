import type { ReactElement } from "react";

import { texts } from "../texts";
import type { Download, DownloadState } from "../types";
import { Spinner } from "./Skeletons";

function stateText(state: DownloadState): string {
  switch (state.kind) {
    case "downloading":
      return texts.downloads.downloading(state.percent);
    case "waiting":
      return texts.downloads.waiting;
    case "placing":
      return texts.downloads.placing;
    case "placed":
      return texts.downloads.placed(state.library);
    case "toPlace":
      return texts.downloads.toPlace;
    case "failed":
      return state.reason === "duplicate" ? texts.downloads.duplicate : texts.downloads.notReceived;
  }
}

function stateTone(state: DownloadState): string {
  switch (state.kind) {
    case "waiting":
      return "bg-slate-100 text-slate-600 ring-slate-200";
    case "downloading":
    case "placing":
      return "bg-violet-50 text-violet-700 ring-violet-200";
    case "placed":
      return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    case "toPlace":
      return "bg-amber-50 text-amber-800 ring-amber-200";
    case "failed":
      return "bg-rose-50 text-rose-700 ring-rose-200";
  }
}

type Props = {
  readonly downloads: readonly Download[];
  readonly retrying: ReadonlySet<string>;
  readonly onRetry: (download: Download) => void;
  readonly onOtherRelease: (download: Download) => void;
  readonly limit?: number;
  readonly onShowAll?: () => void;
};

export function DownloadsTable({
  downloads,
  retrying,
  onRetry,
  onOtherRelease,
  limit,
  onShowAll,
}: Props): ReactElement {
  const shown = limit === undefined ? downloads : downloads.slice(0, limit);

  return (
    <section
      aria-labelledby="downloads-title"
      className="overflow-hidden rounded-xl border border-slate-200 bg-surface"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <h2 id="downloads-title" className="font-semibold text-ink">
          {texts.downloads.caption}
        </h2>
        {onShowAll === undefined ? null : (
          <button type="button" onClick={onShowAll} className="text-sm font-medium text-accent-text hover:underline">
            {texts.nav.downloads}
          </button>
        )}
      </div>
      {shown.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">{texts.downloads.empty}</p>
      ) : (
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col className="w-24" />
            <col />
            <col className="w-32" />
            <col className="w-72" />
            <col className="w-56" />
          </colgroup>
          <thead className="bg-band text-left text-ink">
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">
                {texts.downloads.added}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.downloads.item}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.downloads.kind}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.downloads.state}
              </th>
              <th scope="col" className="px-5 py-3">
                <span className="sr-only">{texts.downloads.actions}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {shown.map((download) => (
              <tr key={download.id}>
                <td className="px-5 py-3 text-slate-500 tabular-nums">{download.addedAt}</td>
                <td className="truncate px-3 py-3 font-medium text-ink" title={download.label}>
                  {download.label}
                </td>
                <td className="px-3 py-3 text-slate-600">{texts.kinds[download.kind]}</td>
                <td className="px-3 py-3">
                  <span
                    className={`inline-block rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${stateTone(download.state)}`}
                  >
                    {stateText(download.state)}
                  </span>
                  {download.state.kind === "downloading" ? (
                    <progress
                      max={100}
                      value={download.state.percent}
                      aria-hidden="true"
                      className="mt-1.5 block h-1 w-full overflow-hidden rounded [&::-moz-progress-bar]:bg-violet-500 [&::-webkit-progress-bar]:bg-slate-100 [&::-webkit-progress-value]:bg-violet-500"
                    />
                  ) : null}
                </td>
                <td className="px-5 py-3">
                  {download.state.kind === "failed" && download.state.reason === "not_received" ? (
                    <span className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          onOtherRelease(download);
                        }}
                        aria-label={texts.downloads.otherFor(download.label)}
                        className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                      >
                        {texts.downloads.otherRelease}
                      </button>
                      <button
                        type="button"
                        disabled={retrying.has(download.id)}
                        onClick={() => {
                          onRetry(download);
                        }}
                        aria-label={texts.downloads.retryFor(download.label)}
                        className="hover:bg-accent-strong-strong flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:cursor-wait disabled:opacity-80"
                      >
                        {retrying.has(download.id) ? <Spinner className="size-3.5" /> : null}
                        {retrying.has(download.id) ? texts.downloads.retrying : texts.downloads.retry}
                      </button>
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
