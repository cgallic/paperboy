(function () {
  "use strict";

  var STORAGE_KEY = "paperboy.product-demo.v2";
  var ANALYTICS_CONSENT_KEY = "paperboy.analytics.consent.v1";
  var CHECKOUT_MANAGEMENT_KEY = "paperboy.checkout.management.v1";
  var ANALYTICS_ID_KEY = "paperboy.analytics.anonymous.v1";
  var MAX_REPOS = 5;
  var MAX_SUBSCRIPTION_SOURCES = 6;

  var fixtureRepos = [
    { id: "agent-router", name: "demo-labs/agent-router", language: "TypeScript", description: "Routes tool-using agents across model providers." },
    { id: "api-evals", name: "demo-labs/api-evals", language: "Python", description: "Evaluation harness for structured model output." },
    { id: "local-rag", name: "demo-labs/local-rag", language: "Python", description: "Hybrid retrieval over a private technical corpus." },
    { id: "usage-meter", name: "demo-labs/usage-meter", language: "Go", description: "Meters inference usage and provider cost." },
    { id: "tool-stream", name: "demo-labs/tool-stream", language: "Rust", description: "Streams and validates long-running tool calls." },
    { id: "founder-console", name: "demo-labs/founder-console", language: "TypeScript", description: "Small operating console for technical founders." },
    { id: "schema-guard", name: "demo-labs/schema-guard", language: "Python", description: "Constrained generation and schema repair utilities." }
  ];

  var briefSections = [
    {
      section: "Today in 60 Seconds",
      items: [
        {
          id: "today-model-pricing",
          source: "Public data · fixture",
          score: 8,
          repo: "Daily watchlist",
          title: "A model price shift changes the cheapest reliable fallback",
          why: "The fixture watchlist prioritizes inference margin. The modeled price move is large enough to revisit the fallback order before the next usage review.",
          next: "Recalculate one representative workload. If the difference is immaterial, keep the current routing.",
          evidence: "Public Paperboy fixture"
        },
        {
          id: "today-api-deadline",
          source: "Forwarded newsletter · fixture",
          score: 7,
          repo: "API watchlist",
          title: "One provider deprecation date moved into the next release window",
          why: "The simulated newsletter item overlaps the configured release risk. It deserves a calendar check, not an emergency migration.",
          next: "Confirm whether the deprecated endpoint appears in active dependencies. Otherwise, watch and do nothing.",
          evidence: "Forwarded-message fixture"
        }
      ]
    },
    {
      section: "Repo Radar",
      items: [
        {
          id: "repo-tool-stream",
          source: "Release · fixture",
          score: 8,
          repo: "demo-labs/agent-router",
          title: "A provider SDK changed its tool-stream completion contract",
          why: "The selected fixture repo handles streamed tool calls. A completion-state change may affect the router's retry boundary.",
          next: "Inspect the adapter test that covers partial tool output. Do not change code until the contract difference is reproduced.",
          evidence: "Action-queue demo shape"
        }
      ]
    },
    {
      section: "Research Worth Reading",
      items: [
        {
          id: "research-rubric",
          source: "Research paper · fixture",
          score: 8,
          repo: "demo-labs/api-evals",
          title: "Rubric-grounded critique may improve smaller-model judge agreement",
          why: "The selected fixture repo already evaluates structured output. The technique is specific enough for a bounded comparison.",
          next: "Compare rubric-guided and freeform critique on one held-out set.",
          evidence: "Research-score fixture"
        }
      ]
    },
    {
      section: "Watchlist / Do Nothing",
      items: [
        {
          id: "watchlist-vector-memory",
          source: "Technical news · fixture",
          score: 5,
          repo: "demo-labs/local-rag",
          title: "A new memory benchmark is interesting, but not decision-changing",
          why: "The benchmark does not test the fixture repo's hybrid retrieval constraint and ships no transferable implementation detail.",
          next: "Watch. Do nothing unless code or a matching evaluation set appears.",
          evidence: "Public Paperboy fixture"
        }
      ]
    }
  ];

  var defaultState = {
    email: "",
    magicLinkPreviewed: false,
    fixtureLoaded: false,
    selectedRepos: [],
    sources: { forwarding: true, publicCatalog: true },
    interests: {
      description: "",
      watchlist: "",
      themes: [],
      skip: ""
    },
    delivery: {
      email: "",
      time: "07:30",
      timezone: "America/New_York",
      cadence: "daily",
      weeklyDay: 0,
      days: ["Mon", "Tue", "Wed", "Thu", "Fri"]
    },
    billingState: "active",
    feedback: {}
  };

  var state = loadState();
  var pendingDialogAction = null;
  var currentScreen = "home";
  var currentStep = "sources";
  var activeManageUrl = "";
  var activeStatusUrl = "";
  var activeUnsubscribeUrl = "";
  var activeManagementToken = "";
  var activeCadence = "daily";
  var confirmationToken = "";

  var screens = Array.prototype.slice.call(document.querySelectorAll("[data-screen]"));
  var siteHeader = document.getElementById("site-header");
  var siteFooter = document.getElementById("site-footer");
  var menuButton = document.querySelector(".menu-button");
  var mobileNav = document.getElementById("mobile-nav");
  var toastRegion = document.getElementById("toast-region");

  function cloneDefault() {
    return JSON.parse(JSON.stringify(defaultState));
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return cloneDefault();
      var parsed = JSON.parse(raw);
      var merged = cloneDefault();
      Object.assign(merged, parsed);
      merged.sources = Object.assign({}, defaultState.sources, parsed.sources || {});
      merged.interests = Object.assign({}, defaultState.interests, parsed.interests || {});
      merged.delivery = Object.assign({}, defaultState.delivery, parsed.delivery || {});
      merged.selectedRepos = Array.isArray(parsed.selectedRepos) ? parsed.selectedRepos.slice(0, MAX_REPOS) : [];
      merged.feedback = parsed.feedback || {};
      return merged;
    } catch (error) {
      return cloneDefault();
    }
  }

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    window.__paperboyDemo = { state: state, storageKey: STORAGE_KEY };
  }

  function analyticsAllowed() {
    return localStorage.getItem(ANALYTICS_CONSENT_KEY) === "granted";
  }

  function updateAnalyticsConsentUi() {
    var note = document.getElementById("analytics-note");
    if (!note) return;
    var choice = localStorage.getItem(ANALYTICS_CONSENT_KEY);
    note.textContent = choice === "granted"
      ? "Optional first-party product analytics is allowed. No advertising tracker is loaded."
      : choice === "declined"
        ? "Optional analytics is off. No advertising tracker is loaded."
        : "Optional analytics stays off unless you allow it. No advertising tracker is loaded.";
  }

  function trackProductEvent(name, properties) {
    var allowed = ["page_view", "signup_started", "subscription_requested", "email_verified", "begin_checkout", "trial_started"];
    if (!analyticsAllowed() || allowed.indexOf(name) < 0) return;
    window.dataLayer = window.dataLayer || [];
    var event = { event: name, product: "paperboy" };
    var safe = properties || {};
    ["source_count", "cadence", "weekly_day", "billing_status", "currency"].forEach(function (key) {
      if (safe[key] !== undefined && safe[key] !== null) event[key] = safe[key];
    });
    window.dataLayer.push(event);
    var anonymousId = localStorage.getItem(ANALYTICS_ID_KEY);
    if (!anonymousId) {
      anonymousId = window.crypto && typeof window.crypto.randomUUID === "function"
        ? window.crypto.randomUUID()
        : "pb-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
      localStorage.setItem(ANALYTICS_ID_KEY, anonymousId);
    }
    fetch("/api/analytics/event", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event: name,
        anonymous_id: anonymousId,
        properties: Object.keys(event).reduce(function (result, key) {
          if (key !== "event" && key !== "product") result[key] = event[key];
          return result;
        }, {})
      })
    }).catch(function () {
      // Analytics never blocks the product flow.
    });
  }

  function trackPageViewOnce() {
    var key = "paperboy.analytics.page_view";
    if (!analyticsAllowed() || sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    trackProductEvent("page_view");
    var pixel = new Image();
    pixel.alt = "";
    pixel.src = "/api/hit?slug=paperboy&r=" + Date.now();
  }

  async function loadRuntimeAvailability() {
    var title = document.getElementById("launch-status-title");
    var copy = document.getElementById("launch-status-copy");
    var note = document.getElementById("checkout-availability-note");
    try {
      var response = await fetch("/api/config", { headers: { "Accept": "application/json" } });
      var result = await response.json();
      if (!response.ok || !result || !result.billing || typeof result.billing.enabled !== "boolean") return;
      document.body.setAttribute("data-billing-available", result.billing.enabled ? "true" : "false");
      if (result.billing.enabled) {
        title.textContent = "Automatic daily or weekly delivery";
        copy.textContent = "Add your feeds once. Confirm your email and start the hosted trial, then Paperboy delivers on your chosen schedule.";
        note.querySelector("strong").textContent = "Hosted checkout available";
        note.querySelector("span").textContent = "Email verification comes first. Stripe confirms the trial before scheduled delivery becomes active.";
      } else {
        title.textContent = "Preview and email verification are live";
        copy.textContent = "Checkout is temporarily unavailable, so paid delivery cannot activate yet. No card will be requested or charged.";
        note.querySelector("strong").textContent = "Checkout temporarily unavailable";
        note.querySelector("span").textContent = "You can preview the filter and verify your email, but delivery will not start until hosted checkout is enabled.";
      }
    } catch (error) {
      // Availability copy stays conservative when runtime configuration cannot be read.
    }
  }

  function routeTo(screen, options) {
    var target = screen || "home";
    var step = options && options.step ? options.step : null;
    currentScreen = target;
    if (step) currentStep = step;

    screens.forEach(function (node) {
      node.hidden = node.getAttribute("data-screen") !== target;
    });

    document.body.setAttribute("data-active-screen", target);
    siteHeader.hidden = target !== "home";
    siteFooter.hidden = target !== "home";
    closeMobileNav();

    if (target === "setup") {
      showSetupStep(currentStep);
      renderAll();
      history.replaceState(null, "", "#setup/" + currentStep);
    } else {
      history.replaceState(null, "", "#" + target);
      renderAll();
    }

    window.scrollTo({ top: 0, behavior: "auto" });
    var heading = document.querySelector('[data-screen="' + target + '"] h1');
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
  }

  function showSetupStep(step) {
    var allowed = ["sources", "focus", "delivery"];
    currentStep = allowed.indexOf(step) >= 0 ? step : "sources";
    document.querySelectorAll("[data-step-panel]").forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-step-panel") !== currentStep;
    });
    document.querySelectorAll("[data-step-marker]").forEach(function (marker) {
      var markerStep = marker.getAttribute("data-step-marker");
      var markerIndex = allowed.indexOf(markerStep);
      var currentIndex = allowed.indexOf(currentStep);
      marker.classList.toggle("active", markerStep === currentStep);
      marker.classList.toggle("complete", markerIndex < currentIndex);
    });
    renderAll();
  }

  function closeMobileNav() {
    if (!mobileNav || !menuButton) return;
    mobileNav.hidden = true;
    menuButton.setAttribute("aria-expanded", "false");
  }

  function toast(message) {
    var node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    toastRegion.appendChild(node);
    window.setTimeout(function () {
      node.remove();
    }, 3200);
  }

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  function sourceLines(value) {
    return value.split(/\r?\n/).map(function (line) {
      return line.trim();
    }).filter(Boolean);
  }

  function subscriptionErrorMessage(response, result) {
    if (result && typeof result.detail === "string") return result.detail;
    if (result && result.detail && typeof result.detail.message === "string") return result.detail.message;
    if (result && typeof result.message === "string") return result.message;
    return "Paperboy could not save the rollup request. Check the feeds and try again.";
  }

  function renderLivePreview(result) {
    var summary = document.getElementById("preview-summary");
    var list = document.getElementById("live-preview-list");
    var items = result && Array.isArray(result.items) ? result.items : [];
    var sourceResults = result && Array.isArray(result.sources) ? result.sources : [];
    var failed = sourceResults.filter(function (source) { return source.status !== "ok"; });
    var scanned = result && Number.isFinite(result.scanned) ? result.scanned : items.length;
    summary.replaceChildren();
    list.replaceChildren();

    var summaryStrong = document.createElement("strong");
    summaryStrong.textContent = items.length + (items.length === 1 ? " signal" : " signals") + " made the cut";
    var summaryCopy = document.createElement("span");
    summaryCopy.textContent = scanned + " recent items scanned" + (failed.length ? " · " + failed.length + " feed error" + (failed.length === 1 ? "" : "s") : "");
    summary.append(summaryStrong, summaryCopy);

    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "preview-empty";
      empty.textContent = "No recent item matched strongly enough. Broaden the focus or add another feed, then run the filter again.";
      list.appendChild(empty);
    }

    items.forEach(function (item, index) {
      var article = document.createElement("article");
      article.className = "live-preview-card";
      var meta = document.createElement("div");
      meta.className = "live-preview-meta";
      var rank = document.createElement("span");
      rank.textContent = "0" + (index + 1);
      var source = document.createElement("span");
      source.textContent = item.source || "Public feed";
      var score = document.createElement("strong");
      score.textContent = typeof item.score === "number" ? item.score.toFixed(1) : "—";
      meta.append(rank, source, score);

      var title = document.createElement("h3");
      title.textContent = item.title || "Untitled feed item";
      var why = document.createElement("p");
      why.textContent = item.why || item.summary || "Matched the focus supplied for this preview.";
      article.append(meta, title, why);

      if (item.url) {
        var link = document.createElement("a");
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "Open original source ↗";
        article.appendChild(link);
      }
      list.appendChild(article);
    });

    failed.forEach(function (source) {
      var warning = document.createElement("p");
      warning.className = "preview-source-error";
      warning.textContent = "Skipped " + (source.url || "one feed") + ": " + (source.error || "could not read feed");
      list.appendChild(warning);
    });
  }

  function actionUrl(value) {
    if (typeof value !== "string" || !value.trim()) return "";
    try {
      var parsed = new URL(value, window.location.origin);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "";
      if (parsed.origin !== window.location.origin) return "";
      return parsed.href;
    } catch (error) {
      return "";
    }
  }

  function checkoutUrl(value) {
    if (typeof value !== "string" || !value.trim()) return "";
    try {
      var parsed = new URL(value, window.location.origin);
      return parsed.protocol === "https:" && parsed.hostname === "checkout.stripe.com" ? parsed.href : "";
    } catch (error) {
      return "";
    }
  }

  function managementTokenFromResult(result) {
    var candidates = [result && result.manage_url, result && result.status_url];
    for (var i = 0; i < candidates.length; i += 1) {
      if (typeof candidates[i] !== "string") continue;
      try {
        var parsed = new URL(candidates[i], window.location.origin);
        var queryToken = parsed.searchParams.get("manage");
        if (queryToken) return queryToken;
        var match = parsed.pathname.match(/\/api\/firehose\/subscriptions\/([^/]+)$/);
        if (match) return decodeURIComponent(match[1]);
      } catch (error) {
        continue;
      }
    }
    return "";
  }

  function renderSubscriptionActions(result) {
    activeManageUrl = actionUrl(result && result.manage_url);
    activeStatusUrl = actionUrl(result && result.status_url);
    activeUnsubscribeUrl = actionUrl(result && result.unsubscribe_url);
    activeManagementToken = managementTokenFromResult(result) || activeManagementToken;
    document.getElementById("manage-subscription").hidden = !activeStatusUrl && !activeManageUrl;
    document.getElementById("unsubscribe-subscription").hidden = !activeUnsubscribeUrl;
    document.getElementById("subscription-actions").hidden = !activeStatusUrl && !activeManageUrl && !activeUnsubscribeUrl && !activeManagementToken;
  }

  function showSubscriptionPreview(result) {
    var preview = result && result.preview;
    var wrapper = document.getElementById("preview-results");
    if (preview && Array.isArray(preview.items)) {
      renderLivePreview(preview);
      wrapper.hidden = false;
    } else {
      wrapper.hidden = true;
      document.getElementById("preview-summary").replaceChildren();
      document.getElementById("live-preview-list").replaceChildren();
    }
  }

  function subscriptionDetails(result) {
    if (!result || typeof result !== "object") return null;
    return result.subscription && typeof result.subscription === "object" ? result.subscription : result;
  }

  function trackLifecycleOnce(key, eventName, properties) {
    var storageKey = "paperboy.lifecycle." + key;
    if (sessionStorage.getItem(storageKey)) return;
    sessionStorage.setItem(storageKey, "1");
    trackProductEvent(eventName, properties);
  }

  function renderManagedSubscription(result) {
    var details = subscriptionDetails(result);
    if (!details) return;
    var status = String(details.status || result.status || "pending_verification").toLowerCase();
    var billingStatus = String(details.billing_status || result.billing_status || "unpaid").toLowerCase();
    if (details.cadence === "weekly" || details.cadence === "daily") activeCadence = details.cadence;
    var cadenceLabel = activeCadence === "weekly" ? "weekly" : "daily";
    var delivery = details.delivery || details.schedule || (cadenceLabel === "weekly" ? "Weekly · automatic" : "Daily · automatic");
    var isVerified = status === "active" || status === "confirmed";
    var isUnsubscribed = status === "unsubscribed";
    var isDelivering = isVerified && (billingStatus === "trialing" || billingStatus === "active");
    var checkoutRequired = isVerified && !isUnsubscribed && !isDelivering;
    var canCheckout = checkoutRequired && (billingStatus === "unpaid" || billingStatus === "canceled");
    var paymentLabels = {
      unpaid: "Checkout required",
      trialing: "7-day trial",
      active: "$5/month",
      past_due: "Payment past due",
      canceled: "Canceled"
    };
    var statusLabel = isUnsubscribed ? "Unsubscribed" : isVerified ? "Email verified" : "Awaiting confirmation";
    var deliveryLabel = isDelivering
      ? (typeof delivery === "string" ? delivery : "Daily · automatic")
      : isUnsubscribed || billingStatus === "canceled" ? "Stopped"
        : billingStatus === "past_due" ? "Paused"
          : checkoutRequired ? "Checkout required" : "Not started";
    document.getElementById("subscription-status").textContent = statusLabel;
    document.getElementById("subscription-delivery").textContent = deliveryLabel;
    document.getElementById("subscription-payment").textContent = isVerified
      ? (paymentLabels[billingStatus] || "Checkout required")
      : "Not started";
    if (result.manage_url || result.status_url || result.unsubscribe_url) renderSubscriptionActions(result);

    var summary = document.getElementById("management-summary");
    summary.replaceChildren();
    if (details.email_masked) {
      var email = document.createElement("p");
      email.textContent = "Email: " + details.email_masked;
      summary.appendChild(email);
    }
    if (details.focus) {
      var focus = document.createElement("p");
      focus.textContent = "Filter: " + details.focus;
      summary.appendChild(focus);
    }
    if (Array.isArray(details.sources)) {
      var sources = document.createElement("p");
      sources.textContent = details.sources.length + (details.sources.length === 1 ? " public source" : " public sources") + " connected";
      summary.appendChild(sources);
    }
    if (details.timezone) {
      var timezone = document.createElement("p");
      timezone.textContent = "Time zone: " + details.timezone;
      summary.appendChild(timezone);
    }
    if (details.cadence) {
      var cadence = document.createElement("p");
      cadence.textContent = "Frequency: " + (details.cadence === "weekly" ? "Weekly" : "Daily");
      summary.appendChild(cadence);
    }
    if (details.next_delivery_at && isDelivering) {
      var next = document.createElement("p");
      next.textContent = "Next delivery: " + details.next_delivery_at;
      summary.appendChild(next);
    }
    summary.hidden = !summary.childElementCount;

    document.getElementById("subscription-success-title").textContent = isUnsubscribed
      ? "This " + cadenceLabel + " rollup is unsubscribed."
      : billingStatus === "past_due" ? "Payment needs attention."
        : billingStatus === "canceled" ? "Your paid delivery is canceled."
      : isDelivering ? "Your " + cadenceLabel + " rollup is active."
        : isVerified ? "Email verified. Finish checkout to start delivery."
          : "Check your email.";
    document.getElementById("subscription-success-copy").textContent = isUnsubscribed
      ? "Automatic delivery is off. You can create a new filter whenever you are ready."
      : billingStatus === "past_due" ? "Delivery is paused until payment is updated. No new charge was attempted from this page."
        : billingStatus === "canceled" ? "Delivery is off. Your filter remains saved, and you can start a new hosted checkout when ready."
      : isDelivering ? "Paperboy will refresh the sources and deliver the strongest matches automatically."
        : isVerified ? "Your filter is saved. Start the hosted seven-day trial checkout; then it is $5 per month until canceled."
          : "Paperboy saved the filter and sent a confirmation link. Nothing will be delivered until you confirm the address.";
    document.getElementById("unsubscribe-subscription").hidden = isUnsubscribed || !activeUnsubscribeUrl;
    document.getElementById("start-checkout").hidden = !canCheckout || !activeManagementToken || result.checkout_available === false;
    document.getElementById("manage-billing").hidden = !activeManagementToken || result.portal_available !== true;
    if (result.checkout_available === false && checkoutRequired) {
      var fallback = document.getElementById("billing-fallback");
      fallback.textContent = "Checkout is temporarily unavailable. Your email is verified, no card was charged, and delivery has not started.";
      fallback.hidden = false;
    }
    if (isVerified) {
      trackLifecycleOnce("email_verified", "email_verified");
    }
    if (billingStatus === "trialing") {
      trackLifecycleOnce("trial_started", "trial_started", { billing_status: billingStatus });
    }
  }

  function attributionFields() {
    var params = new URLSearchParams(window.location.search);
    var fields = {};
    ["ref", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"].forEach(function (key) {
      var value = params.get(key);
      if (value) fields[key] = value;
    });
    return fields;
  }

  function getSelectedRepoObjects() {
    return fixtureRepos.filter(function (repo) {
      return state.selectedRepos.indexOf(repo.id) >= 0;
    });
  }

  function selectedSourceCount() {
    return (state.sources.forwarding ? 1 : 0) +
      (state.sources.publicCatalog ? 1 : 0) +
      (state.selectedRepos.length ? 1 : 0);
  }

  function sourceSummaryText() {
    var parts = [];
    if (state.sources.forwarding) parts.push("forwarded newsletters");
    if (state.sources.publicCatalog) parts.push("public intelligence");
    if (state.selectedRepos.length) parts.push(state.selectedRepos.length + " GitHub " + (state.selectedRepos.length === 1 ? "repo" : "repos"));
    return parts.length ? parts.join(", ") : "no sources";
  }

  function renderRepoList() {
    var picker = document.getElementById("repo-picker");
    var list = document.getElementById("repo-list");
    var count = document.getElementById("repo-count");
    var search = document.getElementById("repo-search");
    var selectedOnly = document.getElementById("selected-only");
    var message = document.getElementById("repo-message");
    var query = search ? search.value.trim().toLowerCase() : "";
    var only = selectedOnly ? selectedOnly.checked : false;

    picker.hidden = !state.fixtureLoaded;
    count.textContent = state.selectedRepos.length + " of " + MAX_REPOS + " selected";
    list.replaceChildren();

    if (!state.fixtureLoaded) return;

    var visible = fixtureRepos.filter(function (repo) {
      var matches = !query || (repo.name + " " + repo.language + " " + repo.description).toLowerCase().indexOf(query) >= 0;
      var selected = state.selectedRepos.indexOf(repo.id) >= 0;
      return matches && (!only || selected);
    });

    if (!visible.length) {
      var empty = document.createElement("p");
      empty.className = "repo-empty";
      empty.textContent = only ? "No selected repositories match." : "No fixture repositories match.";
      list.appendChild(empty);
      return;
    }

    visible.forEach(function (repo) {
      var label = document.createElement("label");
      label.className = "repo-row";
      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.selectedRepos.indexOf(repo.id) >= 0;
      checkbox.setAttribute("aria-label", "Select " + repo.name);

      var main = document.createElement("span");
      main.className = "repo-main";
      var name = document.createElement("strong");
      name.textContent = repo.name;
      var description = document.createElement("span");
      description.textContent = repo.description;
      main.append(name, description);

      var language = document.createElement("span");
      language.className = "repo-language";
      language.textContent = repo.language;

      checkbox.addEventListener("change", function () {
        var index = state.selectedRepos.indexOf(repo.id);
        if (checkbox.checked && index < 0) {
          if (state.selectedRepos.length >= MAX_REPOS) {
            checkbox.checked = false;
            message.textContent = "The local MVP preview supports up to five repositories. Remove one to choose another.";
            toast("Five-repository cap reached.");
            return;
          }
          state.selectedRepos.push(repo.id);
          message.textContent = repo.name + " selected. " + state.selectedRepos.length + " of five selected.";
        } else if (!checkbox.checked && index >= 0) {
          state.selectedRepos.splice(index, 1);
          message.textContent = repo.name + " removed.";
        }
        saveState();
        renderAll();
      });

      label.append(checkbox, main, language);
      list.appendChild(label);
    });
  }

  function renderSourceControls() {
    var forwarding = document.getElementById("source-forwarding");
    var publicCatalog = document.getElementById("source-public");
    if (forwarding) forwarding.checked = state.sources.forwarding;
    if (publicCatalog) publicCatalog.checked = state.sources.publicCatalog;
  }

  function renderFocus() {
    var summary = document.getElementById("focus-repo-summary");
    if (!summary) return;
    summary.replaceChildren();

    var sourceChip = document.createElement("span");
    sourceChip.className = "repo-chip";
    sourceChip.textContent = "Sources: " + sourceSummaryText();
    summary.appendChild(sourceChip);

    getSelectedRepoObjects().forEach(function (repo) {
      var chip = document.createElement("span");
      chip.className = "repo-chip";
      chip.textContent = repo.name;
      summary.appendChild(chip);
    });

    var description = document.getElementById("system-description");
    var watchlist = document.getElementById("current-friction");
    var skip = document.getElementById("score-low");
    if (description && document.activeElement !== description) description.value = state.interests.description;
    if (watchlist && document.activeElement !== watchlist) watchlist.value = state.interests.watchlist;
    if (skip && document.activeElement !== skip) skip.value = state.interests.skip;

    document.querySelectorAll('input[name="themes"]').forEach(function (input) {
      input.checked = state.interests.themes.indexOf(input.value) >= 0;
    });
  }

  function detectTimezone() {
    try {
      var detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      var select = document.getElementById("delivery-zone");
      if (!localStorage.getItem(STORAGE_KEY) && detected) state.delivery.timezone = detected;
      if (select && !Array.prototype.some.call(select.options, function (option) { return option.value === state.delivery.timezone; })) {
        state.delivery.timezone = "UTC";
      }
    } catch (error) {
      state.delivery.timezone = state.delivery.timezone || "UTC";
    }
    var intakeTimezone = document.getElementById("intake-timezone");
    if (intakeTimezone) intakeTimezone.value = state.delivery.timezone || "UTC";
  }

  function renderDelivery() {
    var email = document.getElementById("delivery-email");
    var time = document.getElementById("delivery-time");
    var timezone = document.getElementById("delivery-zone");
    var intakeTimezone = document.getElementById("intake-timezone");
    var intakeCadence = document.getElementById("intake-cadence");
    var intakeWeeklyDay = document.getElementById("intake-weekly-day");
    if (email && document.activeElement !== email) email.value = state.delivery.email || state.email;
    if (time && document.activeElement !== time) time.value = state.delivery.time;
    if (timezone) timezone.value = state.delivery.timezone;
    if (intakeTimezone && document.activeElement !== intakeTimezone) intakeTimezone.value = state.delivery.timezone || "UTC";
    if (intakeCadence) intakeCadence.value = state.delivery.cadence || "daily";
    if (intakeWeeklyDay) intakeWeeklyDay.value = String(state.delivery.weeklyDay || 0);
    renderCadenceFields();
    document.querySelectorAll('input[name="days"]').forEach(function (input) {
      input.checked = state.delivery.days.indexOf(input.value) >= 0;
    });
    renderMiniEmail();
  }

  function renderCadenceFields() {
    var cadence = document.getElementById("intake-cadence");
    var weeklyField = document.getElementById("weekly-day-field");
    var weeklyDay = document.getElementById("intake-weekly-day");
    if (!cadence || !weeklyField || !weeklyDay) return;
    var isWeekly = cadence.value === "weekly";
    weeklyField.hidden = !isWeekly;
    weeklyDay.disabled = !isWeekly;
  }

  function renderMiniEmail() {
    var container = document.getElementById("mini-email-content");
    if (!container) return;
    container.replaceChildren();
    [
      ["Today in 60 Seconds", "Two changes clear the morning bar"],
      ["Repo Radar", state.selectedRepos.length ? "One impact across selected fixture repos" : "Add a repo to enable this section"],
      ["Research Worth Reading", "One bounded technique to inspect"],
      ["Watchlist / Do Nothing", "One trend that does not deserve work"]
    ].forEach(function (entry) {
      var item = document.createElement("div");
      item.className = "mini-item";
      var code = document.createElement("code");
      code.textContent = entry[0];
      var strong = document.createElement("strong");
      strong.textContent = entry[1];
      item.append(code, strong);
      container.appendChild(item);
    });
  }

  function renderCheckout() {
    var repoCount = document.getElementById("checkout-repo-count");
    var delivery = document.getElementById("checkout-delivery");
    if (repoCount) repoCount.textContent = sourceSummaryText();
    if (delivery) {
      delivery.textContent = state.delivery.email ?
        state.delivery.days.join(", ") + " · " + state.delivery.time + " · " + state.delivery.timezone :
        "Not set";
    }
  }

  var billingStates = {
    active: { pill: "Active preview", message: "Your subscription is active—in this preview only.", action: "Manage billing preview" },
    incomplete: { pill: "Incomplete", message: "Finish payment to activate scheduled delivery. No payment exists in this demo.", action: "Finish payment preview" },
    processing: { pill: "Processing", message: "Payment is processing. This preview will not poll or settle a charge.", action: "Refresh preview" },
    past_due: { pill: "Past due", message: "Payment needs attention. Delivery would pause after the configured recovery policy.", action: "Update payment preview" },
    cancel_scheduled: { pill: "Ends later", message: "A live product would show the provider-verified period end. No date is invented here.", action: "Keep Paperboy preview" },
    canceled: { pill: "Canceled", message: "Hosted delivery is off. Data deletion remains a separate control.", action: "Restart preview" },
    unavailable: { pill: "Unavailable", message: "Billing details are unavailable. No new charge was started from this page.", action: "Try preview again" }
  };

  function renderAccount() {
    var selected = getSelectedRepoObjects();
    var heading = document.getElementById("account-repo-heading");
    var list = document.getElementById("account-repo-list");
    var details = document.getElementById("account-delivery-details");
    if (!heading || !list || !details) return;

    heading.textContent = selected.length + " of " + MAX_REPOS + " fixture repos selected";
    list.replaceChildren();
    var sourceChip = document.createElement("span");
    sourceChip.className = "repo-chip";
    sourceChip.textContent = "Sources: " + sourceSummaryText();
    list.appendChild(sourceChip);
    selected.forEach(function (repo) {
      var chip = document.createElement("span");
      chip.className = "repo-chip";
      chip.textContent = repo.name;
      list.appendChild(chip);
    });

    details.replaceChildren();
    [
      ["Email", state.delivery.email || state.email || "Not set"],
      ["Days", state.delivery.days.join(", ") || "Not set"],
      ["Time", state.delivery.time || "Not set"],
      ["Time zone", state.delivery.timezone || "Not set"]
    ].forEach(function (entry) {
      var row = document.createElement("div");
      var dt = document.createElement("dt");
      var dd = document.createElement("dd");
      dt.textContent = entry[0];
      dd.textContent = entry[1];
      row.append(dt, dd);
      details.appendChild(row);
    });

    var billingSelect = document.getElementById("billing-state");
    var billingPill = document.getElementById("billing-pill");
    var billingMessage = document.getElementById("billing-message");
    var billingAction = document.getElementById("billing-action");
    var preview = billingStates[state.billingState] || billingStates.active;
    billingSelect.value = state.billingState;
    billingPill.textContent = preview.pill;
    billingMessage.textContent = preview.message;
    billingAction.textContent = preview.action;
  }

  function renderBrief() {
    var list = document.getElementById("email-impact-list");
    var summary = document.getElementById("email-summary");
    if (!list || !summary) return;
    list.replaceChildren();

    var itemCount = briefSections.reduce(function (total, section) { return total + section.items.length; }, 0);
    summary.textContent = "Local sample · " + itemCount + " capped items · " + sourceSummaryText();

    briefSections.forEach(function (section) {
      var sectionHeading = document.createElement("div");
      sectionHeading.className = "email-section-heading";
      sectionHeading.textContent = section.section;
      list.appendChild(sectionHeading);

      section.items.forEach(function (item) {
        var article = document.createElement("section");
        article.className = "email-impact";
        article.setAttribute("aria-labelledby", "item-" + item.id);

        var meta = document.createElement("div");
        meta.className = "email-impact-meta";
        [item.source, item.score + "/10", item.repo].forEach(function (value) {
          var span = document.createElement("span");
          span.textContent = value;
          meta.appendChild(span);
        });

        var title = document.createElement("h2");
        title.id = "item-" + item.id;
        title.textContent = item.title;

        var whyHeading = document.createElement("h3");
        whyHeading.textContent = "Why it matters";
        var why = document.createElement("p");
        why.textContent = item.why;

        var inspect = document.createElement("div");
        inspect.className = "email-inspect";
        var inspectHeading = document.createElement("h3");
        inspectHeading.textContent = section.section === "Watchlist / Do Nothing" ? "Decision" : "Inspect next";
        var inspectCopy = document.createElement("p");
        inspectCopy.textContent = item.next;
        inspect.append(inspectHeading, inspectCopy);

        var evidence = document.createElement("a");
        evidence.className = "evidence-link";
        evidence.href = "https://github.com/cgallic/paperboy/blob/main/examples/action-queue.demo.jsonl";
        evidence.target = "_blank";
        evidence.rel = "noreferrer";
        evidence.textContent = "View " + item.evidence + " ↗";

        var feedback = document.createElement("div");
        feedback.className = "feedback-row";
        feedback.setAttribute("aria-label", "Local feedback preview for " + item.title);
        [
          ["useful", "Useful"],
          ["not_useful", "Not useful"],
          ["acted", "Acted"],
          ["wrong_repo", "Wrong repo"]
        ].forEach(function (signal) {
          var button = document.createElement("button");
          button.type = "button";
          button.textContent = signal[1];
          button.classList.toggle("selected", state.feedback[item.id] === signal[0]);
          button.setAttribute("aria-pressed", state.feedback[item.id] === signal[0] ? "true" : "false");
          button.addEventListener("click", function () {
            state.feedback[item.id] = state.feedback[item.id] === signal[0] ? "" : signal[0];
            saveState();
            renderBrief();
            toast(state.feedback[item.id] ? signal[1] + " saved locally." : "Local feedback cleared.");
          });
          feedback.appendChild(button);
        });

        article.append(meta, title, whyHeading, why, inspect, evidence, feedback);
        list.appendChild(article);
      });
    });
  }

  function renderAll() {
    renderSourceControls();
    renderRepoList();
    renderFocus();
    renderDelivery();
    renderCheckout();
    renderAccount();
    renderBrief();
  }

  function openConfirm(title, copy, actionLabel, action) {
    var dialog = document.getElementById("confirm-dialog");
    document.getElementById("confirm-title").textContent = title;
    document.getElementById("confirm-copy").textContent = copy;
    document.getElementById("confirm-action").textContent = actionLabel;
    pendingDialogAction = action;
    dialog.showModal();
  }

  document.addEventListener("click", function (event) {
    var start = event.target.closest("[data-start]");
    if (start) {
      event.preventDefault();
      trackProductEvent("signup_started");
      routeTo("signin");
      return;
    }

    var route = event.target.closest("[data-route]");
    if (route) {
      event.preventDefault();
      routeTo(route.getAttribute("data-route"), { step: route.getAttribute("data-setup-step") || null });
      return;
    }

    var step = event.target.closest("[data-go-step]");
    if (step) {
      event.preventDefault();
      showSetupStep(step.getAttribute("data-go-step"));
      history.replaceState(null, "", "#setup/" + currentStep);
    }
  });

  menuButton.addEventListener("click", function () {
    var open = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", open ? "false" : "true");
    mobileNav.hidden = open;
  });

  document.getElementById("magic-link-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var form = event.currentTarget;
    var input = document.getElementById("signin-email");
    var error = document.getElementById("email-error");
    var intakeError = document.getElementById("intake-error");
    var submit = document.getElementById("subscription-submit");
    var email = input.value.trim();
    var sourceUrls = sourceLines(document.getElementById("source-urls").value);
    var workFocus = document.getElementById("work-focus").value.trim();
    var ignoreFocus = document.getElementById("ignore-focus").value.trim();
    var timezone = document.getElementById("intake-timezone").value.trim();
    var cadence = document.getElementById("intake-cadence").value;
    var weeklyDay = Number(document.getElementById("intake-weekly-day").value);
    var consent = document.getElementById("email-consent").checked;
    if (!isValidEmail(input.value.trim())) {
      error.textContent = "Enter a valid email address.";
      input.setAttribute("aria-invalid", "true");
      input.focus();
      return;
    }
    error.textContent = "";
    input.removeAttribute("aria-invalid");
    intakeError.textContent = "";
    if (!sourceUrls.length) {
      intakeError.textContent = "Add at least one public RSS or Atom feed URL.";
      document.getElementById("source-urls").focus();
      return;
    }
    if (sourceUrls.length > MAX_SUBSCRIPTION_SOURCES || sourceUrls.some(function (url) { return !/^https?:\/\/\S+$/i.test(url); })) {
      intakeError.textContent = "Use up to six public feed URLs beginning with http:// or https://.";
      document.getElementById("source-urls").focus();
      return;
    }
    if (!workFocus) {
      intakeError.textContent = "Describe what should make an item relevant.";
      document.getElementById("work-focus").focus();
      return;
    }
    if (!timezone) {
      intakeError.textContent = "Confirm the time zone for the rollup.";
      document.getElementById("intake-timezone").focus();
      return;
    }
    if (!consent) {
      intakeError.textContent = "Agree to receive the brief before continuing.";
      document.getElementById("email-consent").focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Validating and sending confirmation…";
    state.email = email;
    state.delivery.email = state.email;
    state.delivery.timezone = timezone;
    state.delivery.cadence = cadence;
    state.delivery.weeklyDay = weeklyDay;
    saveState();

    var subscribeResult;
    try {
      var subscribeResponse = await fetch("/api/firehose/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({
          email: email,
          sources: sourceUrls,
          focus: workFocus,
          ignore: ignoreFocus ? ignoreFocus.split(",").map(function (term) { return term.trim(); }).filter(Boolean) : [],
          timezone: timezone,
          cadence: cadence,
          weekly_day: weeklyDay,
          consent: true,
          analytics_consent: analyticsAllowed()
        }, {
          source: "paperboy_automatic_subscription",
          page: window.location.href
        }, attributionFields()))
      });
      subscribeResult = await subscribeResponse.json();
      if (!subscribeResponse.ok || !subscribeResult || subscribeResult.ok !== true || ["pending_verification", "pending"].indexOf(subscribeResult.status) < 0) {
        throw new Error(subscriptionErrorMessage(subscribeResponse, subscribeResult));
      }
    } catch (subscriptionError) {
      intakeError.textContent = subscriptionError && subscriptionError.message ? subscriptionError.message : "Paperboy could not save the rollup request. Try again.";
      submit.disabled = false;
      submit.textContent = "Build my rollup";
      return;
    }

    trackProductEvent("subscription_requested", {
      source_count: sourceUrls.length,
      cadence: cadence,
      weekly_day: weeklyDay
    });
    document.getElementById("subscription-success-title").textContent = "Check your email.";
    document.getElementById("subscription-success-copy").textContent = "Paperboy saved your filter and sent a confirmation link. Nothing will be delivered until you confirm the address and finish checkout.";
    document.getElementById("subscription-status").textContent = "Awaiting confirmation";
    document.getElementById("subscription-delivery").textContent = "Not started";
    document.getElementById("subscription-payment").textContent = "Not started";
    document.getElementById("start-checkout").hidden = true;
    document.getElementById("management-summary").hidden = true;
    showSubscriptionPreview(subscribeResult);
    renderSubscriptionActions(subscribeResult);
    form.hidden = true;
    document.getElementById("magic-success").hidden = false;
  });

  document.getElementById("change-email").addEventListener("click", function () {
    document.getElementById("magic-success").hidden = true;
    document.getElementById("confirmation-panel").hidden = true;
    document.getElementById("magic-link-form").hidden = false;
    var submit = document.getElementById("subscription-submit");
    submit.disabled = false;
    submit.textContent = "Build my rollup";
    document.getElementById("source-urls").focus();
  });

  async function refreshManagedSubscription(url) {
    var response = await fetch(url, { headers: { "Accept": "application/json" } });
    var result = await response.json();
    if (!response.ok || !result || result.ok !== true || ["pending_verification", "active", "confirmed", "unsubscribed"].indexOf(result.status) < 0) {
      throw new Error(subscriptionErrorMessage(response, result));
    }
    renderManagedSubscription(result);
    return result;
  }

  document.getElementById("manage-subscription").addEventListener("click", async function (event) {
    var button = event.currentTarget;
    if (!activeStatusUrl && activeManageUrl) {
      window.location.assign(activeManageUrl);
      return;
    }
    if (!activeStatusUrl) return;
    button.disabled = true;
    button.textContent = "Refreshing…";
    try {
      await refreshManagedSubscription(activeStatusUrl);
      toast("Subscription status refreshed.");
    } catch (error) {
      document.getElementById("subscription-success-copy").textContent = error && error.message
        ? error.message
        : "Paperboy could not load this subscription.";
    } finally {
      button.disabled = false;
      button.textContent = "Refresh subscription status";
    }
  });

  document.getElementById("start-checkout").addEventListener("click", async function (event) {
    var button = event.currentTarget;
    var fallback = document.getElementById("billing-fallback");
    if (!activeManagementToken) {
      fallback.textContent = "Open the private management link from your email before starting checkout.";
      fallback.hidden = false;
      return;
    }
    button.disabled = true;
    button.textContent = "Opening secure checkout…";
    fallback.hidden = true;
    trackProductEvent("begin_checkout", { currency: "USD" });
    try {
      var response = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: activeManagementToken })
      });
      var result = await response.json();
      var target = checkoutUrl(result && result.checkout_url);
      if (!response.ok || !result || result.ok !== true || !target) {
        throw new Error(result && (result.detail || result.error));
      }
      sessionStorage.setItem(CHECKOUT_MANAGEMENT_KEY, activeManagementToken);
      window.location.assign(target);
    } catch (error) {
      fallback.textContent = "Checkout is temporarily unavailable. Your email is verified, no card was charged, and delivery has not started.";
      fallback.hidden = false;
      button.disabled = false;
      button.textContent = "Try founding checkout again";
    }
  });

  document.getElementById("manage-billing").addEventListener("click", async function (event) {
    var button = event.currentTarget;
    var fallback = document.getElementById("billing-fallback");
    button.disabled = true;
    fallback.hidden = true;
    try {
      var response = await fetch("/api/billing/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: activeManagementToken })
      });
      var result = await response.json();
      var target = typeof result.portal_url === "string" ? new URL(result.portal_url) : null;
      if (!response.ok || !result.ok || !target || target.protocol !== "https:" || target.hostname !== "billing.stripe.com") {
        throw new Error("billing portal unavailable");
      }
      window.location.assign(target.href);
    } catch (error) {
      fallback.textContent = "Billing management is temporarily unavailable. No account change was made.";
      fallback.hidden = false;
      button.disabled = false;
    }
  });

  document.getElementById("unsubscribe-subscription").addEventListener("click", function () {
    if (!activeUnsubscribeUrl) return;
    openConfirm(
      "Stop this rollup?",
      "Paperboy will stop automatic delivery. Your existing source links are not deleted by this action.",
      "Unsubscribe",
      async function () {
        var button = document.getElementById("unsubscribe-subscription");
        button.disabled = true;
        try {
          var response = await fetch(activeUnsubscribeUrl, {
            method: "POST",
            headers: { "Accept": "application/json" }
          });
          var result = await response.json();
          if (!response.ok || !result || result.ok !== true || result.status !== "unsubscribed") {
            throw new Error(subscriptionErrorMessage(response, result));
          }
          renderManagedSubscription(result);
          toast("Scheduled delivery stopped.");
        } catch (error) {
          document.getElementById("subscription-success-copy").textContent = error && error.message
            ? error.message
            : "Paperboy could not stop this subscription. Try again.";
        } finally {
          button.disabled = false;
        }
      }
    );
  });

  document.getElementById("confirm-subscription").addEventListener("click", async function (event) {
    var button = event.currentTarget;
    var errorNode = document.getElementById("confirmation-error");
    if (!confirmationToken) return;
    button.disabled = true;
    button.textContent = "Confirming…";
    errorNode.textContent = "";
    try {
      var encoded = encodeURIComponent(confirmationToken);
      var response = await fetch("/api/firehose/subscriptions/" + encoded + "/confirm", {
        method: "POST",
        headers: { "Accept": "application/json" }
      });
      var result = await response.json();
      if (!response.ok || !result || result.ok !== true || ["active", "confirmed"].indexOf(result.status) < 0) {
        throw new Error(subscriptionErrorMessage(response, result));
      }
      confirmationToken = "";
      history.replaceState(null, "", window.location.pathname + "#signin");
      document.getElementById("confirmation-panel").hidden = true;
      document.getElementById("magic-success").hidden = false;
      renderSubscriptionActions(result);
      renderManagedSubscription(result);
      document.getElementById("billing-fallback").hidden = true;
      if (result.checkout_available === false) {
        document.getElementById("start-checkout").hidden = true;
        document.getElementById("billing-fallback").textContent = "Checkout is temporarily unavailable. Your email is verified, no card was charged, and delivery has not started.";
        document.getElementById("billing-fallback").hidden = false;
      }
    } catch (error) {
      errorNode.textContent = error && error.message ? error.message : "Paperboy could not verify this link. It may be invalid or expired.";
      button.disabled = false;
      button.textContent = "Confirm my email";
    }
  });

  document.querySelectorAll("[data-feed-preset]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById("source-urls");
      var url = button.getAttribute("data-feed-preset");
      var sources = sourceLines(input.value);
      var existingIndex = sources.indexOf(url);
      if (existingIndex >= 0) {
        sources.splice(existingIndex, 1);
        button.setAttribute("aria-pressed", "false");
      } else {
        sources.push(url);
        button.setAttribute("aria-pressed", "true");
      }
      input.value = sources.join("\n");
    });
  });

  document.getElementById("intake-cadence").addEventListener("change", function (event) {
    state.delivery.cadence = event.target.value === "weekly" ? "weekly" : "daily";
    saveState();
    renderCadenceFields();
  });

  document.getElementById("intake-weekly-day").addEventListener("change", function (event) {
    state.delivery.weeklyDay = Number(event.target.value);
    saveState();
  });

  document.getElementById("source-forwarding").addEventListener("change", function (event) {
    state.sources.forwarding = event.target.checked;
    saveState();
    renderAll();
  });

  document.getElementById("source-public").addEventListener("change", function (event) {
    state.sources.publicCatalog = event.target.checked;
    saveState();
    renderAll();
  });

  document.getElementById("load-fixture-repos").addEventListener("click", function () {
    state.fixtureLoaded = true;
    saveState();
    renderRepoList();
    document.getElementById("repo-picker").scrollIntoView({ behavior: "smooth", block: "start" });
    toast("Fictional repositories loaded locally.");
  });

  document.getElementById("repo-search").addEventListener("input", renderRepoList);
  document.getElementById("selected-only").addEventListener("change", renderRepoList);

  document.getElementById("continue-to-focus").addEventListener("click", function () {
    var message = document.getElementById("repo-message");
    if (!selectedSourceCount()) {
      message.textContent = "Choose forwarded newsletters, public intelligence, or at least one fixture repository.";
      message.focus();
      return;
    }
    showSetupStep("focus");
    history.replaceState(null, "", "#setup/focus");
  });

  document.getElementById("focus-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var description = document.getElementById("system-description").value.trim();
    var watchlist = document.getElementById("current-friction").value.trim();
    var error = document.getElementById("focus-error");
    if (!description || !watchlist) {
      error.textContent = "Describe your interests and one decision or risk on your watchlist.";
      (!description ? document.getElementById("system-description") : document.getElementById("current-friction")).focus();
      return;
    }
    error.textContent = "";
    state.interests.description = description;
    state.interests.watchlist = watchlist;
    state.interests.skip = document.getElementById("score-low").value.trim();
    state.interests.themes = Array.prototype.slice.call(document.querySelectorAll('input[name="themes"]:checked')).map(function (input) { return input.value; });
    saveState();
    showSetupStep("delivery");
    history.replaceState(null, "", "#setup/delivery");
  });

  document.getElementById("delivery-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var email = document.getElementById("delivery-email").value.trim();
    var days = Array.prototype.slice.call(document.querySelectorAll('input[name="days"]:checked')).map(function (input) { return input.value; });
    var error = document.getElementById("delivery-error");
    if (!isValidEmail(email)) {
      error.textContent = "Enter a valid delivery email.";
      document.getElementById("delivery-email").focus();
      return;
    }
    if (!days.length) {
      error.textContent = "Choose at least one delivery day.";
      return;
    }
    error.textContent = "";
    state.delivery.email = email;
    state.delivery.time = document.getElementById("delivery-time").value;
    state.delivery.timezone = document.getElementById("delivery-zone").value;
    state.delivery.days = days;
    saveState();
    routeTo("checkout");
  });

  document.getElementById("simulate-checkout").addEventListener("click", function () {
    state.billingState = "active";
    saveState();
    toast("Successful setup previewed locally. No charge or schedule was created.");
    routeTo("account");
  });

  document.getElementById("billing-state").addEventListener("change", function (event) {
    state.billingState = event.target.value;
    saveState();
    renderAccount();
  });

  document.getElementById("billing-action").addEventListener("click", function () {
    toast("Billing action preview only. No provider was called.");
  });

  document.getElementById("preview-disconnect").addEventListener("click", function () {
    openConfirm(
      "Preview GitHub disconnect?",
      "This clears selected fixture repositories and leaves newsletter/public source choices intact. It does not contact GitHub or affect billing.",
      "Clear fixture repos",
      function () {
        state.selectedRepos = [];
        saveState();
        renderAll();
        toast("Fixture repository state cleared locally.");
      }
    );
  });

  document.getElementById("clear-local-data").addEventListener("click", function () {
    openConfirm(
      "Clear all local demo data?",
      "This removes the email, source choices, fixture repos, interests, schedule, billing preview, and feedback stored under the Paperboy demo key in this browser.",
      "Clear local data",
      function () {
        localStorage.removeItem(STORAGE_KEY);
        state = cloneDefault();
        saveState();
        renderAll();
        toast("Local Paperboy demo data cleared.");
        routeTo("home");
      }
    );
  });

  document.getElementById("confirm-dialog").addEventListener("close", function (event) {
    if (event.target.returnValue === "confirm" && typeof pendingDialogAction === "function") {
      pendingDialogAction();
    }
    pendingDialogAction = null;
  });

  document.getElementById("allow-analytics").addEventListener("click", function () {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, "granted");
    updateAnalyticsConsentUi();
    trackPageViewOnce();
    toast("Optional first-party product analytics allowed.");
  });

  document.getElementById("decline-analytics").addEventListener("click", function () {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, "declined");
    localStorage.removeItem(ANALYTICS_ID_KEY);
    updateAnalyticsConsentUi();
    toast("Optional product analytics remains off.");
  });

  function openConfirmationScreen(token) {
    confirmationToken = token;
    routeTo("signin");
    document.getElementById("magic-link-form").hidden = true;
    document.getElementById("magic-success").hidden = true;
    document.getElementById("confirmation-panel").hidden = false;
    document.getElementById("confirmation-error").textContent = "";
    var button = document.getElementById("confirm-subscription");
    button.disabled = false;
    button.textContent = "Confirm my email";
  }

  async function openManagedSubscription(token) {
    routeTo("signin");
    confirmationToken = "";
    document.getElementById("magic-link-form").hidden = true;
    document.getElementById("confirmation-panel").hidden = true;
    document.getElementById("magic-success").hidden = false;
    document.getElementById("subscription-success-title").textContent = "Loading your rollup…";
    document.getElementById("subscription-success-copy").textContent = "Paperboy is checking the current subscription status.";
    document.getElementById("subscription-status").textContent = "Checking";
    document.getElementById("preview-results").hidden = true;
    var encoded = encodeURIComponent(token);
    renderSubscriptionActions({
      status_url: "/api/firehose/subscriptions/" + encoded,
      manage_url: window.location.href,
      unsubscribe_url: "/api/firehose/subscriptions/" + encoded + "/unsubscribe"
    });
    try {
      await refreshManagedSubscription(activeStatusUrl);
    } catch (error) {
      document.getElementById("subscription-success-title").textContent = "Paperboy could not open this rollup.";
      document.getElementById("subscription-success-copy").textContent = error && error.message
        ? error.message
        : "The management link may be invalid or expired.";
      document.getElementById("subscription-status").textContent = "Unavailable";
      document.getElementById("subscription-delivery").textContent = "Not confirmed";
      document.getElementById("unsubscribe-subscription").hidden = true;
    }
  }

  function initialRoute() {
    detectTimezone();
    updateAnalyticsConsentUi();
    trackPageViewOnce();
    void loadRuntimeAvailability();
    var params = new URLSearchParams(location.search);
    var confirmToken = params.get("confirm");
    var manageToken = params.get("manage");
    if (confirmToken) {
      openConfirmationScreen(confirmToken);
      return;
    }
    if (params.get("billing") === "success" && !manageToken) {
      manageToken = sessionStorage.getItem(CHECKOUT_MANAGEMENT_KEY) || "";
    }
    if (manageToken) {
      openManagedSubscription(manageToken);
      return;
    }
    var hash = location.hash.replace(/^#/, "");
    if (hash.indexOf("setup/") === 0) {
      routeTo("setup", { step: hash.split("/")[1] });
    } else if (["home", "signin", "checkout", "account", "brief"].indexOf(hash) >= 0) {
      routeTo(hash);
    } else {
      routeTo("home");
    }
  }

  saveState();
  initialRoute();
})();
