// La langue de la page : celle choisie sur cet appareil (localStorage), sinon celle du navigateur
// (français s'il commence par « fr », anglais sinon). Lue une fois, au chargement du module : un
// changement enregistre le choix et recharge la page (ADR 0008).
export type Language = "fr" | "en";

export const languages: readonly Language[] = ["fr", "en"];

const storageKey = "shelfdrop.language";

/** Le choix enregistré s'il est connu, sinon la langue du navigateur. */
export function languageOf(saved: string | null, browser: string | undefined): Language {
  if (saved === "fr" || saved === "en") {
    return saved;
  }
  return browser?.toLowerCase().startsWith("fr") === true ? "fr" : "en";
}

export const language: Language = languageOf(window.localStorage.getItem(storageKey), window.navigator.language);

/**
 * Les dates, heures et nombres : fr-FR, ou en-GB (jour avant le mois et horloge sur 24 h, comme la
 * page en français ; point décimal).
 */
export const locale: string = language === "fr" ? "fr-FR" : "en-GB";

/** `<html lang>`, à appeler une fois au démarrage, avant le premier rendu. */
export function initLanguage(): void {
  document.documentElement.lang = language;
}

/** Enregistre le choix de cet appareil et recharge la page dans cette langue. */
export function saveLanguage(choice: Language): void {
  if (choice === language) {
    return;
  }
  window.localStorage.setItem(storageKey, choice);
  window.location.reload();
}
