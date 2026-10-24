import { useEffect, useRef, useState } from "react";

/** Les sections de la page ; chacune a son adresse. */
export type Page = "auto" | "manual" | "waiting" | "downloads" | "place" | "metadata" | "settings";

/** Les onglets de Paramètres, dans leur ordre. */
export const settingsTabs = ["services", "sources", "search", "filters", "placement", "discord", "access"] as const;

export type SettingsTab = (typeof settingsTabs)[number];

/** La vue montrée : une section, et l'onglet pour Paramètres. La recherche n'y est jamais. */
export type Route =
  { readonly page: Exclude<Page, "settings"> } | { readonly page: "settings"; readonly tab: SettingsTab };

const pagePaths: Readonly<Record<Page, string>> = {
  auto: "/",
  manual: "/manuel",
  waiting: "/en-attente",
  downloads: "/telechargements",
  place: "/ranger",
  metadata: "/jellyfin",
  settings: "/parametres",
};

const tabSlugs: Readonly<Record<SettingsTab, string>> = {
  services: "services",
  sources: "sources",
  search: "recherche",
  filters: "filtres",
  placement: "rangement",
  discord: "discord",
  access: "acces",
};

/** La vue où mène une section de la barre : Paramètres s'ouvre sur son premier onglet. */
export function sectionRoute(page: Page): Route {
  return page === "settings" ? { page, tab: settingsTabs[0] } : { page };
}

/** L'adresse d'une vue ; le premier onglet de Paramètres est `/parametres` seul. */
export function pathOf(route: Route): string {
  if (route.page === "settings" && route.tab !== settingsTabs[0]) {
    return `${pagePaths.settings}/${tabSlugs[route.tab]}`;
  }
  return pagePaths[route.page];
}

/** La vue d'une adresse ; une adresse inconnue est la page Automatique. */
export function routeOf(pathname: string): Route {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const settingsPrefix = `${pagePaths.settings}/`;
  if (path.startsWith(settingsPrefix)) {
    const slug = path.slice(settingsPrefix.length);
    const tab = settingsTabs.find((option) => tabSlugs[option] === slug);
    return tab === undefined ? { page: "auto" } : { page: "settings", tab };
  }
  const page = (Object.keys(pagePaths) as Page[]).find((option) => pagePaths[option] === path);
  if (page === undefined) {
    return { page: "auto" };
  }
  return sectionRoute(page);
}

/**
 * La vue tenue par l'adresse : `navigate` ajoute une entrée à l'historique, les boutons
 * Précédent et Suivant du navigateur changent la vue et appellent `onBrowse` avant.
 */
export function useRoute(onBrowse: (next: Route) => void): readonly [Route, (next: Route) => void] {
  const [route, setRoute] = useState<Route>(() => routeOf(window.location.pathname));
  const browseRef = useRef(onBrowse);

  useEffect(() => {
    browseRef.current = onBrowse;
  });

  useEffect(() => {
    // Une adresse inconnue, ou écrite autrement, est remplacée par celle de sa vue.
    const path = pathOf(routeOf(window.location.pathname));
    if (path !== window.location.pathname) {
      window.history.replaceState(null, "", path);
    }
    function listener(): void {
      const next = routeOf(window.location.pathname);
      browseRef.current(next);
      setRoute(next);
    }
    window.addEventListener("popstate", listener);
    return () => {
      window.removeEventListener("popstate", listener);
    };
  }, []);

  function navigate(next: Route): void {
    const path = pathOf(next);
    if (path !== window.location.pathname) {
      window.history.pushState(null, "", path);
    }
    setRoute(next);
  }

  return [route, navigate];
}
