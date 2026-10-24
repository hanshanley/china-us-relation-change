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
    const bar = coverage.querySelector("#coverage-bar");
    const key = coverage.querySelector("#coverage-key");
    const explanation = coverage.querySelector("#coverage-explanation");
    let modeId = "evidence", mode = payload.coverage.modes.evidence, pinned = "", inspected = "";
    const emphasize = state => {
      if (state === inspected) return;
      inspected = state;
      const group = mode.groups.find(item => item.id === state);
      for (const segment of bar.children) {
        segment.classList.toggle("coverage-dimmed", !!state && segment.dataset.state !== state);
      }
      for (const button of key.querySelectorAll("button")) {
        button.setAttribute("aria-pressed", String(button.dataset.state === state));
      }
      explanation.textContent = group ? group.note : mode.explanation;
    };
    const renderCoverage = (selectedMode, writeUrl = false) => {
      modeId = selectedMode;
      mode = payload.coverage.modes[modeId];
      pinned = inspected = "";
      bar.replaceChildren();
      key.replaceChildren();
      for (const group of mode.groups) {
        const segment = document.createElement("span");
        segment.className = `coverage-segment ${group.id}`;
        segment.dataset.state = group.id;
        segment.dataset.count = group.count;
        segment.style.width = `${group.count / total * 100}%`;
        segment.title = `${group.label}: ${group.count.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} (${group.percent.toFixed(1)}%)`;
        bar.append(segment);
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
        button.addEventListener("click", () => {
          pinned = pinned === group.id ? "" : group.id;
          emphasize(pinned);
        });
        key.append(button);
      }
      const tally = coverage.querySelector("#coverage-tally");
      const amount = document.createElement("strong");
      amount.textContent = `${mode.documented.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} selected domains`;
      tally.replaceChildren(amount, document.createTextNode(modeId === "evidence" ?
        " have a documented account association." : " have a recorded manual review."));
      bar.setAttribute("aria-label", `${total} selected domains: ${mode.count} ${mode.headline}`);
      for (const button of coverage.querySelectorAll("[data-coverage-mode]")) {
        button.setAttribute("aria-pressed", String(button.dataset.coverageMode === modeId));
      }
      explanation.textContent = mode.explanation;
      if (writeUrl && location.protocol !== "file:") {
        const url = new URL(location.href);
        if (modeId === "evidence") url.searchParams.delete("coverage");
        else url.searchParams.set("coverage", modeId);
        history.replaceState(null, "", url);
      }
    };
    coverage.querySelector(".coverage-modes").hidden = false;
    bar.setAttribute("role", "group");
    bar.tabIndex = 0;
    bar.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight Home End Escape");
    for (const button of coverage.querySelectorAll("[data-coverage-mode]")) {
      button.addEventListener("click", () => renderCoverage(button.dataset.coverageMode, true));
    }
    bar.addEventListener("pointermove", event => {
      const segment = event.target.closest(".coverage-segment");
      if (segment) emphasize(segment.dataset.state);
    });
    bar.addEventListener("pointerleave", () => emphasize(pinned));
    bar.addEventListener("click", event => {
      const segment = event.target.closest(".coverage-segment");
      if (segment) {
        pinned = pinned === segment.dataset.state ? "" : segment.dataset.state;
        emphasize(pinned);
      }
    });
    bar.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
      event.preventDefault();
      const index = mode.groups.findIndex(group => group.id === inspected);
      const next = index < 0 ? (event.key === "ArrowLeft" ? mode.groups.length - 1 : 0) :
        (index + (event.key === "ArrowLeft" ? -1 : 1) + mode.groups.length) % mode.groups.length;
      pinned = event.key === "Escape" ? "" : event.key === "Home" ? mode.groups[0].id :
        event.key === "End" ? mode.groups.at(-1).id : mode.groups[next].id;
      emphasize(pinned);
    });
    const requested = new URL(location.href).searchParams.get("coverage");
    renderCoverage(Object.hasOwn(payload.coverage.modes, requested) ? requested : "evidence");
    if (Object.hasOwn(payload.coverage.modes, requested)) coverage.open = true;
  }
  const form = root.querySelector("#weibo-filters");
  const search = root.querySelector("#weibo-search");
  const category = root.querySelector("#weibo-category");
  const evidence = root.querySelector("#weibo-evidence");
  const followup = root.querySelector("#weibo-followup");
  const filterOptions = root.querySelector("#weibo-filter-options");
  const filterToggle = root.querySelector("#weibo-filter-toggle");
  const mobileFilters = matchMedia("(max-width: 760px)");
  const links = [...root.querySelectorAll(".weibo-channel-link")];
  const cards = [...root.querySelectorAll(".weibo-brand")];
  const details = [...root.querySelectorAll(".weibo-channel-detail")];
  const pager = root.querySelector("#weibo-pagination");
  const previous = root.querySelector("#weibo-previous");
  const next = root.querySelector("#weibo-next");
  const pageSize = 8;
  const normalize = value => String(value).normalize("NFKC").toLocaleLowerCase();
  const byId = new Map(accounts.map(account => [account.id, {...account, search: normalize(account.search)}]));
  const parameters = new URL(location.href).searchParams;
  search.value = parameters.get("q") || "";
  for (const [select, parameter] of [[category, "category"], [evidence, "evidence"]]) {
    if ([...select.options].some(option => option.value === parameters.get(parameter))) {
      select.value = parameters.get(parameter);
    }
  }
  followup.checked = parameters.get("followup") === "1";
  let filtersExpanded = Boolean(category.value || evidence.value || followup.checked);
  const layoutFilters = () => {
    const expanded = !mobileFilters.matches || filtersExpanded;
    filterOptions.hidden = !expanded;
    filterToggle.hidden = !mobileFilters.matches;
    filterToggle.setAttribute("aria-expanded", String(expanded));
    const active = [category.value, evidence.value, followup.checked].filter(Boolean).length;
    filterToggle.textContent = active ? `Filters (${active})` : "Filters";
  };
  filterToggle.addEventListener("click", () => {
    filtersExpanded = !filtersExpanded;
    layoutFilters();
  });
  mobileFilters.addEventListener("change", layoutFilters);
  let page = Math.max(1, Number.parseInt(parameters.get("page"), 10) || 1);
  const hashId = () => {
    try {
      return location.hash.startsWith("#weibo-account-") ? decodeURIComponent(location.hash.slice(15)) : "";
    } catch { return ""; }
  };
  let selected = byId.has(hashId()) ? hashId() : "";
  const matchingAccounts = () => {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    return accounts.filter(account => {
      const item = byId.get(account.id);
      return (!category.value || item.category === category.value) &&
        (!evidence.value || item.state === evidence.value) &&
        (!followup.checked || item.needs_review) &&
        terms.every(term => item.search.includes(term));
    });
  };
  const clearFilters = () => {
    search.value = category.value = evidence.value = "";
    followup.checked = false;
    filtersExpanded = false;
  };
  const update = ({writeUrl = true, resetPage = false, revealSelection = false} = {}) => {
    layoutFilters();
    const matching = matchingAccounts();
    const ids = new Set(matching.map(account => account.id));
    const outlets = new Set(matching.map(account => account.outlet));
    const ordered = cards.map(card => card.dataset.outletId).filter(id => outlets.has(id));
    if (!ids.has(selected)) selected = matching[0]?.id || "";
    if (resetPage) page = 1;
    if (revealSelection && selected) page = Math.floor(ordered.indexOf(byId.get(selected).outlet) / pageSize) + 1;
    const pages = Math.max(1, Math.ceil(ordered.length / pageSize));
    page = Math.max(1, Math.min(page, pages));
    const visible = new Set(ordered.slice((page - 1) * pageSize, page * pageSize));
    if (selected && !visible.has(byId.get(selected).outlet)) {
      selected = matching.find(account => visible.has(account.outlet))?.id || "";
    }
    for (const link of links) {
      link.hidden = !ids.has(link.dataset.accountId);
      link.dataset.matched = String(ids.has(link.dataset.accountId));
      link.setAttribute("aria-current", String(link.dataset.accountId === selected));
    }
    for (const card of cards) card.hidden = !visible.has(card.dataset.outletId);
    for (const detail of details) detail.hidden = detail.dataset.accountId !== selected;
    root.querySelector("#weibo-empty").hidden = matching.length !== 0;
    root.querySelector("#weibo-empty-detail").hidden = matching.length !== 0;
    root.querySelector("#weibo-result-count").textContent =
      `${matching.length} matching channel${matching.length === 1 ? "" : "s"} across ` +
      `${outlets.size} publisher / brand group${outlets.size === 1 ? "" : "s"}`;
    for (const count of root.querySelectorAll("[data-state-count]")) {
      count.textContent = matching.filter(account => account.state === count.dataset.stateCount).length;
    }
    pager.hidden = pages === 1;
    previous.disabled = page === 1;
    next.disabled = page === pages;
    root.querySelector("#weibo-page-label").textContent = `Page ${page} of ${pages}`;
    if (writeUrl) {
      const url = new URL(location.href);
      for (const [key, value] of [["q", search.value.trim()], ["category", category.value],
        ["evidence", evidence.value], ["followup", followup.checked ? "1" : ""],
        ["page", page > 1 ? String(page) : ""]]) {
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      }
      url.hash = root.classList.contains("weibo-detail-open") && selected ? `weibo-account-${selected}` : "";
      if (location.protocol === "file:") url.search = location.search;
      history.replaceState(null, "", url);
    }
  };
  const reveal = (id, writeUrl = true) => {
    if (!byId.has(id)) return;
    selected = id;
    if (!matchingAccounts().some(account => account.id === selected)) clearFilters();
    root.classList.add("weibo-detail-open");
    update({writeUrl, revealSelection: true});
  };
  const backToList = () => {
    root.classList.remove("weibo-detail-open");
    update({revealSelection: true});
    const link = links.find(node => node.dataset.accountId === selected);
    link?.focus({preventScroll: true});
    link?.scrollIntoView({block: "center", behavior: "auto"});
  };
  const scrollToDetail = () => root.querySelector(".weibo-inspector").scrollIntoView({block: "start", behavior: "auto"});
  root.classList.add("weibo-interactive");
  form.hidden = false;
  const back = root.querySelector("#weibo-back");
  back.hidden = false;
  back.addEventListener("click", backToList);
  const changed = () => {
    if (category.value || evidence.value || followup.checked) filtersExpanded = true;
    root.classList.remove("weibo-detail-open");
    update({resetPage: true});
  };
  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("input", changed);
  form.addEventListener("change", changed);
  form.addEventListener("reset", event => {
    event.preventDefault();
    clearFilters();
    changed();
  });
  for (const [button, direction] of [[previous, -1], [next, 1]]) {
    button.addEventListener("click", () => {
      page += direction;
      root.classList.remove("weibo-detail-open");
      update();
      const first = links.find(link => !link.hidden && !link.closest(".weibo-brand").hidden);
      first?.focus({preventScroll: true});
      first?.scrollIntoView({block: "start", behavior: "auto"});
    });
  }
  for (const link of links) link.addEventListener("click", event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    reveal(link.dataset.accountId);
    document.getElementById(`weibo-account-${selected}`).querySelector("h3").focus({preventScroll: true});
    if (matchMedia("(max-width: 760px)").matches) {
      scrollToDetail();
    }
  });
  root.addEventListener("keydown", event => {
    if (event.key === "Escape" && root.classList.contains("weibo-detail-open")) {
      event.preventDefault();
      backToList();
    }
  });
  window.addEventListener("hashchange", () => {
    if (byId.has(hashId())) {
      reveal(hashId(), false);
      scrollToDetail();
    }
    else {
      root.classList.remove("weibo-detail-open");
      update({writeUrl: false});
    }
  });
  if (selected) {
    reveal(selected);
    requestAnimationFrame(scrollToDetail);
  } else {
    update({writeUrl: false});
    if (coverage && Object.hasOwn(payload.coverage.modes, parameters.get("coverage"))) {
      requestAnimationFrame(() => coverage.scrollIntoView({block: "start", behavior: "auto"}));
    }
  }
})();
