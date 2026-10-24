import type { ReactElement } from "react";

import { texts } from "../texts";
import type { Release } from "../types";
import { formatSize } from "../utils/format";
import { formatScore } from "../utils/score";
import { volumesLabel } from "../utils/volumes";
import { ExternalIcon, FileIcon } from "./icons";
import { stacked } from "./stacked";

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
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-4 md:px-5">
        <div className="min-w-0">
          <h2 id="results-title" className="font-semibold wrap-anywhere text-ink">
            {texts.results.title(workTitle)}
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {selectable.length === 0 ? null : (
            <label className="flex items-center gap-2 text-sm text-slate-600 md:hidden">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={() => {
                  onToggleAll(!allSelected);
                }}
                className="size-4 accent-accent"
              />
              {texts.results.selectAll}
            </label>
          )}
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
        <p className="flex flex-wrap items-center justify-between gap-x-3 border-b border-slate-100 bg-band px-4 py-2 text-xs text-slate-500 md:px-5">
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
              className="rounded-lg border border-transparent bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-strong"
            >
              {texts.waiting.add}
            </button>
          )}
        </div>
      ) : (
        <table className={`${stacked.table} w-full md:table-fixed`}>
          <caption className="sr-only">{texts.results.caption}</caption>
          <colgroup className={stacked.columns}>
            <col className="w-12" />
            <col />
            <col className="w-28" />
            <col className="w-36" />
            <col className="w-20" />
            <col className="w-20" />
            <col className="w-24" />
            <col className="w-24" />
          </colgroup>
          <thead className={stacked.head}>
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
          <tbody className={`${stacked.body} divide-slate-100`}>
            {releases.map((release) => {
              const isSelected = selected.has(release.id);
              return (
                <tr
                  key={release.id}
                  className={`${stacked.row} ${isSelected ? "bg-accent-soft/60" : "hover:bg-slate-50"}`}
                >
                  <td className={`${stacked.cell} self-start md:px-5 md:py-3`}>
                    {/* Sur un petit écran, la case se coche sur 44 px sans prendre plus de place. */}
                    <label className="-m-3 flex p-3 md:m-0 md:inline md:p-0">
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
                    </label>
                  </td>
                  <td className={`${stacked.cell} grow basis-[calc(100%-2rem)] md:px-3 md:py-2.5`}>
                    <span className="block wrap-anywhere text-ink md:truncate" title={release.title}>
                      {release.title}
                    </span>
                    {manual || release.matchedName === workTitle ? null : (
                      <span className="block text-xs wrap-anywhere text-slate-500 md:truncate">
                        {texts.results.matched(release.matchedName)}
                      </span>
                    )}
                  </td>
                  <td className={`${stacked.cell} text-xs whitespace-nowrap text-slate-700 md:px-3 md:py-3 md:text-sm`}>
                    {volumesLabel(release.volumes)}
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-3 md:whitespace-nowrap`}>
                    <span
                      className={`rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600 ring-1 ring-slate-200 ring-inset`}
                    >
                      {release.indexer}
                    </span>
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-3 md:text-right`}>
                    <span className={`${stacked.label} text-xs`}>{texts.filters.score} </span>
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
                  <td
                    className={`${stacked.cell} text-xs text-slate-700 tabular-nums md:px-3 md:py-3 md:text-right md:text-sm`}
                  >
                    <span className={stacked.label}>{texts.results.seeders} </span>
                    {release.seeders}
                  </td>
                  <td
                    className={`${stacked.cell} text-xs whitespace-nowrap text-slate-500 tabular-nums md:px-3 md:py-3 md:text-right md:text-sm`}
                  >
                    {formatSize(release.sizeBytes)}
                  </td>
                  <td className={`${stacked.cell} ml-auto md:ml-0 md:px-5 md:py-3`}>
                    <span className="flex justify-end gap-1">
                      {release.infoUrl === "" ? null : (
                        <a
                          href={release.infoUrl}
                          target="_blank"
                          rel="noreferrer noopener"
                          title={texts.results.trackerPage(release.indexer)}
                          aria-label={texts.results.trackerPage(release.indexer)}
                          className="flex size-11 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-ink md:size-auto md:p-1.5"
                        >
                          <ExternalIcon />
                        </a>
                      )}
                      <a
                        href={`/api/v1/releases/${encodeURIComponent(release.id)}/torrent`}
                        download={`${release.title}.torrent`}
                        title={texts.results.torrentFile}
                        aria-label={texts.results.torrentFile}
                        className="flex size-11 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-ink md:size-auto md:p-1.5"
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
