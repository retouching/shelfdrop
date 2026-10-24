import { Outlet, useMatches, useNavigate, useSearch } from "@tanstack/react-router";
import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type ReactElement } from "react";

import { DownloadsTable } from "./components/DownloadsTable";
import { NameChips } from "./components/NameChips";
import { LoginPage } from "./components/LoginPage";
import { PageHeader } from "./components/PageHeader";
import { ResultsCard } from "./components/ResultsCard";
import { SearchForm } from "./components/SearchForm";
import { UploadList } from "./components/UploadList";
import { UploadZone } from "./components/UploadZone";
import { SelectionBar } from "./components/SelectionBar";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { StatStrip, type Stat } from "./components/StatStrip";
import { Bone, LoadingLabel, ResultsSkeleton, WorkListSkeleton } from "./components/Skeletons";
import { WorkList } from "./components/WorkList";
import { ReleasesLoading } from "./components/ReleasesLoading";
import { RefreshBar } from "./components/RefreshBar";
import { useWaiting } from "./api/waiting";
import { whenSignedOut } from "./api/http";
import type { SearchProgress } from "./api/searches";
import { readSession, signOut, type SessionAccount } from "./api/session";
import { readSetup, type SetupState } from "./api/setup";
import { readHealth } from "./api/settings";
import { defaultKind, searchParamsFor, type Page } from "./state/route";
import { ShellContext } from "./state/shell";
import { loadSettings, torrentClientOf, useSettings, valueOf } from "./state/settings";
import { useReleases, useWorks, type ReleasesQuery } from "./api/useSearches";
import { retryDownload } from "./api/downloads";
import { splitWorks } from "./api/works";
import { useDownloads } from "./api/useDownloads";
import { usePlace } from "./api/place";
import { UploadError, uploadFile } from "./api/uploads";
import { guessKind } from "./utils/files";
import { texts } from "./texts";
import type { Download, Kind, ShelfFile, Work } from "./types";
import { bestPerVolume, coverageLabel, volumeNumbers } from "./utils/volumes";

/** Noms envoyés à Prowlarr pour une œuvre avant la lecture des paramètres. */
const DEFAULT_MAX_NAMES = 6;
/** Les tests des services tournent toutes les 5 minutes : la page relit leur résultat au même rythme. */
const HEALTH_EVERY_MS = 5 * 60 * 1000;
const noneSelected: ReadonlySet<string> = new Set();

// Chargés à leur ouverture : l'installation du premier lancement et les fenêtres des recherches.
const SetupPanel = lazy(() => import("./components/SetupPanel").then((module) => ({ default: module.SetupPanel })));
const DownloadDialog = lazy(() =>
  import("./components/DownloadDialog").then((module) => ({ default: module.DownloadDialog })),
);
const WaitDialog = lazy(() => import("./components/WaitDialog").then((module) => ({ default: module.WaitDialog })));
const MergeDialog = lazy(() => import("./components/MergeDialog").then((module) => ({ default: module.MergeDialog })));

/** L'en-tête de chaque section. */
const headings: Readonly<Record<Page, Parameters<typeof PageHeader>[0]>> = {
  auto: { section: texts.nav.search, title: texts.pages.auto, lead: texts.pages.autoLead },
  manual: { section: texts.nav.search, title: texts.pages.manual, lead: texts.pages.manualLead },
  waiting: { section: texts.nav.search, title: texts.pages.waiting, lead: texts.pages.waitingLead },
  downloads: { section: texts.nav.library, title: texts.pages.downloads, lead: texts.pages.downloadsLead },
  place: { section: texts.nav.library, title: texts.pages.place, lead: texts.pages.placeLead },
  metadata: { section: texts.nav.library, title: texts.pages.metadata, lead: texts.pages.metadataLead },
  settings: { section: texts.nav.admin, title: texts.pages.settings, lead: texts.pages.settingsLead },
};

