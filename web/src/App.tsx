import { useEffect, useMemo, useState, type ReactElement } from "react";

import { DownloadDialog } from "./components/DownloadDialog";
import { DownloadsTable } from "./components/DownloadsTable";
import { NameChips } from "./components/NameChips";
import { LoginPage } from "./components/LoginPage";
import { PageHeader } from "./components/PageHeader";
import { PlacePage } from "./components/PlacePage";
import { SettingsPage } from "./components/settings/SettingsPage";
import { ResultsCard } from "./components/ResultsCard";
import { SearchForm } from "./components/SearchForm";
import { UploadZone } from "./components/UploadZone";
import { SelectionBar } from "./components/SelectionBar";
import { Sidebar, type Page } from "./components/Sidebar";
import { StatStrip, type Stat } from "./components/StatStrip";
import { Bone, LoadingLabel, ResultsSkeleton, WorkListSkeleton } from "./components/Skeletons";
import { LibraryPage } from "./components/library/LibraryPage";
import { MergeDialog, unionTitles } from "./components/MergeDialog";
import { WorkList } from "./components/WorkList";
import { ReleasesLoading } from "./components/ReleasesLoading";
import { RefreshBar } from "./components/RefreshBar";
import { useWaiting } from "./mock/waiting";
import { WaitingPage } from "./components/WaitingPage";
import { WaitDialog } from "./components/WaitDialog";
import { whenSignedOut } from "./api/http";
import type { SearchProgress } from "./api/searches";
import { readSession, signOut } from "./api/session";
import { readHealth } from "./api/settings";
import { loadSettings, useSettings, valueOf } from "./state/settings";
import { useReleases, useWorks, type ReleasesQuery } from "./api/useSearches";
import { retryDownload } from "./api/downloads";
import { useDownloads } from "./api/useDownloads";
import { guessKind, mockFiles } from "./mock/files";
import { texts } from "./texts";
import type { Download, Kind, ShelfFile, Work } from "./types";
import { bestPerVolume, coverageLabel, volumeNumbers } from "./utils/volumes";

/** Les œuvres d'une liste, chaque paire fusionnée remplacée par sa fusion, à la place de la première. */
function withMerges(list: readonly Work[], merges: readonly Work[]): readonly Work[] {
  const absorbed = new Map<string, Work>();
  for (const merged of merges) {
    for (const part of merged.mergedFrom ?? []) {
      absorbed.set(part.id, merged);
    }
  }
  const shown = new Set<string>();
  return list.flatMap((entry) => {
    const merged = absorbed.get(entry.id);
    if (merged === undefined) {
      return [entry];
    }
    if (shown.has(merged.id)) {
      return [];
    }
    shown.add(merged.id);
    return [merged];
  });
}

/** Noms envoyés à Prowlarr pour une œuvre avant la lecture des paramètres. */
const DEFAULT_MAX_NAMES = 6;
/** Les tests des services tournent toutes les 5 minutes : la page relit leur résultat au même rythme. */
const HEALTH_EVERY_MS = 5 * 60 * 1000;

function stats(downloads: readonly Download[]): readonly Stat[] {
  const count = (kinds: readonly string[]): string =>
    String(downloads.filter((download) => kinds.includes(download.state.kind)).length);
  return [
    { label: texts.stats.running, value: count(["downloading", "waiting", "placing"]), hint: texts.stats.runningHint },
    { label: texts.stats.placed, value: count(["placed"]), hint: texts.stats.placedHint },
    { label: texts.stats.failed, value: count(["failed"]), hint: texts.stats.failedHint },
  ];
}

