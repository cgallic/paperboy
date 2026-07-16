(function () {
  "use strict";

  var STORAGE_KEY = "paperboy.product-demo.v2";
  var MAX_REPOS = 5;

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
          repo: "Operator watchlist",
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
      days: ["Mon", "Tue", "Wed", "Thu", "Fri"]
    },
    billingState: "active",
    feedback: {}
  };

  var state = loadState();
  var pendingDialogAction = null;
  var currentScreen = "home";
  var currentStep = "sources";

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
      if (select && Array.prototype.some.call(select.options, function (option) { return option.value === detected; })) {
        if (!localStorage.getItem(STORAGE_KEY)) state.delivery.timezone = detected;
      }
    } catch (error) {
      state.delivery.timezone = state.delivery.timezone || "UTC";
    }
  }

  function renderDelivery() {
    var email = document.getElementById("delivery-email");
    var time = document.getElementById("delivery-time");
    var timezone = document.getElementById("delivery-zone");
    if (email && document.activeElement !== email) email.value = state.delivery.email || state.email;
    if (time && document.activeElement !== time) time.value = state.delivery.time;
    if (timezone) timezone.value = state.delivery.timezone;
    document.querySelectorAll('input[name="days"]').forEach(function (input) {
      input.checked = state.delivery.days.indexOf(input.value) >= 0;
    });
    renderMiniEmail();
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

  document.getElementById("magic-link-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var input = document.getElementById("signin-email");
    var error = document.getElementById("email-error");
    if (!isValidEmail(input.value.trim())) {
      error.textContent = "Enter a valid email address.";
      input.setAttribute("aria-invalid", "true");
      input.focus();
      return;
    }
    error.textContent = "";
    input.removeAttribute("aria-invalid");
    state.email = input.value.trim();
    state.delivery.email = state.email;
    saveState();
    event.currentTarget.hidden = true;
    document.getElementById("magic-success").hidden = false;
  });

  document.getElementById("change-email").addEventListener("click", function () {
    document.getElementById("magic-success").hidden = true;
    document.getElementById("magic-link-form").hidden = false;
    document.getElementById("signin-email").focus();
  });

  document.getElementById("simulate-magic-link").addEventListener("click", function () {
    state.magicLinkPreviewed = true;
    saveState();
    routeTo("setup", { step: "sources" });
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

  function initialRoute() {
    detectTimezone();
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
