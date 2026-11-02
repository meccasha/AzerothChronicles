import { expect, test } from "@playwright/test";

/**
 * Full MVP workflow through the real UI and API:
 * register -> create private group -> import simulated game events -> timeline, statistics, Hall of Fame.
 */
test("group creation, event ingestion and derived views", async ({ page }) => {
  const stamp = Date.now();
  await page.goto("/register");
  await page.getByLabel("Display name").fill("E2E Hero");
  await page.getByLabel("Email").fill(`e2e-${stamp}@example.com`);
  await page.getByLabel("Password").fill("a very long e2e password");
  await page.getByRole("button", { name: "Create account" }).click();

  await page.waitForURL("**/groups/new");
  await page.getByLabel("Group name").fill(`E2E Wayfarers ${stamp}`);
  await page.getByLabel("Description").fill("Created by Playwright");
  await page.getByRole("button", { name: "Create group" }).click();
  await page.waitForURL(/\/g\/[0-9a-f-]+$/);
  await expect(page.getByText("Your chronicle is empty")).toBeVisible();
  const base = page.url();

  // Import simulated, normalized game events (clearly labelled as simulated)
  await page.goto(`${base}/integrations`);
  await page.getByRole("tab", { name: "Paste export / JSON" }).click();
  await page.getByTestId("load-sample").click();
  await expect(page.getByLabel("Import data")).toHaveValue(/simulated/);
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByTestId("import-result")).toContainText("4 normalized");

  // Importing the same data again is a no-op
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByTestId("import-result")).toContainText("4 duplicates");

  // Timeline shows the de-duplicated kill as a milestone
  await page.goto(`${base}/timeline`);
  await expect(page.getByRole("link", { name: "Simulated Sentinel defeated" })).toBeVisible();
  await expect(page.getByText("after 1 recorded wipe")).toBeVisible();
  await expect(page.getByRole("link", { name: "Simulated Blade of Testing" })).toBeVisible();

  // Manual memory
  await page.getByRole("button", { name: "Add memory" }).click();
  await page.getByLabel("Title").fill("We named the raid bot Gerald");
  await page.getByRole("button", { name: "Add to timeline" }).click();
  await expect(page.getByRole("link", { name: "We named the raid bot Gerald" })).toBeVisible();

  // Statistics are backed by the database
  await page.goto(`${base}/stats`);
  const kills = page.locator("div", { has: page.getByText("Boss kills", { exact: true }) }).filter({ hasText: "confirmed" }).first();
  await expect(kills).toContainText("1");
  await expect(page.getByText("Simulated Sentinel").first()).toBeVisible();

  // Hall of Fame computes awards automatically
  await page.goto(`${base}/hall-of-fame`);
  const goblin = page.locator("div.flex.flex-col", { has: page.getByRole("heading", { name: "Loot Goblin" }) }).first();
  await expect(goblin).toContainText("E2E Hero");

  // Loot Museum
  await page.goto(`${base}/loot`);
  await expect(page.getByTestId("loot-card").first()).toContainText("Simulated Blade of Testing");
});

test("demo group is browsable and private data stays private @mobile", async ({ page, request }) => {
  await page.goto("/");
  await page.getByTestId("enter-demo").click();
  await page.waitForURL(/\/g\//);
  await expect(page.getByText("Demo mode").first()).toBeVisible();
  await page.goto(page.url().replace(/\/$/, "") + "/timeline");
  await expect(page.getByTestId("event-card").first()).toBeVisible();
  // A fresh, unauthenticated client cannot read group data
  const groups = await request.get("/api/groups");
  expect(groups.status()).toBe(401);
});
