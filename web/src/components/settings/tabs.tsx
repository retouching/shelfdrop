// Rubriques Services, Sources, Recherche, Rangement et Journal Discord, lues et enregistrées par l'API ;
// le dossier des envois et la durée des envois viennent avec l'envoi de fichiers.
import { Fragment, useEffect, useState, type ReactElement } from "react";

import { testConnection, type SettingValue, type Tracker } from "../../api/settings";
import { isTorrentClient, setSecret, setValue, torrentClientOf, useSettings, valueOf } from "../../state/settings";
import { loadSearchSettings, rereadTrackers, setTrackers, useSearchSettings } from "../../state/searchSettings";
import { texts } from "../../texts";
import type { Kind, PlaceMode, TorrentClient } from "../../types";
import { Spinner } from "../Skeletons";
import { stacked } from "../stacked";
import {
  Card,
  Field,
  input,
  probeMessage,
  SecretField,
  TestButton,
  TestStatus,
  Toggle,
  useConnectionTest,
  type ConnectionTest,
} from "./parts";

type ServiceId = "prowlarr" | "torrent" | "jellyfin";

const serviceIds: readonly ServiceId[] = ["prowlarr", "torrent", "jellyfin"];

/** Le texte d'un champ d'adresse : la valeur modifiée, sinon celle enregistrée. */
function textOf(value: SettingValue | undefined): string {
  return typeof value === "string" ? value : "";
}

/** La clé envoyée au test : celle saisie, "" si effacée, null pour celle enregistrée. */
function typedSecret(edit: string | null | undefined): string | null {
  if (edit === undefined || edit === "") {
    return null;
  }
  return edit;
}

/** Le secret d'un client torrent : la clé de qui, le mot de passe des autres. */
function torrentSecretKey(client: TorrentClient): string {
  return client === "qui" ? "torrent.api_key" : "torrent.password";
}

function useServiceTest(id: ServiceId): ConnectionTest {
  const settings = useSettings();
  const url = textOf(valueOf(settings, `${id}.url`));
  const client = torrentClientOf(settings);
  const secretKey = id === "torrent" ? torrentSecretKey(client) : `${id}.api_key`;
  const edit = settings.secrets[secretKey];
  // Le client et l'identifiant saisis ; l'identifiant non modifié : celui enregistré.
  const torrent =
    id === "torrent"
      ? {
          client,
          username: "torrent.username" in settings.values ? textOf(settings.values["torrent.username"]) : null,
        }
      : {};
  const name = id === "torrent" ? texts.torrentClients[client] : texts.settings.services[id].name;
  return useConnectionTest(async () =>
    probeMessage(
      await testConnection({
        service: id,
        url: url === "" ? null : url,
        secret: edit === null ? "" : typedSecret(edit),
        ...torrent,
      }),
      name,
    ),
  );
}

/** Un dossier facultatif : vide, aucun. */
function OptionalPathField({
  label,
  settingKey,
}: {
  readonly label: string;
  readonly settingKey: string;
}): ReactElement {
  const settings = useSettings();
  return (
    <Field label={label}>
      <input
        value={textOf(valueOf(settings, settingKey))}
        onChange={(event) => {
          const value = event.target.value.trim();
          setValue(settingKey, value === "" ? null : value);
        }}
        className={input}
      />
    </Field>
  );
}

function TorrentSecret({
  client,
  note,
}: {
  readonly client: TorrentClient;
  readonly note?: string | undefined;
}): ReactElement {
  const settings = useSettings();
  const key = torrentSecretKey(client);
  return (
    <SecretField
      label={client === "qui" ? texts.settings.apiKey : texts.settings.password}
      note={note}
      setAt={settings.saved?.secrets[key] ?? null}
      edit={settings.secrets[key]}
      onEdit={(next) => {
        setSecret(key, next);
      }}
    />
  );
}

