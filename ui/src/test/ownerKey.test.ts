import { beforeEach, describe, expect, it } from "vitest";

import { ownerKey } from "../lib/ownerKey";

function visit(url: string) {
  window.history.replaceState({}, "", url);
}

describe("ownerKey", () => {
  beforeEach(() => {
    window.localStorage.clear();
    visit("/");
  });

  it("is empty for the visitor it is invisible to", () => {
    expect(ownerKey()).toBe("");
  });

  it("claims the key from the URL and keeps it", () => {
    visit("/?key=s3cret");
    expect(ownerKey()).toBe("s3cret");

    visit("/");
    expect(ownerKey()).toBe("s3cret");
  });

  it("strips the key from the address so it cannot be shared by accident", () => {
    visit("/evals?key=s3cret&tab=sweep");
    ownerKey();

    expect(window.location.search).not.toContain("s3cret");
    expect(window.location.search).toContain("tab=sweep");
    expect(window.location.pathname).toBe("/evals");
  });

  it("lets a new key replace an old one", () => {
    visit("/?key=old");
    ownerKey();

    visit("/?key=new");
    expect(ownerKey()).toBe("new");
  });
});
