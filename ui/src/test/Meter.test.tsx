import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConfidenceMeter, ScoreTicks, scoreTone } from "../components/Meter";
import type { Policy } from "../lib/types";

const policy: Policy = {
  thresholds: { auto_reply: 0.9, review: 0.55, weak_retrieval_floor: 0.4 },
  composite_weights: { judge: 0.5, classifier: 0.3, retrieval: 0.2 },
  models: {},
  max_tickets_per_day: 50,
};

/** The meter encodes routing policy visually, so it must read the threshold from the server. */
describe("ConfidenceMeter", () => {
  it("labels the value and the threshold it is measured against", () => {
    render(<ConfidenceMeter value={0.78} policy={policy} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "confidence 0.78, auto-reply threshold 0.9",
    );
  });

  it("draws the notch where the policy says, not at a hardcoded 0.9", () => {
    const shifted: Policy = {
      ...policy,
      thresholds: { ...policy.thresholds, auto_reply: 0.75 },
    };
    render(<ConfidenceMeter value={0.8} policy={shifted} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "confidence 0.80, auto-reply threshold 0.75",
    );
  });

  it("renders a dash when there is no score, rather than 0.00", () => {
    // No composite when classification failed; showing 0.00 would read as "scored zero".
    render(<ConfidenceMeter value={null} policy={policy} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("treats a value exactly on the threshold as clearing it", () => {
    // decide_route uses >=, so 0.90 auto-replies. The meter must agree.
    const { container } = render(<ConfidenceMeter value={0.9} policy={policy} />);
    expect(container.querySelector(".bg-teal-fill")).not.toBeNull();
  });

  it("colours the review band and the escalate band differently", () => {
    const review = render(<ConfidenceMeter value={0.7} policy={policy} />);
    expect(review.container.querySelector(".bg-mustard-fill")).not.toBeNull();

    const escalate = render(<ConfidenceMeter value={0.3} policy={policy} />);
    expect(escalate.container.querySelector(".bg-rust-fill")).not.toBeNull();
  });

  it("falls back to sane defaults before /policy has loaded", () => {
    render(<ConfidenceMeter value={0.95} policy={undefined} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "confidence 0.95, auto-reply threshold 0.9",
    );
  });
});

describe("ScoreTicks", () => {
  it("fills one tick per point and leaves the rest empty", () => {
    const { container } = render(<ScoreTicks value={3} tone="mustard" />);
    expect(container.querySelectorAll(".bg-mustard-fill")).toHaveLength(3);
    expect(container.querySelectorAll(".bg-paper-3")).toHaveLength(2);
  });

  it("is announced as a score rather than as five shapes", () => {
    render(<ScoreTicks value={2} tone="rust" />);
    expect(screen.getByLabelText("2 of 5")).toBeInTheDocument();
  });
});

describe("scoreTone", () => {
  it("maps judge sub-scores onto the shared semantic palette", () => {
    expect(scoreTone(5)).toBe("teal");
    expect(scoreTone(4)).toBe("teal");
    expect(scoreTone(3)).toBe("mustard");
    expect(scoreTone(2)).toBe("rust");
  });
});
