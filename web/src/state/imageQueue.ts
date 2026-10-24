// Les vignettes de l'API chargées par lots : 8 à la fois au plus, la suivante dès qu'une a fini
// (chargée ou en échec). Une page pleine dépasserait sinon la limite de requêtes d'un proxy.
import { useEffect, useRef, useState, type RefObject } from "react";

const IN_FLIGHT = 8;
// Une vignette entre dans la file quand elle arrive à 200 px de l'écran.
const NEAR = "200px";

type Slot = { readonly start: () => void; started: boolean; ended: boolean };

const waiting = new Set<Slot>();
let running = 0;
// Les adresses déjà chargées : le cache du navigateur les sert sans attendre la file.
const loaded = new Set<string>();

function pump(): void {
  for (const slot of waiting) {
    if (running >= IN_FLIGHT) {
      return;
    }
    waiting.delete(slot);
    slot.started = true;
    running += 1;
    slot.start();
  }
}

/** Une place dans la file : `start` est appelé quand le chargement peut commencer. */
function enqueue(start: () => void): { readonly end: () => void } {
  const slot: Slot = { start, started: false, ended: false };
  waiting.add(slot);
  pump();
  return {
    end: () => {
      if (slot.ended) {
        return;
      }
      slot.ended = true;
      if (slot.started) {
        running -= 1;
        pump();
      } else {
        waiting.delete(slot);
      }
    },
  };
}

/** Les adresses de l'API passent par la file ; les autres (sources, data:) se chargent seules. */
function queued(src: string): boolean {
  return src.startsWith("/api/");
}

/**
 * L'adresse à donner à l'image : null tant qu'elle n'est pas près de l'écran ou que la file est
 * pleine. `ended` est à appeler quand l'image a fini de charger, ou n'a pas pu.
 */
export function useQueuedSrc(
  src: string | null,
  ref: RefObject<Element | null>,
): { readonly shown: string | null; readonly ended: () => void } {
  const [allowed, setAllowed] = useState<string | null>(null);
  const endRef = useRef<() => void>(noop);
  const direct = src !== null && (!queued(src) || loaded.has(src));

  useEffect(() => {
    const element = ref.current;
    if (src === null || direct || element === null) {
      return;
    }
    let place: { readonly end: () => void } | null = null;
    let started = false;
    const observer = new IntersectionObserver(
      (entries) => {
        const near = entries.some((entry) => entry.isIntersecting);
        if (near && place === null) {
          place = enqueue(() => {
            started = true;
            observer.disconnect();
            endRef.current = () => {
              loaded.add(src);
              place?.end();
            };
            setAllowed(src);
          });
        } else if (!near && place !== null && !started) {
          // Sortie de l'écran avant son tour : elle laisse sa place.
          place.end();
          place = null;
        }
      },
      { rootMargin: NEAR },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      place?.end();
      endRef.current = noop;
    };
  }, [src, direct, ref]);

  if (src === null) {
    return { shown: null, ended: noop };
  }
  if (direct) {
    return { shown: src, ended: noop };
  }
  return {
    shown: allowed === src ? src : null,
    ended: () => {
      endRef.current();
    },
  };
}

function noop(): void {
  // Rien à libérer : l'image ne tient pas de place dans la file.
}
