import type { ReactElement } from "react";

import { texts } from "../texts";

type Props = {
  readonly section: string;
  readonly title: string;
  readonly lead: string;
};

export function PageHeader({ section, title, lead }: Props): ReactElement {
  return (
    <header className="bg-band px-10 pt-6 pb-8">
      <nav aria-label={texts.nav.breadcrumb} className="text-sm text-slate-500">
        <span>{section}</span>
        <span className="px-2">›</span>
        <span className="text-ink">{title}</span>
      </nav>
      <h1 className="mt-5 text-3xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 text-slate-600">{lead}</p>
    </header>
  );
}
