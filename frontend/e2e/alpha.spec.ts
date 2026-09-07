import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
const password = "Recipe-test-password-892!";
async function register(page: Page, email: string) {
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your recipe box." }),
  ).toBeVisible();
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
}

test("real private URL import → correction → save → find → edit → cook; second account isolation", async ({
  page,
}, info) => {
  const email = `e2e-${info.project.name}-${Date.now()}@example.com`;
  await register(page, email);
  await page.getByRole("link", { name: "Save your first recipe" }).click();
  await page
    .getByLabel("Recipe URL", { exact: true })
    .fill("https://fixture.flavorbuddy.test/pasta");
  await page
    .getByRole("button", { name: "Import recipe", exact: true })
    .click();
  await expect(page.getByLabel("Recipe title")).toHaveValue("Lemon pasta");
  await page.getByLabel("Recipe title").fill("My lemon pasta");
  await noOverflow(page);
  await page.reload();
  await expect(page.getByLabel("Recipe title")).toHaveValue("My lemon pasta");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My lemon pasta" }),
  ).toBeVisible();
  const recipeURL = page.url();
  await page.getByRole("button", { name: "Add favorite", exact: true }).click();
  await page.getByRole("link", { name: "Edit draft", exact: true }).click();
  await page.getByLabel("Personal notes").fill("Extra lemon next time.");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByText("Extra lemon next time.", { exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/#\/recipe\/\d+$/);
  await page
    .getByRole("link", { name: "Your recipe box", exact: true })
    .click();
  await page.getByRole("textbox", { name: "Search recipes" }).fill("My lemon");
  await page.getByRole("heading", { name: "My lemon pasta" }).click();
  await page.getByRole("link", { name: "Let’s cook", exact: true }).click();
  await page.getByLabel("200g pasta", { exact: true }).check();
  await page.getByRole("button", { name: "Next step", exact: true }).click();
  await page.reload();
  await expect(page.getByText("STEP 2 OF 3")).toBeVisible();
  await expect(page.getByLabel("200g pasta", { exact: true })).toBeChecked();
  await noOverflow(page);
  await page.screenshot({
    path: `test-results/cooking-${info.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: "Next step", exact: true }).click();
  await page
    .getByRole("button", { name: "Mark complete", exact: true })
    .click();
  await page.getByLabel("Cooking note").fill("Cooked it. Delicious!");
  await page
    .getByRole("button", { name: "Save note & finish", exact: true })
    .click();
  await expect(
    page.getByText("Cooked it. Delicious!", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: `Sign out ${email}` }).click();
  await expect(
    page.getByRole("button", { name: "New here? Create an account" }),
  ).toBeVisible();
  await register(page, `bob-${email}`);
  await expect(
    page.getByRole("heading", { name: "Every good meal starts somewhere." }),
  ).toBeVisible();
  await page.goto(recipeURL);
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "My lemon pasta" }),
  ).toHaveCount(0);
});

test("source failure supports manual correction; network failure keeps draft", async ({
  page,
}, info) => {
  await register(
    page,
    `recovery-${info.project.name}-${Date.now()}@example.com`,
  );
  await page.getByRole("link", { name: "Save your first recipe" }).click();
  await page
    .getByLabel("Recipe URL", { exact: true })
    .fill("https://unsupported.example/recipe");
  await page
    .getByRole("button", { name: "Import recipe", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("couldn’t extract");
  await page.getByLabel("Recipe title").fill("My recovered soup");
  await page
    .getByLabel("Ingredients", { exact: false })
    .fill("1 carrot\nWater");
  await page
    .getByLabel("Directions", { exact: false })
    .fill("Simmer until tender.");
  await page.route("**/api/v1/recipes", (route) => route.abort());
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(page.getByRole("alert").last()).toContainText(
    "Could not connect",
  );
  await expect(page.getByLabel("Recipe title")).toHaveValue(
    "My recovered soup",
  );
  await page.unroute("**/api/v1/recipes");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My recovered soup" }),
  ).toBeVisible();
  await noOverflow(page);
  await page
    .getByRole("link", { name: "Your recipe box", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "My recovered soup" }),
  ).toBeVisible();
  await expect(page.locator(".recipe-card")).toBeVisible();
  await page.screenshot({
    path: `test-results/library-${info.project.name}.png`,
    fullPage: true,
  });
});

test("expired session preserves edits; concurrent edit requires review", async ({
  page,
}, info) => {
  const email = `session-${info.project.name}-${Date.now()}@example.com`;
  await register(page, email);
  await page.getByRole("link", { name: "Save your first recipe" }).click();
  await page
    .getByRole("button", { name: "Try it with our chickpea toast sample" })
    .click();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Lemony chickpeas on toast" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Edit draft", exact: true }).click();
  await page
    .getByLabel("Personal notes")
    .fill("Preserve these personal edits.");
  await page.evaluate(async () => {
    const me = await (await fetch("/api/v1/me")).json();
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": me.csrf_token,
      },
      body: "{}",
    });
  });
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Personal notes")).toHaveValue(
    "Preserve these personal edits.",
  );
  await page.evaluate(async () => {
    const me = await (await fetch("/api/v1/me")).json();
    const id = location.hash.split("/")[2];
    const recipe = await (await fetch(`/api/v1/recipes/${id}`)).json();
    await fetch(`/api/v1/recipes/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": me.csrf_token,
      },
      body: JSON.stringify({
        notes: "Changed in another tab.",
        version: recipe.version,
      }),
    });
  });
  await page.reload();
  await expect(page.getByLabel("Personal notes")).toHaveValue(
    "Preserve these personal edits.",
  );
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("This recipe changed");
  await page
    .getByRole("button", { name: "Review latest draft, keeping my edits" })
    .click();
  await expect(page.getByText("Notes: Changed in another tab.")).toBeVisible();
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByText("Preserve these personal edits.", { exact: true }),
  ).toBeVisible();
});

