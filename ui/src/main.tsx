import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";

import "./index.css";
import Rail from "./components/Rail";
import StatusBanner from "./components/StatusBanner";
import CommandPalette from "./components/CommandPalette";
import DomainSwitcher from "./components/DomainSwitcher";
import LanguageFilter from "./components/LanguageFilter";
import ThemeToggle from "./components/ThemeToggle";
import { ToastProvider } from "./components/Toast";
import { LANES } from "./lib/lanes";
import { REPO_URL } from "./lib/links";
import { useDomain, withDomain } from "./lib/domain";
import { usePolicy } from "./lib/usePolicy";
import Audit from "./routes/Audit";
import Evals from "./routes/Evals";
import Queues from "./routes/Queues";
import RunIt from "./routes/RunIt";
import Submit from "./routes/Submit";
import TicketReview from "./routes/TicketReview";
import Desks from "./routes/Desks";
import Voice from "./routes/Voice";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

/** "a consumer online shopping service" reads as a label once the article is gone. */
function withoutArticle(domain: string): string {
  return domain.replace(/^(a|an|the)\s+/i, "");
}

function Shell({ children }: { children: React.ReactNode }) {
  // Reviewing a ticket is the one screen where someone is working rather than navigating,
  // and it already carries a sidebar of its own. It gets the full width.
  const focused = useLocation().pathname.startsWith("/tickets/");
  const policy = usePolicy();
  const { id: domainId, domain } = useDomain();

  return (
    <div className="min-h-screen bg-paper text-ink">
      <CommandPalette />
      <header className="border-b border-rule bg-paper-2">
        {/* Wraps rather than shrinks: with the language filter added, a phone had five
            controls on one line and squeezed the wordmark down to the mark alone. */}
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-3 sm:gap-4 sm:px-6">
          <Link to="/" className="flex min-w-0 shrink-0 items-baseline gap-2">
            {/* The mark is the routing decision in miniature: three lanes, one chosen. */}
            <span aria-hidden className="flex items-end gap-[2px]">
              <span className="h-2.5 w-[3px] bg-teal-fill" />
              <span className="h-4 w-[3px] bg-mustard-fill" />
              <span className="h-1.5 w-[3px] bg-rust-fill" />
            </span>
            <span className="truncate text-sm font-semibold tracking-tight">support triage</span>
            {(domain?.description ?? policy?.domain) && (
              <span className="hidden text-xs text-ink-3 sm:inline">
                <span aria-hidden>·</span>{" "}
                {withoutArticle(domain?.description ?? policy?.domain ?? "")}
              </span>
            )}
          </Link>

          <span className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
            <LanguageFilter />
            <DomainSwitcher />
            <Link
              to="/submit"
              className="whitespace-nowrap rounded-[2px] bg-teal px-2.5 py-1.5 text-xs font-medium text-paper transition-opacity hover:opacity-90 sm:px-3"
            >
              {/* "Send a ticket" costs a line of header on a phone and says the same thing. */}
              <span className="sm:hidden">Send</span>
              <span className="hidden sm:inline">Send a ticket</span>
            </Link>
            <ThemeToggle />
          </span>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-8 px-4 py-8 sm:px-6">
        {!focused && (
          <aside className="hidden w-48 shrink-0 lg:block">
            <div className="sticky top-8 h-[calc(100vh-6rem)]">
              <Rail />
            </div>
          </aside>
        )}

        <main className="min-w-0 flex-1">
          {/* Below lg the rail is gone, so the lanes come back as a row of links. */}
          {!focused && (
            <nav
              aria-label="Sections"
              className="-mx-4 mb-6 flex gap-4 overflow-x-auto border-b border-rule px-4 pb-2 text-sm lg:hidden"
            >
              {/* Through withDomain like the rail's links, so the desk and the language
                  filter survive a tap rather than being dropped out of the URL. */}
              {LANES.map((lane) => (
                <Link
                  key={lane.path}
                  to={withDomain(lane.path, domainId)}
                  className="whitespace-nowrap text-ink-2"
                >
                  {lane.label}
                </Link>
              ))}
              <Link to={withDomain("/audit", domainId)} className="text-ink-2">
                audit
              </Link>
              <Link to={withDomain("/evals", domainId)} className="text-ink-2">
                evals
              </Link>
              <Link to={withDomain("/desks", domainId)} className="text-ink-2">
                desks
              </Link>
              <Link to={withDomain("/voice", domainId)} className="text-ink-2">
                voice
              </Link>
              <Link to={withDomain("/run-it", domainId)} className="whitespace-nowrap text-ink-2">
                run it
              </Link>
            </nav>
          )}

          <StatusBanner />
          {children}
        </main>
      </div>

      <footer className="mx-auto max-w-7xl px-4 pb-10 pt-4 sm:px-6">
        <p className="prose-human max-w-3xl text-xs text-ink-3">
          The tickets are {policy?.domain ?? "a consumer online shopping service"}'s, in
          English and Hinglish. More than one desk runs here, each with its own corpus and
          taxonomy. An LLM agent triages each one, a second model on a different
          vendor grades the draft, and fixed policy decides who handles it. Everything here is
          readable without an account.{" "}
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="hover:text-ink">
            Source
          </a>
          .
        </p>
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <Shell>
          <Routes>
            {LANES.map((lane) => (
              <Route key={lane.path} path={lane.path} element={<Queues lane={lane} />} />
            ))}
            <Route path="/tickets/:id" element={<TicketReview />} />
            <Route path="/evals" element={<Evals />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/submit" element={<Submit />} />
            <Route path="/run-it" element={<RunIt />} />
            <Route path="/voice" element={<Voice />} />
            <Route path="/desks" element={<Desks />} />
          </Routes>
          </Shell>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
