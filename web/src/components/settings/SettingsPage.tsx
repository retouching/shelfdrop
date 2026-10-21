import { useState, type ReactElement } from "react";

import { wait } from "../../mock/latency";
import { saveSearchSettings } from "../../state/searchSettings";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { AccessTab } from "./AccessTab";
import { FiltersTab } from "./FiltersTab";
import { DiscordTab, PlacementTab, SearchTab, ServicesTab, SourcesTab } from "./tabs";

type Tab = keyof typeof texts.settings.tabs;

const tabs: readonly Tab[] = ["services", "sources", "search", "filters", "placement", "discord", "access"];

function TabContent({ tab }: { readonly tab: Tab }): ReactElement | null {
  switch (tab) {
    case "services":
      return <ServicesTab />;
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
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save(): Promise<void> {
    setSaving(true);
    setSaved(false);
    try {
      // Recherche et Filtres sont enregistrés par l'API ; les autres rubriques viendront avec elle.
      await Promise.all([saveSearchSettings(), wait(300)]);
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
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                void save();
              }}
              className="flex items-center gap-2 rounded-lg bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-80"
            >
              {saving ? <Spinner /> : null}
              {saving ? texts.settings.saving : texts.settings.save}
            </button>
          </div>
        )}
      </div>
      <div role="tabpanel" id="settings-panel" aria-labelledby={`tab-${tab}`}>
        <TabContent key={tab} tab={tab} />
      </div>
    </div>
  );
}
