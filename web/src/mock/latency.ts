// Maquette : simule le temps de réponse des API (métadonnées, Prowlarr) pour montrer les états de chargement.
import { useEffect, useState } from "react";

/** Vrai pendant `ms` millisecondes chaque fois que `key` change. */
export function useLatency(key: string, ms: number): boolean {
  const [doneKey, setDoneKey] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDoneKey(key);
    }, ms);
    return () => {
      window.clearTimeout(timer);
    };
  }, [key, ms]);

  return doneKey !== key;
}

export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
