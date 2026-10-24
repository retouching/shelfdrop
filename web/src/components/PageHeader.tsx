import type { ReactElement } from "react";

import { texts } from "../texts";

type Props = {
  readonly section: string;
  readonly title: string;
  readonly lead: string;
};

export function PageHeader({ section, title, lead }: Props): ReactElement {
  return (
    <header className="bg-band px-4 pt-5 pb-6 md:px-10 md:pt-6 md:pb-8">
      <nav aria-label={texts.nav.breadcrumb} className="hidden text-sm text-slate-500 md:block">
        <span>{section}</span>
        <span className="px-2">›</span>
        <span className="text-ink">{title}</span>
      </nav>
      <h1 className="text-2xl font-semibold break-words text-ink md:mt-5 md:text-3xl">{title}</h1>
      <p className="mt-2 text-slate-600">{lead}</p>
    </header>
  );
}
