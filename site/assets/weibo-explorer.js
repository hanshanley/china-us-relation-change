"use strict";
(() => {
  const root = document.querySelector("#weibo-explorer");
  const data = document.querySelector("#weibo-explorer-data");
  if (!root || !data) return;
  const accounts = JSON.parse(data.textContent).accounts;
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
  if (byId.has(selected)) root.classList.add("weibo-detail-open");
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
    if (byId.has(selected)) root.classList.add("weibo-detail-open");
    update(false);
  });
  update(false);
})();
