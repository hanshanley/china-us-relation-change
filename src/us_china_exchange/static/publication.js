"use strict";
(() => {
  const revision = new URL(document.currentScript.src).searchParams.get("v");
  const tabs = document.querySelector(".analysis-tabs");
  const currentTab = tabs?.querySelector("[aria-current]");
  if (currentTab && tabs.scrollWidth > tabs.clientWidth) {
    tabs.scrollLeft = currentTab.offsetLeft - tabs.offsetLeft - (tabs.clientWidth - currentTab.clientWidth) / 2;
  }
  const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const color = value => /^#[0-9a-f]{6}$/i.test(value) ? value : "#655f55";
  const compact = (value, unit = "") => {
    const currency = /USD/.test(unit) ? "$" : "";
    const magnitude = Math.abs(value);
    for (const [scale, suffix] of [[1e12, "tn"], [1e9, "bn"], [1e6, "m"], [1e3, "k"]]) {
      if (magnitude >= scale) return currency + (value / scale).toLocaleString("en-US", {maximumFractionDigits: 1}) + suffix;
    }
    return currency + value.toLocaleString("en-US", magnitude > 0 && magnitude < 1 ?
      {maximumSignificantDigits: 3} : {maximumFractionDigits: 2});
  };
  const models = new WeakMap();
  const linearAxis = peak => {
    const extent = peak * 1.08 || 1;
    const power = 10 ** Math.floor(Math.log10(extent / 4));
    const ratio = extent / (4 * power);
    const multiple = [1, 2, 2.5, 5, 10].reduce((best, value) =>
      Math.abs(Math.log(value / ratio)) < Math.abs(Math.log(best / ratio)) ? value : best);
    const step = multiple * power, count = Math.ceil(extent / step);
    return {maximum: count * step, ticks: Array.from({length: count + 1}, (_, i) => i * step)};
  };
  const draw = (container, model) => {
    if (!container.clientWidth) return;
    const width = Math.max(280, Math.floor(container.clientWidth));
    container.dataset.plotWidth = String(width);
    const mobile = width < 600;
    const font = mobile ? 14 : 17;
    let content = "", height;
    if (model.kind === "bars") {
      height = 8;
      const maximum = Math.max(...model.bars.map(p => p.value), 1);
      const context = document.createElement("canvas").getContext("2d");
      context.font = `${font}px Georgia, serif`;
      for (const point of model.bars) {
        const valueLabel = compact(point.value, model.unit);
        const available = width - context.measureText(valueLabel).width - 24;
        const lines = [""];
        for (const word of point.label.split(/\s+/)) {
          const candidate = `${lines.at(-1)} ${word}`.trim();
          if (lines.at(-1) && context.measureText(candidate).width > available) lines.push(word);
          else lines[lines.length - 1] = candidate;
        }
        const y = height + font;
        const length = point.value / maximum * (width - 10);
        content += `<text x="0" y="${y}" font-size="${font}">${lines.map((line, i) =>
          `<tspan x="0" dy="${i ? 19 : 0}">${escape(line)}</tspan>`).join("")}</text>
          <text x="${width - 2}" y="${y}" text-anchor="end" font-size="${font}">${escape(valueLabel)}</text>
          <rect class="screen-bar" data-label="${escape(point.label)}" data-value="${point.value}"
            x="0" y="${y + (lines.length - 1) * 19 + 12}" width="${length}" height="8" rx="1" fill="${color(point.color)}">
            <title>${escape(point.label)}: ${escape(point.value.toLocaleString("en-US"))} ${escape(model.unit)}</title></rect>`;
        height = y + (lines.length - 1) * 19 + 39;
      }
    } else {
      height = mobile ? 340 : Math.round(Math.max(420, Math.min(640, width * .58)));
      const margin = {left: mobile ? 66 : 94, right: 30, top: 44, bottom: 46};
      const points = model.groups.flatMap(group => group.points);
      const monthly = model.frequency === "monthly";
      const daily = model.frequency === "daily";
      const dated = monthly || daily;
      const periodValue = point => daily ? point.date : point.month;
      const position = point => daily ? point.date_index : monthly ? point.month_index : point.year;
      const axis = linearAxis(Math.max(...points.map(p => p.value), 0));
      const logarithmic = model.scale === "log";
      const low = logarithmic ? Math.floor(Math.log10(Math.min(...points.map(p => p.value)))) : 0;
      const high = logarithmic ? Math.max(low + 1, Math.ceil(Math.log10(Math.max(...points.map(p => p.value))))) : 1;
      const maximum = axis.maximum;
      const currency = /USD/.test(model.unit);
      const scalable = !logarithmic && !/percent|%|=\s*100/i.test(model.unit);
      const scale = scalable ? [[1e12, "trillions"], [1e9, "billions"], [1e6, "millions"], [1e4, "thousands"]]
        .find(([threshold]) => maximum >= threshold) : null;
      const divisor = scale ? (scale[0] === 1e4 ? 1e3 : scale[0]) : 1;
      const caption = (currency ? "Nominal US$" : model.unit.replace(/^./, c => c.toUpperCase())) +
        (scale ? ` (${scale[1]})` : logarithmic && (currency || !/log/i.test(model.unit)) ? " (log scale)" : "");
      const step = (axis.ticks[1] || 1) / divisor;
      let decimals = 0;
      while (decimals < 6 && Math.abs(step * 10 ** decimals - Math.round(step * 10 ** decimals)) > 1e-7) decimals++;
      const tickLabel = value => divisor === 1 ? compact(value, model.unit) :
        (value / divisor).toLocaleString("en-US", {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
      const first = model.first, last = Math.max(first + 1, model.last);
      const snapshot = !dated && !logarithmic && model.groups.length === 1 &&
        ((points.length === 1 && model.first === model.last) ||
         (model.snapshots && points.length === 2 && points.every(p => !p.connect)));
      const plotWidth = width - margin.left - margin.right;
      const x = period => margin.left + (dated && model.first === model.last ? .5 :
        snapshot ? (period - first + .5) / (model.last - first + 1) :
        (period - first) / (last - first)) * plotWidth;
      const y = value => height - margin.bottom - (logarithmic ? (Math.log10(value) - low) / (high - low) : value / maximum) * (height - margin.top - margin.bottom);
      const measure = document.createElement("canvas").getContext("2d");
      measure.font = `${font}px Georgia, serif`;
      const unitLines = [""];
      for (const word of caption.split(/\s+/)) {
        const candidate = `${unitLines.at(-1)} ${word}`.trim();
        if (unitLines.at(-1) && measure.measureText(candidate).width > plotWidth) unitLines.push(word);
        else unitLines[unitLines.length - 1] = candidate;
      }
      margin.top = Math.max(margin.top, 16 + unitLines.length * (font + 4));
      content += `<text class="screen-unit" x="${margin.left}" y="${font + 3}" font-size="${font}" fill="#655f55">${unitLines.map((line, i) =>
        `<tspan x="${margin.left}" dy="${i ? font + 4 : 0}">${escape(line)}</tspan>`).join("")}</text>`;
      const ticks = logarithmic ? Array.from({length: high - low + 1}, (_, i) => 10 ** (low + i)) : axis.ticks;
      for (const value of ticks) {
        const yy = y(value);
        content += `<path d="M${margin.left} ${yy}H${width - margin.right}" stroke="#d6d3cc" stroke-width="${value === 0 ? 1 : .6}"/>
          <text class="screen-y-tick" x="${margin.left - 9}" y="${yy + 5}" font-size="${font}" text-anchor="end" fill="#655f55">${escape(tickLabel(value))}</text>`;
      }
      if (dated) {
        const ordered = [...new Map(points.map(p => [position(p), p])).values()]
          .sort((a, b) => position(a) - position(b));
        const labels = [ordered[0]];
        for (const point of ordered.slice(1, -1)) {
          if (periodValue(point).endsWith(daily ? "-01-01" : "-01") && model.last - position(point) >= (daily ? 365 : 12) &&
              x(position(point)) - x(position(labels.at(-1))) >= (mobile ? 90 : 85)) labels.push(point);
        }
        if (ordered.length > 1) labels.push(ordered.at(-1));
        for (const [i, point] of labels.entries()) {
          const label = periodValue(point).endsWith(daily ? "-01-01" : "-01") ? periodValue(point).slice(0, 4) :
            new Date(periodValue(point) + (daily ? "T00:00:00Z" : "-01T00:00:00Z")).toLocaleDateString("en-US",
              {month: "short", year: "numeric", timeZone: "UTC"});
          const anchor = i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle";
          content += `<text class="screen-month" x="${x(position(point))}" y="${height - 7}" font-size="${font}"
            text-anchor="${anchor}" fill="#655f55">${escape(label)}${point.partial_window ? "*" : ""}</text>`;
        }
      } else {
        const step = mobile && last - first > 20 ? 10 : 5;
        let years = [first];
        for (let year = Math.ceil((first + 1) / step) * step; year < last; year += step) {
          if (last - year >= (mobile ? 4 : 2) && year - years.at(-1) >= (mobile ? 4 : 2)) years.push(year);
        }
        years.push(last);
        const observedYears = [...new Set(points.map(p => p.year))].sort((a, b) => a - b);
        if (observedYears.length <= 8 && observedYears.every((year, i) =>
            !i || x(year) - x(observedYears[i - 1]) >= font * 2.4 + 5)) years = observedYears;
        for (const year of years) {
          content += `<text class="screen-year" x="${x(year)}" y="${height - 7}" font-size="${font}" text-anchor="middle" fill="#655f55">${year}</text>`;
        }
      }
      for (const group of model.groups) {
        let previous;
        const path = group.points.map(point => {
          const partial = dated && previous && (point.partial_window || previous.partial_window);
          const command = point.connect && !partial ? "L" : "M";
          previous = point;
          return `${command}${x(position(point)).toFixed(2)},${y(point.value).toFixed(2)}`;
        }).join(" ");
        content += `<path class="screen-line" data-series-id="${escape(group.id)}" d="${path}" fill="none"
          stroke="${color(group.color)}" stroke-width="${mobile ? 2.5 : 3}" stroke-linecap="round" stroke-linejoin="round"${group.dash ? ` stroke-dasharray="${escape(group.dash)}"` : ""}/>`;
        if (dated) {
          for (let i = 1; i < group.points.length; i++) {
            const before = group.points[i - 1], point = group.points[i];
            if (point.connect && (before.partial_window || point.partial_window)) {
              content += `<path class="screen-partial-line" d="M${x(position(before))},${y(before.value)} L${x(position(point))},${y(point.value)}"
                fill="none" stroke="${color(group.color)}" stroke-width="2.3" stroke-dasharray="5 4"/>`;
            }
          }
        }
        for (const point of group.points) {
          if (snapshot) {
            const barWidth = Math.min(52, plotWidth / 8);
            content += `<rect class="screen-snapshot" x="${x(point.year) - barWidth / 2}" y="${y(point.value)}"
              width="${barWidth}" height="${y(0) - y(point.value)}" fill="${color(group.color)}" aria-hidden="true"/>
              <text x="${x(point.year)}" y="${y(point.value) - 9}" font-size="${font}" text-anchor="middle">${escape(compact(point.value, model.unit))}</text>`;
          }
          const period = dated ? `data-${daily ? "date" : "month"}="${escape(periodValue(point))}" data-partial-window="${point.partial_window}"` : `data-year="${point.year}"`;
          const fill = dated && point.partial_window ? "#f7f5f0" : color(group.color);
          const stroke = dated ? ` stroke="${color(group.color)}" stroke-width="1.3"` : "";
          const radius = point === group.points.at(-1) ? 4 : daily ? 0 : monthly ? 1.8 : 2.4;
          content += `<circle class="screen-point" data-series-id="${escape(group.id)}" ${period} data-value="${point.value}"
            cx="${x(position(point))}" cy="${y(point.value)}" r="${radius}" fill="${fill}"${stroke}
            tabindex="-1"><title>${escape(point.label || `${group.label} ${point.year}: ${point.value.toLocaleString("en-US")} ${model.unit}`)}</title></circle>`;
        }
        if (!snapshot && model.groups.length === 1) {
          const point = group.points.at(-1);
          content += `<text class="screen-end-label" x="${x(position(point)) - 9}" y="${y(point.value) - 12}"
            text-anchor="end" font-size="${font}" font-weight="bold" fill="${color(group.color)}"
            stroke="#f2efe7" stroke-width="4" paint-order="stroke">${escape(compact(point.value, model.unit))}</text>`;
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
        const reference = present.find(r => r.year === (present[0].measure === "air_visitors" ? 2019 : 2020));
        let previous;
        const points = present.map(row => {
          const point = {year: row.year, value: indexed ? row.value / reference.value * 100 : row.value,
            connect: !!previous && row.year === previous.year + 1 && row.comparability === previous.comparability,
            label: `${row.period}: ${row.unit === "USD" ? "$" : ""}${row.value.toLocaleString("en-US")} ${row.unit === "USD" ? "" : row.unit}`};
          previous = row;
          return point;
        });
        const colors = {CHN: "#7B2D26", HKG: "#3D6F8C", MAC: "#C2993E"};
        const snapshots = present.length === 2 && present[0].source_id === "ustr" &&
          new Set(present.map(row => row.comparability)).size === 2;
        const model = {kind: "line", title: `${data.measures[get("measure").value]}: ${data.geographies[origin]} to ${data.geographies[destination]}`,
          description: snapshots ? "Separate annual snapshots; release vintages are not connected or used for growth." :
            "Reported observations only. Missing years and changes in definition break the line. Exact values and complete downloads follow.",
          snapshots,
          unit: indexed ? `${reference.year} = 100` : present[0].unit === "USD" ? "Nominal USD" : present[0].unit,
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
