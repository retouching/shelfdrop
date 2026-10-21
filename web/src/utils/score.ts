// Score d'une release selon les filtres : la somme des points des règles qui la reconnaissent.
import type { EditableRule as FilterRule } from "../state/searchSettings";
import type { Kind } from "../types";

export type RuleMatch = { readonly rule: FilterRule; readonly score: number };
export type Score = { readonly total: number; readonly matches: readonly RuleMatch[] };

function escape(word: string): string {
  return word.replace(/[.*+?^${}()|[\]\\]/gu, String.raw`\$&`);
}

/** La regex d'une règle, ou null quand elle est invalide ou vide. */
export function ruleRegex(rule: FilterRule): RegExp | null {
  const source = rule.regex
    ? rule.pattern
    : rule.pattern
        .split(",")
        .map((word) => word.trim())
        .filter((word) => word !== "")
        .map((word) => String.raw`(?<![\p{L}\p{N}])${escape(word)}(?![\p{L}\p{N}])`)
        .join("|");
  if (source === "") {
    return null;
  }
  try {
    return new RegExp(source, "iu");
  } catch {
    return null;
  }
}

export function scoreTitle(title: string, kind: Kind, rules: readonly FilterRule[]): Score {
  const matches = rules
    .filter((rule) => rule.enabled && (rule.kinds.length === 0 || rule.kinds.includes(kind)))
    .filter((rule) => ruleRegex(rule)?.test(title) === true)
    .map((rule) => ({ rule, score: rule.score }));
  return { total: matches.reduce((sum, match) => sum + match.score, 0), matches };
}

export function formatScore(score: number): string {
  return score > 0 ? `+${String(score)}` : String(score);
}
