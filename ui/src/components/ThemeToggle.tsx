import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const STORAGE = "triage-theme";

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    // Private windows and blocked site data both throw. The OS still has an opinion.
    return null;
  }
}

/**
 * Light or dark, nothing else.
 *
 * There used to be a third state called "auto" that a reader had to cycle through and
 * could not interpret: the word named a policy while the other two named a colour. The
 * automatic part is still here, it just stopped being a thing to click. The page opens
 * wherever the operating system is and follows it until someone decides otherwise.
 *
 * The label is the theme you get by clicking, not the one you are in. A button reading
 * "light" while the page is already light is a button with nothing to do.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());
  const [chosen, setChosen] = useState(() => stored() !== null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (chosen) return;
    // Nobody has picked, so the OS is still in charge, including when it flips at sunset.
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => setTheme(query.matches ? "dark" : "light");
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, [chosen]);

  const other: Theme = theme === "dark" ? "light" : "dark";

  return (
    <button
      onClick={() => {
        setTheme(other);
        setChosen(true);
        try {
          localStorage.setItem(STORAGE, other);
        } catch {
          /* the choice still holds for this visit */
        }
      }}
      className="rounded-[2px] border border-rule px-2 py-1 text-[11px] text-ink-2 transition-colors hover:border-rule-2 hover:text-ink"
      title={`Switch to ${other} mode`}
      aria-label={`Switch to ${other} mode`}
    >
      {other}
    </button>
  );
}
