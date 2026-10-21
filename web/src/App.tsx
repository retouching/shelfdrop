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
import { WorkList } from "./components/WorkList";
import { ReleasesLoading } from "./components/ReleasesLoading";
import { mockDownloads, mockQueries, mockReleasesForWork, mockResults, mockWorks } from "./mock/data";
import { guessKind, mockFiles } from "./mock/files";
import { useLatency, wait } from "./mock/latency";
import { texts } from "./texts";
import type { Download, Kind, ShelfFile, Work } from "./types";
import { bestPerVolume, compareForDisplay, coverageLabel } from "./utils/volumes";

/** Maquette : temps simulé de la recherche Prowlarr pour un nom. */
const NAME_STEP_MS = 450;

function stats(downloads: readonly Download[]): readonly Stat[] {
  const count = (kinds: readonly string[]): string =>
    String(downloads.filter((download) => kinds.includes(download.state.kind)).length);
  return [
    { label: texts.stats.running, value: count(["downloading", "waiting", "placing"]), hint: texts.stats.runningHint },
    { label: texts.stats.placed, value: count(["placed"]), hint: texts.stats.placedHint },
    { label: texts.stats.failed, value: count(["failed"]), hint: texts.stats.failedHint },
  ];
}

export function App(): ReactElement {
  const [username, setUsername] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("auto");
  const [kind, setKind] = useState<Kind>("manga");
  const [query, setQuery] = useState(mockQueries.manga);
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [downloads, setDownloads] = useState<readonly Download[]>(mockDownloads);
  const [retrying, setRetrying] = useState<ReadonlySet<string>>(() => new Set());
  const [work, setWork] = useState<Work | null>(null);
  const [names, setNames] = useState<ReadonlySet<string>>(() => new Set());
  const [files, setFiles] = useState<readonly ShelfFile[]>(mockFiles);

  const [searchId, setSearchId] = useState(0);
  const worksLoading = useLatency(`works|${username ?? ""}|${String(searchId)}|${kind}|${query}`, 900);
  const manual = page === "manual";
  const searchedNames = manual
    ? [query]
    : work === null
      ? []
      : work.titles.map((t) => t.title).filter((title) => names.has(title));
  const releasesKey = `releases|${page}|${String(searchId)}|${kind}|${manual ? query : (work?.id ?? "")}|${searchedNames.join("|")}`;
  const releasesLoading = useLatency(releasesKey, NAME_STEP_MS * (searchedNames.length + 1));
  const downloadsLoading = useLatency(`downloads|${page}`, 700);

  const works = mockWorks[kind];
  const releases = useMemo(
    () =>
      manual
        ? [...mockResults[kind]].sort(compareForDisplay)
        : work === null
          ? []
          : mockReleasesForWork(kind, work.id)
              .filter(
                (release) =>
                  names.has(release.matchedName) || !work.titles.some((t) => t.title === release.matchedName),
              )
              .sort(compareForDisplay),
    [manual, kind, work, names],
  );
  const selectedReleases = releases.filter((release) => selected.has(release.id));
  const running = downloads.filter((download) =>
    ["downloading", "waiting", "placing"].includes(download.state.kind),
  ).length;

  // Maquette : fait avancer les envois en cours.
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

  if (username === null) {
    return <LoginPage onSignedIn={setUsername} />;
  }

  function search(nextQuery: string, nextKind: Kind): void {
    setKind(nextKind);
    setQuery(nextQuery === "" || nextKind !== kind ? mockQueries[nextKind] : nextQuery);
    setSelected(new Set());
    setNotice(null);
    setSearchId((id) => id + 1);
    chooseWork(null);
  }

  function chooseWork(next: Work | null): void {
    setWork(next);
    setNames(new Set(next?.titles.map((t) => t.title)));
    setSelected(new Set());
  }

  function toggleName(title: string): void {
    const next = new Set(names);
    if (next.has(title)) {
      next.delete(title);
    } else {
      next.add(title);
    }
    setNames(next);
    setSelected(new Set());
  }

  // Maquette : le nouvel envoi réussit, puis le téléchargement démarre.
  async function retry(download: Download): Promise<void> {
    setRetrying((current) => new Set(current).add(download.id));
    await wait(900);
    setDownloads((current) =>
      current.map((item) => (item.id === download.id ? { ...item, state: { kind: "downloading", percent: 0 } } : item)),
    );
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

  /** Maquette : une release manuelle terminée arrive dans Ranger, à associer. */
  function finishManual(id: string, name: string, kindOf: Kind): void {
    window.setTimeout(() => {
      setDownloads((current) =>
        current.map((item) => (item.id === id ? { ...item, state: { kind: "toPlace" } } : item)),
      );
      setFiles((current) => [
        {
          id: `dl-${id}`,
          name,
          path: `téléchargements/${kindOf}/${name}`,
          origin: "download",
          kind: kindOf,
          sizeBytes: 250_000_000,
          state: { kind: "unlinked" },
        },
        ...current,
      ]);
    }, 2500);
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
        toPlaceCount={files.filter((file) => file.state.kind === "unlinked" || file.state.kind === "misplaced").length}
        onNavigate={(next) => {
          setPage(next);
          setSelected(new Set());
          setNotice(null);
        }}
        onSignOut={() => {
          setUsername(null);
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
                releasesLoading ? (
                  <ReleasesLoading key={releasesKey} workTitle={query} names={searchedNames} stepMs={NAME_STEP_MS} />
                ) : (
                  <ResultsCard
                    workTitle={query}
                    manual
                    releases={releases}
                    selected={selected}
                    onToggle={toggle}
                    onToggleAll={(select) => {
                      setSelected(select ? new Set(releases.map((release) => release.id)) : new Set());
                    }}
                    onBestPerVolume={() => {
                      setSelected(new Set(bestPerVolume(releases)));
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
                      />
                      {work === null ? null : (
                        <>
                          <NameChips titles={work.titles} enabled={names} onToggle={toggleName} />
                          {releasesLoading ? (
                            <ReleasesLoading
                              key={releasesKey}
                              workTitle={work.title}
                              names={searchedNames}
                              stepMs={NAME_STEP_MS}
                            />
                          ) : (
                            <ResultsCard
                              workTitle={work.title}
                              manual={false}
                              releases={releases}
                              selected={selected}
                              onToggle={toggle}
                              onToggleAll={(select) => {
                                setSelected(select ? new Set(releases.map((release) => release.id)) : new Set());
                              }}
                              onBestPerVolume={() => {
                                setSelected(new Set(bestPerVolume(releases)));
                              }}
                            />
                          )}
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
              {downloadsLoading ? (
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
                  <StatStrip stats={stats(downloads)} />
                  <DownloadsTable
                    downloads={downloads}
                    retrying={retrying}
                    onRetry={(download) => {
                      void retry(download);
                    }}
                    onOtherRelease={(download) => {
                      setPage("auto");
                      search(download.label.replace(/\s+-\s+T.*$/u, ""), download.kind);
                    }}
                  />
                </>
              )}
            </main>
          </>
        )}
      </div>
      {dialogOpen ? (
        <DownloadDialog
          kind={kind}
          manual={manual}
          releases={selectedReleases}
          onClose={() => {
            setDialogOpen(false);
          }}
          onSubmit={(label) => {
            setDialogOpen(false);
            setSelected(new Set());
            setNotice(manual ? texts.dialog.manualNote : texts.dialog.sent(selectedReleases.length));
            const id = `new-${String(Date.now())}`;
            if (manual) {
              finishManual(id, label, kind);
            }
            setDownloads([
              {
                id,
                label,
                kind,
                state: { kind: "waiting" },
                addedAt: new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
              },
              ...downloads,
            ]);
          }}
        />
      ) : null}
    </div>
  );
}
