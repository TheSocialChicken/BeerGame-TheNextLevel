import { test, expect } from "@playwright/test";

test.describe("Beer Game Lobby", () => {
  test("lobby page renders correctly", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Beer Game");
    await expect(page.getByRole("button", { name: "New Game" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Join" })).toBeVisible();
    await expect(page.getByPlaceholder("Session ID")).toBeVisible();
  });

  test("new game button calls POST /sessions and redirects to game board", async ({
    page,
  }) => {
    const fakeSessionId = "test-session-abc123";

    // Intercept the API call
    await page.route("**/sessions", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: fakeSessionId,
          join_urls: {
            retailer: `/ws/${fakeSessionId}/retailer`,
            wholesaler: `/ws/${fakeSessionId}/wholesaler`,
            distributor: `/ws/${fakeSessionId}/distributor`,
            factory: `/ws/${fakeSessionId}/factory`,
          },
        }),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "New Game" }).click();

    // Should navigate to the game board for retailer
    await page.waitForURL(`**/game/${fakeSessionId}/retailer`);
    expect(page.url()).toContain(`/game/${fakeSessionId}/retailer`);
  });

  test("join game navigates to the correct role page", async ({ page }) => {
    const sessionId = "existing-game-xyz";

    await page.goto("/");
    await page.getByPlaceholder("Session ID").fill(sessionId);

    // Select wholesaler from the role dropdown
    await page.selectOption("select", "wholesaler");
    await page.getByRole("button", { name: "Join" }).click();

    await page.waitForURL(`**/game/${sessionId}/wholesaler`);
    expect(page.url()).toContain(`/game/${sessionId}/wholesaler`);
  });
});
