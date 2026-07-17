import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname);
const html = readFileSync(resolve(root, "index.html"), "utf8");
const css = readFileSync(resolve(root, "styles.css"), "utf8");
const js = readFileSync(resolve(root, "app.js"), "utf8");
const privacy = readFileSync(resolve(root, "privacy", "index.html"), "utf8");
const terms = readFileSync(resolve(root, "terms", "index.html"), "utf8");
const failures = [];

function requireText(source, text, label) {
  if (!source.includes(text)) failures.push("Missing " + label + ": " + text);
}

[
  ["Build your firehose. Read only what matters.", "filtered-firehose promise"],
  ["Hacker News", "Hacker News source"],
  ["Any public RSS or Atom feed", "open feed boundary"],
  ["Rollup frequency", "cadence control"],
  ["Daily", "daily cadence option"],
  ["Weekly", "weekly cadence option"],
  ["Try your filtered firehose for seven days.", "trial offer"],
  ["$</span>5", "$5 founding price"],
  ["Card required for the seven-day trial", "card-required trial disclosure"],
  ["Stripe-hosted checkout", "hosted checkout boundary"]
].forEach(([text, label]) => requireText(html, text, label));

[
  ["Today in 60 Seconds", "rendered today section"],
  ["Repo Radar", "rendered repo section"],
  ["Research Worth Reading", "rendered research section"],
  ["Watchlist / Do Nothing", "rendered watchlist section"],
  ["localStorage", "local-only persistence"],
  ["MAX_REPOS = 5", "repository cap"]
].forEach(([text, label]) => requireText(js, text, label));

[
  ["https://newpaperboy.com/", "canonical product URL"],
  ["Build your firehose. Read only what matters.", "cold-traffic promise"],
  ["Try your filtered firehose for seven days.", "card-required trial offer"],
  ["Build my rollup", "single subscription CTA"]
].forEach(([text, label]) => requireText(html, text, label));

[
  ['fetch("/api/firehose/subscribe"', "same-origin automatic subscription"],
  ['fetch("/api/config"', "runtime checkout availability"],
  ['["pending_verification", "pending"].indexOf(subscribeResult.status)', "pending verification response"],
  ['/api/firehose/subscriptions/" + encoded + "/confirm', "explicit confirmation endpoint"],
  ['fetch("/api/billing/checkout"', "hosted checkout handoff"],
  ['fetch("/api/billing/portal"', "hosted billing management"],
  ['parsed.hostname === "checkout.stripe.com"', "Stripe checkout URL allowlist"],
  ['fetch("/api/analytics/event"', "consented first-party analytics"],
  ["timezone: timezone", "browser timezone submission"],
  ["cadence: cadence", "daily or weekly cadence submission"],
  ["weekly_day: weeklyDay", "weekly delivery day submission"],
  ["consent: true", "email consent submission"],
  ["activeStatusUrl", "tokenized in-page management status"],
  ["activeUnsubscribeUrl", "tokenized unsubscribe action"],
  ["result.status !== \"unsubscribed\"", "confirmed unsubscribe response"],
  ["sources: sourceUrls", "public feed intake persistence"],
  ["focus: workFocus", "work-focus intake persistence"],
  ["ignore: ignoreFocus", "ignore-list intake persistence"],
  ["attributionFields", "campaign attribution capture"]
].forEach(([text, label]) => requireText(js, text, label));

[
  ["source-urls", "public feed intake field"],
  ["work-focus", "work-focus intake field"],
  ["ignore-focus", "noise filter intake field"]
].forEach(([text, label]) => requireText(html, text, label));

[
  "Know what changes your next move.",
  "evidence-linked morning edition",
  "revenue-bearing",
  "One paid wedge",
  "Paperboy Operator",
  "Request a founding pilot",
  "saved your email and filter for founding-pilot follow-up",
  "No card or subscription was created"
].forEach((text) => {
  if (html.includes(text)) failures.push("Stale internal copy found: " + text);
});

if (html.includes("We’ll email you to collect a few sources")) {
  failures.push("Stale follow-up-only intake copy found.");
}

const primaryCtaMatches = html.match(/Build my rollup/g) || [];
if (primaryCtaMatches.length < 4) failures.push("Primary automatic-subscription CTA is not repeated consistently.");

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
if (duplicates.length) failures.push("Duplicate HTML ids: " + [...new Set(duplicates)].join(", "));

if (/<script[^>]+src="https?:/i.test(html) || /<link(?=[^>]+rel="stylesheet")(?=[^>]+href="https?:)[^>]*>/i.test(html)) {
  failures.push("Remote script or stylesheet dependency found.");
}

if (/<form[^>]+action=/i.test(html)) {
  failures.push("A form action could submit data outside the local preview.");
}

if ((js.match(/fetch\(/g) || []).length !== 8 || !js.includes('fetch("/api/firehose/subscribe"') || !js.includes("refreshManagedSubscription(activeStatusUrl)") || !js.includes("fetch(activeUnsubscribeUrl")) {
  failures.push("Expected same-origin lifecycle fetches are missing or an unexpected fetch was added.");
}

if (!js.includes('"trial_started"') || js.includes('"purchase"') || js.includes('"transaction_id"')) {
  failures.push("Trial analytics must remain distinct from a real paid transaction.");
}

if (js.includes('/api/firehose/preview')) {
  failures.push("Stale preview-only endpoint found in the automatic setup flow.");
}

[
  [privacy, "What Paperboy collects", "privacy data disclosure"],
  [privacy, "does not connect to Gmail", "privacy inbox boundary"],
  [terms, "card-required seven-day trial followed by $5 per month", "terms billing disclosure"],
  [terms, "as-available basis", "terms availability boundary"]
].forEach(([source, text, label]) => requireText(source, text, label));

if (!html.includes('href="/privacy/"') || !html.includes('href="/terms/"')) {
  failures.push("Privacy and terms footer links are missing.");
}

if (!html.includes('href="https://github.com/cgallic/paperboy"')) {
  failures.push("Visible open-source project link is missing.");
}

[["XMLHttpRequest", "XMLHttpRequest"], ["WebSocket", "WebSocket"], ["sendBeacon", "sendBeacon"]].forEach(([needle, label]) => {
  if (js.includes(needle)) failures.push("Unexpected network primitive found: " + label);
});

if (/fetch\(\s*[`'\"]https?:/i.test(js)) {
  failures.push("External fetch URL found.");
}

const cssOpen = (css.match(/{/g) || []).length;
const cssClose = (css.match(/}/g) || []).length;
if (cssOpen !== cssClose) failures.push("CSS brace mismatch: " + cssOpen + " open vs " + cssClose + " close.");

if (failures.length) {
  console.error("Paperboy product static checks failed:");
  failures.forEach((failure) => console.error("- " + failure));
  process.exit(1);
}

console.log("Paperboy product static checks passed.");
console.log("- " + ids.length + " unique HTML ids");
console.log("- no remote UI assets or form actions");
console.log("- only expected same-origin lifecycle and consented analytics requests");
console.log("- pending verification, Stripe-hosted checkout, and legal boundaries present");
console.log("- required rollup sections and demo boundaries present");
