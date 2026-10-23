"use strict";
(() => {
  const revision = new URL(document.currentScript.src).searchParams.get("v");
  const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const color = value => /^#[0-9a-f]{6}$/i.test(value) ? value : "#655f55";
  const compact = (value, unit = "") => {
    const currency = /USD/.test(unit) ? "$" : "";
    const magnitude = Math.abs(value);
    for (const [scale, suffix] of [[1e12, "tn"], [1e9, "bn"], [1e6, "m"], [1e3, "k"]]) {
      if (magnitude >= scale) return currency + (value / scale).toLocaleString("en-US", {maximumFractionDigits: 1}) + suffix;
    }
    return currency + value.toLocaleString("en-US", {maximumFractionDigits: 1});
  };
  const models = new WeakMap();
  const draw = (container, model) => {
    if (!container.clientWidth) return;
    const width = Math.max(280, Math.floor(container.clientWidth));
    container.dataset.plotWidth = String(width);
    const mobile = width < 600;
    const font = mobile ? 12 : 13;
    let content = "", height;
    if (model.kind === "bars") {
      height = model.bars.length * 52 + 8;
      const maximum = Math.max(...model.bars.map(p => p.value), 1);
      for (const [i, point] of model.bars.entries()) {
        const y = i * 52 + 17;
        const length = point.value / maximum * (width - 10);
        content += `<text x="0" y="${y}" font-size="${font}">${escape(point.label)}</text>
          <text x="${width - 2}" y="${y}" text-anchor="end" font-size="${font}">${escape(compact(point.value, model.unit))}</text>
          <rect class="screen-bar" data-label="${escape(point.label)}" data-value="${point.value}"
            x="0" y="${y + 10}" width="${length}" height="7" fill="${color(point.color)}">
            <title>${escape(point.label)}: ${escape(point.value.toLocaleString("en-US"))} ${escape(model.unit)}</title></rect>`;
      }
    } else {
      height = mobile ? 270 : 355;
      const margin = {left: mobile ? 52 : 74, right: 14, top: 30, bottom: 34};
      const points = model.groups.flatMap(group => group.points);
      const highest = Math.max(...points.map(p => p.value), 0) * 1.12 || 1;
      const magnitude = 10 ** Math.floor(Math.log10(highest));
      const logarithmic = model.scale === "log";
      const low = logarithmic ? Math.floor(Math.log10(Math.min(...points.map(p => p.value)))) : 0;
      const high = logarithmic ? Math.max(low + 1, Math.ceil(Math.log10(Math.max(...points.map(p => p.value))))) : 1;
      const maximum = Math.ceil(highest / magnitude) * magnitude;
      const first = model.first, last = Math.max(first + 1, model.last);
      const snapshot = !logarithmic && model.groups.length === 1 && points.length === 1 && model.first === model.last;
      const plotWidth = width - margin.left - margin.right;
      const x = year => margin.left + (snapshot ? .5 : (year - first) / (last - first)) * plotWidth;
      const y = value => height - margin.bottom - (logarithmic ? (Math.log10(value) - low) / (high - low) : value / maximum) * (height - margin.top - margin.bottom);
      content += `<text x="${margin.left}" y="13" font-size="${font}" fill="#655f55">${escape(model.unit)}</text>`;
      const ticks = logarithmic ? Array.from({length: high - low + 1}, (_, i) => 10 ** (low + i)) : [0, maximum / 2, maximum];
      for (const value of ticks) {
        const yy = y(value);
        content += `<path d="M${margin.left} ${yy}H${width - margin.right}" stroke="#d6d3cc" stroke-width=".7"/>
          <text x="${margin.left - 9}" y="${yy + 4}" font-size="${font}" text-anchor="end" fill="#655f55">${escape(compact(value, model.unit))}</text>`;
      }
      const step = mobile && last - first > 20 ? 10 : 5;
      let years = [first];
      for (let year = Math.ceil((first + 1) / step) * step; year < last; year += step) {
        if (last - year >= (mobile ? 4 : 2) && year - years.at(-1) >= (mobile ? 4 : 2)) years.push(year);
      }
      years.push(last);
      const observedYears = [...new Set(points.map(p => p.year))].sort((a, b) => a - b);
      if (observedYears.length <= 8 && observedYears.every((year, i) =>
          !i || x(year) - x(observedYears[i - 1]) >= font * 3 + 2)) years = observedYears;
      for (const year of years) {
        content += `<text class="screen-year" x="${x(year)}" y="${height - 7}" font-size="${font}" text-anchor="middle" fill="#655f55">${year}</text>`;
      }
      for (const group of model.groups) {
        const path = group.points.map(p => `${p.connect ? "L" : "M"}${x(p.year).toFixed(2)},${y(p.value).toFixed(2)}`).join(" ");
        content += `<path class="screen-line" data-series-id="${escape(group.id)}" d="${path}" fill="none"
          stroke="${color(group.color)}" stroke-width="2.3" stroke-linejoin="round"${group.dash ? ` stroke-dasharray="${escape(group.dash)}"` : ""}/>`;
        for (const point of group.points) {
          if (snapshot) {
            const barWidth = Math.min(52, plotWidth / 8);
            content += `<rect class="screen-snapshot" x="${x(point.year) - barWidth / 2}" y="${y(point.value)}"
              width="${barWidth}" height="${y(0) - y(point.value)}" fill="${color(group.color)}" aria-hidden="true"/>
              <text x="${x(point.year)}" y="${y(point.value) - 9}" font-size="${font}" text-anchor="middle">${escape(compact(point.value, model.unit))}</text>`;
          }
          content += `<circle class="screen-point" data-series-id="${escape(group.id)}" data-year="${point.year}" data-value="${point.value}"
            cx="${x(point.year)}" cy="${y(point.value)}" r="${mobile ? 2.8 : 3.2}" fill="${color(group.color)}"
            tabindex="-1"><title>${escape(point.label || `${group.label} ${point.year}: ${point.value.toLocaleString("en-US")} ${model.unit}`)}</title></circle>`;
        }
      }
    }
    const keys = model.legend || model.groups;
    const legend = keys?.length > 1 ? '<div class="plot-legend">' + keys.map(group =>
      `<span><i style="${group.dash ? `border-top:2px dashed ${color(group.color)}` : `background:${color(group.color)}`}"></i>${escape(group.label)}</span>`).join("") + "</div>" : "";
    container.innerHTML = `${model.kind === "bars" ? `<p class="plot-unit">${escape(model.unit)}</p>` : ""}${legend}<svg class="screen-chart" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}"
      role="img" aria-label="${escape(model.title)}"><title>${escape(model.title)}</title><desc>${escape(model.description)}</desc>
      <g font-family="Georgia,serif" fill="#171713">${content}</g></svg>`;
  };
  const observe = new ResizeObserver(entries => {
    for (const {target} of entries) {
      const width = Math.max(280, Math.floor(target.clientWidth));
      if (String(width) !== target.dataset.plotWidth && models.has(target)) draw(target, models.get(target));
    }
  });
  for (const container of document.querySelectorAll(".native-chart")) {
    const model = JSON.parse(container.querySelector(".plot-data").textContent);
    models.set(container, model);
    draw(container, model);
    observe.observe(container);
  }
  const moduleSelector = document.getElementById("module-chart");
  if (moduleSelector) {
    const requested = new URLSearchParams(location.search).get("indicator");
    if ([...moduleSelector.options].some(option => option.value === requested)) moduleSelector.value = requested;
    const select = () => {
      for (const section of document.querySelectorAll("[data-module-chart]")) {
        section.hidden = section.dataset.moduleChart !== moduleSelector.value;
      }
      for (const container of document.querySelectorAll(".native-chart")) {
        if (container.clientWidth) draw(container, models.get(container));
      }
    };
    moduleSelector.addEventListener("change", select);
    select();
    document.querySelector(".module-controls").hidden = false;
  }
  const embedded = document.getElementById("exchange-data");
  if (embedded) {
    const data = JSON.parse(embedded.textContent);
    const get = id => document.getElementById(id);
    const update = () => {
      const geo = get("geography").value;
      const outgoing = get("direction").value === "from_us";
      const origin = outgoing ? "USA" : geo, destination = outgoing ? geo : "USA";
      const rows = data.observations.filter(r => r.origin === origin && r.destination === destination &&
        r.measure === get("measure").value && r.frequency === "annual").sort((a, b) => a.year - b.year);
      const present = rows.filter(r => r.value !== null);
      const chart = get("chart");
      if (chart.querySelector("svg") && present.length) {
        const indexed = get("chart-mode").value === "index";
        const reference = present.find(r => r.year === 2020);
        let previous;
        const points = present.map(row => {
          const point = {year: row.year, value: indexed ? row.value / reference.value * 100 : row.value,
            connect: !!previous && row.year === previous.year + 1 && row.comparability === previous.comparability,
            label: `${row.period}: ${row.unit === "USD" ? "$" : ""}${row.value.toLocaleString("en-US")} ${row.unit === "USD" ? "" : row.unit}`};
          previous = row;
          return point;
        });
        const colors = {CHN: "#7B2D26", HKG: "#3D6F8C", MAC: "#C2993E"};
        const model = {kind: "line", title: `${data.measures[get("measure").value]}: ${data.geographies[origin]} to ${data.geographies[destination]}`,
          description: "Reported observations only. Missing years and changes in definition break the line. Exact values and complete downloads follow.",
          unit: indexed ? "2020 = 100" : present[0].unit === "USD" ? "Nominal USD" : present[0].unit,
          first: Math.min(...rows.map(r => r.year)), last: Math.max(...rows.map(r => r.year)),
          groups: [{id: present[0].series_id, label: data.geographies[geo], color: colors[geo], points}]};
        models.set(chart, model);
        draw(chart, model);
        observe.observe(chart);
        const latest = present.at(-1);
        get("latest-value").textContent = compact(latest.value, latest.unit);
      } else {
        models.delete(chart);
      }
      for (const a of get("figure-link").querySelectorAll("a")) {
        a.dataset.originalChart = "";
        if (revision) {
          const url = new URL(a.href);
          url.searchParams.set("v", revision);
          a.href = url.href;
        }
      }
      for (const id of ["baseline-change", "yoy-change"]) {
        const node = get(id);
        if (node) {
          node.title = node.textContent;
          node.textContent = node.textContent.replace(/\$([\d,]+(?:\.\d+)?)/g,
            (_, value) => compact(Number(value.replaceAll(",", "")), "USD"));
        }
      }
      const partial = get("partial-panel");
      if (!partial.hidden) {
        const paragraphs = [...partial.querySelectorAll(":scope > p")];
        if (paragraphs.length > 1) {
          const detail = document.createElement("details");
          const summary = document.createElement("summary");
          summary.textContent = "Matched-period comparisons & definition";
          detail.append(summary, ...paragraphs.slice(1));
          partial.append(detail);
        }
      }
    };
    for (const id of ["geography", "direction", "measure", "chart-mode", "chart-theme"]) get(id).addEventListener("change", update);
    update();
    document.querySelector("form.controls").hidden = false;
  }
})();
