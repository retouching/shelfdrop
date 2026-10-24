import { useEffect, useState, type ReactElement } from "react";

import {
  loadSearchSettings,
  newRuleId,
  setFilters,
  useSearchSettings,
  type EditableFilters,
  type EditableRule as FilterRule,
} from "../../state/searchSettings";
import { texts } from "../../texts";
import type { Kind } from "../../types";
import { formatScore, ruleRegex, scoreTitle } from "../../utils/score";
import { stacked } from "../stacked";
import { Card, Field, input } from "./parts";

const kinds: readonly Kind[] = ["manga", "ebook", "audiobook"];
const NONE: EditableFilters = { rules: [], minimum: 0 };

export function FiltersTab(): ReactElement {
  const filters = useSearchSettings().filters ?? NONE;
  const [sample, setSample] = useState("Chainsaw.Man.T23.FRENCH.CBZ.eBook-Paprika+");
  const [sampleKind, setSampleKind] = useState<Kind>("manga");

  function update(id: string, change: Partial<FilterRule>): void {
    setFilters({ ...filters, rules: filters.rules.map((rule) => (rule.id === id ? { ...rule, ...change } : rule)) });
  }

  useEffect(() => {
    // Une erreur de lecture laisse la rubrique vide ; « Enregistrer » ne l'écrase pas.
    loadSearchSettings().catch(() => undefined);
  }, []);

  const tested = scoreTitle(sample, sampleKind, filters.rules);

  return (
    <div className="space-y-4">
      <Card title={texts.filters.title} hint={texts.filters.hint}>
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className={stacked.table}>
            <thead className={stacked.head}>
              <tr>
                <th scope="col" className="w-16 px-3 py-2 font-semibold">
                  {texts.filters.enabled}
                </th>
                <th scope="col" className="w-44 px-3 py-2 font-semibold">
                  {texts.filters.name}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {texts.filters.pattern}
                </th>
                <th scope="col" className="w-24 px-3 py-2 font-semibold">
                  {texts.filters.points}
                </th>
                <th scope="col" className="w-36 px-3 py-2 font-semibold">
                  {texts.filters.kinds}
                </th>
                <th scope="col" className="w-10 px-3 py-2">
                  <span className="sr-only">{texts.filters.remove("")}</span>
                </th>
              </tr>
            </thead>
            <tbody className={stacked.body}>
              {filters.rules.map((rule) => {
                const invalid = rule.pattern !== "" && ruleRegex(rule) === null;
                return (
                  <tr key={rule.id} className={`${stacked.row} ${rule.enabled ? "" : "opacity-50"}`}>
                    <td className={`${stacked.cell} order-first md:px-3 md:py-2`}>
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        aria-label={`${texts.filters.enabled} : ${rule.name}`}
                        onChange={(event) => {
                          update(rule.id, { enabled: event.target.checked });
                        }}
                        className="size-4 accent-accent"
                      />
                    </td>
                    <td className={`${stacked.cell} order-first flex-1 md:px-3 md:py-2`}>
                      <input
                        value={rule.name}
                        aria-label={texts.filters.name}
                        onChange={(event) => {
                          update(rule.id, { name: event.target.value });
                        }}
                        className={input}
                      />
                    </td>
                    <td className={`${stacked.cell} basis-full md:px-3 md:py-2`}>
                      <span className="flex gap-2">
                        <span className="w-28 shrink-0 md:w-24">
                          <select
                            value={rule.regex ? "regex" : "words"}
                            aria-label={`${texts.filters.words} / ${texts.filters.regex}`}
                            onChange={(event) => {
                              update(rule.id, { regex: event.target.value === "regex" });
                            }}
                            className={input}
                          >
                            <option value="words">{texts.filters.words}</option>
                            <option value="regex">{texts.filters.regex}</option>
                          </select>
                        </span>
                        <input
                          value={rule.pattern}
                          aria-label={texts.filters.pattern}
                          aria-invalid={invalid}
                          placeholder={rule.regex ? texts.filters.regexPlaceholder : texts.filters.wordsPlaceholder}
                          onChange={(event) => {
                            update(rule.id, { pattern: event.target.value });
                          }}
                          className={`${input} font-mono text-xs ${invalid ? "border-rose-400" : ""}`}
                        />
                      </span>
                      {invalid ? (
                        <span className="mt-1 block text-xs text-rose-700">{texts.filters.invalid}</span>
                      ) : null}
                    </td>
                    <td className={`${stacked.cell} w-28 md:w-auto md:px-3 md:py-2`}>
                      <span className={`${stacked.label} block text-xs`}>{texts.filters.points}</span>
                      <input
                        type="number"
                        step={5}
                        value={rule.score}
                        aria-label={texts.filters.points}
                        onChange={(event) => {
                          update(rule.id, { score: Number(event.target.value) });
                        }}
                        className={`${input} tabular-nums`}
                      />
                    </td>
                    <td className={`${stacked.cell} flex-1 md:px-3 md:py-2`}>
                      <span className={`${stacked.label} block text-xs`}>{texts.filters.kinds}</span>
                      <select
                        value={rule.kinds.length === 1 ? rule.kinds[0] : "all"}
                        aria-label={texts.filters.kinds}
                        onChange={(event) => {
                          const value = event.target.value;
                          update(rule.id, {
                            kinds: kinds.includes(value as Kind) ? [value as Kind] : [],
                          });
                        }}
                        className={input}
                      >
                        <option value="all">{texts.filters.allKinds}</option>
                        {kinds.map((kind) => (
                          <option key={kind} value={kind}>
                            {texts.kinds[kind]}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className={`${stacked.cell} order-first md:px-3 md:py-2 md:text-right`}>
                      <button
                        type="button"
                        aria-label={texts.filters.remove(rule.name)}
                        onClick={() => {
                          setFilters({ ...filters, rules: filters.rules.filter((other) => other.id !== rule.id) });
                        }}
                        className="rounded px-2 py-1 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <button
          type="button"
          onClick={() => {
            setFilters({
              ...filters,
              rules: [
                ...filters.rules,
                {
                  id: newRuleId(),
                  name: "",
                  pattern: "",
                  regex: false,
                  score: 0,
                  kinds: [],
                  enabled: true,
                },
              ],
            });
          }}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50"
        >
          {texts.filters.add}
        </button>
        <div className="max-w-xs">
          <Field label={texts.filters.minimum} hint={texts.filters.minimumHint}>
            <input
              type="number"
              step={10}
              value={filters.minimum}
              onChange={(event) => {
                setFilters({ ...filters, minimum: Number(event.target.value) });
              }}
              className={`${input} tabular-nums`}
            />
          </Field>
        </div>
      </Card>

      <Card title={texts.filters.test}>
        <div className="flex flex-wrap gap-2">
          <input
            value={sample}
            onChange={(event) => {
              setSample(event.target.value);
            }}
            placeholder={texts.filters.testPlaceholder}
            aria-label={texts.filters.testPlaceholder}
            className={`${input} min-w-0 flex-1 font-mono text-xs`}
          />
          <select
            value={sampleKind}
            aria-label={texts.filters.kinds}
            onChange={(event) => {
              setSampleKind(event.target.value as Kind);
            }}
            className={`${input} w-36`}
          >
            {kinds.map((kind) => (
              <option key={kind} value={kind}>
                {texts.kinds[kind]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span
            className={`rounded-md px-2 py-0.5 font-medium tabular-nums ${
              tested.total < filters.minimum ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"
            }`}
          >
            {texts.filters.testResult(formatScore(tested.total))}
            {tested.total < filters.minimum ? ` · ${texts.filters.testRejected}` : ""}
          </span>
          {tested.matches.map((match) => (
            <span key={match.rule.id} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {match.rule.name} {formatScore(match.score)}
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
}
