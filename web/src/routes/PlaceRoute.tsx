import { getRouteApi, useNavigate } from "@tanstack/react-router";
import type { ReactElement } from "react";

import { PlacePage } from "../components/PlacePage";
import { useShell } from "../state/shell";

const route = getRouteApi("/place");

/** Ranger : le texte cherché et le filtre sont dans l'adresse, `/place?q=…&filter=…`. */
export function PlaceRoute(): ReactElement {
  const { placeFiles, refreshPlace } = useShell();
  const params = route.useSearch();
  const navigate = useNavigate();
  return (
    <PlacePage
      files={placeFiles}
      onPlaced={refreshPlace}
      initialQuery={params.q ?? ""}
      filter={params.filter ?? "todo"}
      onChange={(q, filter) => {
        // Un filtre remplace l'adresse : Précédent quitte la page, il ne défait pas chaque lettre.
        void navigate({
          to: "/place",
          search: {
            ...(q.trim() === "" ? {} : { q: q.trim() }),
            ...(filter === "todo" ? {} : { filter }),
          },
          replace: true,
          resetScroll: false,
        });
      }}
    />
  );
}
