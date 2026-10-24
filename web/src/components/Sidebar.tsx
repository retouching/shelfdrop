import { useEffect, useRef, useState, type MouseEvent, type ReactElement, type RefObject } from "react";

import { pathOf, sectionRoute, type Page } from "../state/route";
import { texts } from "../texts";
import { readTheme, saveTheme, type ThemeChoice } from "../theme";
import {
  ClockIcon,
  CloseIcon,
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
          className={`flex min-h-10 flex-1 items-center justify-center gap-1.5 rounded-md py-1 text-xs md:min-h-0 ${
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
  /** Le compte interne de shelfdrop, et non un compte de Jellyfin. */
  readonly internal: boolean;
  readonly runningCount: number;
  readonly toPlaceCount: number;
  readonly waitingFound: number;
  /** Un service enregistré ne répond pas : point rouge sur Paramètres. */
  readonly settingsAlert: boolean;
  readonly onNavigate: (page: Page) => void;
  readonly onSignOut: () => void;
  /** L'identifiant de la barre, que le bouton Menu des petits écrans contrôle. */
  readonly id: string;
  /** Sur un petit écran, la barre s'ouvre par-dessus la page. */
  readonly open: boolean;
  /** Fermer la barre ouverte ; une fonction stable, la même à chaque rendu. */
  readonly onClose: () => void;
};

/** Ce que la touche Tab parcourt dans la barre ouverte. */
const focusable = "a[href], button:not([disabled])";

/**
 * La barre ouverte d'un petit écran : le focus y entre et y reste, Échap, un clic à côté ou le
 * passage à un grand écran la ferment, et le focus revient où il était ; la page ne défile plus.
 */
function useDrawer(id: string, open: boolean, onClose: () => void): RefObject<HTMLElement | null> {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const panel = ref.current;
    if (!open || panel === null) {
      return undefined;
    }
    const box: HTMLElement = panel;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.querySelector<HTMLElement>(focusable)?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKey(event: KeyboardEvent): void {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const items = [...box.querySelectorAll<HTMLElement>(focusable)];
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      } else if (!box.contains(document.activeElement)) {
        event.preventDefault();
        first?.focus();
      }
    }
    function onPointer(event: PointerEvent): void {
      const target = event.target;
      // Le bouton Menu ferme la barre lui-même.
      if (
        target instanceof Node &&
        !box.contains(target) &&
        !(target instanceof Element && target.closest(`[aria-controls="${id}"]`) !== null)
      ) {
        onClose();
      }
    }
    const wide = window.matchMedia("(min-width: 48rem)");
    function onWide(event: MediaQueryListEvent): void {
      if (event.matches) {
        onClose();
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    wide.addEventListener("change", onWide);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      wide.removeEventListener("change", onWide);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [id, open, onClose]);
  return ref;
}

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
      className={`flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[15px] md:min-h-0 ${
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
  internal,
  runningCount,
  toPlaceCount,
  waitingFound,
  settingsAlert,
  onNavigate,
  onSignOut,
  id,
  open,
  onClose,
}: Props): ReactElement {
  const ref = useDrawer(id, open, onClose);
  return (
    <>
      {open ? <div aria-hidden="true" className="fixed inset-0 z-40 bg-black/45 md:hidden" /> : null}
      <aside
        ref={ref}
        id={id}
        className={`${
          open ? "fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] overflow-y-auto shadow-2xl" : "hidden"
        } flex-col border-r border-slate-200 bg-surface md:static md:z-auto md:flex md:w-64 md:max-w-none md:shrink-0 md:overflow-visible md:shadow-none`}
      >
        <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
          <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-white">
            <ShelfIcon className="size-5" />
          </span>
          <span>
            <span className="block text-lg leading-tight font-semibold text-ink">{texts.appName}</span>
            <span className="block text-sm text-slate-500">{texts.appTagline}</span>
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label={texts.nav.closeMenu}
            title={texts.nav.closeMenu}
            className="-mr-2 ml-auto flex size-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-ink md:hidden"
          >
            <CloseIcon className="size-5" />
          </button>
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
            <span className="block text-xs text-slate-500">{internal ? texts.nav.internalRole : texts.nav.role}</span>
          </span>
          <button
            type="button"
            onClick={onSignOut}
            title={texts.nav.logout}
            aria-label={texts.nav.logout}
            className="flex size-11 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-ink md:size-auto md:p-1.5"
          >
            <LogoutIcon />
          </button>
        </div>
      </aside>
    </>
  );
}
