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
  ["Daily Intelligence Brief", "commercial product name"],
  ["Forwarded newsletters", "forwarding source lane"],
  ["Public news, research, and data", "public source lane"],
  ["Selected public GitHub repos", "GitHub source lane"],
  ["Today in 60 Seconds", "daily brief section"],
  ["Repo Radar", "repo section"],
  ["Research Worth Reading", "research section"],
  ["Watchlist / Do Nothing", "watchlist section"],
  ["$</span>49", "$49 price hypothesis"],
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
  ["Founding pilot: $49/month", "live pilot offer"],
  ["Request the $49 founding pilot", "pilot lead CTA"]
].forEach(([text, label]) => requireText(html, text, label));

[
  ['fetch("/api/lead"', "same-origin KaiBuilds lead capture"],
  ["/api/hit?slug=paperboy", "KaiBuilds visit capture"],
  ['slug: "paperboy"', "Paperboy capture slug"],
  ["attributionFields", "campaign attribution capture"]
].forEach(([text, label]) => requireText(js, text, label));

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
if (duplicates.length) failures.push("Duplicate HTML ids: " + [...new Set(duplicates)].join(", "));

if (/<script[^>]+src="https?:/i.test(html) || /<link(?=[^>]+rel="stylesheet")(?=[^>]+href="https?:)[^>]*>/i.test(html)) {
  failures.push("Remote script or stylesheet dependency found.");
}

if (/<form[^>]+action=/i.test(html)) {
  failures.push("A form action could submit data outside the local preview.");
}

if ((js.match(/fetch\(/g) || []).length !== 1 || !js.includes('fetch("/api/lead"')) {
  failures.push("Only the same-origin /api/lead fetch is allowed.");
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
console.log("- only same-origin KaiBuilds lead and visit capture");
console.log("- required Daily Brief sections and demo boundaries present");
