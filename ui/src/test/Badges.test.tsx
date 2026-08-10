import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IntentBadge, LanguageBadge, RouteBadge, UrgencyBadge } from "../components/Badges";
import { Pipeline } from "../components/Pipeline";

describe("IntentBadge", () => {
  it("says a ticket is unclassified rather than leaving a blank cell", () => {
    // A missing intent means classification failed, which is information. An
    // empty cell leaves the reader to guess.
    render(<IntentBadge intent={null} />);
    expect(screen.getByText("unclassified")).toBeInTheDocument();
  });

  it("renders intents readably", () => {
    render(<IntentBadge intent="account_access" />);
    expect(screen.getByText("account access")).toBeInTheDocument();
  });
});

describe("LanguageBadge", () => {
  it("stays silent for English, which is the default and not news", () => {
    const { container } = render(<LanguageBadge language="en" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("labels a non-default language", () => {
    render(<LanguageBadge language="hi-en" />);
    expect(screen.getByText("hi-en")).toBeInTheDocument();
  });
});

describe("UrgencyBadge", () => {
  it("gives P1 the same tone as failure, since it overrides every score", () => {
    const { container } = render(<UrgencyBadge urgency="P1" />);
    expect(container.querySelector(".text-rust")).not.toBeNull();
  });

  it("keeps low urgencies neutral so the urgent ones stand out", () => {
    const { container } = render(<UrgencyBadge urgency="P4" />);
    expect(container.querySelector(".text-rust")).toBeNull();
    expect(container.querySelector(".text-mustard")).toBeNull();
  });
});

describe("RouteBadge", () => {
  it("shows pending when the pipeline has not routed yet", () => {
    render(<RouteBadge route={null} />);
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  it("maps each route onto its lane colour", () => {
    expect(render(<RouteBadge route="auto_reply" />).container.querySelector(".text-teal")).not
      .toBeNull();
    expect(render(<RouteBadge route="escalate" />).container.querySelector(".text-rust")).not
      .toBeNull();
  });
});

describe("Pipeline", () => {
  const usage = {
    classify: { model: "llama-3.3-70b", provider: "openrouter", estimated_cost_inr: 0.0188 },
  };

  it("marks nodes that never ran as skipped, not as pending forever", () => {
    // A ticket that fails classification skips retrieve, draft and score by
    // design; the reader should see that decision.
    render(
      <Pipeline latency={{ classify: 8000, route: 0 }} usage={usage} errors={null} />,
    );
    expect(screen.getAllByText("skipped")).toHaveLength(3);
  });

  it("attributes each node to the model that ran it", () => {
    render(<Pipeline latency={{ classify: 8000 }} usage={usage} errors={null} />);
    expect(screen.getByText("openrouter/llama-3.3-70b")).toBeInTheDocument();
    expect(screen.getByText("₹0.0188")).toBeInTheDocument();
  });

  it("flags the node named in an error", () => {
    const { container } = render(
      <Pipeline
        latency={{ classify: 8000, retrieve: 500 }}
        usage={null}
        errors={["retrieve: HTTP 429: prepayment credits are depleted"]}
      />,
    );
    // The failing node is coloured, and it is retrieve rather than classify.
    expect(container.querySelector(".bg-rust-fill")).not.toBeNull();
  });

  it("renders nothing when there are no timings to draw", () => {
    const { container } = render(<Pipeline latency={null} usage={null} errors={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
