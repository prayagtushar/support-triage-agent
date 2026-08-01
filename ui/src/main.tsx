import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";

import "./index.css";
import Audit from "./routes/Audit";
import Queues from "./routes/Queues";
import TicketReview from "./routes/TicketReview";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function navClass({ isActive }: { isActive: boolean }) {
  return isActive
    ? "text-neutral-900 dark:text-neutral-100"
    : "text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-300";
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <header className="border-b border-neutral-200 dark:border-neutral-800">
        <div className="mx-auto flex max-w-5xl items-baseline gap-6 px-6 py-4">
          <span className="font-semibold">Support triage</span>
          <nav className="flex gap-4 text-sm">
            <NavLink to="/" end className={navClass}>Queues</NavLink>
            <NavLink to="/audit" className={navClass}>Audit</NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
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
            <Route path="/audit" element={<Audit />} />
          </Routes>
        </Shell>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
