import { useEffect, useRef, useState, type ReactElement } from "react";

import { linkWork, type Proposals } from "../../api/library";
import { texts } from "../../texts";
import type { Kind } from "../../types";
import { dialogBody, dialogFrame } from "../dialog";
import { Spinner } from "../Skeletons";
import { WorkPicker, type Pick } from "../WorkPicker";

type Props = {
  readonly seriesId: string;
  readonly kind: Kind;
  readonly name: string;
  readonly onClose: () => void;
  readonly onLinked: (proposals: Proposals) => void;
};

/** Une autre œuvre pour une série : la recherche d'œuvres, pré-remplie de son nom. */
export function WorkLinkDialog({ seriesId, kind, name, onClose, onLinked }: Props): ReactElement {
  const ref = useRef<HTMLDialogElement>(null);
  const [pick, setPick] = useState<Pick | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  async function choose(): Promise<void> {
    if (pick === null) {
      return;
    }
    setPending(true);
    setFailed(false);
    try {
      onLinked(await linkWork(seriesId, pick.work.id));
      ref.current?.close();
    } catch {
      setPending(false);
      setFailed(true);
    }
  }

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="link-work-title" className={dialogFrame.fit}>
      <div className={dialogBody.regular}>
        <div className="border-b border-slate-200 px-4 py-4 md:px-6">
          <h2 id="link-work-title" className="text-lg font-semibold">
            {texts.seriesWork.pickerTitle}
          </h2>
          <p className="mt-0.5 text-sm text-slate-500">{name}</p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
          <WorkPicker kind={kind} initialQuery={name} value={pick} onChange={setPick} withName={false} />
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-4 py-4 md:px-6">
          {failed ? (
            <p role="alert" className="mr-auto text-sm text-rose-700">
              {texts.seriesWork.failed}
            </p>
          ) : null}
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
            disabled={pick === null || pending}
            onClick={() => {
              void choose();
            }}
            className="flex items-center gap-2 rounded-lg border border-transparent bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner /> : null}
            {texts.seriesWork.choose}
          </button>
        </div>
      </div>
    </dialog>
  );
}
