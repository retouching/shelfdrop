// Squelettes et indicateurs de chargement. L'animation suit prefers-reduced-motion (motion-safe).
import type { ReactElement } from "react";

export function Bone({ className }: { readonly className: string }): ReactElement {
  return <span aria-hidden="true" className={`block rounded bg-slate-200/80 motion-safe:animate-pulse ${className}`} />;
}

export function Spinner({ className }: { readonly className?: string }): ReactElement {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={`motion-safe:animate-spin ${className ?? "size-4"}`}>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/** Texte lu par les lecteurs d'écran pendant un chargement (la zone porte aria-busy). */
export function LoadingLabel({ label }: { readonly label: string }): ReactElement {
  return (
    <p role="status" className="sr-only">
      {label}
    </p>
  );
}

export function WorkListSkeleton(): ReactElement {
  return (
    <ul aria-hidden="true" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex gap-4 rounded-xl border border-slate-200 bg-surface p-4">
          <Bone className="h-24 w-16 shrink-0 rounded-md" />
          <span className="flex-1 space-y-2.5 pt-1">
            <Bone className="h-4 w-3/4" />
            <Bone className="h-3 w-1/2" />
            <span className="flex gap-1.5 pt-1">
              <Bone className="h-5 w-16" />
              <Bone className="h-5 w-20" />
              <Bone className="h-5 w-12" />
            </span>
            <Bone className="h-3 w-24" />
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ResultsSkeleton({ rows = 6 }: { readonly rows?: number }): ReactElement {
  return (
    <div aria-hidden="true" className="overflow-hidden rounded-xl border border-slate-200 bg-surface">
      <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <span className="space-y-2">
          <Bone className="h-4 w-56" />
          <Bone className="h-3 w-80" />
        </span>
        <Bone className="h-4 w-40" />
      </div>
      <div className="h-11 bg-band" />
      <ul className="divide-y divide-slate-100">
        {Array.from({ length: rows }, (_, i) => (
          <li key={i} className="flex items-center gap-4 px-5 py-3.5">
            <Bone className="size-4" />
            <Bone className={`h-3.5 flex-1 ${i % 2 === 0 ? "max-w-xl" : "max-w-md"}`} />
            <Bone className="h-3.5 w-16" />
            <Bone className="h-5 w-24" />
            <Bone className="h-3.5 w-8" />
            <Bone className="h-3.5 w-14" />
            <Bone className="h-6 w-14" />
          </li>
        ))}
      </ul>
    </div>
  );
}
