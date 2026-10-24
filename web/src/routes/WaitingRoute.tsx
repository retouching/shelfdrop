import { useNavigate } from "@tanstack/react-router";
import { useState, type ReactElement } from "react";

import { WaitDialog } from "../components/WaitDialog";
import { WaitingPage } from "../components/WaitingPage";
import { defaultKind, searchParamsFor } from "../state/route";

/** En attente : une recherche ouverte mène à son adresse sur la page Automatique. */
export function WaitingRoute(): ReactElement {
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  return (
    <>
      <WaitingPage
        onAdd={() => {
          setAdding(true);
        }}
        onOpen={(entry) => {
          void navigate({ to: "/", search: searchParamsFor(entry.title, entry.kind) });
        }}
      />
      {adding ? (
        <WaitDialog
          kind={defaultKind}
          work={null}
          foundVolumes={[]}
          onClose={() => {
            setAdding(false);
          }}
          onAdded={() => undefined}
        />
      ) : null}
    </>
  );
}