/** Le client torrent : son type, puis les champs qui vont avec. */
function TorrentFields(): ReactElement {
  const settings = useSettings();
  const client = torrentClientOf(settings);
  const name = texts.torrentClients[client];
  // Les clients de cette version, et celui choisi s'il n'en fait pas partie.
  const offered = (settings.saved?.torrent_clients ?? []).filter(isTorrentClient);
  const choices = offered.includes(client) ? offered : [...offered, client];
  const username = textOf(valueOf(settings, "torrent.username"));
  const optional = client === "transmission" ? texts.settings.optional : undefined;
  return (
    <>
      <Field label={texts.settings.torrentClient}>
        <select
          value={client}
          onChange={(event) => {
            setValue("torrent.client", event.target.value);
          }}
          className={input}
        >
          {choices.map((choice) => (
            <option key={choice} value={choice}>
              {texts.settings.torrentChoices[choice]}
            </option>
          ))}
        </select>
      </Field>
      {client === "qbittorrent" || client === "transmission" ? (
        <Field label={texts.settings.username} note={optional}>
          <input
            value={username}
            autoComplete="off"
            onChange={(event) => {
              setValue("torrent.username", event.target.value === "" ? null : event.target.value);
            }}
            onBlur={() => {
              const trimmed = username.trim();
              if (trimmed !== username) {
                setValue("torrent.username", trimmed === "" ? null : trimmed);
              }
            }}
            className={input}
          />
        </Field>
      ) : null}
      <TorrentSecret client={client} note={optional} />
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-ink">{texts.settings.torrentFolders}</h3>
          <p className="text-xs text-slate-500">{texts.settings.torrentFoldersHint(name)}</p>
        </div>
        {kinds.map((kind) => (
          <OptionalPathField key={kind} label={texts.libraries[kind]} settingKey={`torrent.folder.${kind}`} />
        ))}
        <OptionalPathField label={texts.settings.manualFolder} settingKey="torrent.folder.manual" />
      </div>
    </>
  );
}

export function ServiceCard({ id, test }: { readonly id: ServiceId; readonly test: ConnectionTest }): ReactElement {
  const settings = useSettings();
  const info = texts.settings.services[id];
  const secretKey = `${id}.api_key`;
  const url = textOf(valueOf(settings, `${id}.url`));
  return (
    <Card
      title={info.name}
      hint={info.hint}
      aside={
        <span className="flex items-center gap-3">
          <TestStatus state={test.state} />
          <TestButton
            busy={test.state.kind === "running" || url === ""}
            onClick={() => {
              void test.run();
            }}
          />
        </span>
      }
    >
      <Field label={texts.settings.url}>
        <input
          value={url}
          onChange={(event) => {
            setValue(`${id}.url`, event.target.value === "" ? null : event.target.value);
          }}
          className={input}
        />
      </Field>
      {id === "torrent" ? (
        <TorrentFields />
      ) : (
        <SecretField
          label={texts.settings.apiKey}
          setAt={settings.saved?.secrets[secretKey] ?? null}
          edit={settings.secrets[secretKey]}
          onEdit={(next) => {
            setSecret(secretKey, next);
          }}
        />
      )}
    </Card>
  );
}

export type ServiceTests = Readonly<Record<ServiceId, ConnectionTest>>;

/** Les tests des trois services, tenus par la page : son bouton « Tout tester » les lance. */
export function useServiceTests(): ServiceTests {
  return {
    prowlarr: useServiceTest("prowlarr"),
    torrent: useServiceTest("torrent"),
    jellyfin: useServiceTest("jellyfin"),
  };
}

/** Tous les services testés à la fois. */
export function testAll(tests: ServiceTests): void {
  for (const id of serviceIds) {
    void tests[id].run();
  }
}

export function ServicesTab({ tests }: { readonly tests: ServiceTests }): ReactElement {
  return (
    <div className="space-y-4">
      {serviceIds.map((id) => (
        <ServiceCard key={id} id={id} test={tests[id]} />
      ))}
    </div>
  );
}

type Source = {
  readonly id: string;
  readonly name: string;
  readonly kind: "manga" | "books";
  readonly key: "none" | "optional";
};

