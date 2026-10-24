"use strict";
(() => {
  const root = document.querySelector("#weibo-explorer");
  const data = document.querySelector("#weibo-explorer-data");
  if (!root || !data) return;
  const payload = JSON.parse(data.textContent);
  const accounts = payload.accounts;
  const coverage = document.querySelector("#weibo-coverage");
  if (coverage && payload.coverage) {
    const total = payload.coverage.total;
    const waffle = coverage.querySelector("#coverage-waffle");
    const cells = [...waffle.querySelectorAll(".coverage-cell")];
    const key = coverage.querySelector("#coverage-key");
    const explanation = coverage.querySelector("#coverage-explanation");
    let modeId = "evidence", mode = payload.coverage.modes.evidence, pinned = "", inspected = "";
    const emphasize = state => {
      if (state === inspected) return;
      inspected = state;
      const group = mode.groups.find(item => item.id === state);
      for (const cell of cells) cell.classList.toggle("coverage-dimmed", !!state && cell.dataset.state !== state);
      for (const button of key.querySelectorAll("button")) {
        button.setAttribute("aria-pressed", String(button.dataset.state === state));
      }
      explanation.textContent = group ? group.note : mode.explanation;
    };
    const renderCoverage = (selectedMode, writeUrl = false) => {
      modeId = selectedMode;
      mode = payload.coverage.modes[modeId];
      pinned = inspected = "";
      let index = 0;
      for (const group of mode.groups) {
        for (let i = 0; i < group.count; i++) {
          const cell = cells[index++];
          cell.dataset.state = group.id;
          cell.setAttribute("class", `coverage-cell ${group.id}`);
        }
      }
      coverage.querySelector("#coverage-percent").textContent = `${mode.percent.toFixed(1)}%`;
      coverage.querySelector("#coverage-headline").textContent = mode.headline;
      coverage.querySelector("#coverage-tally").textContent =
        `${mode.count.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} selected outlets ` +
        (modeId === "evidence" ? "have no confirmed account decision." : "have not had a manual review.");
      waffle.setAttribute("aria-label", `${total} selected domains: ${mode.count} ${mode.headline}`);
      waffle.querySelector("title").textContent = modeId === "evidence" ?
        "Known accounts occupy a small part of the research coverage map" : "Manual review coverage";
      waffle.querySelector("desc").textContent = modeId === "evidence" ?
        "Each square is one selected domain, grouped by research outcome. Unfilled squares are unknown, not verified absences." :
        "Each square is one selected domain. Filled squares have been manually reviewed; unfilled squares have not. Review does not guarantee an account decision.";
      for (const button of coverage.querySelectorAll("[data-coverage-mode]")) {
        button.setAttribute("aria-pressed", String(button.dataset.coverageMode === modeId));
      }
      key.replaceChildren();
      for (const group of mode.groups) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "coverage-category";
        button.dataset.state = group.id;
        button.setAttribute("aria-pressed", "false");
        const swatch = document.createElement("span");
        swatch.className = `coverage-swatch ${group.id}`;
        swatch.setAttribute("aria-hidden", "true");
        const name = document.createElement("span");
        name.className = "coverage-category-name";
        name.textContent = group.label;
        const count = document.createElement("small");
        count.textContent = `${group.count.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} domains`;
        name.append(count);
        const percent = document.createElement("strong");
        percent.textContent = `${group.percent.toFixed(1)}%`;
        button.append(swatch, name, percent);
        button.addEventListener("pointerenter", () => emphasize(group.id));
        button.addEventListener("pointerleave", () => emphasize(pinned));
        button.addEventListener("focus", () => emphasize(group.id));
        button.addEventListener("click", () => { pinned = pinned === group.id ? "" : group.id; emphasize(pinned); });
        key.append(button);
      }
      explanation.textContent = mode.explanation;
      if (writeUrl && location.protocol !== "file:") {
        const url = new URL(location.href);
        if (modeId === "evidence") url.searchParams.delete("coverage");
        else url.searchParams.set("coverage", modeId);
        history.replaceState(null, "", url);
      }
    };
    for (const button of coverage.querySelectorAll("[data-coverage-mode]")) {
      button.addEventListener("click", () => renderCoverage(button.dataset.coverageMode, true));
    }
    waffle.addEventListener("pointermove", event => {
      const cell = event.target.closest(".coverage-cell");
      if (cell) emphasize(cell.dataset.state);
    });
    waffle.addEventListener("pointerleave", () => emphasize(pinned));
    waffle.addEventListener("click", event => {
      const cell = event.target.closest(".coverage-cell");
      if (cell) { pinned = pinned === cell.dataset.state ? "" : cell.dataset.state; emphasize(pinned); }
    });
    waffle.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
      event.preventDefault();
      const index = mode.groups.findIndex(group => group.id === inspected);
      const next = index < 0 ? (event.key === "ArrowLeft" ? mode.groups.length - 1 : 0) :
        (index + (event.key === "ArrowLeft" ? -1 : 1) + mode.groups.length) % mode.groups.length;
      pinned = event.key === "Escape" ? "" : event.key === "Home" ? mode.groups[0].id :
        event.key === "End" ? mode.groups.at(-1).id :
        mode.groups[next].id;
      emphasize(pinned);
    });
    const requested = new URL(location.href).searchParams.get("coverage");
    renderCoverage(Object.hasOwn(payload.coverage.modes, requested) ? requested : "evidence");
  }
  const form = root.querySelector("#weibo-filters");
  const search = root.querySelector("#weibo-search");
  const category = root.querySelector("#weibo-category");
  const evidence = root.querySelector("#weibo-evidence");
  const followup = root.querySelector("#weibo-followup");
  const dots = [...root.querySelectorAll(".weibo-dot")];
  const cards = [...root.querySelectorAll(".weibo-brand")];
  const details = [...root.querySelectorAll(".weibo-channel-detail")];
  const normalize = value => String(value).normalize("NFKC").toLocaleLowerCase();
  const byId = new Map(accounts.map(account => [account.id, {...account, search: normalize(account.search)}]));
  const parameters = new URL(location.href).searchParams;
  search.value = parameters.get("q") || "";
  if ([...category.options].some(option => option.value === parameters.get("category"))) {
    category.value = parameters.get("category");
  }
  if ([...evidence.options].some(option => option.value === parameters.get("evidence"))) {
    evidence.value = parameters.get("evidence");
  }
  followup.checked = parameters.get("followup") === "1";
  const hashId = () => {
    try { return decodeURIComponent(location.hash).replace(/^#weibo-account-/, ""); }
    catch { return ""; }
  };
  let selected = hashId();

  const update = (writeUrl = true) => {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    const matching = accounts.filter(account => {
      const item = byId.get(account.id);
      return (!category.value || item.category === category.value) &&
        (!evidence.value || item.state === evidence.value) &&
        (!followup.checked || item.needs_review) &&
        terms.every(term => item.search.includes(term));
    });
    const ids = new Set(matching.map(account => account.id));
    const outlets = new Set(matching.map(account => account.outlet));
    if (!ids.has(selected)) selected = matching[0]?.id || "";
    for (const dot of dots) {
      const active = dot.dataset.accountId === selected;
      dot.hidden = !ids.has(dot.dataset.accountId);
      dot.setAttribute("aria-current", String(active));
    }
    for (const card of cards) card.hidden = !outlets.has(card.dataset.outletId);
    for (const detail of details) detail.hidden = detail.dataset.accountId !== selected;
    root.querySelector("#weibo-empty").hidden = matching.length !== 0;
    root.querySelector("#weibo-empty-detail").hidden = matching.length !== 0;
    root.querySelector("#weibo-result-count").textContent =
      `${matching.length} channel${matching.length === 1 ? "" : "s"} across ${outlets.size} publisher / brand group${outlets.size === 1 ? "" : "s"}`;
    for (const count of root.querySelectorAll("[data-state-count]")) {
      count.textContent = matching.filter(account => account.state === count.dataset.stateCount).length;
    }
    if (writeUrl) {
      const url = new URL(location.href);
      for (const [key, value] of [["q", search.value.trim()], ["category", category.value],
        ["evidence", evidence.value], ["followup", followup.checked ? "1" : ""]]) {
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      }
      url.hash = selected ? `weibo-account-${selected}` : "";
      if (location.protocol === "file:") url.search = location.search;
      history.replaceState(null, "", url);
    }
  };
  root.classList.add("weibo-interactive");
  if (byId.has(selected)) {
    root.classList.add("weibo-detail-open");
    root.closest("#weibo-directory")?.setAttribute("open", "");
  }
  form.hidden = false;
  const back = root.querySelector("#weibo-back");
  back.hidden = false;
  back.addEventListener("click", () => {
    root.classList.remove("weibo-detail-open");
    const dot = dots.find(node => node.dataset.accountId === selected);
    dot?.focus({preventScroll: true});
    dot?.scrollIntoView({block: "center", behavior: "auto"});
  });
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("input", () => update());
  form.addEventListener("change", () => update());
  form.addEventListener("reset", event => {
    event.preventDefault();
    search.value = category.value = evidence.value = "";
    followup.checked = false;
    root.classList.remove("weibo-detail-open");
    update();
  });
  for (const dot of dots) dot.addEventListener("click", event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    selected = dot.dataset.accountId;
    root.classList.add("weibo-detail-open");
    update();
    const detail = document.getElementById(`weibo-account-${selected}`);
    detail.querySelector("h3").focus({preventScroll: true});
    if (matchMedia("(max-width: 760px)").matches) {
      detail.scrollIntoView({block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
    }
  });
  window.addEventListener("hashchange", () => {
    selected = hashId();
    if (byId.has(selected)) {
      root.classList.add("weibo-detail-open");
      root.closest("#weibo-directory")?.setAttribute("open", "");
    }
    update(false);
  });
  update(false);
})();
