import type { ReactElement } from "react";

import { texts } from "../texts";
import type { Release } from "../types";
import { formatSize } from "../utils/format";
import { formatScore } from "../utils/score";
import { volumesLabel } from "../utils/volumes";
import { ExternalIcon, FileIcon } from "./icons";

type Props = {
  readonly workTitle: string;
  readonly manual: boolean;
  readonly releases: readonly Release[];
  readonly selected: ReadonlySet<string>;
  readonly onToggle: (id: string) => void;
  readonly onToggleAll: (select: boolean) => void;
  readonly onBestPerVolume: () => void;
  readonly rejectedCount: number;
  readonly showRejected: boolean;
  readonly onShowRejected: (show: boolean) => void;
  readonly minimum: number;
  /** Quand rien n'est trouvé : garder la recherche en attente. */
  readonly onWait?: () => void;
  /** Âge des résultats en minutes (réponses de Prowlarr gardées en cache), et de quoi relancer. */
  readonly cachedMinutes: number | null;
  readonly onRefresh: () => void;
};

export function ResultsCard({
  workTitle,
  manual,
  releases,
  selected,
  onToggle,
  onToggleAll,
  onBestPerVolume,
  rejectedCount,
  showRejected,
  onShowRejected,
  minimum,
  onWait,
  cachedMinutes,
  onRefresh,
}: Props): ReactElement {
  // La page Automatique n'envoie que les releases qu'un téléchargement automatique peut prendre.
  const selectable = manual ? releases : releases.filter((release) => release.automatic);
  const allSelected = selectable.length > 0 && selectable.every((release) => selected.has(release.id));

  return (
    <section aria-labelledby="results-title" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <h2 id="results-title" className="font-semibold text-ink">
            {texts.results.title(workTitle)}
          </h2>
        </div>
        <div className="flex items-center gap-4">
          {cachedMinutes === null ? null : (
            <span className="text-xs text-slate-500">
              {texts.results.cachedAgo(cachedMinutes)}
              {" · "}
              <button type="button" onClick={onRefresh} className="font-medium text-accent-text hover:underline">
                {texts.results.refresh}
              </button>
            </span>
          )}
          <span className="text-sm text-slate-500">{texts.results.count(releases.length)}</span>
          {onWait === undefined || releases.length === 0 ? null : (
            <button type="button" onClick={onWait} className="text-sm font-medium text-accent-text hover:underline">
              {texts.waiting.add}
            </button>
          )}
          <button
            type="button"
            onClick={onBestPerVolume}
            className="text-sm font-medium text-accent-text hover:underline"
          >
            {texts.results.bestPerVolume}
          </button>
        </div>
      </div>
      {rejectedCount === 0 ? null : (
        <p className="flex items-center justify-between gap-3 border-b border-slate-100 bg-band px-5 py-2 text-xs text-slate-500">
          {texts.filters.rejected(rejectedCount, minimum)}
          <button
            type="button"
            onClick={() => {
              onShowRejected(!showRejected);
            }}
            className="font-medium text-accent-text hover:underline"
          >
            {showRejected ? texts.filters.hideRejected : texts.filters.showRejected}
          </button>
        </p>
      )}
      {releases.length === 0 ? (
        <div className="space-y-3 px-5 py-10 text-center text-sm text-slate-500">
          <p>{texts.search.empty(workTitle)}</p>
          {onWait === undefined ? null : (
            <button
              type="button"
              onClick={onWait}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong"
            >
              {texts.waiting.add}
            </button>
          )}
        </div>
      ) : (
        <table className="w-full table-fixed text-sm">
          <caption className="sr-only">{texts.results.caption}</caption>
          <colgroup>
            <col className="w-12" />
            <col />
            <col className="w-28" />
            <col className="w-36" />
            <col className="w-20" />
            <col className="w-20" />
            <col className="w-24" />
            <col className="w-24" />
          </colgroup>
          <thead className="bg-band text-left text-ink">
            <tr>
              <th scope="col" className="px-5 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() => {
                    onToggleAll(!allSelected);
                  }}
                  aria-label={texts.results.selectAll}
                  className="size-4 accent-accent"
                />
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.results.release}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.results.volumes}
              </th>
              <th scope="col" className="px-3 py-3 font-semibold">
                {texts.results.indexer}
              </th>
              <th scope="col" className="px-3 py-3 text-right font-semibold">
                {texts.filters.score}
              </th>
              <th scope="col" className="px-3 py-3 text-right font-semibold">
                {texts.results.seeders}
              </th>
              <th scope="col" className="px-3 py-3 text-right font-semibold">
                {texts.results.size}
              </th>
              <th scope="col" className="px-5 py-3 text-right font-semibold">
                {texts.results.links}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {releases.map((release) => {
              const isSelected = selected.has(release.id);
              return (
                <tr key={release.id} className={isSelected ? "bg-accent-soft/60" : "hover:bg-slate-50"}>
                  <td className="px-5 py-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      disabled={!manual && !release.automatic}
                      onChange={() => {
                        onToggle(release.id);
                      }}
                      aria-label={texts.results.select(release.title)}
                      className="size-4 accent-accent disabled:cursor-not-allowed disabled:opacity-40"
                    />
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="block truncate text-ink" title={release.title}>
                      {release.title}
                    </span>
                    {manual || release.matchedName === workTitle ? null : (
                      <span className="block truncate text-xs text-slate-500">
                        {texts.results.matched(release.matchedName)}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-3 whitespace-nowrap text-slate-700">{volumesLabel(release.volumes)}</td>
                  <td className="px-3 py-3 whitespace-nowrap">
                    <span
                      className={`rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600 ring-1 ring-slate-200 ring-inset`}
                    >
                      {release.indexer}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span
                      title={
                        release.scoreRules.length === 0
                          ? texts.filters.noRule
                          : release.scoreRules.map((rule) => `${rule.name} ${formatScore(rule.score)}`).join("\n")
                      }
                      className={`rounded-md px-1.5 py-0.5 text-xs font-medium tabular-nums ${
                        release.score < minimum
                          ? "bg-rose-50 text-rose-700"
                          : release.score > 0
                            ? "bg-emerald-50 text-emerald-700"
                            : release.score < 0
                              ? "bg-amber-50 text-amber-800"
                              : "text-slate-500"
                      }`}
                    >
                      {formatScore(release.score)}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right text-slate-700 tabular-nums">{release.seeders}</td>
                  <td className="px-3 py-3 text-right whitespace-nowrap text-slate-500 tabular-nums">
                    {formatSize(release.sizeBytes)}
                  </td>
                  <td className="px-5 py-3">
                    <span className="flex justify-end gap-1">
                      {release.infoUrl === "" ? null : (
                        <a
                          href={release.infoUrl}
                          target="_blank"
                          rel="noreferrer noopener"
                          title={texts.results.trackerPage(release.indexer)}
                          aria-label={texts.results.trackerPage(release.indexer)}
                          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-ink"
                        >
                          <ExternalIcon />
                        </a>
                      )}
                      <a
                        href={`/api/v1/releases/${encodeURIComponent(release.id)}/torrent`}
                        download={`${release.title}.torrent`}
                        title={texts.results.torrentFile}
                        aria-label={texts.results.torrentFile}
                        className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-ink"
                      >
                        <FileIcon />
                      </a>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
