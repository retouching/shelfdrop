import { useRef, useState, type ReactElement } from "react";

import { useQueuedSrc } from "../../state/imageQueue";

type Props = {
  /** L'adresse de l'image ; null sans image. */
  readonly src: string | null;
  readonly label: string;
  readonly className?: string;
  /** Sans le titre sur l'emplacement vide, pour les petites vignettes. */
  readonly bare?: boolean;
};

/**
 * Vignette de couverture : l'image, ou un emplacement vide quand il n'y en a pas ou qu'elle ne se charge pas.
 * Les images de l'API se chargent près de l'écran, par lots (`useQueuedSrc`), à une taille fixe.
 */
export function Cover({ src, label, className, bare = false }: Props): ReactElement {
  const size = className ?? "h-36 w-24";
  const [broken, setBroken] = useState<string | null>(null);
  const ref = useRef<HTMLImageElement>(null);
  const wanted = src === null || broken === src ? null : src;
  const { shown, ended } = useQueuedSrc(wanted, ref);
  if (wanted === null) {
    return (
      <span
        className={`${size} flex shrink-0 flex-col items-center justify-center gap-1 rounded-md border border-dashed border-slate-300 bg-band p-2 text-center text-slate-400`}
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
        {bare ? null : <span className="line-clamp-2 text-xs">{label}</span>}
      </span>
    );
  }
  return (
    <img
      ref={ref}
      src={shown ?? undefined}
      alt=""
      loading="lazy"
      decoding="async"
      width={200}
      height={300}
      onLoad={ended}
      onError={() => {
        ended();
        setBroken(wanted);
      }}
      className={`${size} shrink-0 rounded-md bg-band object-cover shadow-sm`}
    />
  );
}