export function App(): ReactElement | null {
  const [username, setUsername] = useState<string | null>(null);
  // La session est lue au chargement : rien n'est affiché avant sa réponse.
  const [sessionRead, setSessionRead] = useState(false);
  const [servicesDown, setServicesDown] = useState(false);
  const settings = useSettings();
  const maxNamesSetting = valueOf(settings, "search.max_names");
  const maxNames = typeof maxNamesSetting === "number" ? maxNamesSetting : DEFAULT_MAX_NAMES;
  const [page, setPage] = useState<Page>("auto");
  const [kind, setKind] = useState<Kind>("manga");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [liveEvery, setLiveEvery] = useState(5);
  const [retrying, setRetrying] = useState<ReadonlySet<string>>(() => new Set());
  const [work, setWork] = useState<Work | null>(null);
  const [merges, setMerges] = useState<readonly Work[]>([]);
  const [merging, setMerging] = useState<Work | null>(null);
  const [names, setNames] = useState<ReadonlySet<string>>(() => new Set());
  const [files, setFiles] = useState<readonly ShelfFile[]>(mockFiles);

  const [searchId, setSearchId] = useState(0);
  const [refreshRound, setRefreshRound] = useState(0);
  const manual = page === "manual";
  const worksState = useWorks(query, kind, searchId, username !== null && page === "auto");
  const worksLoading = worksState.status === "loading";
  const searchedNames = manual
    ? query === ""
      ? []
      : [query]
    : work === null
      ? []
      : work.titles.map((t) => t.title).filter((title) => names.has(title));
  const releasesQuery: ReleasesQuery | null =
    (manual || work !== null) && searchedNames.length > 0 && (page === "auto" || page === "manual")
      ? {
          mode: manual ? "manual" : "work",
          kind,
          title: manual ? query : (work?.title ?? query),
          names: searchedNames,
          author: manual ? "" : (work?.author ?? ""),
          series: manual ? "" : (work?.title ?? ""),
        }
      : null;
  const releasesState = useReleases(releasesQuery, refreshRound);
  const releasesLoading = releasesState.status === "running";
  const downloadsList = useDownloads(username !== null, page === "downloads", live, liveEvery);
  const downloads = downloadsList.downloads ?? [];

  const works = withMerges(worksState.status === "done" ? worksState.works : [], merges);
  const [showRejected, setShowRejected] = useState(false);
  const waitingList = useWaiting();
  const [waitOpen, setWaitOpen] = useState(false);
  const [waitAdding, setWaitAdding] = useState(false);
  // Releases dans l'ordre du serveur ; celles écartées pour un mot manquant ne sont pas montrées.
  const found = useMemo(
    () =>
      releasesState.status === "done"
        ? releasesState.result.releases.filter((release) => release.rejected !== "relevance")
        : [],
    [releasesState],
  );
  const minimum = releasesState.status === "done" ? releasesState.result.minimum : 0;
  const cachedMinutes = releasesState.status === "done" ? releasesState.ageMinutes : null;
  const progress = releasesState.status === "running" ? releasesState.progress : null;
  const rejected = found.filter((release) => release.rejected === "score");
  const releases = showRejected ? found : found.filter((release) => release.rejected !== "score");
  // La page Automatique n'envoie que les releases qu'un téléchargement automatique peut prendre.
  const selectable = manual ? releases : releases.filter((release) => release.automatic);
  const selectedReleases = selectable.filter((release) => selected.has(release.id));
  const searchIdOfReleases = releasesState.status === "done" ? releasesState.result.progress.id : null;
  const running = downloads.filter((download) =>
    ["downloading", "waiting", "placing"].includes(download.state.kind),
  ).length;

  // Maquette : fait avancer les envois de fichiers en cours.
  const uploading = files.some((file) => file.state.kind === "uploading");
  useEffect(() => {
    if (!uploading) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setFiles((current) =>
        current.map((file) => {
          if (file.state.kind !== "uploading") {
            return file;
          }
          const percent = Math.min(100, file.state.percent + 17);
          return { ...file, state: percent >= 100 ? { kind: "unlinked" } : { kind: "uploading", percent } };
        }),
      );
    }, 400);
    return () => {
      window.clearInterval(timer);
    };
  }, [uploading]);

  useEffect(() => {
    whenSignedOut(() => {
      setUsername(null);
    });
    readSession().then(
      (name) => {
        setUsername(name);
        setSessionRead(true);
      },
      () => {
        setSessionRead(true);
      },
    );
    return () => {
      whenSignedOut(null);
    };
  }, []);

  useEffect(() => {
    if (username === null) {
      return undefined;
    }
    loadSettings().catch(() => undefined);
    function check(): void {
      readHealth().then(
        (services) => {
          setServicesDown(services.some((service) => !service.ok));
        },
        () => undefined,
      );
    }
    check();
    const timer = window.setInterval(check, HEALTH_EVERY_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [username]);

  if (!sessionRead) {
    return null;
  }
  if (username === null) {
    return <LoginPage onSignedIn={setUsername} />;
  }

  function search(nextQuery: string, nextKind: Kind): void {
    setKind(nextKind);
    setQuery(nextQuery);
    setRefreshRound(0);
    setSelected(new Set());
    setNotice(null);
    setSearchId((id) => id + 1);
    chooseWork(null);
  }

  function merge(base: Work, others: readonly Work[], shelfName: string): void {
    const parts = [...(base.mergedFrom ?? [base]), ...others.flatMap((other) => other.mergedFrom ?? [other])];
    const first = parts[0] ?? base;
    const merged: Work = {
      id: parts.map((part) => part.id).join("+"),
      source: first.source,
      title: shelfName,
      author: first.author,
      year: parts.reduce<number | null>(
        (min, part) => (part.year === null ? min : Math.min(min ?? part.year, part.year)),
        null,
      ),
      volumeCount: parts.find((part) => part.volumeCount !== null)?.volumeCount ?? null,
      // Le nom gardé en tête, comme le titre de la carte.
      titles: [...unionTitles(parts)].sort((x, y) => Number(y.title === shelfName) - Number(x.title === shelfName)),
      mergedFrom: parts,
    };
    const replaced = new Set([base.id, ...others.map((other) => other.id)]);
    setMerges((current) => [...current.filter((entry) => !replaced.has(entry.id)), merged]);
    chooseWork(null);
  }

  function split(merged: Work): void {
    setMerges((current) => current.filter((entry) => entry.id !== merged.id));
    chooseWork(null);
  }

  function chooseWork(next: Work | null): void {
    setWork(next);
    setNames(
      new Set(
        next?.titles
          .filter((t) => t.checked !== false)
          .map((t) => t.title)
          .slice(0, maxNames),
      ),
    );
    setRefreshRound(0);
    setSelected(new Set());
  }

  function toggleName(title: string): void {
    const next = new Set(names);
    if (next.has(title)) {
      next.delete(title);
    } else if (next.size < maxNames) {
      next.add(title);
    }
    setRefreshRound(0);
    setNames(next);
    setSelected(new Set());
  }

  /** Le même torrent renvoyé à qBittorrent ; un refus laisse la ligne telle quelle. */
  async function retry(download: Download): Promise<void> {
    setRetrying((current) => new Set(current).add(download.id));
    try {
      downloadsList.merge([await retryDownload(download.id)]);
    } catch {
      downloadsList.refresh();
    }
    setRetrying((current) => {
      const next = new Set(current);
      next.delete(download.id);
      return next;
    });
  }

  function upload(list: readonly File[]): void {
    const added: ShelfFile[] = list.map((file, index) => ({
      id: `up-${String(Date.now())}-${String(index)}`,
      name: file.name,
      path: `envois/${file.name}`,
      origin: "upload",
      kind: guessKind(file.name),
      sizeBytes: file.size,
      state: { kind: "uploading", percent: 0 },
    }));
    setFiles((current) => [...added, ...current]);
    setNotice(texts.place.sentToPlace(added.length));
  }

  function toggle(id: string): void {
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelected(next);
  }

  return (
    <div className="flex min-h-screen bg-page text-ink">
      <Sidebar
        page={page}
        username={username}
        runningCount={running}
        settingsAlert={servicesDown}
        waitingFound={waitingList.filter((entry) => entry.state.kind === "found").length}
        toPlaceCount={files.filter((file) => file.state.kind === "unlinked" || file.state.kind === "misplaced").length}
        onNavigate={(next) => {
          setPage(next);
          setSelected(new Set());
          setNotice(null);
        }}
        onSignOut={() => {
          signOut().then(
            () => {
              setUsername(null);
            },
            () => {
              setUsername(null);
            },
          );
        }}
      />
      <div className="min-w-0 flex-1">
        {page === "auto" || page === "manual" ? (
          <>
            <PageHeader
              section={texts.nav.search}
              title={manual ? texts.pages.manual : texts.pages.auto}
              lead={manual ? texts.pages.manualLead : texts.pages.autoLead}
            />
            <main className="space-y-6 px-10 pt-8 pb-24">
              <SearchForm
                key={`${kind}-${query}`}
                kind={kind}
                initialQuery={query}
                busy={manual ? releasesLoading : worksLoading}
                onSearch={search}
              />
              {manual ? <UploadZone onFiles={upload} /> : null}
              {notice === null ? null : (
                <p
                  role="status"
                  className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800"
                >
                  {notice}
                </p>
              )}
              {manual ? (
                query === "" ? null : (
                  <Releases
                    state={releasesState}
                    workTitle={query}
                    progressNames={progress}
                    manual
                    releases={releases}
                    rejectedCount={rejected.length}
                    showRejected={showRejected}
                    onShowRejected={setShowRejected}
                    minimum={minimum}
                    cachedMinutes={cachedMinutes}
                    onRefresh={() => {
                      setRefreshRound((n) => n + 1);
                    }}
                    selected={selected}
                    onToggle={toggle}
                    onToggleAll={(select) => {
                      setSelected(select ? new Set(selectable.map((release) => release.id)) : new Set());
                    }}
                    onBestPerVolume={() => {
                      setSelected(new Set(bestPerVolume(selectable, selected)));
                    }}
                  />
                )
              ) : (
                <>
                  {worksLoading ? (
                    <section aria-busy="true" aria-labelledby="works-loading" className="space-y-3">
                      <h2 id="works-loading" className="font-semibold text-ink">
                        {texts.works.caption(query)}
                      </h2>
                      <LoadingLabel label={texts.loading.works} />
                      <WorkListSkeleton />
                    </section>
                  ) : (
                    <>
                      <WorkList
                        query={query}
                        works={works}
                        selectedId={work?.id ?? null}
                        loading={releasesLoading}
                        onChoose={chooseWork}
                        onMerge={setMerging}
                        onSplit={split}
                      />
                      {work === null ? null : (
                        <>
                          <NameChips titles={work.titles} enabled={names} onToggle={toggleName} />
                          <Releases
                            state={releasesState}
                            workTitle={work.title}
                            progressNames={progress}
                            manual={false}
                            releases={releases}
                            rejectedCount={rejected.length}
                            showRejected={showRejected}
                            onShowRejected={setShowRejected}
                            minimum={minimum}
                            cachedMinutes={cachedMinutes}
                            onRefresh={() => {
                              setRefreshRound((n) => n + 1);
                            }}
                            onWait={() => {
                              setWaitOpen(true);
                            }}
                            selected={selected}
                            onToggle={toggle}
                            onToggleAll={(select) => {
                              setSelected(select ? new Set(selectable.map((release) => release.id)) : new Set());
                            }}
                            onBestPerVolume={() => {
                              setSelected(new Set(bestPerVolume(selectable, selected)));
                            }}
                          />
                        </>
                      )}
                    </>
                  )}
                </>
              )}
              <SelectionBar
                count={selectedReleases.length}
                coverage={coverageLabel(selectedReleases)}
                onClear={() => {
                  setSelected(new Set());
                }}
                onDownload={() => {
                  setDialogOpen(true);
                }}
              />
            </main>
          </>
        ) : page === "settings" ? (
          <>
            <PageHeader section={texts.nav.admin} title={texts.pages.settings} lead={texts.pages.settingsLead} />
            <main className="px-10 pt-8 pb-24">
              <SettingsPage />
            </main>
          </>
        ) : page === "waiting" ? (
          <>
            <PageHeader section={texts.nav.search} title={texts.pages.waiting} lead={texts.pages.waitingLead} />
            <main className="px-10 pt-8 pb-24">
              <WaitingPage
                onAdd={() => {
                  setWaitAdding(true);
                }}
                onOpen={(entry) => {
                  setPage("auto");
                  search(entry.title, entry.kind);
                }}
              />
            </main>
          </>
        ) : page === "metadata" ? (
          <>
            <PageHeader section={texts.nav.library} title={texts.pages.metadata} lead={texts.pages.metadataLead} />
            <main className="px-10 pt-8 pb-24">
              <LibraryPage />
            </main>
          </>
        ) : page === "place" ? (
          <>
            <PageHeader section={texts.nav.library} title={texts.pages.place} lead={texts.pages.placeLead} />
            <main className="px-10 pt-8 pb-24">
              <PlacePage
                files={files}
                onPlaced={(id, destination) => {
                  setFiles((current) =>
                    current.map((file) =>
                      file.id === id ? { ...file, state: { kind: "placed", destination } } : file,
                    ),
                  );
                }}
              />
            </main>
          </>
        ) : (
          <>
            <PageHeader section={texts.nav.library} title={texts.pages.downloads} lead={texts.pages.downloadsLead} />
            <main className="space-y-8 px-10 py-8">
              {downloadsList.downloads === null ? (
                <section aria-busy="true" aria-label={texts.loading.downloads} className="space-y-8">
                  <LoadingLabel label={texts.loading.downloads} />
                  <div aria-hidden="true" className="grid gap-4 sm:grid-cols-3">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="space-y-2 border-l border-slate-200 pl-4">
                        <Bone className="h-3.5 w-24" />
                        <Bone className="h-7 w-10" />
                        <Bone className="h-3 w-32" />
                      </div>
                    ))}
                  </div>
                  <ResultsSkeleton rows={4} />
                </section>
              ) : (
                <>
                  <RefreshBar
                    updatedAt={downloadsList.updatedAt}
                    refreshing={downloadsList.refreshing}
                    onRefresh={downloadsList.refresh}
                    live={{ on: live, every: liveEvery, onToggle: setLive, onEvery: setLiveEvery }}
                  />
                  <StatStrip stats={stats(downloads)} />
                  <DownloadsTable
                    downloads={downloads}
                    retrying={retrying}
                    onRetry={(download) => {
                      void retry(download);
                    }}
                    onOtherRelease={(download) => {
                      setPage(download.manual ? "manual" : "auto");
                      search(download.workTitle, download.kind);
                    }}
                  />
                </>
              )}
            </main>
          </>
        )}
      </div>
      {dialogOpen && searchIdOfReleases !== null ? (
        <DownloadDialog
          kind={kind}
          searchId={searchIdOfReleases}
          workId={manual ? null : (work?.id ?? null)}
          manual={manual}
          releases={selectedReleases}
          onClose={() => {
            setDialogOpen(false);
          }}
          onSent={(sent) => {
            setDialogOpen(false);
            setSelected(new Set());
            setNotice(manual ? texts.dialog.manualNote : texts.dialog.sent(sent.length));
            downloadsList.merge(sent);
          }}
        />
      ) : null}
      {waitOpen && work !== null ? (
        <WaitDialog
          kind={kind}
          work={work}
          foundVolumes={releases.flatMap((release) => volumeNumbers(release.volumes))}
          onClose={() => {
            setWaitOpen(false);
          }}
          onAdded={(count) => {
            setNotice(texts.waitDialog.added(count));
          }}
        />
      ) : null}
      {waitAdding ? (
        <WaitDialog
          kind={kind}
          work={null}
          foundVolumes={[]}
          onClose={() => {
            setWaitAdding(false);
          }}
          onAdded={() => undefined}
        />
      ) : null}
      {merging === null ? null : (
        <MergeDialog
          kind={kind}
          work={merging}
          onClose={() => {
            setMerging(null);
          }}
          onMerged={(others, shelfName) => {
            merge(merging, others, shelfName);
          }}
        />
      )}
    </div>
  );
}

type ReleasesProps = Omit<Parameters<typeof ResultsCard>[0], "workTitle"> & {
  readonly state: ReturnType<typeof useReleases>;
  readonly workTitle: string;
  readonly progressNames: SearchProgress | null;
};

/** La recherche de releases : avancement nom par nom, Prowlarr injoignable, ou les résultats. */
function Releases({ state, workTitle, progressNames, ...card }: ReleasesProps): ReactElement | null {
  if (state.status === "idle") {
    return null;
  }
  if (state.status === "unavailable") {
    return (
      <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-800">
        {texts.search.unavailable}
      </p>
    );
  }
  if (state.status === "running") {
    return (
      <ReleasesLoading
        workTitle={workTitle}
        names={progressNames?.names ?? []}
        queuedAhead={progressNames?.queued_ahead ?? 0}
        shared={(progressNames?.followers ?? 1) > 1}
      />
    );
  }
  return <ResultsCard workTitle={workTitle} {...card} />;
}
