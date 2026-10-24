import { useState, type ReactElement, type SubmitEvent } from "react";

import { texts } from "../texts";
import { ShelfIcon } from "./icons";
import { Spinner } from "./Skeletons";
import { signIn } from "../api/session";

type Props = {
  readonly onSignedIn: (username: string) => void;
};

const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

export function LoginPage({ onSignedIn }: Props): ReactElement {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [refused, setRefused] = useState(false);

  async function send(): Promise<void> {
    setPending(true);
    setRefused(false);
    try {
      onSignedIn(await signIn(username.trim(), password));
    } catch {
      // Refus, trop d'essais ou Jellyfin injoignable : le même message, sans détail.
      setRefused(true);
      setPending(false);
    }
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void send();
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-band px-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-surface p-8 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-white">
            <ShelfIcon className="size-5" />
          </span>
          <span>
            <span className="block text-lg leading-tight font-semibold text-ink">{texts.appName}</span>
            <span className="block text-sm text-slate-500">{texts.appTagline}</span>
          </span>
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink">{texts.login.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{texts.login.hint}</p>
        </div>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">{texts.login.username}</span>
          <input
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
            }}
            autoComplete="username"
            required
            className={field}
          />
        </label>
        <label className="block space-y-1.5">
          <span className="text-sm font-medium text-ink">{texts.login.password}</span>
          <input
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
            autoComplete="current-password"
            required
            className={field}
          />
        </label>
        {refused ? (
          <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {texts.login.refused}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={pending}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-transparent bg-accent px-4 py-2.5 font-medium text-white hover:bg-accent-strong disabled:cursor-wait disabled:opacity-80"
        >
          {pending ? <Spinner /> : null}
          {pending ? texts.loading.signingIn : texts.login.submit}
        </button>
      </form>
    </main>
  );
}
