import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Composite } from "../components/Composite";
import type { Classification, JudgeScores, Policy, Retrieval } from "../lib/types";

const policy: Policy = {
  domain: "a consumer online shopping service",
  thresholds: { auto_reply: 0.9, review: 0.55, weak_retrieval_floor: 0.4 },
  composite_weights: { judge: 0.5, classifier: 0.3, retrieval: 0.2 },
  models: {},
  max_tickets_per_day: 50,
};

const judge: JudgeScores = { groundedness: 5, completeness: 5, tone: 5, notes: "fine" };
const classification: Classification = {
  intent: "billing",
  urgency: "P3",
  language: "en",
  sentiment: "neutral",
  confidence: 0.95,
  rationale: "duplicate charge",
};
const retrieval: Retrieval = { cases: [], weak: false, best_similarity: 0.324 };

/** This panel restates the server's arithmetic, so the tests check the numbers, not markup. */
describe("Composite", () => {
  it("shows each signal's weighted contribution", () => {
    render(
      <Composite
        policy={policy}
        judge={judge}
        classification={classification}
        retrieval={retrieval}
        composite={0.85}
      />,
    );
    // 0.5 x 1.000, 0.3 x 0.950, 0.2 x 0.324
    expect(screen.getByText("0.500")).toBeInTheDocument();
    expect(screen.getByText("0.285")).toBeInTheDocument();
    expect(screen.getByText("0.065")).toBeInTheDocument();
    expect(screen.getByText("0.850")).toBeInTheDocument();
  });

  it("states the distance to the threshold when the score falls short", () => {
    render(
      <Composite
        policy={policy}
        judge={judge}
        classification={classification}
        retrieval={retrieval}
        composite={0.85}
      />,
    );
    expect(
      screen.getByText("0.050 short of the 0.9 auto-reply threshold"),
    ).toBeInTheDocument();
  });

  it("says so when the score clears the threshold", () => {
    render(
      <Composite
        policy={policy}
        judge={judge}
        classification={classification}
        retrieval={retrieval}
        composite={0.92}
      />,
    );
    expect(screen.getByText(/at or above the 0.9 auto-reply threshold/)).toBeInTheDocument();
  });

  it("uses the weights the server reports, not the shipped defaults", () => {
    // The weights should change; hardcoding them here would start lying the moment they did.
    const retuned: Policy = {
      ...policy,
      composite_weights: { judge: 1, classifier: 0, retrieval: 0 },
    };
    render(
      <Composite
        policy={retuned}
        judge={judge}
        classification={classification}
        retrieval={retrieval}
        composite={1}
      />,
    );
    expect(screen.getByText("1.00 × 1.000")).toBeInTheDocument();
    expect(screen.getByText("0.00 × 0.950")).toBeInTheDocument();
  });

  it("renders nothing without a composite, instead of implying a zero", () => {
    const { container } = render(
      <Composite
        policy={policy}
        judge={null}
        classification={null}
        retrieval={null}
        composite={null}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a dash for a signal the pipeline never produced", () => {
    render(
      <Composite
        policy={policy}
        judge={null}
        classification={classification}
        retrieval={retrieval}
        composite={0.35}
      />,
    );
    expect(screen.getByText("0.50 × —")).toBeInTheDocument();
  });
});
