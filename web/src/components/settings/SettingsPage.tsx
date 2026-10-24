import { useEffect, useState, type ReactElement } from "react";

import { saveSearchSettings } from "../../state/searchSettings";
import { loadSettings, saveChangedSettings } from "../../state/settings";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { AccessTab } from "./AccessTab";
import { FiltersTab } from "./FiltersTab";
import {
  DiscordTab,
  PlacementTab,
  SearchTab,
  ServicesTab,
  SourcesTab,
  testAll,
  useServiceTests,
  type ServiceTests,
} from "./tabs";

type Tab = keyof typeof texts.settings.tabs;

const tabs: readonly Tab[] = ["services", "sources", "search", "filters", "placement", "discord", "access"];

function TabContent({ tab, tests }: { readonly tab: Tab; readonly tests: ServiceTests }): ReactElement | null {
  switch (tab) {
    case "services":
      return <ServicesTab tests={tests} />;
    case "sources":
      return <SourcesTab />;
    case "search":
      return <SearchTab />;
    case "filters":
      return <FiltersTab />;
    case "placement":
      return <PlacementTab />;
    case "discord":
      return <DiscordTab />;
    case "access":
      return <AccessTab />;
  }
}

export function SettingsPage(): ReactElement {
  const [tab, setTab] = useState<Tab>("services");

  useEffect(() => {
    // Une erreur de lecture laisse les champs vides.
    loadSettings().catch(() => undefined);
  }, []);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // « Tout tester » est à côté de « Enregistrer », aligné avec lui : la page tient les tests de Services.
  const tests = useServiceTests();

  async function save(): Promise<void> {
    setSaving(true);
    setSaved(false);
    try {
      // Rangement et API et MCP ne sont pas encore enregistrés : ils viennent avec leur étape.
      await Promise.all([saveSearchSettings(), saveChangedSettings()]);
      setSaved(true);
    } catch {
      setSaved(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          role="tablist"
          aria-label={texts.settings.tabsLabel}
          className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1"
        >
          {tabs.map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              id={`tab-${option}`}
              aria-selected={option === tab}
              aria-controls="settings-panel"
              onClick={() => {
                setTab(option);
                setSaved(false);
              }}
              className={
                option === tab
                  ? "rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-ink shadow-sm"
                  : "rounded-md px-3 py-1.5 text-sm text-slate-500 hover:text-ink"
              }
            >
              {texts.settings.tabs[option]}
            </button>
          ))}
        </div>
        {tab === "access" ? null : (
          <div className="flex items-center gap-3">
            {saved ? (
              <p role="status" className="text-sm text-emerald-700">
                {texts.settings.saved}
              </p>
            ) : null}
            {tab === "services" ? (
              <button
                type="button"
                onClick={() => {
                  testAll(tests);
                }}
                className="rounded-lg border border-slate-200 bg-surface px-4 py-2 text-sm font-medium text-ink hover:bg-slate-100"
              >
                {texts.settings.testAll}
              </button>
            ) : null}
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                void save();
              }}
              className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-80"
            >
              {saving ? <Spinner /> : null}
              {saving ? texts.settings.saving : texts.settings.save}
            </button>
          </div>
        )}
      </div>
      <div role="tabpanel" id="settings-panel" aria-labelledby={`tab-${tab}`}>
        <TabContent key={tab} tab={tab} tests={tests} />
      </div>
    </div>
  );
}
