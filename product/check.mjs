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

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
if (duplicates.length) failures.push("Duplicate HTML ids: " + [...new Set(duplicates)].join(", "));

if (/<(?:script|link)[^>]+(?:src|href)="https?:/i.test(html)) {
  failures.push("Remote script or stylesheet dependency found.");
}

if (/<form[^>]+action=/i.test(html)) {
  failures.push("A form action could submit data outside the local preview.");
}

[
  ["fetch(", "fetch"],
  ["XMLHttpRequest", "XMLHttpRequest"],
  ["WebSocket", "WebSocket"],
  ["sendBeacon", "sendBeacon"]
].forEach(([needle, label]) => {
  if (js.includes(needle)) failures.push("Live network primitive found: " + label);
});

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
console.log("- no JavaScript network primitives");
console.log("- required Daily Brief sections and demo boundaries present");
