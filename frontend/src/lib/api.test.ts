import { vi, describe, it, expect } from "vitest";

vi.mock("$env/dynamic/public", () => ({ env: {} }));

import { API_BASE, WS_BASE } from "./api";

describe("api", () => {
  it("API_BASE defaults to localhost:8000", () => {
    expect(API_BASE).toBe("http://localhost:8000");
  });

  it("WS_BASE defaults to ws://localhost:8000", () => {
    expect(WS_BASE).toBe("ws://localhost:8000");
  });

  it("createSession posts to /sessions", async () => {
    const mockResponse = { session_id: "abc", join_urls: {} };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      }),
    );

    const { createSession } = await import("./api");
    const result = await createSession();

    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "http://localhost:8000/sessions",
      { method: "POST" },
    );
    expect(result).toEqual(mockResponse);

    vi.unstubAllGlobals();
  });

  it("createSession throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500 }),
    );

    const { createSession } = await import("./api");
    await expect(createSession()).rejects.toThrow("Failed to create session");

    vi.unstubAllGlobals();
  });
});
