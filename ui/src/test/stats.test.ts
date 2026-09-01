import { describe, expect, it } from "vitest";

import { ageTone } from "../lib/format";
import { formatInterval, wilson } from "../lib/stats";

/** The interval is the point: a proportion measured on ten tickets is not three decimals. */
describe("wilson", () => {
  it("widens as the denominator shrinks", () => {
    const [smallLo, smallHi] = wilson(5, 10);
    const [bigLo, bigHi] = wilson(50, 100);
    expect(smallHi - smallLo).toBeGreaterThan(bigHi - bigLo);
  });

  it("stays inside [0, 1] at the extremes, where the normal approximation does not", () => {
    const [lo, hi] = wilson(10, 10);
    expect(lo).toBeGreaterThan(0);
    expect(hi).toBeLessThanOrEqual(1);
    expect(wilson(0, 10)[0]).toBe(0);
  });

  it("brackets the observed proportion", () => {
    const [lo, hi] = wilson(5, 10);
    expect(lo).toBeLessThan(0.5);
    expect(hi).toBeGreaterThan(0.5);
  });

  it("admits it knows nothing with no observations", () => {
    expect(wilson(0, 0)).toEqual([0, 1]);
  });
});

describe("formatInterval", () => {
  it("reads the eval report's own n/d detail string", () => {
    expect(formatInterval("5/10")).toMatch(/95% CI 0\.2\d–0\.7\d · n=10/);
  });

  it("returns null rather than a fake interval when there is no detail", () => {
    expect(formatInterval(undefined)).toBeNull();
    expect(formatInterval("most of them")).toBeNull();
  });
});

/** Age in a queue is a risk signal, and the window that makes it one depends on priority. */
describe("ageTone", () => {
  const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

  it("stays neutral inside the window for the priority", () => {
    expect(ageTone(hoursAgo(2), "P1")).toBe("text-ink-3");
    expect(ageTone(hoursAgo(20), "P2")).toBe("text-ink-3");
  });

  it("warns past the window and escalates at twice it", () => {
    expect(ageTone(hoursAgo(6), "P1")).toBe("text-mustard");
    expect(ageTone(hoursAgo(10), "P1")).toBe("text-rust");
  });

  it("holds a P4 to a longer window than a P1 at the same age", () => {
    expect(ageTone(hoursAgo(30), "P1")).toBe("text-rust");
    expect(ageTone(hoursAgo(30), "P4")).toBe("text-ink-3");
  });

  it("says nothing about a ticket that was never classified", () => {
    expect(ageTone(hoursAgo(500), null)).toBe("text-ink-3");
  });
});
