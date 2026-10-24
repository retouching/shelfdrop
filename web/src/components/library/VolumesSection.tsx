import { useEffect, useState, type ReactElement } from "react";

import { itemImage, readVolumes, volumeFile, type Series, type SeriesVolumes, type Volume } from "../../api/library";
import { texts } from "../../texts";
import { formatSize } from "../../utils/format";
import { Spinner } from "../Skeletons";
import { Cover } from "./Cover";
import { VolumeEditor } from "./VolumeEditor";

type Props = {
  readonly series: Series;
  /** Relu à chaque changement : après une synchronisation, par exemple. */
  readonly version: number;
  readonly onNotice: (message: string) => void;
  /** Un tome a changé : la série (ses tomes sans résumé, sans image) est relue. */
  readonly onChanged: () => void;
};

/** Les tomes d'une série : leur couverture, leur numéro, leur fichier, et les numéros manquants. */
export function VolumesSection({ series, version, onNotice, onChanged }: Props): ReactElement {
  const [read, setRead] = useState<SeriesVolumes | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<Volume | null>(null);

  useEffect(() => {
    let stopped = false;
    readVolumes(series.id)
      .then((found) => {
        if (!stopped) {
          setRead(found);
          setFailed(false);
        }
      })
      .catch(() => {
        if (!stopped) {
          setFailed(true);
        }
      });
    return () => {
      stopped = true;
    };
  }, [series.id, version]);

  function replace(next: Volume): void {
    setRead((current) =>
      current === null
        ? current
        : { ...current, volumes: current.volumes.map((volume) => (volume.id === next.id ? next : volume)) },
    );
    onNotice(texts.volumes.applied(next.name));
    onChanged();
  }

  return (
    <section aria-labelledby="volumes-title" className="space-y-3 border-t border-slate-200 pt-5 md:col-span-2">
      <h3 id="volumes-title" className="text-sm font-semibold">
        {texts.volumes.title}
      </h3>
      {failed ? (
        <p role="alert" className="text-sm text-rose-700">
          {texts.library.unavailable}
        </p>
      ) : read === null ? (
        <p role="status" className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="size-3.5" /> {texts.volumes.loading}
        </p>
      ) : (
        <>
          <p className={`text-sm ${read.missing.length === 0 ? "text-slate-500" : "text-amber-800"}`}>
            {read.missing.length === 0
              ? texts.volumes.complete
              : texts.volumes.missing(read.missing.map(String).join(", "))}
          </p>
          {read.volumes.length === 0 ? (
            <p className="text-sm text-slate-500">{texts.volumes.empty}</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {read.volumes.map((volume) => (
                <li key={volume.id} className="flex items-center gap-3 py-2">
                  <Cover
                    src={volume.hasImage ? itemImage(volume.id, volume.imageTag, 120) : null}
                    label={volume.name}
                    className="h-16 w-11"
                    bare
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">
                      {volume.number === null ? texts.volumes.noNumber : texts.volumes.number(volume.number)}
                      <span className="ml-2 font-normal text-slate-600">{volume.name}</span>
                    </span>
                    <span className="block truncate text-xs text-slate-500">
                      {volume.fileName} · {volume.size === null ? texts.volumes.unknownSize : formatSize(volume.size)}
                    </span>
                  </span>
                  <a
                    href={volumeFile(volume.id)}
                    download={volume.fileName}
                    aria-label={texts.volumes.downloadLabel(volume.fileName)}
                    className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    {texts.volumes.download}
                  </a>
                  <button
                    type="button"
                    aria-label={texts.volumes.editLabel(volume.name)}
                    onClick={() => {
                      setEditing(volume);
                    }}
                    className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
                  >
                    {texts.volumes.edit}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {editing === null ? null : (
        <VolumeEditor
          volume={editing}
          onClose={() => {
            setEditing(null);
          }}
          onApplied={replace}
        />
      )}
    </section>
  );
}
