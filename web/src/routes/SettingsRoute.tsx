import { useNavigate, useParams } from "@tanstack/react-router";
import type { ReactElement } from "react";

import { SettingsPage } from "../components/settings/SettingsPage";
import { settingsTabOf, settingsTabs } from "../state/route";

/** Paramètres : `/settings` (Services), `/settings/<onglet>` pour les autres. */
export function SettingsRoute(): ReactElement {
  const navigate = useNavigate();
  const tab = settingsTabOf(useParams({ strict: false }).tab) ?? settingsTabs[0];
  return (
    <SettingsPage
      tab={tab}
      onTab={(next) => {
        if (next === settingsTabs[0]) {
          void navigate({ to: "/settings", resetScroll: false });
        } else {
          void navigate({ to: "/settings/$tab", params: { tab: next }, resetScroll: false });
        }
      }}
    />
  );
}
