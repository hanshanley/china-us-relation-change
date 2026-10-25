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
  const relationship = root.querySelector("#weibo-relationship");
  const evidence = root.querySelector("#weibo-evidence");
  const followup = root.querySelector("#weibo-followup");
  const filterOptions = root.querySelector("#weibo-filter-options");
  const filterToggle = root.querySelector("#weibo-filter-toggle");
  const links = [...root.querySelectorAll(".weibo-channel-link")];
  const cards = [...root.querySelectorAll(".weibo-brand")];
  const publisherLinks = [...root.querySelectorAll(".weibo-publisher-link")];
  const publisherDetails = [...root.querySelectorAll(".weibo-publisher-detail")];
  const details = [...root.querySelectorAll(".weibo-channel-detail")];
  const map = root.querySelector("#weibo-map");
  const detailList = root.querySelector("#weibo-detail-list");
  const statusButtons = [...root.querySelectorAll("[data-publisher-filter]")];
  const pager = root.querySelector("#weibo-pagination");
  const previous = root.querySelector("#weibo-previous");
  const next = root.querySelector("#weibo-next");
  const pageSize = 12;
  const normalize = value => String(value).normalize("NFKC").toLocaleLowerCase();
  const byId = new Map(accounts.map(account => [account.id, {...account, search: normalize(account.search)}]));
  const publishers = payload.publishers.map(publisher => ({...publisher, search: normalize(publisher.search)}));
  const byPublisher = new Map(publishers.map(publisher => [publisher.id, publisher]));
  const parameters = new URL(location.href).searchParams;
  search.value = parameters.get("q") || "";
  for (const [select, parameter] of [[category, "category"], [relationship, "relationship"], [evidence, "evidence"]]) {
    if ([...select.options].some(option => option.value === parameters.get(parameter))) {
      select.value = parameters.get(parameter);
    }
  }
  followup.checked = parameters.get("followup") === "1";
  let filtersExpanded = Boolean(category.value || relationship.value || followup.checked);
  const layoutFilters = () => {
    filterOptions.hidden = !filtersExpanded;
    filterToggle.hidden = false;
    filterToggle.setAttribute("aria-expanded", String(filtersExpanded));
    const active = [category.value, relationship.value, followup.checked].filter(Boolean).length;
    filterToggle.textContent = active ? `More filters (${active})` : "More filters";
  };
  filterToggle.addEventListener("click", () => {
    filtersExpanded = !filtersExpanded;
    layoutFilters();
  });
  let page = Math.max(1, Number.parseInt(parameters.get("page"), 10) || 1);
  const hashSelection = () => {
    try {
      if (location.hash.startsWith("#weibo-account-")) {
        const account = byId.get(decodeURIComponent(location.hash.slice(15)));
        return account ? {publisher: account.outlet, account: account.id} : null;
      }
      if (location.hash.startsWith("#weibo-publisher-")) {
        const publisher = decodeURIComponent(location.hash.slice(17));
        return byPublisher.has(publisher) ? {publisher, account: ""} : null;
      }
    } catch {}
    return null;
  };
  const requested = hashSelection();
  let selectedPublisher = requested?.publisher || "";
  let selected = requested?.account || "";
  const matchingPublishers = () => {
    const terms = normalize(search.value).trim().split(/\s+/).filter(Boolean);
    return publishers.filter(publisher =>
      (!category.value || publisher.categories.includes(category.value)) &&
      (!relationship.value || publisher.relationships.includes(relationship.value)) &&
      (!evidence.value || publisher.state === evidence.value) &&
      (!followup.checked || publisher.needs_review) &&
      terms.every(term => publisher.search.includes(term)));
  };
  const clearFilters = () => {
    search.value = category.value = relationship.value = evidence.value = "";
    followup.checked = false;
    filtersExpanded = false;
  };
  const update = ({writeUrl = true, resetPage = false, revealSelection = false} = {}) => {
    layoutFilters();
    const matching = matchingPublishers();
    const ordered = matching.map(publisher => publisher.id);
    if (selectedPublisher && !ordered.includes(selectedPublisher)) selectedPublisher = selected = "";
    if (resetPage) page = 1;
    if (revealSelection && selectedPublisher) page = Math.floor(ordered.indexOf(selectedPublisher) / pageSize) + 1;
    const pages = Math.max(1, Math.ceil(ordered.length / pageSize));
    page = Math.max(1, Math.min(page, pages));
    const visible = new Set(ordered.slice((page - 1) * pageSize, page * pageSize));
    if (selectedPublisher && !visible.has(selectedPublisher)) selectedPublisher = selected = "";
    if (selectedPublisher && !byPublisher.get(selectedPublisher).accounts.includes(selected)) {
      selected = byPublisher.get(selectedPublisher).accounts[0];
    }
    for (const link of links) {
      link.setAttribute("aria-current", String(link.dataset.accountId === selected));
    }
    for (const card of cards) card.hidden = !visible.has(card.dataset.outletId);
    for (const link of publisherLinks) {
      link.setAttribute("aria-current", String(link.dataset.outletId === selectedPublisher));
      link.setAttribute("aria-expanded", String(link.dataset.outletId === selectedPublisher));
    }
    for (const detail of publisherDetails) {
      detail.hidden = detail.dataset.outletId !== selectedPublisher;
      if (detail.hidden && detail.parentElement === map) detailList.append(detail);
    }
    if (selectedPublisher) {
      const activeCards = cards.filter(card => !card.hidden);
      const index = activeCards.findIndex(card => card.dataset.outletId === selectedPublisher);
      const columns = getComputedStyle(map).gridTemplateColumns.split(" ").length;
      const rowEnd = activeCards[Math.min(activeCards.length - 1, Math.floor(index / columns) * columns + columns - 1)];
      const detail = document.getElementById(`weibo-publisher-${selectedPublisher}`);
      if (detail.previousElementSibling !== rowEnd) {
        const focused = detail.contains(document.activeElement) ? document.activeElement : null;
        rowEnd.after(detail);
        focused?.focus({preventScroll: true});
      }
    }
    for (const detail of details) detail.hidden = detail.dataset.accountId !== selected;
    root.querySelector("#weibo-empty").hidden = matching.length !== 0;
    root.classList.toggle("weibo-detail-open", !!selectedPublisher);
    root.querySelector("#weibo-result-count").textContent =
      (matching.length ? `Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, matching.length)} of ` : "") +
      `${matching.length} publisher${matching.length === 1 ? "" : "s"}`;
    for (const button of statusButtons) {
      button.setAttribute("aria-pressed", String(button.dataset.publisherFilter === evidence.value));
    }
    pager.hidden = pages === 1;
    previous.disabled = page === 1;
    next.disabled = page === pages;
    root.querySelector("#weibo-page-label").textContent = `Page ${page} of ${pages}`;
    if (writeUrl) {
      const url = new URL(location.href);
      for (const [key, value] of [["q", search.value.trim()], ["category", category.value],
        ["relationship", relationship.value],
        ["evidence", evidence.value], ["followup", followup.checked ? "1" : ""],
        ["page", page > 1 ? String(page) : ""]]) {
        if (value) url.searchParams.set(key, value);
        else url.searchParams.delete(key);
      }
      url.hash = selectedPublisher ? `weibo-account-${selected}` : "";
      if (location.protocol === "file:") url.search = location.search;
      history.replaceState(null, "", url);
    }
  };
  const reveal = (publisher, account = "", writeUrl = true) => {
    if (!byPublisher.has(publisher)) return;
    selectedPublisher = publisher;
    selected = account || byPublisher.get(publisher).accounts[0];
    if (!matchingPublishers().some(item => item.id === publisher)) clearFilters();
    update({writeUrl, revealSelection: true});
  };
  const backToList = () => {
    const identity = selectedPublisher;
    selectedPublisher = selected = "";
    update();
    const link = publisherLinks.find(node => node.dataset.outletId === identity);
    link?.focus({preventScroll: true});
    link?.scrollIntoView({block: "center", behavior: "auto"});
  };
  const scrollToDetail = () => {
    if (selectedPublisher) {
      document.getElementById(`weibo-publisher-${selectedPublisher}`).scrollIntoView({block: "start", behavior: "auto"});
    }
  };
  root.classList.add("weibo-interactive");
  form.hidden = false;
  for (const button of root.querySelectorAll(".weibo-close-publisher")) button.addEventListener("click", backToList);
  const changed = () => {
    if (category.value || relationship.value || followup.checked) filtersExpanded = true;
    selectedPublisher = selected = "";
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
  for (const button of statusButtons) button.addEventListener("click", () => {
    evidence.value = button.dataset.publisherFilter;
    changed();
  });
  for (const [button, direction] of [[previous, -1], [next, 1]]) {
    button.addEventListener("click", () => {
      page += direction;
      selectedPublisher = selected = "";
      update();
      const first = publisherLinks.find(link => !link.closest(".weibo-brand").hidden);
      first?.focus({preventScroll: true});
      first?.scrollIntoView({block: "start", behavior: "auto"});
    });
  }
  for (const link of publisherLinks) {
    link.addEventListener("click", event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (selectedPublisher === link.dataset.outletId) {
        backToList();
        return;
      }
      reveal(link.dataset.outletId);
      document.getElementById(`weibo-publisher-${selectedPublisher}`).querySelector("h3").focus({preventScroll: true});
      scrollToDetail();
    });
    link.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const visible = publisherLinks.filter(item => !item.closest(".weibo-brand").hidden);
      const columns = getComputedStyle(root.querySelector("#weibo-map")).gridTemplateColumns.split(" ").length;
      const step = event.key === "ArrowUp" ? -columns : event.key === "ArrowDown" ? columns :
        event.key === "ArrowLeft" ? -1 : 1;
      const index = event.key === "Home" ? 0 : event.key === "End" ? visible.length - 1 :
        Math.max(0, Math.min(visible.length - 1, visible.indexOf(link) + step));
      visible[index]?.focus();
    });
  }
  for (const link of links) link.addEventListener("click", event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    reveal(byId.get(link.dataset.accountId).outlet, link.dataset.accountId);
    const heading = document.getElementById(`weibo-account-${selected}`).querySelector("h4");
    heading.focus({preventScroll: true});
    heading.scrollIntoView({block: "nearest", behavior: "auto"});
  });
  root.addEventListener("keydown", event => {
    if (event.key === "Escape" && root.classList.contains("weibo-detail-open")) {
      event.preventDefault();
      backToList();
    }
  });
  window.addEventListener("hashchange", () => {
    const target = hashSelection();
    if (target) {
      reveal(target.publisher, target.account, false);
      scrollToDetail();
    }
    else {
      selectedPublisher = selected = "";
      update({writeUrl: false});
    }
  });
  window.addEventListener("resize", () => update({writeUrl: false}));
  if (selectedPublisher) {
    reveal(selectedPublisher, selected);
    requestAnimationFrame(scrollToDetail);
  } else {
    update({writeUrl: false});
    if (coverage && Object.hasOwn(payload.coverage.modes, parameters.get("coverage"))) {
      requestAnimationFrame(() => coverage.scrollIntoView({block: "start", behavior: "auto"}));
    }
  }
})();
