import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";
const STORAGE = "triage-theme";

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

/** Light, dark, or follow the OS. "system" unsets the attribute so the OS keeps winning. */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem(STORAGE) as Theme | null) ?? "system",
  );

  useEffect(() => {
    apply(theme);
    if (theme === "system") localStorage.removeItem(STORAGE);
    else localStorage.setItem(STORAGE, theme);
  }, [theme]);

  const next: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
  const label: Record<Theme, string> = { system: "auto", light: "light", dark: "dark" };

  return (
    <button
      onClick={() => setTheme(next[theme])}
      className="rounded-[2px] border border-rule px-2 py-1 text-[11px] text-ink-2 transition-colors hover:border-rule-2 hover:text-ink"
      title={`Theme: ${label[theme]}. Click to change.`}
      aria-label={`Theme: ${label[theme]}. Click to change.`}
    >
      {label[theme]}
    </button>
  );
}
