import { test, expect } from "@playwright/test";

// Uses the real Firebase client/Admin SDKs and only the local Auth emulator.
test("Google sign-in, private recipe ownership, reload, logout and revoked session", async ({
  page,
  request,
}, info) => {
  const email = `firebase-${info.project.name}-${Date.now()}@example.com`;
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "New here? Create an account" }),
  ).toHaveCount(0);
  const popupEvent = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  const popup = await popupEvent;
  await popup.waitForLoadState("networkidle");
  await popup.getByText("Add new account").click();
  await popup.locator("#email-input").fill(email);
  await popup
    .getByRole("button", { name: "Sign in with Google.com", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your recipe box." }),
  ).toBeVisible();
  const session = await page.request.get("/api/v1/me");
  const account = await session.json();
  expect(account.user.email).toBe(email);
  const saved = await page.request.post("/api/v1/recipes", {
    headers: { "X-CSRFToken": account.csrf_token },
    data: {
      title: "My Google recipe",
      ingredients: ["1 lemon"],
      instructions: ["Slice the lemon."],
    },
  });
  expect(saved.status()).toBe(201);
  const recipe = await saved.json();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "My Google recipe" }),
  ).toBeVisible();
  expect(
    (await page.context().cookies()).find(
      (cookie) => cookie.name === "sessionid",
    )?.httpOnly,
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).some((key) => key.startsWith("firebase:")),
    ),
  ).toBe(false);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/firebase-${info.project.name}.png`,
    fullPage: true,
  });
  // A separate anonymous browser cannot fetch the saved recipe.
  expect((await request.get(`/api/v1/recipes/${recipe.id}`)).status()).toBe(
    403,
  );
  // Disable the emulator user via its admin API; the next app request must fail closed.
  const users = await request.get(
    "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/projects/demo-flavorbuddy/accounts:batchGet",
    { headers: { Authorization: "Bearer owner" } },
  );
  const uid = (await users.json()).users.find(
    (user: { email: string }) => user.email === email,
  ).localId;
  const disabled = await request.post(
    "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/projects/demo-flavorbuddy/accounts:update",
    {
      headers: { Authorization: "Bearer owner" },
      data: { localId: uid, disableUser: true },
    },
  );
  expect(disabled.ok()).toBe(true);
  expect(
    (await page.request.get(`/api/v1/recipes/${recipe.id}`)).status(),
  ).toBe(403);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Continue with Google" }),
  ).toBeVisible();
});

test("an existing recipe box requires its password once before linking Google", async ({
  page,
}, info) => {
  await page.goto("/");
  const popupEvent = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  const popup = await popupEvent;
  await popup.waitForLoadState("networkidle");
  await popup.getByText("Add new account").click();
  await popup
    .locator("#email-input")
    .fill(`legacy-${info.project.name}@example.com`);
  await popup
    .getByRole("button", { name: "Sign in with Google.com", exact: true })
    .click();
  await expect(page.getByLabel("Existing FlavorBuddy password")).toBeVisible();
  await page.getByLabel("Existing FlavorBuddy password").fill("wrong-password");
  await page
    .getByRole("button", { name: "Connect Google and keep my recipes" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "existing FlavorBuddy password",
  );
  await page
    .getByLabel("Existing FlavorBuddy password")
    .fill("Legacy-test-password-892!");
  await page
    .getByRole("button", { name: "Connect Google and keep my recipes" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Existing family recipe" }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: `Sign out legacy-${info.project.name}@example.com`,
    })
    .click();
  await expect(
    page.getByRole("button", { name: "Continue with Google" }),
  ).toBeEnabled();
  expect((await page.request.get("/api/v1/me")).ok()).toBe(true);
  expect((await (await page.request.get("/api/v1/me")).json()).user).toBeNull();
});