const sources: readonly Source[] = [
  { id: "mangaupdates", name: "MangaUpdates", kind: "manga", key: "none" },
  { id: "kitsu", name: "Kitsu", kind: "manga", key: "none" },
  { id: "myanimelist", name: "MyAnimeList", kind: "manga", key: "optional" },
  { id: "anilist", name: "AniList", kind: "manga", key: "none" },
  { id: "mangadex", name: "MangaDex", kind: "manga", key: "none" },
  { id: "bnf", name: "BnF", kind: "books", key: "none" },
  { id: "openlibrary", name: "Open Library", kind: "books", key: "none" },
  { id: "wikidata", name: "Wikidata", kind: "books", key: "none" },
];

const CLIENT_ID_KEY = "sources.myanimelist.client_id";

function SourceRow({ source }: { readonly source: Source }): ReactElement {
  const settings = useSettings();
  const enabledKey = `sources.${source.id}.enabled`;
  const edit = settings.secrets[CLIENT_ID_KEY];
  const { state, run } = useConnectionTest(async () =>
    probeMessage(
      await testConnection({
        service: source.id,
        url: null,
        secret: source.key === "none" ? null : edit === null ? "" : typedSecret(edit),
      }),
      source.name,
    ),
  );
  return (
    <li className="space-y-3 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-48 flex-1">
          <Toggle
            label={source.name}
            hint={source.key === "none" ? texts.settings.noKey : texts.settings.optionalKey}
            checked={valueOf(settings, enabledKey) !== false}
            onChange={(checked) => {
              setValue(enabledKey, checked);
            }}
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
      {source.key === "none" ? null : (
        <SecretField
          label={texts.settings.clientId}
          setAt={settings.saved?.secrets[CLIENT_ID_KEY] ?? null}
          edit={edit}
          onEdit={(next) => {
            setSecret(CLIENT_ID_KEY, next);
          }}
          optional
        />
      )}
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

/** Un champ numérique d'un paramètre : vide ou hors bornes, il n'est pas pris. */
function NumberField({
  label,
  settingKey,
  min,
  max,
}: {
  readonly label: string;
  readonly settingKey: string;
  readonly min: number;
  readonly max: number;
}): ReactElement {
  const settings = useSettings();
  const value = valueOf(settings, settingKey);
  return (
    <Field label={label}>
      <input
        type="number"
        min={min}
        max={max}
        value={typeof value === "number" ? value : ""}
        onChange={(event) => {
          const next = event.target.valueAsNumber;
          if (Number.isInteger(next) && next >= min && next <= max) {
            setValue(settingKey, next);
          }
        }}
        className={input}
      />
    </Field>
  );
}

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];

/** Les catégories proposées : celles lues dans Prowlarr, puis celles choisies qu'il ne donne plus. */
function categoryOptions(tracker: Tracker): readonly { readonly id: number; readonly name: string }[] {
  const known = new Set(tracker.available_categories.map((category) => category.id));
  const missing = [...new Set(kinds.flatMap((kind) => tracker.categories[kind]))]
    .filter((id) => !known.has(id))
    .map((id) => ({ id, name: texts.settings.trackerCategoryUnknown(id) }));
  return [...tracker.available_categories, ...missing];
}

/** Les catégories d'un indexeur, une liste à cocher par type. */
function TrackerCategories({
  tracker,
  onChange,
}: {
  readonly tracker: Tracker;
  readonly onChange: (kind: Kind, ids: readonly number[]) => void;
}): ReactElement {
  const options = categoryOptions(tracker);
  return (
    <div className="space-y-2">
      {tracker.available_categories.length === 0 ? (
        <p className="text-xs text-slate-500">{texts.settings.trackerCategoriesUnread}</p>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-3">
        {kinds.map((kind) => {
          const chosen = tracker.categories[kind];
          return (
            <fieldset key={kind} className="min-w-0">
              <legend className="mb-1 text-xs font-semibold text-ink">{texts.kinds[kind]}</legend>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
                {options.map((category) => (
                  <label
                    key={category.id}
                    className="flex min-h-10 cursor-pointer items-center gap-2 text-xs md:min-h-0"
                  >
                    <input
                      type="checkbox"
                      checked={chosen.includes(category.id)}
                      onChange={(event) => {
                        onChange(
                          kind,
                          event.target.checked ? [...chosen, category.id] : chosen.filter((id) => id !== category.id),
                        );
                      }}
                      className="size-3.5 accent-accent"
                    />
                    <span className="truncate" title={category.name}>
                      {category.name}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
          );
        })}
      </div>
      <p className="text-xs text-slate-500">{texts.settings.trackerCategoriesHint}</p>
    </div>
  );
}

/** « fr-FR » → « FR » ; rien quand Prowlarr ne donne pas la langue. */
function languageOf(tracker: Tracker): string {
  return (tracker.language ?? "").split("-")[0]?.toUpperCase() ?? "";
}

export function SearchTab(): ReactElement {
  const trackers = useSearchSettings().trackers ?? [];
  const [hideNoSeed, setHideNoSeed] = useState(true);
  const [relevance, setRelevance] = useState(true);
  const [reading, setReading] = useState(false);
  const [opened, setOpened] = useState<number | null>(null);
  const shown = trackers.filter((tracker) => tracker.prowlarr_enabled);
  const off = trackers.filter((tracker) => !tracker.prowlarr_enabled);

  useEffect(() => {
    // Une erreur de lecture laisse la liste vide ; « Relire Prowlarr » la remplit.
    loadSearchSettings().catch(() => undefined);
  }, []);

  function move(id: number, delta: number): void {
    const next = [...trackers];
    const index = next.findIndex((tracker) => tracker.indexer_id === id);
    let target = index + delta;
    while (next[target]?.prowlarr_enabled === false) {
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

  function update(id: number, change: Partial<Tracker>): void {
    setTrackers(trackers.map((tracker) => (tracker.indexer_id === id ? { ...tracker, ...change } : tracker)));
  }

  function choose(tracker: Tracker, kind: Kind, ids: readonly number[]): void {
    update(tracker.indexer_id, { categories: { ...tracker.categories, [kind]: ids }, default_categories: false });
  }

  async function reread(): Promise<void> {
    setReading(true);
    try {
      await rereadTrackers();
    } catch {
      // Prowlarr ne répond pas : la liste reste celle enregistrée.
    } finally {
      setReading(false);
    }
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
        <table className={`${stacked.table} w-full rounded-lg border border-slate-200`}>
          <thead className={stacked.head}>
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
              <th scope="col" className="w-32 px-3 py-2 font-semibold">
                {texts.settings.trackerCategories}
              </th>
              <th scope="col" className="w-24 px-3 py-2">
                <span className="sr-only">{texts.settings.trackerOrder}</span>
              </th>
            </tr>
          </thead>
          <tbody className={`${stacked.body} divide-slate-100`}>
            {shown.map((tracker, index) => (
              <Fragment key={tracker.indexer_id}>
                <tr className={`${stacked.row} ${tracker.used ? "" : "text-slate-400"}`}>
                  <td className={`${stacked.cell} order-first tabular-nums md:px-3 md:py-2`}>
                    {tracker.used ? index + 1 : "–"}
                  </td>
                  <td className={`${stacked.cell} order-first flex-1 font-medium wrap-anywhere md:px-3 md:py-2`}>
                    {tracker.name}
                  </td>
                  <td className={`${stacked.cell} order-first text-slate-500 md:px-3 md:py-2`}>
                    {languageOf(tracker)}
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-2`}>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={tracker.used}
                        aria-label={`${texts.settings.trackerUsed} : ${tracker.name}`}
                        onChange={(event) => {
                          update(tracker.indexer_id, {
                            used: event.target.checked,
                            auto: event.target.checked && tracker.auto,
                          });
                        }}
                        className="size-4 accent-accent"
                      />
                      <span className={stacked.label}>{texts.settings.trackerUsed}</span>
                    </label>
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-2`}>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={tracker.auto}
                        disabled={!tracker.used}
                        aria-label={`${texts.settings.trackerAuto} : ${tracker.name}`}
                        onChange={(event) => {
                          update(tracker.indexer_id, { auto: event.target.checked });
                        }}
                        className="size-4 accent-accent disabled:opacity-40"
                      />
                      <span className={stacked.label}>{texts.settings.trackerAuto}</span>
                    </label>
                  </td>
                  <td className={`${stacked.cell} md:px-3 md:py-2`}>
                    <button
                      type="button"
                      aria-expanded={opened === tracker.indexer_id}
                      aria-label={texts.settings.trackerCategoriesOf(tracker.name)}
                      onClick={() => {
                        setOpened(opened === tracker.indexer_id ? null : tracker.indexer_id);
                      }}
                      className="rounded px-2 py-0.5 text-xs text-slate-600 hover:bg-slate-100 hover:text-ink"
                    >
                      {tracker.default_categories
                        ? texts.settings.trackerCategoriesDefault
                        : texts.settings.trackerCategoriesChosen}{" "}
                      {opened === tracker.indexer_id ? "▴" : "▾"}
                    </button>
                  </td>
                  <td className={`${stacked.cell} order-first md:px-3 md:py-2 md:text-right`}>
                    <button
                      type="button"
                      disabled={index === 0}
                      onClick={() => {
                        move(tracker.indexer_id, -1);
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
                        move(tracker.indexer_id, 1);
                      }}
                      aria-label={texts.settings.moveDown(tracker.name)}
                      className="rounded px-2 text-slate-500 hover:bg-slate-100 hover:text-ink disabled:opacity-30"
                    >
                      ↓
                    </button>
                  </td>
                </tr>
                {opened === tracker.indexer_id ? (
                  <tr className="block md:table-row">
                    <td colSpan={7} className="block bg-slate-50 px-3 py-3 md:table-cell">
                      <TrackerCategories
                        tracker={tracker}
                        onChange={(kind, ids) => {
                          choose(tracker, kind, ids);
                        }}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
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
          <NumberField label={texts.settings.maxNames} settingKey="search.max_names" min={1} max={10} />
          <Field label={texts.settings.parallel}>
            <input type="number" min={1} max={4} defaultValue={2} className={input} />
          </Field>
          <NumberField
            label={texts.settings.cacheProwlarr}
            settingKey="search.release_cache_minutes"
            min={0}
            max={1440}
          />
          <NumberField label={texts.settings.cacheWorks} settingKey="search.work_cache_hours" min={0} max={720} />
        </div>
        <Toggle label={texts.settings.hideNoSeed} checked={hideNoSeed} onChange={setHideNoSeed} />
        <Toggle label={texts.settings.relevance} checked={relevance} onChange={setRelevance} />
      </Card>
    </div>
  );
}

function PathField({ label, settingKey }: { readonly label: string; readonly settingKey: string }): ReactElement {
  const settings = useSettings();
  return (
    <Field label={label}>
      <input
        value={textOf(valueOf(settings, settingKey))}
        onChange={(event) => {
          setValue(settingKey, event.target.value.trim());
        }}
        className={input}
      />
    </Field>
  );
}

function TimeField({ label, settingKey }: { readonly label: string; readonly settingKey: string }): ReactElement {
  const settings = useSettings();
  return (
    <Field label={label}>
      <input
        type="time"
        value={textOf(valueOf(settings, settingKey))}
        onChange={(event) => {
          if (event.target.value !== "") {
            setValue(settingKey, event.target.value);
          }
        }}
        className={input}
      />
    </Field>
  );
}

function SwitchField({ label, settingKey }: { readonly label: string; readonly settingKey: string }): ReactElement {
  const settings = useSettings();
  return (
    <Toggle
      label={label}
      checked={valueOf(settings, settingKey) !== false}
      onChange={(checked) => {
        setValue(settingKey, checked);
      }}
    />
  );
}

const placeModes: readonly PlaceMode[] = ["hardlink", "hardlink_or_copy", "copy"];

function isPlaceMode(value: unknown): value is PlaceMode {
  return placeModes.some((mode) => mode === value);
}

/** Le mode de rangement d'un fichier de téléchargement : lien dur, lien dur sinon copie, copie. */
function PlaceModeField(): ReactElement {
  const settings = useSettings();
  const value = valueOf(settings, "placement.mode");
  const mode = isPlaceMode(value) ? value : "hardlink";
  return (
    <Field label={texts.settings.placeMode} hint={texts.settings.placeModeHints[mode]}>
      <select
        value={mode}
        onChange={(event) => {
          setValue("placement.mode", event.target.value);
        }}
        className={input}
      >
        {placeModes.map((choice) => (
          <option key={choice} value={choice}>
            {texts.settings.placeModes[choice]}
          </option>
        ))}
      </select>
    </Field>
  );
}

/** Les dossiers des bibliothèques et celui des envois (Rangement, et l'installation). */
export function LibrariesCard(): ReactElement {
  return (
    <Card title={texts.settings.libraries}>
      <PathField label={texts.settings.libraryPath(texts.libraries.manga)} settingKey="placement.library.manga" />
      <PathField label={texts.settings.libraryPath(texts.libraries.ebook)} settingKey="placement.library.ebook" />
      <PathField
        label={texts.settings.libraryPath(texts.libraries.audiobook)}
        settingKey="placement.library.audiobook"
      />
      <PathField label={texts.settings.uploadsPath} settingKey="uploads.folder" />
    </Card>
  );
}

/** Dossiers et options du rangement, heure du scan, dossier et durée des envois. */
export function PlacementTab(): ReactElement {
  return (
    <div className="space-y-4">
      <LibrariesCard />
      <Card title={texts.nav.place}>
        <PlaceModeField />
        <SwitchField label={texts.settings.mergeMp3} settingKey="placement.merge_mp3" />
        <SwitchField label={texts.settings.covers} settingKey="placement.covers" />
        <SwitchField label={texts.settings.lockJellyfin} settingKey="placement.lock_jellyfin" />
        <div className="grid gap-4 sm:grid-cols-2">
          <TimeField label={texts.settings.scanHour} settingKey="placement.scan_time" />
          <NumberField label={texts.settings.uploadRetention} settingKey="uploads.keep_days" min={1} max={365} />
        </div>
      </Card>
    </div>
  );
}

/** Couleurs des embeds, une par type d'événement (palette Radix du site). */
const events: readonly { readonly id: string; readonly name: string; readonly color: string }[] = [
  { id: "sent", name: "Envoyé", color: "#6E56CF" },
  { id: "downloaded", name: "Téléchargé", color: "#7CE2FE" },
  { id: "placed", name: "Rangé", color: "#30A46C" },
  { id: "to_place", name: "À associer", color: "#FFC53D" },
  { id: "uploaded", name: "Fichier envoyé", color: "#AB4ABA" },
  { id: "retry", name: "Réessai", color: "#F76B15" },
  { id: "failed", name: "Échec", color: "#E5484D" },
  { id: "misplaced", name: "Mal rangés", color: "#8E8C99" },
  { id: "login", name: "Connexion", color: "#D6409F" },
];

const WEBHOOK_KEY = "discord.webhook";

function EventRow({ event }: { readonly event: (typeof events)[number] }): ReactElement {
  const settings = useSettings();
  const key = `discord.events.${event.id}`;
  return (
    <li className="flex items-center gap-3 py-2.5">
      <svg viewBox="0 0 10 10" aria-hidden="true" className="size-3 shrink-0">
        <circle cx="5" cy="5" r="5" fill={event.color} />
      </svg>
      <div className="flex-1">
        <Toggle
          label={event.name}
          checked={valueOf(settings, key) !== false}
          onChange={(checked) => {
            setValue(key, checked);
          }}
        />
      </div>
    </li>
  );
}

/** Le webhook et les événements sont enregistrés ; l'envoi des messages vient avec le journal. */
export function DiscordTab(): ReactElement {
  const settings = useSettings();
  return (
    <div className="space-y-4">
      <Card title={texts.settings.webhook}>
        <SecretField
          label={texts.settings.webhook}
          setAt={settings.saved?.secrets[WEBHOOK_KEY] ?? null}
          edit={settings.secrets[WEBHOOK_KEY]}
          onEdit={(next) => {
            setSecret(WEBHOOK_KEY, next);
          }}
        />
      </Card>
      <Card title={texts.settings.events}>
        <ul className="-my-2.5 divide-y divide-slate-200">
          {events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
        </ul>
      </Card>
    </div>
  );
}
