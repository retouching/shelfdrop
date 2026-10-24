// The screenshots of the README (docs/screenshots/), taken from a running shelfdrop with
// Playwright, in the image mcr.microsoft.com/playwright:v1.56.0-noble (the command is in
// CONTRIBUTING.md).
//
// The target and its account come from the environment alone, and are never printed nor
// written: SHELFDROP_SHOTS_URL, SHELFDROP_SHOTS_USERNAME, SHELFDROP_SHOTS_PASSWORD;
// SHELFDROP_SHOTS_QUERY is the title searched (RuriDragon by default), SHELFDROP_SHOTS_SERIES the
// start of the name of the series whose dialog is shot (Kaguya-sama by default). The addresses
// of the services are replaced by neutral ones in the page before their shot.
//
// The script only reads: it signs in, opens the pages, types a search, chooses a work and opens
// the dialog of a series. Every other write of the pages is aborted before it leaves the
// browser (READ_ONLY_WRITES lists the writes let through, all of them reads on the server).
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const OUT = path.resolve(__dirname, "..", "docs", "screenshots");
const QUALITY = 0.85;
const DESKTOP = { viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 };
const MOBILE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
// The writes let through: the sign-in, a release search, the tests of the connections.
const READ_ONLY_WRITES = [
  /^POST \/api\/v1\/session$/,
  /^POST \/api\/v1\/searches$/,
  /^POST \/api\/v1\/settings\/test$/,
];

function setting(name, fallback) {
  const value = process.env[name] ?? fallback;
  if (value === undefined || value === "") {
    throw new Error(`${name} is not set`);
  }
  return value;
}

const base = setting("SHELFDROP_SHOTS_URL").replace(/\/+$/, "");
const query = setting("SHELFDROP_SHOTS_QUERY", "RuriDragon");
// A word of the card of the work whose releases are shot (its author), and the search of the phone.
const author = setting("SHELFDROP_SHOTS_AUTHOR", "Shind");
// The search of the shot of the works found (a title with several works), and that of the phone.
const worksQuery = setting("SHELFDROP_SHOTS_WORKS_QUERY", "Call of the Night");
const phoneQuery = setting("SHELFDROP_SHOTS_PHONE_QUERY", "Monster");
const series = setting("SHELFDROP_SHOTS_SERIES", "Kaguya-sama");
// The neutral address shown for each service, by the start of the title of its card.
const ADDRESSES = { Prowlarr: "http://prowlarr:9696", qBittorrent: "http://qui:7476", Jellyfin: "http://jellyfin:8096" };

/** A context in the light theme, whose writes are aborted but READ_ONLY_WRITES. */
async function newContext(browser, device, storageState) {
  const context = await browser.newContext({ ...device, colorScheme: "light", locale: "fr-FR", storageState });
  await context.addInitScript(() => {
    window.localStorage.setItem("shelfdrop.theme", "light");
  });
  await context.route("**/*", (route) => {
    const request = route.request();
    const method = request.method();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
      return route.continue();
    }
    const key = `${method} ${new URL(request.url()).pathname}`;
    if (READ_ONLY_WRITES.some((allowed) => allowed.test(key))) {
      return route.continue();
    }
    console.log(`blocked ${key}`);
    return route.abort("blockedbyclient");
  });
  return context;
}

/** Wait for the page to settle: no request for a while, nothing busy, every image loaded, then
 * a short pause. The pauses also keep the pages under the rate limit of a reverse proxy. */
async function settle(page, seconds = 1.5) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
  await page
    .waitForFunction(() => document.querySelectorAll('[aria-busy="true"]').length === 0, null, { timeout: 90_000 })
    .catch(() => console.log("still busy, shot anyway"));
  await page
    .waitForFunction(() => [...document.images].every((image) => image.complete), null, { timeout: 30_000 })
    .catch(() => console.log("images still loading, shot anyway"));
  await page.waitForTimeout(seconds * 1000);
}

/** The screenshot of the viewport, encoded in WebP by Chromium itself. */
async function shoot(page, name) {
  const png = await page.screenshot({ type: "png", animations: "disabled", caret: "hide" });
  const encoder = await page.context().browser().newPage();
  const webp = await encoder.evaluate(
    async ({ data, quality }) => {
      const image = new Image();
      image.src = `data:image/png;base64,${data}`;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      canvas.getContext("2d").drawImage(image, 0, 0);
      return canvas.toDataURL("image/webp", quality).split(",")[1];
    },
    { data: png.toString("base64"), quality: QUALITY },
  );
  await encoder.close();
  const file = path.join(OUT, `${name}.webp`);
  fs.writeFileSync(file, Buffer.from(webp, "base64"));
  console.log(`${name}.webp ${Math.round(fs.statSync(file).size / 1024)} KiB`);
}

