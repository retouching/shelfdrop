// Rubriques Services, Sources, Recherche, Rangement et Journal Discord. Valeurs fictives de la maquette.
import { useState, type ReactElement } from "react";

import { wait } from "../../mock/latency";
import { setTrackers, useTrackers, type Tracker } from "../../mock/trackers";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import {
  Card,
  Field,
  input,
  SecretField,
  TestButton,
  TestStatus,
  Toggle,
  useConnectionTest,
  type ConnectionTest,
  type TestResult,
} from "./parts";

type Service = {
  readonly id: "prowlarr" | "qbittorrent" | "jellyfin";
  readonly url: string;
  readonly secrets: readonly { readonly label: string; readonly setOn: string | null }[];
  readonly result: TestResult;
  readonly delayMs: number;
};

const services: readonly Service[] = [
  {
    id: "prowlarr",
    url: "http://tunnel:9696",
    secrets: [{ label: texts.settings.apiKey, setOn: "21/10/2026" }],
    result: { ok: true, message: "Connecté · Prowlarr 2.1 · 6 indexeurs actifs" },
    delayMs: 900,
  },
  {
    id: "qbittorrent",
    url: "http://tunnel:7476",
    secrets: [{ label: texts.settings.apiKey, setOn: "20/10/2026" }],
    result: { ok: true, message: "Connecté · qui · 3 catégories trouvées" },
    delayMs: 1100,
  },
  {
    id: "jellyfin",
    url: "http://jellyfin:8096",
    secrets: [{ label: texts.settings.apiKey, setOn: null }],
    result: { ok: false, message: "Clé API manquante" },
    delayMs: 700,
  },
];

function ServiceCard({ service, test }: { readonly service: Service; readonly test: ConnectionTest }): ReactElement {
  const info = texts.settings.services[service.id];
  return (
    <Card
      title={info.name}
      hint={info.hint}
      aside={
        <span className="flex items-center gap-3">
          <TestStatus state={test.state} />
          <TestButton
            busy={test.state.kind === "running"}
            onClick={() => {
              void test.run();
            }}
          />
        </span>
      }
    >
      <Field label={texts.settings.url}>
        <input defaultValue={service.url} className={input} />
      </Field>
      {service.secrets.map((secret) => (
        <SecretField key={secret.label} label={secret.label} setOn={secret.setOn} />
      ))}
    </Card>
  );
}

const [prowlarr, qbittorrent, jellyfin] = services;

export function ServicesTab(): ReactElement | null {
  const tests = [
    useConnectionTest(prowlarr?.result ?? { ok: false, message: "" }, prowlarr?.delayMs ?? 0),
    useConnectionTest(qbittorrent?.result ?? { ok: false, message: "" }, qbittorrent?.delayMs ?? 0),
    useConnectionTest(jellyfin?.result ?? { ok: false, message: "" }, jellyfin?.delayMs ?? 0),
  ];
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => {
            for (const test of tests) {
              void test.run();
            }
          }}
          className="rounded-lg border border-slate-200 bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-slate-100"
        >
          {texts.settings.testAll}
        </button>
      </div>
      {services.map((service, index) => {
        const test = tests[index];
        return test === undefined ? null : <ServiceCard key={service.id} service={service} test={test} />;
      })}
    </div>
  );
}

type Source = {
  readonly id: string;
  readonly name: string;
  readonly kind: "manga" | "books";
  readonly key: "none" | "optional" | "required";
  readonly enabled: boolean;
  readonly result: TestResult;
};

const sources: readonly Source[] = [
  {
    id: "mu",
    name: "MangaUpdates",
    kind: "manga",
    key: "none",
    enabled: true,
    result: { ok: true, message: "Répond en 0,4 s" },
  },
  {
    id: "kitsu",
    name: "Kitsu",
    kind: "manga",
    key: "none",
    enabled: true,
    result: { ok: true, message: "Répond en 0,6 s" },
  },
  {
    id: "mal",
    name: "MyAnimeList",
    kind: "manga",
    key: "optional",
    enabled: true,
    result: { ok: false, message: "Ne répond pas (503)" },
  },
  {
    id: "anilist",
    name: "AniList",
    kind: "manga",
    key: "none",
    enabled: true,
    result: { ok: false, message: "Ne répond pas (403)" },
  },
  {
    id: "mangadex",
    name: "MangaDex",
    kind: "manga",
    key: "none",
    enabled: false,
    result: { ok: false, message: "Ne répond pas (503)" },
  },
  {
    id: "bnf",
    name: "BnF",
    kind: "books",
    key: "none",
    enabled: true,
    result: { ok: true, message: "Répond en 1,2 s" },
  },
  {
    id: "ol",
    name: "Open Library",
    kind: "books",
    key: "none",
    enabled: true,
    result: { ok: true, message: "Répond en 0,9 s" },
  },
  {
    id: "wikidata",
    name: "Wikidata",
    kind: "books",
    key: "none",
    enabled: true,
    result: { ok: true, message: "Répond en 0,5 s" },
  },
];

