import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname);
const html = readFileSync(resolve(root, "index.html"), "utf8");
const css = readFileSync(resolve(root, "styles.css"), "utf8");
const js = readFileSync(resolve(root, "app.js"), "utf8");
const failures = [];

function requireText(source, text, label) {
  if (!source.includes(text)) failures.push("Missing " + label + ": " + text);
}

[
  ["Build your firehose. Read only what matters.", "filtered-firehose promise"],
  ["Hacker News", "Hacker News source"],
  ["Any public RSS or Atom feed", "open feed boundary"],
  ["Start the daily brief without a card.", "automatic launch offer"],
  ["$</span>0", "no-payment launch price"],
  ["Planned founding price: $49/month", "$49 price hypothesis"],
  ["No charge can be created here", "disabled checkout boundary"]
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
  ["https://paperboy.kaibuilds.com/", "canonical KaiBuilds URL"],
  ["Build your firehose. Read only what matters.", "cold-traffic promise"],
  ["Start the daily brief without a card.", "no-card launch offer"],
  ["Start my daily brief", "single subscription CTA"]
].forEach(([text, label]) => requireText(html, text, label));

[
  ['fetch("/api/firehose/subscribe"', "same-origin automatic subscription"],
  ['subscribeResult.status !== "subscribed"', "confirmed active subscription response"],
  ["activeStatusUrl", "tokenized in-page management status"],
  ["activeUnsubscribeUrl", "tokenized unsubscribe action"],
  ["result.status !== \"unsubscribed\"", "confirmed unsubscribe response"],
  ["/api/hit?slug=paperboy", "KaiBuilds visit capture"],
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

const primaryCtaMatches = html.match(/Start my daily brief/g) || [];
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

if ((js.match(/fetch\(/g) || []).length !== 3 || !js.includes('fetch("/api/firehose/subscribe"') || !js.includes("refreshManagedSubscription(activeStatusUrl)") || !js.includes("fetch(activeUnsubscribeUrl")) {
  failures.push("Only same-origin subscription, status, and unsubscribe fetches are allowed.");
}

if (js.includes('/api/firehose/preview') || js.includes('/api/lead')) {
  failures.push("Stale preview or lead-capture endpoint found in the automatic setup flow.");
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
console.log("- only same-origin subscription, status, unsubscribe, and visit capture");
console.log("- required Daily Brief sections and demo boundaries present");
