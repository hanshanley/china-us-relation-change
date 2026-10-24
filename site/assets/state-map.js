(() => {
  "use strict";
  const panel = document.getElementById("state-china-map");
  if (!panel) return;
  const data = JSON.parse(panel.querySelector(".state-map-data").textContent);
  const states = new Map(data.states.map(row => [row.fips, row]));
  const controls = panel.querySelector(".state-map-controls");
  const selector = panel.querySelector("#state-map-select");
  const readout = panel.querySelector(".state-map-readout");
  const legend = panel.querySelector(".state-map-legend");
  const svg = panel.querySelector("svg[data-state-map]");
  const targets = [...panel.querySelectorAll(".state-shape,.state-callout")];
  const number = value => value == null ? "Unavailable" : value.toLocaleString("en-US");
  const share = value => value == null ? "Unavailable" : `${value.toFixed(2)}%`;
  let metric = "share";
  let selected = "";
  let transient = null;

  function color(row) {
    const config = data.metrics[metric];
    const value = row[config.field];
    if (value == null) return "#D6D3CC";
    const index = config.bounds.reduce((result, threshold, i) => value >= threshold ? i : result, 0);
    return data.colors[index];
  }
  function text(tag, content, className) {
    const node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  }
  function show(fips) {
    const row = states.get(fips) || data.national;
    readout.replaceChildren();
    readout.dataset.stateFips = row.fips;
    readout.append(text("strong", `${row.name} · ${data.start_year}–${data.end_year}`));
    const values = document.createElement("div");
    values.className = "state-map-values";
    values.append(text("span", `${number(row.china_born)} China-born residents`),
      text("span", `${share(row.share_percent)} of ${number(row.foreign_born)} foreign-born residents`));
    readout.append(values, text("span",
      `90% count margins of error: China-born ${row.china_born_moe == null ? "unavailable" : "±" + number(row.china_born_moe)}; ` +
      `all foreign-born ${row.foreign_born_moe == null ? "unavailable" : "±" + number(row.foreign_born_moe)}.`,
      "state-map-uncertainty"));
    for (const target of targets) target.classList.toggle("state-active", target.dataset.stateFips === row.fips);
  }
  function render() {
    const config = data.metrics[metric];
    svg.dataset.stateMap = metric;
    for (const target of targets) {
      const row = states.get(target.dataset.stateFips);
      const shape = target.matches(".state-shape") ? target : target.querySelector(".state-callout-fill");
      shape.setAttribute("fill", color(row));
      target.setAttribute("aria-label", `${row.name}, ${data.start_year}–${data.end_year}: ` +
        `${number(row.china_born)} China-born residents; ${share(row.share_percent)} of ` +
        `${number(row.foreign_born)} foreign-born residents. China excludes Hong Kong and Taiwan.`);
    }
    legend.replaceChildren();
    legend.setAttribute("aria-label", `${config.label} colour key`);
    config.labels.forEach((label, i) => {
      const item = text("span", label);
      const swatch = document.createElement("i");
      swatch.style.backgroundColor = data.colors[i];
      item.prepend(swatch);
      legend.append(item);
    });
    if (data.states.some(row => row[config.field] == null)) {
      const item = text("span", "Unavailable");
      const swatch = document.createElement("i");
      swatch.style.backgroundColor = "#D6D3CC";
      item.prepend(swatch);
      legend.append(item);
    }
    for (const button of controls.querySelectorAll("[data-map-metric]")) {
      button.setAttribute("aria-pressed", String(button.dataset.mapMetric === metric));
    }
    show(transient || selected);
  }
  function select(fips) {
    selected = fips;
    transient = null;
    selector.value = fips;
    show(fips);
  }
  function reset() {
    transient = null;
    show(selected);
  }
  for (const target of targets) {
    const fips = target.dataset.stateFips;
    target.addEventListener("pointerenter", event => {
      if (event.pointerType === "touch") return;
      transient = fips;
      show(fips);
    });
    target.addEventListener("pointerleave", reset);
    target.addEventListener("focus", () => { transient = fips; show(fips); });
    target.addEventListener("blur", reset);
    target.addEventListener("click", () => select(fips));
    target.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(fips);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        select("");
        selector.focus();
      }
    });
  }
  controls.addEventListener("click", event => {
    const button = event.target.closest("[data-map-metric]");
    if (!button) return;
    metric = button.dataset.mapMetric;
    render();
  });
  selector.addEventListener("change", () => select(selector.value));
  render();
  controls.hidden = false;
})();