function SourceRow({ source }: { readonly source: Source }): ReactElement {
  const [enabled, setEnabled] = useState(source.enabled);
  const { state, run } = useConnectionTest(source.result, 800);
  return (
    <li className="space-y-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-48 flex-1">
          <Toggle
            label={source.name}
            hint={source.key === "none" ? texts.settings.noKey : texts.settings.optionalKey}
            checked={enabled}
            onChange={setEnabled}
          />
        </div>
        <TestStatus state={state} />
        <TestButton
          busy={state.kind === "running"}
          onClick={() => {
            void run();
          }}
        />
      </div>
      {source.key === "none" ? null : <SecretField label={texts.settings.clientId} setOn={null} optional />}
    </li>
  );
}

export function SourcesTab(): ReactElement {
  return (
    <div className="space-y-4">
      {(["manga", "books"] as const).map((kind) => (
        <Card key={kind} title={texts.settings.sourceKinds[kind]}>
          <ul className="-my-3 divide-y divide-slate-200">
            {sources
              .filter((source) => source.kind === kind)
              .map((source) => (
                <SourceRow key={source.id} source={source} />
              ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}

export function SearchTab(): ReactElement {
  const trackers = useTrackers();
  const [hideNoSeed, setHideNoSeed] = useState(true);
  const [relevance, setRelevance] = useState(true);
  const [reading, setReading] = useState(false);
  const shown = trackers.filter((tracker) => tracker.prowlarrEnabled);
  const off = trackers.filter((tracker) => !tracker.prowlarrEnabled);

  function move(name: string, delta: number): void {
    const next = [...trackers];
    const index = next.findIndex((tracker) => tracker.name === name);
    let target = index + delta;
    while (next[target]?.prowlarrEnabled === false) {
      target += delta;
    }
    const a = next[index];
    const b = next[target];
    if (a === undefined || b === undefined) {
      return;
    }
    next[index] = b;
    next[target] = a;
    setTrackers(next);
  }

  function update(name: string, change: Partial<Tracker>): void {
    setTrackers(trackers.map((tracker) => (tracker.name === name ? { ...tracker, ...change } : tracker)));
  }

  async function reread(): Promise<void> {
    setReading(true);
    await wait(800);
    setReading(false);
  }

  return (
    <div className="space-y-4">
      <Card
        title={texts.settings.trackers}
        hint={texts.settings.trackersHint}
        aside={
          <button
            type="button"
            disabled={reading}
            onClick={() => {
              void reread();
            }}
            className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
          >
            {reading ? <Spinner className="size-3.5" /> : null}
            {texts.settings.trackersReread}
          </button>
        }
      >
        <table className="w-full rounded-lg border border-slate-200 text-sm">
          <thead className="bg-band text-left text-ink">
            <tr>
              <th scope="col" className="w-10 px-3 py-2 font-semibold">
                #
              </th>
              <th scope="col" className="px-3 py-2 font-semibold">
                {texts.settings.tracker}
              </th>
              <th scope="col" className="w-20 px-3 py-2 font-semibold">
                {texts.settings.trackerLanguage}
              </th>
              <th scope="col" className="w-28 px-3 py-2 font-semibold">
                {texts.settings.trackerUsed}
              </th>
              <th scope="col" className="w-36 px-3 py-2 font-semibold">
                {texts.settings.trackerAuto}
              </th>
              <th scope="col" className="w-24 px-3 py-2">
                <span className="sr-only">{texts.settings.trackerOrder}</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {shown.map((tracker, index) => (
              <tr key={tracker.name} className={tracker.used ? "" : "text-slate-400"}>
                <td className="px-3 py-2 tabular-nums">{tracker.used ? index + 1 : "–"}</td>
                <td className="px-3 py-2 font-medium">{tracker.name}</td>
                <td className="px-3 py-2 text-slate-500">{tracker.language}</td>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={tracker.used}
                    aria-label={`${texts.settings.trackerUsed} : ${tracker.name}`}
                    onChange={(event) => {
                      update(tracker.name, { used: event.target.checked, auto: event.target.checked && tracker.auto });
                    }}
                    className="size-4 accent-accent"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={tracker.auto}
                    disabled={!tracker.used}
                    aria-label={`${texts.settings.trackerAuto} : ${tracker.name}`}
                    onChange={(event) => {
                      update(tracker.name, { auto: event.target.checked });
                    }}
                    className="size-4 accent-accent disabled:opacity-40"
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => {
                      move(tracker.name, -1);
                    }}
                    aria-label={texts.settings.moveUp(tracker.name)}
                    className="rounded px-2 text-slate-500 hover:bg-slate-100 hover:text-ink disabled:opacity-30"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    disabled={index === shown.length - 1}
                    onClick={() => {
                      move(tracker.name, 1);
                    }}
                    aria-label={texts.settings.moveDown(tracker.name)}
                    className="rounded px-2 text-slate-500 hover:bg-slate-100 hover:text-ink disabled:opacity-30"
                  >
                    ↓
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {off.length === 0 ? null : (
          <p className="text-xs text-slate-500">
            {texts.settings.trackersOff(off.map((tracker) => tracker.name).join(", "))}
          </p>
        )}
      </Card>
      <Card title={texts.nav.search}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={texts.settings.maxNames}>
            <input type="number" min={1} max={10} defaultValue={6} className={input} />
          </Field>
          <Field label={texts.settings.parallel}>
            <input type="number" min={1} max={4} defaultValue={2} className={input} />
          </Field>
          <Field label={texts.settings.cacheProwlarr}>
            <input type="number" min={0} defaultValue={10} className={input} />
          </Field>
          <Field label={texts.settings.cacheWorks}>
            <input type="number" min={0} defaultValue={24} className={input} />
          </Field>
        </div>
        <Toggle label={texts.settings.hideNoSeed} checked={hideNoSeed} onChange={setHideNoSeed} />
        <Toggle label={texts.settings.relevance} checked={relevance} onChange={setRelevance} />
      </Card>
    </div>
  );
}

export function PlacementTab(): ReactElement {
  const [merge, setMerge] = useState(true);
  const [covers, setCovers] = useState(true);
  const [lock, setLock] = useState(true);
  return (
    <div className="space-y-4">
      <Card title={texts.settings.libraries}>
        <Field label={texts.settings.libraryPath(texts.libraries.manga)}>
          <input defaultValue="/data/media/comics" className={input} />
        </Field>
        <Field label={texts.settings.libraryPath(texts.libraries.ebook)}>
          <input defaultValue="/data/media/ebooks" className={input} />
        </Field>
        <Field label={texts.settings.libraryPath(texts.libraries.audiobook)}>
          <input defaultValue="/data/media/audiobooks" className={input} />
        </Field>
        <Field label={texts.settings.uploadsPath}>
          <input defaultValue="/data/shelfdrop/envois" className={input} />
        </Field>
      </Card>
      <Card title={texts.nav.place}>
        <Toggle label={texts.settings.mergeMp3} checked={merge} onChange={setMerge} />
        <Toggle label={texts.settings.covers} checked={covers} onChange={setCovers} />
        <Toggle label={texts.settings.lockJellyfin} checked={lock} onChange={setLock} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={texts.settings.scanHour}>
            <input type="time" defaultValue="04:30" className={input} />
          </Field>
          <Field label={texts.settings.uploadRetention}>
            <input type="number" min={1} defaultValue={7} className={input} />
          </Field>
        </div>
      </Card>
    </div>
  );
}

/** Couleurs des embeds, une par type d'événement (palette Radix du site). */
const events: readonly { readonly name: string; readonly color: string }[] = [
  { name: "Envoyé", color: "#6E56CF" },
  { name: "Téléchargé", color: "#7CE2FE" },
  { name: "Rangé", color: "#30A46C" },
  { name: "À associer", color: "#FFC53D" },
  { name: "Fichier envoyé", color: "#AB4ABA" },
  { name: "Réessai", color: "#F76B15" },
  { name: "Échec", color: "#E5484D" },
  { name: "Mal rangés", color: "#8E8C99" },
  { name: "Connexion", color: "#D6409F" },
];

function EventRow({ event }: { readonly event: (typeof events)[number] }): ReactElement {
  const [on, setOn] = useState(true);
  return (
    <li className="flex items-center gap-3 py-2.5">
      <svg viewBox="0 0 10 10" aria-hidden="true" className="size-3 shrink-0">
        <circle cx="5" cy="5" r="5" fill={event.color} />
      </svg>
      <div className="flex-1">
        <Toggle label={event.name} checked={on} onChange={setOn} />
      </div>
    </li>
  );
}

export function DiscordTab(): ReactElement {
  const { state, run } = useConnectionTest({ ok: true, message: "Message de test publié dans #captain-hook" }, 900);
  return (
    <div className="space-y-4">
      <Card
        title={texts.settings.webhook}
        aside={
          <span className="flex items-center gap-3">
            <TestStatus state={state} />
            <button
              type="button"
              disabled={state.kind === "running"}
              onClick={() => {
                void run();
              }}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-ink hover:bg-slate-100 disabled:opacity-60"
            >
              {texts.settings.sendTest}
            </button>
          </span>
        }
      >
        <SecretField label={texts.settings.webhook} setOn="20/10/2026" />
      </Card>
      <Card title={texts.settings.events}>
        <ul className="-my-2.5 divide-y divide-slate-200">
          {events.map((event) => (
            <EventRow key={event.name} event={event} />
          ))}
        </ul>
      </Card>
    </div>
  );
}