const mainClasses: Readonly<Record<Page, string>> = {
  auto: "space-y-6 px-4 pt-6 pb-24 md:px-10 md:pt-8",
  manual: "space-y-6 px-4 pt-6 pb-24 md:px-10 md:pt-8",
  waiting: "px-4 pt-6 pb-24 md:px-10 md:pt-8",
  downloads: "space-y-8 px-4 py-6 md:px-10 md:py-8",
  place: "px-4 pt-6 pb-24 md:px-10 md:pt-8",
  metadata: "px-4 pt-6 pb-24 md:px-10 md:pt-8",
  settings: "px-4 pt-6 pb-24 md:px-10 md:pt-8",
};

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
  const [user, setUser] = useState<SessionAccount | null>(null);
  const username = user?.username ?? null;
  // La session et l'état de l'installation sont lus au chargement : rien n'est affiché avant.
  const [sessionRead, setSessionRead] = useState(false);
  const [setup, setSetup] = useState<SetupState | null>(null);
  const setupNeeded = setup?.needed === true;
  // Les données du site ne sont lues qu'une session ouverte et l'installation terminée.
  const ready = username !== null && !setupNeeded;
  const [servicesDown, setServicesDown] = useState(false);
  const settings = useSettings();
  const maxNamesSetting = valueOf(settings, "search.max_names");
  const maxNames = typeof maxNamesSetting === "number" ? maxNamesSetting : DEFAULT_MAX_NAMES;
  const navigate = useNavigate();
  // La section est celle de la route la plus profonde qui en nomme une.
  const page: Page = useMatches({
    select: (matches) => matches.findLast((match) => match.staticData.page !== undefined)?.staticData.page ?? "auto",
  });
  // La recherche est tenue par l'adresse (ADR 0008) : `/?q=…&kind=…&work=…`, `/manual?q=…&kind=…`.
  const params = useSearch({ strict: false });
  const searching = page === "auto" || page === "manual";
  const query = searching ? (params.q ?? "") : "";
  const kind: Kind = searching ? (params.kind ?? defaultKind) : defaultKind;
  const workId = page === "auto" ? (params.work ?? null) : null;
  // Le message d'une recherche ne reste que sur elle.
  const noticeKey = `${page}|${kind}|${query}`;
  const [noticeOf, setNoticeOf] = useState<{ readonly key: string; readonly text: string | null }>({
    key: "",
    text: null,
  });
  const notice = noticeOf.key === noticeKey ? noticeOf.text : null;
  function setNotice(text: string | null): void {
    setNoticeOf({ key: noticeKey, text });
  }
  const [live, setLive] = useState(false);
  const [liveEvery, setLiveEvery] = useState(5);
  const [retrying, setRetrying] = useState<ReadonlySet<string>>(() => new Set());
  // Une fenêtre ouverte sur une recherche se ferme quand l'adresse en change (Précédent).
  const [mergingOf, setMergingOf] = useState<{ readonly key: string; readonly work: Work } | null>(null);
  const merging = mergingOf?.key === noticeKey ? mergingOf.work : null;
  // Les noms cochés d'une œuvre restent hors de l'adresse : une autre œuvre repart des siens.
  const [namesOf, setNamesOf] = useState<{ readonly workId: string | null; readonly names: ReadonlySet<string> }>(
    () => ({
      workId: null,
      names: new Set(),
    }),
  );
  // Les envois de fichiers de la page Manuel : en cours, refusés, ou vérifiés en attente de Ranger.
  const [uploads, setUploads] = useState<readonly ShelfFile[]>([]);
  // La navigation des petits écrans, ouverte par le bouton Menu de la barre du haut.
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => {
    setMenuOpen(false);
  }, []);

  const [searchId, setSearchId] = useState(0);
  const manual = page === "manual";
  const [worksRetry, setWorksRetry] = useState(0);
  const worksState = useWorks(query, kind, searchId, worksRetry, ready && page === "auto");
  const worksLoading = worksState.status === "loading";
  const works = worksState.status === "done" ? worksState.works : [];
  // L'œuvre de l'adresse, une fois la liste lue ; un identifiant inconnu est ignoré.
  const work = workId === null ? null : (works.find((option) => option.id === workId) ?? null);
  const names =
    work === null
      ? new Set<string>()
      : namesOf.workId === work.id
        ? namesOf.names
        : new Set(
            work.titles
              .filter((t) => t.checked !== false)
              .map((t) => t.title)
              .slice(0, maxNames),
          );
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
  // Relancer sans cache et cocher des releases ne vaut que pour la recherche de releases en cours.
  const releasesKey = `${page}|${JSON.stringify(releasesQuery)}`;
  const [refreshOf, setRefreshOf] = useState({ key: "", round: 0 });
  const refreshRound = refreshOf.key === releasesKey ? refreshOf.round : 0;
  function refreshReleases(): void {
    setRefreshOf({ key: releasesKey, round: refreshRound + 1 });
  }
  const [selection, setSelection] = useState<{ readonly key: string; readonly ids: ReadonlySet<string> }>(() => ({
    key: "",
    ids: new Set(),
  }));
  const selected = selection.key === releasesKey ? selection.ids : noneSelected;
  function setSelected(ids: ReadonlySet<string>): void {
    setSelection({ key: releasesKey, ids });
  }
  const [dialogFor, setDialogFor] = useState<string | null>(null);
  const dialogOpen = dialogFor === releasesKey;
  const [waitFor, setWaitFor] = useState<string | null>(null);
  const waitOpen = waitFor === releasesKey;
  const releasesState = useReleases(releasesQuery, refreshRound);
  const releasesLoading = releasesState.status === "running";
  const downloadsList = useDownloads(ready, page === "downloads", live, liveEvery);
  const downloads = downloadsList.downloads ?? [];

  const [showRejected, setShowRejected] = useState(false);
  const waitingList = useWaiting(ready)?.searches ?? [];
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

  const placeText = page === "place" ? (params.q ?? "") : "";
  const place = usePlace(ready, page === "place", placeText);
  // Un envoi vérifié reste affiché ici jusqu'à ce que Ranger liste le fichier.
  const listed = new Set(place.files.filter((file) => file.origin === "upload").map((file) => file.name));
  const files = [
    ...uploads.filter(
      (file) => !(file.state.kind === "uploading" && file.state.percent === 100 && listed.has(file.name)),
    ),
    ...place.files,
  ];
  const shell = { placeFiles: files, refreshPlace: place.refresh };

  useEffect(() => {
    whenSignedOut(() => {
      setUser(null);
    });
    // Sans réponse sur l'installation, la page se comporte comme une installation terminée.
    Promise.all([readSession(), readSetup().catch(() => null)]).then(
      ([account, state]) => {
        setUser(account);
        setSetup(state);
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
    if (!ready) {
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
  }, [ready]);

  if (!sessionRead) {
    return null;
  }
  if (setup !== null && setup.needed && (user !== null || !setup.account)) {
    return (
      <Suspense fallback={null}>
        <SetupPanel
          account={user}
          onSignedIn={(account) => {
            setUser(account);
            setSetup({ needed: true, account: true });
          }}
          onFinished={() => {
            setSetup({ needed: false, account: true });
          }}
        />
      </Suspense>
    );
  }
  if (user === null || username === null) {
    return <LoginPage onSignedIn={setUser} />;
  }

  /**
   * Une recherche lancée ajoute son adresse à l'historique : Précédent revient à la précédente,
   * puis à la recherche vide. La même recherche relancée est cherchée à nouveau.
   */
  function search(nextQuery: string, nextKind: Kind, to: "/" | "/manual" = manual ? "/manual" : "/"): void {
    setSearchId((id) => id + 1);
    setSelected(new Set());
    setNotice(null);
    void navigate({ to, search: searchParamsFor(nextQuery, nextKind) });
  }

  /** Tout effacer : le texte, l'œuvre et ses noms, les releases, la sélection et le message. */
  function clearSearch(nextKind: Kind = kind): void {
    setShowRejected(false);
    void navigate({
      to: manual ? "/manual" : "/",
      search: searchParamsFor("", nextKind),
      // Sans recherche affichée, changer de type ne fait pas d'entrée dans l'historique.
      replace: query === "",
      resetScroll: false,
    });
  }

  /** La liste relue après une fusion ou une séparation : le serveur l'applique à chaque recherche. */
  function searchAgain(): void {
    setSearchId((id) => id + 1);
    void navigate({ to: "/", search: searchParamsFor(query, kind), replace: true, resetScroll: false });
  }

  function split(merged: Work): void {
    if (merged.mergeId === undefined) {
      return;
    }
    splitWorks(merged.mergeId).then(searchAgain, searchAgain);
  }

  /** L'œuvre choisie ajoute son adresse : Précédent revient à la liste des œuvres. */
  function chooseWork(next: Work): void {
    if (next.id === workId) {
      return;
    }
    void navigate({ to: "/", search: searchParamsFor(query, kind, next.id), resetScroll: false });
  }

  function toggleName(title: string): void {
    if (work === null) {
      return;
    }
    const next = new Set(names);
    if (next.has(title)) {
      next.delete(title);
    } else if (next.size < maxNames) {
      next.add(title);
    }
    setNamesOf({ workId: work.id, names: next });
  }

  /** Le même torrent renvoyé au client torrent ; un refus laisse la ligne telle quelle. */
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

  function setUploadState(id: string, state: ShelfFile["state"]): void {
    setUploads((current) => current.map((file) => (file.id === id ? { ...file, state } : file)));
  }

  /** Les fichiers envoyés l'un après l'autre ; chacun vérifié arrive ensuite dans Ranger. */
  async function upload(list: readonly File[]): Promise<void> {
    const added: ShelfFile[] = list.map((file, index) => ({
      id: `up-${String(Date.now())}-${String(index)}`,
      name: file.name,
      path: `envois/${file.name}`,
      origin: "upload",
      kind: guessKind(file.name),
      sizeBytes: file.size,
      state: { kind: "uploading", percent: 0, sent: 0, phase: "sending" },
    }));
    setUploads((current) => [...added, ...current]);
    let sent = 0;
    for (const [index, entry] of added.entries()) {
      const file = list[index];
      if (file === undefined) {
        continue;
      }
      try {
        await uploadFile(file, (progress) => {
          setUploadState(entry.id, {
            kind: "uploading",
            percent: Math.min(99, Math.floor((progress.sent / progress.total) * 100)),
            sent: progress.sent,
            phase: progress.checking ? "checking" : "sending",
          });
        });
        setUploadState(entry.id, { kind: "uploading", percent: 100, sent: file.size, phase: "done" });
        sent += 1;
        setNotice(texts.place.sentToPlace(sent));
      } catch (error) {
        setUploadState(entry.id, {
          kind: "uploadFailed",
          reason: error instanceof UploadError ? error.reason : "interrupted",
        });
      }
    }
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

  /** La vue de la section : la barre, l'en-tête et le cadre restent, seule la vue change. */
  function view(current: Page): ReactElement {
    switch (current) {
      case "auto":
      case "manual":
        return (
          <>
            <SearchForm
              key={`${kind}-${query}`}
              kind={kind}
              initialQuery={query}
              busy={manual ? releasesLoading : worksLoading}
              onSearch={search}
              onKind={(next) => {
                clearSearch(next);
              }}
              onClear={() => {
                clearSearch();
              }}
              searched={query !== ""}
            />
            {manual ? (
              <UploadZone
                onFiles={(list) => {
                  void upload(list);
                }}
              />
            ) : null}
            {manual && uploads.length > 0 ? (
              <UploadList
                files={uploads}
                onPlace={() => {
                  void navigate({ to: "/place" });
                }}
                onClear={() => {
                  setUploads((current) =>
                    current.filter((file) => file.state.kind === "uploading" && file.state.phase !== "done"),
                  );
                }}
              />
            ) : null}
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
                  onRefresh={refreshReleases}
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
            ) : query === "" ? null : (
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
                      onMerge={(next) => {
                        setMergingOf({ key: noticeKey, work: next });
                      }}
                      onSplit={split}
                      unavailable={worksState.status === "done" ? worksState.unavailable : []}
                      failed={worksState.status === "done" && worksState.failed}
                      onRetry={() => {
                        setWorksRetry((n) => n + 1);
                      }}
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
                          onRefresh={refreshReleases}
                          onWait={() => {
                            setWaitFor(releasesKey);
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
                setDialogFor(releasesKey);
              }}
            />
          </>
        );
      case "waiting":
      case "metadata":
      case "place":
      case "settings":
        // Les pages chargées à la demande : la route les montre.
        return <Outlet />;
      case "downloads":
        return (
          <>
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
                    search(download.workTitle, download.kind, download.manual ? "/manual" : "/");
                  }}
                />
              </>
            )}
          </>
        );
    }
  }

  return (
    <div className="min-h-screen bg-page text-ink md:flex">
      <TopBar
        title={headings[page].title}
        controls="navigation"
        open={menuOpen}
        alert={servicesDown}
        onMenu={() => {
          setMenuOpen((current) => !current);
        }}
      />
      <Sidebar
        id="navigation"
        open={menuOpen}
        onClose={closeMenu}
        page={page}
        username={username}
        internal={user.internal}
        runningCount={running}
        settingsAlert={servicesDown}
        waitingFound={waitingList.filter((entry) => entry.state.kind === "found").length}
        toPlaceCount={place.open}
        onNavigate={() => {
          setMenuOpen(false);
        }}
        onSignOut={() => {
          signOut().then(
            () => {
              setUser(null);
            },
            () => {
              setUser(null);
            },
          );
        }}
      />
      <div className="min-w-0 md:flex-1">
        <PageHeader {...headings[page]} />
        <main className={mainClasses[page]}>
          <ShellContext value={shell}>{view(page)}</ShellContext>
        </main>
      </div>
      <Suspense fallback={null}>
        {dialogOpen && searchIdOfReleases !== null ? (
          <DownloadDialog
            kind={kind}
            searchId={searchIdOfReleases}
            workId={manual ? null : (work?.id ?? null)}
            manual={manual}
            releases={selectedReleases}
            onClose={() => {
              setDialogFor(null);
            }}
            onSent={(sent) => {
              setDialogFor(null);
              setSelected(new Set());
              setNotice(
                manual
                  ? texts.dialog.manualNote
                  : texts.dialog.sent(sent.length, texts.torrentClients[torrentClientOf(settings, true)]),
              );
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
              setWaitFor(null);
            }}
            onAdded={(count) => {
              setNotice(texts.waitDialog.added(count));
            }}
          />
        ) : null}
        {merging === null ? null : (
          <MergeDialog
            kind={kind}
            work={merging}
            onClose={() => {
              setMergingOf(null);
            }}
            onMerged={searchAgain}
          />
        )}
      </Suspense>
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
