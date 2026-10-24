import { useState, type MouseEvent, type ReactElement } from "react";

import { pathOf, sectionRoute, type Page } from "../state/route";
import { texts } from "../texts";
import { readTheme, saveTheme, type ThemeChoice } from "../theme";
import {
  ClockIcon,
  DownloadIcon,
  FileIcon,
  GearIcon,
  ImageIcon,
  LogoutIcon,
  MonitorIcon,
  MoonIcon,
  SearchIcon,
  ShelfIcon,
  SunIcon,
} from "./icons";

const themeChoices: readonly ThemeChoice[] = ["light", "dark", "system"];
const themeIcons: Readonly<Record<ThemeChoice, ReactElement>> = {
  light: <SunIcon />,
  dark: <MoonIcon />,
  system: <MonitorIcon />,
};

function ThemeSwitch(): ReactElement {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  return (
    <div role="radiogroup" aria-label={texts.nav.theme} className="flex rounded-lg bg-slate-100 p-1">
      {themeChoices.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={option === choice}
          title={texts.nav.themes[option]}
          onClick={() => {
            setChoice(option);
            saveTheme(option);
          }}
          className={`flex flex-1 items-center justify-center gap-1.5 rounded-md py-1 text-xs ${
            option === choice ? "bg-surface font-medium text-ink shadow-sm" : "text-slate-500 hover:text-ink"
          }`}
        >
          {themeIcons[option]}
          {texts.nav.themes[option]}
        </button>
      ))}
    </div>
  );
}

type Props = {
  readonly page: Page;
  readonly username: string;
  readonly runningCount: number;
  readonly toPlaceCount: number;
  readonly waitingFound: number;
  /** Un service enregistré ne répond pas : point rouge sur Paramètres. */
  readonly settingsAlert: boolean;
  readonly onNavigate: (page: Page) => void;
  readonly onSignOut: () => void;
};

/** Le lien d'une section : un clic simple change la vue, un clic du milieu ouvre un onglet. */
function NavLink({
  page,
  active,
  label,
  icon,
  badge,
  alert,
  onClick,
}: {
  readonly page: Page;
  readonly active: boolean;
  readonly label: string;
  readonly icon: ReactElement;
  readonly badge?: number;
  readonly alert?: boolean;
  readonly onClick: () => void;
}): ReactElement {
  return (
    <a
      href={pathOf(sectionRoute(page))}
      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
          return;
        }
        event.preventDefault();
        onClick();
      }}
      aria-current={active ? "page" : undefined}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[15px] ${
        active ? "bg-accent-soft font-medium text-accent-text" : "text-slate-600 hover:bg-slate-50 hover:text-ink"
      }`}
    >
      {icon}
      <span className="flex-1">{label}</span>
      {badge === undefined || badge === 0 ? null : (
        <span className="rounded-full bg-accent px-2 text-xs leading-5 font-medium text-white tabular-nums">
          {badge}
        </span>
      )}
      {alert === true ? <span aria-hidden="true" className="size-2 rounded-full bg-rose-500" /> : null}
    </a>
  );
}

export function Sidebar({
  page,
  username,
  runningCount,
  toPlaceCount,
  waitingFound,
  settingsAlert,
  onNavigate,
  onSignOut,
}: Props): ReactElement {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-surface">
      <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
        <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-white">
          <ShelfIcon className="size-5" />
        </span>
        <span>
          <span className="block text-lg leading-tight font-semibold text-ink">{texts.appName}</span>
          <span className="block text-sm text-slate-500">{texts.appTagline}</span>
        </span>
      </div>
      <nav aria-label={texts.nav.label} className="flex-1 space-y-6 px-3 py-5">
        <div className="space-y-1">
          <p className="px-3 pb-1 text-sm font-semibold text-ink">{texts.nav.search}</p>
          <NavLink
            page="auto"
            active={page === "auto"}
            label={texts.nav.auto}
            icon={<SearchIcon />}
            onClick={() => {
              onNavigate("auto");
            }}
          />
          <NavLink
            page="manual"
            active={page === "manual"}
            label={texts.nav.manual}
            icon={<FileIcon />}
            onClick={() => {
              onNavigate("manual");
            }}
          />
          <NavLink
            page="waiting"
            active={page === "waiting"}
            label={texts.nav.waiting}
            icon={<ClockIcon />}
            badge={waitingFound}
            onClick={() => {
              onNavigate("waiting");
            }}
          />
        </div>
        <div className="space-y-1">
          <p className="px-3 pb-1 text-sm font-semibold text-ink">{texts.nav.library}</p>
          <NavLink
            page="downloads"
            active={page === "downloads"}
            label={texts.nav.downloads}
            icon={<DownloadIcon />}
            badge={runningCount}
            onClick={() => {
              onNavigate("downloads");
            }}
          />
          <NavLink
            page="place"
            active={page === "place"}
            label={texts.nav.place}
            icon={<ShelfIcon />}
            badge={toPlaceCount}
            onClick={() => {
              onNavigate("place");
            }}
          />
          <NavLink
            page="metadata"
            active={page === "metadata"}
            label={texts.nav.metadata}
            icon={<ImageIcon />}
            onClick={() => {
              onNavigate("metadata");
            }}
          />
        </div>
        <div className="space-y-1">
          <p className="px-3 pb-1 text-sm font-semibold text-ink">{texts.nav.admin}</p>
          <NavLink
            page="settings"
            active={page === "settings"}
            label={texts.nav.settings}
            icon={<GearIcon />}
            alert={settingsAlert}
            onClick={() => {
              onNavigate("settings");
            }}
          />
        </div>
      </nav>
      <div className="px-3 pb-3">
        <ThemeSwitch />
      </div>
      <div className="flex items-center gap-3 border-t border-slate-200 px-5 py-4">
        <span className="flex size-9 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent-text uppercase">
          {username.slice(0, 1)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink capitalize">{username}</span>
          <span className="block text-xs text-slate-500">{texts.nav.role}</span>
        </span>
        <button
          type="button"
          onClick={onSignOut}
          title={texts.nav.logout}
          aria-label={texts.nav.logout}
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-ink"
        >
          <LogoutIcon />
        </button>
      </div>
    </aside>
  );
}
