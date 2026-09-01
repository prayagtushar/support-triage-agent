import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Diff } from "../components/Diff";

/** What a reviewer changed is the labelled signal; two paragraphs side by side is not. */
describe("Diff", () => {
  it("marks a replaced word on both sides", () => {
    const { container } = render(
      <Diff before="your refund is processing" after="your refund is complete" />,
    );
    expect(container.querySelector("del")).toHaveTextContent("processing");
    expect(container.querySelector("ins")).toHaveTextContent("complete");
  });

  it("keeps the unchanged text once, not twice", () => {
    const { container } = render(<Diff before="a b c" after="a x c" />);
    expect(container.textContent).toBe("a bx c");
  });

  it("shows an insertion with nothing deleted", () => {
    const { container } = render(<Diff before="sorry about that" after="very sorry about that" />);
    expect(container.querySelector("ins")).toHaveTextContent("very");
    expect(container.querySelector("del")).toBeNull();
  });

  it("says so plainly when the reviewer has not changed anything", () => {
    render(<Diff before="identical text" after="identical text" />);
    expect(screen.getByText("No change yet.")).toBeInTheDocument();
  });
});