async function signIn(page) {
  await page.goto(`${base}/`);
  await page.locator('input[autocomplete="username"]').waitFor();
  await page.locator('input[autocomplete="username"]').fill(setting("SHELFDROP_SHOTS_USERNAME"));
  await page.locator('input[autocomplete="current-password"]').fill(setting("SHELFDROP_SHOTS_PASSWORD"));
  await page.locator('button[type="submit"]').click();
  await page.locator('input[autocomplete="username"]').waitFor({ state: "detached", timeout: 30_000 });
  await settle(page);
}

async function searchWorks(page, text = query) {
  await page.goto(`${base}/`);
  const field = page.locator("#query");
  await field.fill(text);
  await field.press("Enter");
  await page.locator('button[aria-label^="Choisir "]').first().waitFor({ timeout: 90_000 });
  await settle(page);
}

async function desktop(browser) {
  const context = await newContext(browser, DESKTOP);
  const page = await context.newPage();

  await page.goto(`${base}/`);
  await page.locator('input[autocomplete="username"]').waitFor();
  await settle(page, 0.5);
  await shoot(page, "sign-in");
  await signIn(page);

  await searchWorks(page, worksQuery);
  await shoot(page, "search-works");
  await page.waitForTimeout(2000);
  await searchWorks(page);
  await page.locator("li").filter({ hasText: author }).locator('button[aria-label^="Choisir "]').first().click();
  await page.locator("#results-title").waitFor({ timeout: 120_000 });
  await settle(page, 2);
  // From the top of the page: the search typed, the work chosen, its names, then its releases.
  await page.evaluate(() => {
    window.scrollTo(0, 0);
  });
  await settle(page, 1);
  await shoot(page, "search-releases");

  const pages = [
    ["downloads", "/downloads"],
    ["ranger", "/place"],
    ["waiting-list", "/waiting"],
    ["settings-services", "/settings"],
    ["settings-logs", "/settings/logs"],
    ["jellyfin-series", "/jellyfin"],
  ];
  for (const [name, address] of pages) {
    await page.waitForTimeout(2000);
    await page.goto(`${base}${address}`);
    await settle(page, 2.5);
    if (name === "ranger") {
      // A filter of the page alone: every file of the library, not only those to place.
      await page.getByRole("radio", { name: "Toute la bibliothèque" }).click();
      await settle(page, 1);
    }
    if (name === "settings-services") {
      await page.evaluate((addresses) => {
        for (const input of document.querySelectorAll("input")) {
          if (!/^https?:\/\//.test(input.value)) continue;
          // The first ancestor whose text starts with the title of a service: its card.
          let service;
          for (let node = input.parentElement; node !== null && service === undefined; node = node.parentElement) {
            const text = (node.textContent ?? "").trimStart();
            service = Object.keys(addresses).find((title) => text.startsWith(title));
          }
          input.value = service === undefined ? "http://service:8080" : addresses[service];
        }
      }, ADDRESSES);
    }
    await shoot(page, name);
  }

  const chosen = page.locator(`button[aria-label^="Modifier ${series}"]`);
  const opened = (await chosen.count()) > 0 ? chosen : page.locator('button[aria-label^="Modifier "]');
  await opened.first().click();
  await page.locator("dialog[open]").waitFor();
  // The covers proposed by the sources come after the dialog.
  await page
    .getByText("Recherche dans les sources")
    .waitFor({ state: "hidden", timeout: 60_000 })
    .catch(() => console.log("covers still searched, shot anyway"));
  await settle(page, 2);
  await shoot(page, "jellyfin-series-dialog");
  const session = await context.storageState();
  await context.close();
  return session;
}

/** The phone shots, in the session of the desktop ones: one sign-in alone. */
async function mobile(browser, session) {
  const context = await newContext(browser, MOBILE, session);
  const page = await context.newPage();

  await searchWorks(page, phoneQuery);
  await page.locator('button[aria-label="Menu"]').click();
  await page.waitForTimeout(800);
  await shoot(page, "mobile-search-menu");

  await page.waitForTimeout(2000);
  await page.goto(`${base}/downloads`);
  await settle(page, 2.5);
  await shoot(page, "mobile-downloads");
  await context.close();
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  try {
    const session = await desktop(browser);
    await mobile(browser, session);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  // The message of Playwright alone: it names a selector or a timeout, never the account.
  console.error(error instanceof Error ? error.message.split("\n")[0] : "failed");
  process.exitCode = 1;
});
