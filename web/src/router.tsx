// Les adresses de la page (ADR 0008) : TanStack Router, ses routes et leurs paramètres typés.
import { createRootRoute, createRoute, createRouter, lazyRouteComponent, redirect } from "@tanstack/react-router";

import { App } from "./App";
import {
  parseSearch,
  placeParamsOf,
  searchParamsOf,
  settingsTabOf,
  settingsTabs,
  stringifySearch,
  type Page,
} from "./state/route";

const root = createRootRoute({ component: App });

// Les pages de recherche et Téléchargements partagent l'état du cadre (App) : elles sont dans le
// premier chargement. Les autres pages arrivent à la demande, chacune dans son fichier.
const auto = createRoute({
  getParentRoute: () => root,
  path: "/",
  staticData: { page: "auto" },
  validateSearch: (raw: Record<string, unknown>) => searchParamsOf(raw, true),
});

const manual = createRoute({
  getParentRoute: () => root,
  path: "manual",
  staticData: { page: "manual" },
  validateSearch: (raw: Record<string, unknown>) => searchParamsOf(raw, false),
});

const waiting = createRoute({
  getParentRoute: () => root,
  path: "waiting",
  staticData: { page: "waiting" },
  component: lazyRouteComponent(() => import("./routes/WaitingRoute"), "WaitingRoute"),
});

const downloads = createRoute({
  getParentRoute: () => root,
  path: "downloads",
  staticData: { page: "downloads" },
});

const place = createRoute({
  getParentRoute: () => root,
  path: "place",
  staticData: { page: "place" },
  validateSearch: placeParamsOf,
  component: lazyRouteComponent(() => import("./routes/PlaceRoute"), "PlaceRoute"),
});

// La fiche d'une série s'ouvre sur la liste, qui reste montée dessous.
const jellyfin = createRoute({
  getParentRoute: () => root,
  path: "jellyfin",
  staticData: { page: "metadata" },
  component: lazyRouteComponent(() => import("./routes/LibraryRoute"), "LibraryRoute"),
});

const jellyfinList = createRoute({ getParentRoute: () => jellyfin, path: "/" });

const series = createRoute({ getParentRoute: () => jellyfin, path: "series/$seriesId" });

// Les onglets sont des routes filles : la page reste montée d'un onglet à l'autre.
const settings = createRoute({
  getParentRoute: () => root,
  path: "settings",
  staticData: { page: "settings" },
  component: lazyRouteComponent(() => import("./routes/SettingsRoute"), "SettingsRoute"),
});

const settingsFirst = createRoute({ getParentRoute: () => settings, path: "/" });

// Un onglet inconnu, ou le premier écrit en entier, est remplacé par `/settings`.
const settingsTab = createRoute({
  getParentRoute: () => settings,
  path: "$tab",
  beforeLoad: ({ params }) => {
    const tab = settingsTabOf(params.tab);
    if (tab === null || tab === settingsTabs[0]) {
      redirect({ to: "/settings", replace: true, throw: true });
    }
  },
});

// Une adresse inconnue est remplacée par la page Automatique.
const unknown = createRoute({
  getParentRoute: () => root,
  path: "$",
  beforeLoad: () => {
    redirect({ to: "/", replace: true, throw: true });
  },
});

const routeTree = root.addChildren([
  auto,
  manual,
  waiting,
  downloads,
  place,
  jellyfin.addChildren([jellyfinList, series]),
  settings.addChildren([settingsFirst, settingsTab]),
  unknown,
]);

// Une adresse écrite avec une barre à la fin est remplacée par celle sans, avant que le routeur
// ne la lise.
const { pathname, search, hash } = window.location;
if (pathname.length > 1 && pathname.endsWith("/")) {
  window.history.replaceState(null, "", `${pathname.replace(/\/+$/, "")}${search}${hash}`);
}

export const router = createRouter({
  routeTree,
  parseSearch,
  stringifySearch,
  trailingSlash: "never",
  // Le code d'une page est chargé dès que son lien est survolé ou reçoit le focus.
  defaultPreload: "intent",
});

/* eslint-disable @typescript-eslint/consistent-type-definitions -- l'extension d'un module de TanStack Router passe par une interface */
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
  interface StaticDataRouteOption {
    /** La section de la barre que la route montre. */
    page?: Page;
  }
}
/* eslint-enable @typescript-eslint/consistent-type-definitions -- la règle vaut de nouveau après l'extension */
