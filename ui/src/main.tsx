import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";

import "./index.css";
import Rail from "./components/Rail";
import StatusBanner from "./components/StatusBanner";
import ThemeToggle from "./components/ThemeToggle";
import { LANES } from "./lib/lanes";
import { REPO_URL } from "./lib/links";
import Audit from "./routes/Audit";
import Evals from "./routes/Evals";
import Queues from "./routes/Queues";
import RunIt from "./routes/RunIt";
import Submit from "./routes/Submit";
import TicketReview from "./routes/TicketReview";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function Shell({ children }: { children: React.ReactNode }) {
  // Reviewing a ticket is the one screen where someone is working rather than navigating,
  // and it already carries a sidebar of its own. It gets the full width.
  const focused = useLocation().pathname.startsWith("/tickets/");

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-rule bg-paper-2">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-baseline gap-2">
            {/* The mark is the routing decision in miniature: three lanes, one chosen. */}
            <span aria-hidden className="flex items-end gap-[2px]">
              <span className="h-2.5 w-[3px] bg-teal-fill" />
              <span className="h-4 w-[3px] bg-mustard-fill" />
              <span className="h-1.5 w-[3px] bg-rust-fill" />
            </span>
            <span className="text-sm font-semibold tracking-tight">support triage</span>
          </Link>

          <span className="ml-auto flex items-center gap-3">
            <Link
              to="/submit"
              className="rounded-[2px] bg-teal px-3 py-1.5 text-xs font-medium text-paper transition-opacity hover:opacity-90"
            >
              Send a ticket
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
              {LANES.map((lane) => (
                <Link key={lane.path} to={lane.path} className="whitespace-nowrap text-ink-2">
                  {lane.label}
                </Link>
              ))}
              <Link to="/audit" className="text-ink-2">
                audit
              </Link>
              <Link to="/evals" className="text-ink-2">
                evals
              </Link>
              <Link to="/run-it" className="whitespace-nowrap text-ink-2">
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
          An LLM agent triages each ticket, a second model on a different vendor grades the
          draft, and fixed policy decides who handles it. Everything here is readable without
          an account.{" "}
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
          </Routes>
        </Shell>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
