/**
 * Les fenêtres : plein écran sous md, leur défilement à elles et leurs boutons en bas, au-dessus
 * de la zone sûre ; à partir de md, une fenêtre centrée, de la largeur donnée.
 */
const frame =
  "m-0 h-dvh max-h-none w-full max-w-none overflow-hidden bg-surface p-0 text-ink md:m-auto md:h-auto md:flex-col md:rounded-2xl md:open:flex md:border md:border-slate-200 md:shadow-2xl";

export const dialogFrame = {
  md: `${frame} md:max-h-[90vh] md:max-w-md`,
  lg: `${frame} md:max-h-[90vh] md:max-w-lg`,
  "2xl": `${frame} md:max-h-[90vh] md:max-w-2xl`,
  "3xl": `${frame} md:max-h-[90vh] md:max-w-3xl`,
  "3xlTall": `${frame} md:max-h-[92vh] md:max-w-3xl`,
  "5xlTall": `${frame} md:max-h-[92vh] md:max-w-5xl`,
  "6xlTall": `${frame} md:max-h-[94vh] md:max-w-6xl`,
} as const;

/**
 * L'en-tête, le contenu qui défile (`min-h-0 flex-1 overflow-y-auto`) et les boutons, en colonne.
 * À partir de md, la fenêtre est elle-même une colonne : le corps la remplit, sa hauteur suit le
 * contenu jusqu'à la hauteur maximale de la fenêtre, et les boutons restent en bas.
 */
export const dialogBody = {
  regular: "flex h-full min-h-0 flex-col pb-[env(safe-area-inset-bottom)] md:h-auto md:flex-1 md:pb-0",
  tall: "flex h-full min-h-0 flex-col pb-[env(safe-area-inset-bottom)] md:h-auto md:flex-1 md:pb-0",
  taller: "flex h-full min-h-0 flex-col pb-[env(safe-area-inset-bottom)] md:h-auto md:flex-1 md:pb-0",
} as const;
