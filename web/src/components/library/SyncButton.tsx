import { useRef, useState, type ReactElement } from "react";

import { runSync, type SyncState } from "../../api/library";
import { texts } from "../../texts";
import { Spinner } from "../Skeletons";
import { dialogBody, dialogFrame } from "../dialog";

type Props = {
  /** La série à synchroniser ; null pour toutes les bibliothèques. */
  readonly seriesId: string | null;
  readonly question: string;
  readonly onDone: (message: string, failed: boolean) => void;
};

function messageOf(state: SyncState): string {
  return state.stage === "done" ? texts.sync.done(state.changed, state.unchanged, state.notFound) : texts.sync.failed;
}

/** Bouton de synchronisation des métadonnées vers Jellyfin, après confirmation. */
export function SyncButton({ seriesId, question, onDone }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [running, setRunning] = useState(false);

  async function run(): Promise<void> {
    ref.current?.close();
    setRunning(true);
    try {
      const state = await runSync(seriesId);
      onDone(messageOf(state), state.stage !== "done");
    } catch {
      onDone(texts.sync.failed, true);
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <button
        type="button"
        disabled={running}
        onClick={() => {
          ref.current?.showModal();
        }}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-surface px-3 py-1.5 text-sm hover:bg-slate-50 disabled:cursor-wait"
      >
        {running ? <Spinner className="size-3.5" /> : null}
        {running ? texts.sync.running : texts.sync.action}
      </button>
      <dialog ref={ref} aria-label={texts.sync.action} className={dialogFrame.fit}>
        <div className={dialogBody.regular}>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 pt-4 md:px-6 md:pt-6">
            <p className="text-sm font-medium">{question}</p>
            <p className="mt-2 text-sm text-slate-500">{texts.sync.confirmHint}</p>
          </div>
          <div className="mt-5 flex flex-wrap justify-end gap-2 px-4 pb-4 md:px-6 md:pb-6">
            <button
              type="button"
              onClick={() => {
                ref.current?.close();
              }}
              className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100"
            >
              {texts.dialog.cancel}
            </button>
            <button
              type="button"
              onClick={() => {
                void run();
              }}
              className="rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong"
            >
              {texts.sync.confirm}
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
}
