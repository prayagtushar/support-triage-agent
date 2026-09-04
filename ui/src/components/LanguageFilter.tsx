import { useLanguage, type Language } from "../lib/domain";

/**
 * Which languages to show.
 *
 * The corpus is English and Hinglish, and the classifier records which one each ticket
 * came in as. Someone who cannot read Hinglish cannot judge those drafts, so this exists
 * for them. It filters server side, so the rail's lane counts move with it.
 *
 * The default is every language, deliberately. Defaulting to English would hide the
 * thing worth showing: the same pipeline handling both without a translation step.
 */
const OPTIONS: readonly { value: Language; label: string; short: string }[] = [
  { value: "", label: "all", short: "all" },
  { value: "en", label: "English", short: "EN" },
  // Devanagari and romanised Hindi are one choice here. Hinglish is Hindi typed in
  // Latin script, and a reader who wants one wants the other.
  { value: "hi", label: "Hindi", short: "हि" },
];

export default function LanguageFilter() {
  const { lang, setLanguage } = useLanguage();

  return (
    <div
      role="group"
      aria-label="Filter tickets by language"
      className="flex shrink-0 overflow-hidden rounded-[2px] border border-rule bg-paper"
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => setLanguage(o.value)}
          aria-pressed={lang === o.value}
          title={o.value ? `Show ${o.label} tickets only` : "Show tickets in every language"}
          className={`px-1.5 py-1.5 text-[11px] transition-colors sm:px-2 ${
            lang === o.value ? "bg-paper-3 text-ink" : "text-ink-3 hover:text-ink-2"
          }`}
        >
          <span className="sm:hidden">{o.short}</span>
          <span className="hidden sm:inline">{o.label}</span>
        </button>
      ))}
    </div>
  );
}
