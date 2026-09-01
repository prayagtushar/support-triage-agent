/**
 * Word-level diff between the drafted reply and what the reviewer is about to send.
 * The edit is the signal worth keeping, and "here are two paragraphs, spot the change"
 * does not show it.
 */

type Span = { text: string; kind: "same" | "added" | "removed" };

function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter(Boolean);
}

/** Longest common subsequence over words. The texts being compared are one reply long. */
function diff(before: string[], after: string[]): Span[] {
  const table: number[][] = Array.from({ length: before.length + 1 }, () =>
    new Array(after.length + 1).fill(0),
  );

  for (let i = before.length - 1; i >= 0; i--) {
    for (let j = after.length - 1; j >= 0; j--) {
      table[i][j] =
        before[i] === after[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }

  const spans: Span[] = [];
  let i = 0;
  let j = 0;
  while (i < before.length && j < after.length) {
    if (before[i] === after[j]) {
      spans.push({ text: before[i], kind: "same" });
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      spans.push({ text: before[i], kind: "removed" });
      i++;
    } else {
      spans.push({ text: after[j], kind: "added" });
      j++;
    }
  }
  while (i < before.length) spans.push({ text: before[i++], kind: "removed" });
  while (j < after.length) spans.push({ text: after[j++], kind: "added" });

  return spans;
}

export function Diff({ before, after }: { before: string; after: string }) {
  const spans = diff(tokenize(before), tokenize(after));
  const changed = spans.filter((s) => s.kind !== "same").length;

  if (changed === 0) {
    return <p className="text-xs text-ink-3">No change yet.</p>;
  }

  return (
    <p className="prose-human rounded-[2px] border border-rule bg-paper-2 p-3 text-sm leading-relaxed whitespace-pre-wrap">
      {spans.map((span, i) =>
        span.kind === "same" ? (
          <span key={i}>{span.text}</span>
        ) : span.kind === "removed" ? (
          <del key={i} className="bg-rust-bg text-rust decoration-rust/50">
            {span.text}
          </del>
        ) : (
          <ins key={i} className="bg-olive-bg text-olive no-underline">
            {span.text}
          </ins>
        ),
      )}
    </p>
  );
}
