// Thème clair, sombre ou celui du système. Le choix reste dans le navigateur (localStorage).
export type ThemeChoice = "light" | "dark" | "system";

const storageKey = "shelfdrop.theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");

export function readTheme(): ThemeChoice {
  const saved = window.localStorage.getItem(storageKey);
  return saved === "light" || saved === "dark" ? saved : "system";
}

export function applyTheme(choice: ThemeChoice): void {
  const dark = choice === "dark" || (choice === "system" && media.matches);
  document.documentElement.dataset["theme"] = dark ? "dark" : "light";
}

export function saveTheme(choice: ThemeChoice): void {
  if (choice === "system") {
    window.localStorage.removeItem(storageKey);
  } else {
    window.localStorage.setItem(storageKey, choice);
  }
  applyTheme(choice);
}

/** À appeler une fois au démarrage, avant le premier rendu. */
export function initTheme(): void {
  applyTheme(readTheme());
  media.addEventListener("change", () => {
    applyTheme(readTheme());
  });
}
