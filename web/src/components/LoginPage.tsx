import { useState, type ReactElement, type SubmitEvent } from "react";

import { texts } from "../texts";
import { ShelfIcon } from "./icons";
import { Spinner } from "./Skeletons";
import { wait } from "../mock/latency";

type Props = {
  readonly onSignedIn: (username: string) => void;
};

const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring";

export function LoginPage({ onSignedIn }: Props): ReactElement {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  async function signIn(): Promise<void> {
    setPending(true);
    await wait(800);
    onSignedIn(username.trim() === "" ? "sylvain" : username.trim());
  }

  function submit(event: SubmitEvent<HTMLFormElement>): void {
    event.preventDefault();
    void signIn();
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
            className={field}
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="hover:bg-accent-strong-strong flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 font-medium text-white disabled:cursor-wait disabled:opacity-80"
        >
          {pending ? <Spinner /> : null}
          {pending ? texts.loading.signingIn : texts.login.submit}
        </button>
      </form>
    </main>
  );
}
