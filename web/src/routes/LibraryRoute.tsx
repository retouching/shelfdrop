import { useCanGoBack, useNavigate, useParams, useRouter } from "@tanstack/react-router";
import type { ReactElement } from "react";

import { LibraryPage } from "../components/library/LibraryPage";

/** Jellyfin : la fiche d'une série a son adresse, `/jellyfin/series/<id>`. */
export function LibraryRoute(): ReactElement {
  const navigate = useNavigate();
  const router = useRouter();
  const canGoBack = useCanGoBack();
  const seriesId = useParams({ strict: false }).seriesId ?? null;
  return (
    <LibraryPage
      seriesId={seriesId}
      onOpen={(id) => {
        void navigate({ to: "/jellyfin/series/$seriesId", params: { seriesId: id }, resetScroll: false });
      }}
      onClose={() => {
        // Fermer la fiche revient à la liste ; une fiche ouverte par son adresse la remplace.
        if (canGoBack) {
          router.history.back();
        } else {
          void navigate({ to: "/jellyfin", replace: true, resetScroll: false });
        }
      }}
    />
  );
}