test("keyboard-accessible forms and responsive visual system", async ({
  page,
}, info) => {
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  let results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  await register(page, `access-${info.project.name}-${Date.now()}@example.com`);
  await page.getByRole("link", { name: "Save your first recipe" }).focus();
  await page.keyboard.press("Enter");
  await page
    .getByRole("button", { name: "Try it with our chickpea toast sample" })
    .click();
  await expect(page.getByLabel("Recipe title")).toBeVisible();
  results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  for (const width of [360, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await noOverflow(page);
  }
  await page.getByRole("button", { name: "Save recipe", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("link", { name: "Let’s cook", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Let’s cook", exact: true }).click();
  results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("starter catalog is public and saves an independent private copy", async ({
  page,
}, info) => {
  await page.goto("/#/starters");
  await expect(page.getByText("415 recipes", { exact: true })).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search starter recipes" })
    .fill("Apple Pie");
  await page.getByRole("heading", { name: "Apple Pie", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in to save" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign in to save" }).click();
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page
    .getByLabel("Email", { exact: true })
    .fill(`starter-${info.project.name}-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByRole("button", { name: "Save to my recipes" }).click();
  await expect(
    page.getByRole("link", { name: "Edit draft", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Edit draft", exact: true }).click();
  await page.getByLabel("Recipe title").fill("My private apple pie");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "My private apple pie" }),
  ).toBeVisible();
  await expect(page).toHaveURL(/#\/recipe\/\d+$/);
  await page.goto("/#/starters");
  await page
    .getByRole("textbox", { name: "Search starter recipes" })
    .fill("Apple Pie");
  await expect(
    page.getByRole("heading", { name: "Apple Pie", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
});

test("pantry edit, used-up undo, matching and private photo lifecycle", async ({
  page,
}, info) => {
  await register(
    page,
    `kitchen-${info.project.name}-${Date.now()}@example.com`,
  );
  await page.evaluate(async () => {
    const me = await (await fetch("/api/v1/me")).json();
    const response = await fetch("/api/v1/recipes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": me.csrf_token,
      },
      body: JSON.stringify({
        title: "Pantry rice supper",
        state: "finalized",
        ingredients: ["2 cups rice", "1 onion"],
        instructions: ["Cook the rice."],
        description: "",
        author: "",
        yields: "2",
        total_time: 20,
        source_url: null,
        image: "",
      }),
    });
    return (await response.json()).id;
  });
  await page.getByRole("link", { name: "Pantry", exact: true }).click();
  await page.getByLabel("Ingredient", { exact: true }).fill("Rice");
  await page.getByLabel("Quantity (optional)", { exact: true }).fill("one bag");
  await page.getByLabel("Location", { exact: true }).fill("Upper cupboard");
  await page.getByLabel("Use soon", { exact: true }).check();
  await page
    .getByRole("button", { name: "Add ingredient", exact: true })
    .click();
  await expect(
    page.getByText("one bag · Upper cupboard · Use soon"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Used up Rice", exact: true }).click();
  await page
    .getByRole("button", { name: "Undo used up Rice", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Find recipes with my pantry", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Pantry rice supper" }),
  ).toBeVisible();
  await noOverflow(page);
  await page.screenshot({
    path: `test-results/pantry-${info.project.name}.png`,
    fullPage: true,
  });
  await page.getByRole("link", { name: "Pantry rice supper" }).click();
  await page
    .getByLabel("Photo (JPEG, PNG or WebP, up to 8 MiB)")
    .setInputFiles("e2e/fixtures/photo.png");
  await page
    .getByRole("button", { name: "Save private photo", exact: true })
    .click();
  await expect(page.getByAltText("Your recipe cover")).toBeVisible();
  const image = page.getByAltText("Your recipe cover");
  await expect
    .poll(() => image.evaluate((el: HTMLImageElement) => el.naturalWidth))
    .toBeGreaterThan(0);
  await noOverflow(page);
  await page.screenshot({
    path: `test-results/photos-${info.project.name}.png`,
    fullPage: true,
  });
  const imageURL = await image.getAttribute("src");
  await page.getByRole("button", { name: /Sign out/ }).click();
  await expect(page.getByRole("button", { name: /Sign out/ })).toHaveCount(0);
  expect((await page.request.get(imageURL!)).status()).toBe(403);
});

test("fixture capture requires editable approval and survives refresh", async ({
  page,
}, info) => {
  await register(
    page,
    `capture-${info.project.name}-${Date.now()}@example.com`,
  );
  await page.getByRole("link", { name: "Pantry", exact: true }).click();
  await page.getByText("Try the photo review demo", { exact: true }).click();
  await page
    .getByLabel("Pantry photo", { exact: true })
    .setInputFiles("e2e/fixtures/photo.png");
  await page
    .getByRole("button", { name: "Create demo preview", exact: true })
    .click();
  await expect(
    page.getByText("Capture: queued", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Your pantry is empty.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Capture: preview", { exact: true })).toBeVisible(
    { timeout: 10000 },
  );
  await page
    .getByRole("group", { name: "Item 1", exact: true })
    .getByLabel("Name", { exact: true })
    .fill("Cherry tomatoes");
  await page
    .getByRole("button", { name: "Remove item 2", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve items into pantry", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cherry tomatoes", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
  await page.screenshot({
    path: `test-results/capture-${info.project.name}.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Discard capture photo and preview" })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Cherry tomatoes", exact: true }),
  ).toBeVisible();
});

test("draft finalization, public sharing and an independent variation", async ({
  page,
}, info) => {
  await register(
    page,
    `lifecycle-${info.project.name}-${Date.now()}@example.com`,
  );
  await page.getByRole("link", { name: "Save your first recipe" }).click();
  await page
    .getByRole("button", { name: "Try it with our chickpea toast sample" })
    .click();
  await page.getByLabel("Recipe title").fill("Immutable original");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Edit draft", exact: true }),
  ).toBeVisible();
  const originalURL = page.url();
  await page.reload();
  await page.getByRole("link", { name: "Edit draft", exact: true }).click();
  await page.getByLabel("Personal notes").fill("Do not publish my note");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(page).toHaveURL(originalURL);
  await expect(
    page.getByRole("link", { name: "Edit draft", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Share publicly", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Make private", exact: true }),
  ).toBeVisible();
  const link = await page
    .getByRole("link", { name: "Permanent recipe link" })
    .getAttribute("href");
  const id = link!.split("/").at(-1)!;
  const publicRecipe = await (
    await page.request.get(`/api/v1/shared-recipes/${id}`)
  ).json();
  expect(publicRecipe.notes).toBeUndefined();
  expect(publicRecipe.private_cover).toBeUndefined();
  await page
    .getByRole("button", { name: "Make a variation", exact: true })
    .click();
  await expect(page.getByLabel("Recipe title")).toHaveValue(
    "Immutable original",
  );
  expect(page.url()).not.toBe(originalURL);
  await page.getByLabel("Recipe title").fill("Inspired new recipe");
  await page.getByRole("button", { name: "Save recipe", exact: true }).click();
  await expect(page).toHaveURL(/#\/recipe\/\d+$/);
  expect(
    await (await page.request.get(`/api/v1/shared-recipes/${id}`)).json(),
  ).toEqual(publicRecipe);
  await page.goto(`/${link}`);
  await expect(
    page.getByRole("heading", { name: "Immutable original", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Do not publish my note", { exact: true }),
  ).toHaveCount(0);
  await noOverflow(page);
});
