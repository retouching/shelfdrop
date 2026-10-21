import type { ReactElement } from "react";

import { texts } from "../texts";
import type { Release } from "../types";
import { formatSize } from "../utils/format";
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
};

export function ResultsCard({
  workTitle,
  manual,
  releases,
  selected,
  onToggle,
  onToggleAll,
  onBestPerVolume,
}: Props): ReactElement {
  const allSelected = releases.length > 0 && releases.every((release) => selected.has(release.id));

  return (
    <section aria-labelledby="results-title" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <h2 id="results-title" className="font-semibold text-ink">
            {texts.results.title(workTitle)}
          </h2>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-500">{texts.results.count(releases.length)}</span>
          <button
            type="button"
            onClick={onBestPerVolume}
            className="text-sm font-medium text-accent-text hover:underline"
          >
            {texts.results.bestPerVolume}
          </button>
        </div>
      </div>
      {releases.length === 0 ? (
        <p className="px-5 py-10 text-center text-sm text-slate-500">{texts.search.empty(workTitle)}</p>
      ) : (
        <table className="w-full table-fixed text-sm">
          <caption className="sr-only">{texts.results.caption}</caption>
          <colgroup>
            <col className="w-12" />
            <col />
            <col className="w-28" />
            <col className="w-36" />
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
                      onChange={() => {
                        onToggle(release.id);
                      }}
                      aria-label={texts.results.select(release.title)}
                      className="size-4 accent-accent"
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
                  <td className="px-3 py-3 text-right text-slate-700 tabular-nums">{release.seeders}</td>
                  <td className="px-3 py-3 text-right whitespace-nowrap text-slate-500 tabular-nums">
                    {formatSize(release.sizeBytes)}
                  </td>
                  <td className="px-5 py-3">
                    <span className="flex justify-end gap-1">
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
                      <a
                        href={`/api/releases/${release.id}/torrent`}
                        download
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
