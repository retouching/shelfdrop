/**
 * Un tableau en cartes sous md, en tableau à partir de md : les mêmes cellules, empilées sur un
 * petit écran. Chaque cellule ajoute sa place dans la carte (`basis-full`, `order-first`) et son
 * espacement de tableau (`md:px-3 md:py-3`).
 */
export const stacked = {
  table: "block text-sm md:table",
  /** Les largeurs des colonnes ne servent qu'au tableau. */
  columns: "hidden md:table-column-group",
  /** Les en-têtes ne sont lus qu'au tableau ; une carte nomme ce qui ne se comprend pas seul. */
  head: "hidden bg-band text-left text-ink md:table-header-group",
  body: "block divide-y md:table-row-group",
  row: "flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 md:table-row md:p-0",
  cell: "block min-w-0 md:table-cell",
  /** Le nom d'une valeur dans la carte, que l'en-tête de la colonne porte au tableau. */
  label: "text-slate-500 md:hidden",
} as const;
