import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";

import "./index.css";
import DemoKey from "./components/DemoKey";
import StatusBanner from "./components/StatusBanner";
import ThemeToggle from "./components/ThemeToggle";
import Audit from "./routes/Audit";
import Evals from "./routes/Evals";
import Queues from "./routes/Queues";
import Submit from "./routes/Submit";
import TicketReview from "./routes/TicketReview";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const NAV = [
  { to: "/", label: "queues", end: true },
  { to: "/evals", label: "evals", end: false },
  { to: "/audit", label: "audit", end: false },
  { to: "/submit", label: "submit", end: false },
];

function navClass({ isActive }: { isActive: boolean }) {
  return [
    "border-b-2 pb-1 text-sm transition-colors",
    isActive
      ? "border-teal text-ink"
      : "border-transparent text-ink-3 hover:text-ink",
  ].join(" ");
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-rule bg-paper-2">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-6 py-4">
          <span className="flex items-baseline gap-2">
            {/* The mark is the routing decision in miniature: three lanes, one
                of them chosen. */}
            <span aria-hidden className="flex items-end gap-[2px]">
              <span className="h-2.5 w-[3px] bg-teal-fill" />
              <span className="h-4 w-[3px] bg-mustard-fill" />
              <span className="h-1.5 w-[3px] bg-rust-fill" />
            </span>
            <span className="text-sm font-semibold tracking-tight">support triage</span>
          </span>

          <nav className="flex items-end gap-4">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={navClass}>
                {n.label}
              </NavLink>
            ))}
          </nav>

          <span className="ml-auto flex items-center gap-2">
            <DemoKey />
            <ThemeToggle />
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <StatusBanner />
        {children}
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-10 pt-4">
        <p className="prose-human text-xs text-ink-3">
          An LLM agent triages each ticket, a second model on a different vendor grades
          the draft, and fixed policy decides who handles it. Reading is open; submitting
          a ticket or recording a review spends a pipeline run and needs a key.
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
            <Route path="/" element={<Queues />} />
            <Route path="/tickets/:id" element={<TicketReview />} />
            <Route path="/evals" element={<Evals />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/submit" element={<Submit />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
