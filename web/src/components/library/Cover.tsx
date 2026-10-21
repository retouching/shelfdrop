import type { ReactElement } from "react";

type Props = {
  readonly hue: number | null;
  readonly label: string;
  readonly className?: string;
  /** Sans le titre, pour les petites vignettes. */
  readonly bare?: boolean;
};

/** Vignette de couverture. La maquette n'a pas les vraies images : un dégradé et l'initiale en tiennent lieu. */
export function Cover({ hue, label, className, bare = false }: Props): ReactElement {
  const size = className ?? "h-36 w-24";
  if (hue === null) {
    return (
      <span
        className={`${size} flex shrink-0 items-center justify-center rounded-md border border-dashed border-slate-300 bg-band text-slate-400`}
      >
        <svg
          viewBox="0 0 24 24"
          className="size-6"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <path d="m3 16 5-5 4 4 3-3 6 6" />
          <circle cx="15.5" cy="8.5" r="1.5" />
        </svg>
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${size} flex shrink-0 items-end overflow-hidden rounded-md p-2 text-left text-xs leading-tight font-semibold text-white shadow-sm`}
      style={{
        backgroundImage: `linear-gradient(160deg, hsl(${String(hue)} 55% 52%), hsl(${String((hue + 30) % 360)} 50% 22%))`,
      }}
    >
      {bare ? null : <span className="line-clamp-3 drop-shadow">{label}</span>}
    </span>
  );
}
