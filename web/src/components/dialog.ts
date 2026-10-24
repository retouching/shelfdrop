/**
 * Les fenêtres : plein écran sous md, leur défilement à elles et leurs boutons en bas, au-dessus
 * de la zone sûre ; à partir de md, une fenêtre centrée aussi haute que son contenu (`h-fit` : la
 * hauteur `auto` d'une fenêtre modale l'étirerait d'un bord à l'autre de l'écran), jusqu'à sa
 * hauteur maximale.
 */
const frame =
  "m-0 h-dvh max-h-none w-full max-w-none overflow-hidden bg-surface p-0 text-ink md:m-auto md:h-fit md:flex-col md:rounded-2xl md:border md:border-slate-200 md:shadow-2xl md:open:flex";

/**
 * La largeur à partir de md : `fit`, celle du contenu, entre 28rem et 56rem (90 % de l'écran au plus) ; les autres,
 * des fenêtres faites surtout de champs (qui n'ont pas de largeur propre), une largeur préférée
 * qui rétrécit sur un écran étroit. Un texte coupé (`truncate`) d'une fenêtre `fit` porte
 * `[contain:inline-size]`, sinon sa longueur entière ferait la largeur de la fenêtre.
 */
export const dialogFrame = {
  fit: `${frame} md:max-h-[90vh] md:w-fit md:min-w-[min(28rem,90vw)] md:max-w-[min(90vw,56rem)]`,
  form48: `${frame} md:max-h-[92vh] md:w-[min(90vw,48rem)]`,
  form64: `${frame} md:max-h-[92vh] md:w-[min(90vw,64rem)]`,
  form72: `${frame} md:max-h-[94vh] md:w-[min(90vw,72rem)]`,
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
