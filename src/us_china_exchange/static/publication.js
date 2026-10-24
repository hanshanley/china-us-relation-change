"use strict";
(() => {
  const revision = new URL(document.currentScript.src).searchParams.get("v");
  const regionalRoutes = document.getElementById("regional-topic-routes");
  if (regionalRoutes) {
    const indicator = new URLSearchParams(location.search).get("indicator") || location.hash.slice(1);
    const routes = JSON.parse(regionalRoutes.textContent);
    const target = Object.hasOwn(routes, indicator) ? routes[indicator] : null;
    if (target) location.replace(`${target}?indicator=${encodeURIComponent(indicator)}#regional-comparisons`);
  }
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
  const hoverCleanup = new WeakMap();
  const visible = container => container.clientWidth && !container.closest("[hidden],details:not([open])");
  let tooltipSerial = 0;
  const periodLabel = point => {
    if (point.period) return String(point.period);
    if (point.date || point.month) {
      return new Date((point.date || point.month + "-01") + "T00:00:00Z").toLocaleDateString("en-US",
        {month: "short", ...(point.date ? {day: "numeric"} : {}), year: "numeric", timeZone: "UTC"});
    }
    return String(point.year ?? point.label ?? "");
  };
  const fullValue = (value, unit) => (/USD|US\$/i.test(unit) ? "$" : "") +
    value.toLocaleString("en-US", {maximumFractionDigits: 2}) + (/percent|%/i.test(unit) ? "%" : "");
  const sameUnit = (a, b) => (/USD|US\$/i.test(a) ? "usd" : a.toLowerCase()) ===
    (/USD|US\$/i.test(b) ? "usd" : b.toLowerCase());
  const enableHover = (container, model, selections, axis, guide) => {
    if (!selections.length) return;
    const svg = container.querySelector(".screen-chart");
    const controller = new AbortController(), options = {signal: controller.signal};
    const tooltip = document.createElement("div");
    tooltip.id = `plot-tooltip-${++tooltipSerial}`;
    tooltip.className = "plot-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.append(tooltip);
    container.dataset.tooltipId = tooltip.id;
    container.removeAttribute("tabindex");
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-describedby", tooltip.id);
    svg.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight Home End Escape");
    const layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    layer.setAttribute("class", "plot-hover-layer");
    layer.setAttribute("aria-hidden", "true");
    svg.append(layer);
    let active = -1, pinned = false, keyboard = false;
    const hide = () => {
      tooltip.hidden = true;
      layer.replaceChildren();
      for (const bar of svg.querySelectorAll(".screen-bar")) bar.removeAttribute("data-hovered");
    };
    const show = (index, clientX, clientY) => {
      active = Math.max(0, Math.min(selections.length - 1, index));
      const selection = selections[active];
      tooltip.setAttribute("aria-live", keyboard ? "polite" : "off");
      tooltip.innerHTML = `<p class="plot-tooltip-period">${escape(selection.heading)}</p>` +
        selection.rows.map(row => {
          const point = row.point;
          const value = point ? `<strong class="plot-tooltip-value" data-value="${point.value}">${escape(fullValue(point.value, model.unit))}</strong>` :
            '<span class="plot-tooltip-missing">Not reported</span>';
          const reported = point && point.reported_value !== undefined &&
            (!sameUnit(point.reported_unit || model.unit, model.unit) || point.reported_value !== point.value) ?
            `<small class="plot-tooltip-reported" data-value="${point.reported_value}">Reported: ${escape(fullValue(point.reported_value, point.reported_unit))}${/USD|US\$/i.test(point.reported_unit) ? "" : " " + escape(point.reported_unit)}</small>` : "";
          const qualifier = point?.status === "low_reliability" ? "Small survey sample" :
            point?.status === "rounded" ? "Rounded in source" : point?.status === "estimated" ? "Estimate" : "";
          return `<div class="plot-tooltip-row" data-series-id="${escape(row.id)}">
            <span class="plot-tooltip-label"><i style="background:${color(row.color)}"></i>${escape(row.label)}</span>
            ${value}${reported}${qualifier ? `<small class="plot-tooltip-qualifier">${escape(qualifier)}</small>` : ""}</div>`;
        }).join("") + (axis === "x" ? `<p class="plot-tooltip-unit">${escape(model.unit)}</p>` : "") +
        (selection.rows.some(row => row.point?.partial_window) ?
          '<p class="plot-tooltip-note">Partial reporting period</p>' : "");
      tooltip.hidden = false;
      const rect = svg.getBoundingClientRect();
      const view = svg.viewBox.baseVal;
      const anchorX = clientX ?? rect.left + (axis === "x" ? selection.position : view.width / 2) / view.width * rect.width;
      const anchorY = clientY ?? rect.top + (axis === "y" ? selection.position : guide.top + 20) / view.height * rect.height;
      const bounds = tooltip.getBoundingClientRect();
      let left = anchorX + 16, top = anchorY + 16;
      if (left + bounds.width > innerWidth - 12) left = anchorX - bounds.width - 16;
      if (top + bounds.height > innerHeight - 12) top = anchorY - bounds.height - 16;
      tooltip.style.left = `${Math.max(12, Math.min(left, innerWidth - bounds.width - 12))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(top, innerHeight - bounds.height - 12))}px`;
      if (axis === "x") {
        layer.innerHTML = `<line x1="${selection.position}" x2="${selection.position}" y1="${guide.top}" y2="${guide.bottom}"/>` +
          selection.markers.map(p => `<circle class="plot-hover-dot" data-series-id="${escape(p.id)}" cx="${p.x}" cy="${p.y}" r="4.5" fill="#f2efe7"
            stroke="${color(p.color)}" stroke-width="1.8"/>`).join("");
      } else {
        for (const [i, bar] of [...svg.querySelectorAll(".screen-bar")].entries()) {
          bar.toggleAttribute("data-hovered", i === active);
        }
      }
    };
    const nearest = event => {
      const rect = svg.getBoundingClientRect(), view = svg.viewBox.baseVal;
      const position = axis === "x" ? (event.clientX - rect.left) / rect.width * view.width :
        (event.clientY - rect.top) / rect.height * view.height;
      return selections.reduce((best, item, i) =>
        Math.abs(item.position - position) < Math.abs(selections[best].position - position) ? i : best, 0);
    };
    svg.addEventListener("pointermove", event => {
      keyboard = false;
      show(nearest(event), event.clientX, event.clientY);
    }, options);
    svg.addEventListener("pointerdown", event => {
      keyboard = false;
      pinned = event.pointerType === "touch";
      show(nearest(event), event.clientX, event.clientY);
    }, options);
    svg.addEventListener("pointerleave", () => { if (!pinned && !keyboard) hide(); }, options);
    svg.addEventListener("pointercancel", () => { pinned = false; hide(); }, options);
    svg.addEventListener("focus", () => { keyboard = true; show(active < 0 ? selections.length - 1 : active); }, options);
    svg.addEventListener("blur", () => { keyboard = false; pinned = false; hide(); }, options);
    svg.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "Escape"].includes(event.key)) return;
      event.preventDefault();
      keyboard = true;
      if (event.key === "Escape") { hide(); return; }
      const index = event.key === "Home" ? 0 : event.key === "End" ? selections.length - 1 :
        active + (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1);
      show(index);
    }, options);
    document.addEventListener("pointerdown", event => {
      if (!container.contains(event.target)) { pinned = false; hide(); }
    }, options);
    hoverCleanup.set(container, () => {
      controller.abort();
      hide();
      tooltip.remove();
      delete container.dataset.tooltipId;
      svg.removeAttribute("aria-describedby");
    });
  };
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
    hoverCleanup.get(container)?.();
    hoverCleanup.delete(container);
    if (!visible(container)) {
      delete container.dataset.plotWidth;
      return;
    }
    const width = Math.max(280, Math.floor(container.clientWidth));
    container.dataset.plotWidth = String(width);
    const mobile = width < 600;
    const font = mobile ? 14 : 17;
    let content = "", height, selections = [], hoverAxis = "x", guide;
    if (model.kind === "bars") {
      hoverAxis = "y";
      height = 8;
      const maximum = model.axis_max || Math.max(...model.bars.map(p => p.value), 1);
      const context = document.createElement("canvas").getContext("2d");
      context.font = `${font}px Georgia, serif`;
      for (const point of model.bars) {
        const valueLabel = /USD/.test(model.unit) ? compact(point.value, model.unit) :
          point.value.toLocaleString("en-US", {maximumFractionDigits: 6}) +
          (model.axis_max && /percent|%/i.test(model.unit) ? "%" : "");
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
          <text class="screen-bar-value" x="${width - 2}" y="${y}" text-anchor="end" font-size="${font}">${escape(valueLabel)}</text>
          ${model.axis_max ? `<rect class="screen-bar-track" x="0" y="${y + (lines.length - 1) * 19 + 12}"
            width="${width - 10}" height="8" rx="1" fill="#d6d3cc" fill-opacity=".35"></rect>` : ""}
          <rect class="screen-bar" data-label="${escape(point.label)}" data-value="${point.value}"
            x="0" y="${y + (lines.length - 1) * 19 + 12}" width="${length}" height="8" rx="1" fill="${color(point.color)}"
            aria-label="${escape(point.label)}: ${escape(point.value.toLocaleString("en-US"))} ${escape(model.unit)}"></rect>`;
        const heading = point.period && !point.label.includes(point.period) ?
          `${point.label.replace(/\s\(\d{4}\)$/, "")} · ${point.period}` : point.label;
        selections.push({position: y + (lines.length - 1) * 19 + 16, heading,
          rows: [{id: point.id || point.label, label: model.unit, color: point.color, point}]});
        height = y + (lines.length - 1) * 19 + 39;
      }
      for (const point of model.unavailable_bars || []) {
        const y = height + font;
        content += `<text x="0" y="${y}" font-size="${font}">${escape(point.label)}</text>
          <text x="${width - 2}" y="${y}" text-anchor="end" font-size="${font}">${escape(point.reason)}</text>`;
        height = y + 39;
      }
    } else {
      height = mobile ? 310 : Math.round(Math.max(380, Math.min(520, width * .5)));
      const margin = {left: mobile ? 66 : 94, right: 30, top: 44, bottom: 46};
      const points = model.groups.flatMap(group => group.points);
      const monthly = model.frequency === "monthly";
      const daily = model.frequency === "daily";
      const dated = monthly || daily;
      const columns = !!model.columns && !dated && model.groups.length === 1 && model.scale !== "log";
      const periodValue = point => daily ? point.date : point.month;
      const position = point => daily ? point.date_index : monthly ? point.month_index : point.year;
      const axis = model.axis_max ? {maximum: model.axis_max, ticks: [0, .25, .5, .75, 1].map(f => f * model.axis_max)} :
        linearAxis(Math.max(...points.map(p => p.value), 0));
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
      const tickLabel = value => logarithmic ? compact(value, model.unit) :
        (value / divisor).toLocaleString("en-US", {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
      const first = model.first, last = Math.max(first + 1, model.last);
      const snapshot = !dated && !logarithmic && model.groups.length === 1 &&
        ((points.length === 1 && model.first === model.last) ||
         (model.snapshots && points.length === 2 && points.every(p => !p.connect)));
      const plotWidth = width - margin.left - margin.right;
      const x = period => margin.left + (dated && model.first === model.last ? .5 :
        snapshot || columns ? (period - first + .5) / (model.last - first + 1) :
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
      if (!dated && model.covid_context && first <= 2022 && model.last >= 2020) margin.top += 18;
      content += `<text class="screen-unit" x="${margin.left}" y="${font + 3}" font-size="${font}" fill="#655f55">${unitLines.map((line, i) =>
        `<tspan x="${margin.left}" dy="${i ? font + 4 : 0}">${escape(line)}</tspan>`).join("")}</text>`;
      if (!dated && model.covid_context && first <= 2022 && model.last >= 2020) {
        const low = columns || snapshot ? first - .5 : first;
        const high = columns || snapshot ? model.last + .5 : last;
        const bandX = year => margin.left + (year - low) / (high - low) * plotWidth;
        const start = bandX(Math.max(low, 2019.5)), stop = bandX(Math.min(high, 2022.5));
        const centre = Math.max(margin.left + 70, Math.min(width - margin.right - 70, (start + stop) / 2));
        content += `<rect class="covid-band" data-start-year="2020" data-end-year="2022"
          x="${start}" y="${margin.top}" width="${stop - start}" height="${height - margin.bottom - margin.top}"
          fill="#d6d3cc" fill-opacity=".3" pointer-events="none"></rect>
          <text class="covid-label" x="${centre}" y="${margin.top - 9}" text-anchor="middle"
          font-size="${mobile ? 10 : 12}" fill="#6b6b6b">COVID travel restrictions</text>`;
      }
      const ticks = logarithmic ? Array.from({length: high - low + 1}, (_, i) => 10 ** (low + i)) : axis.ticks;
      for (const value of ticks) {
        const yy = y(value);
        content += `<path d="M${margin.left} ${yy}H${width - margin.right}" stroke="#d6d3cc" stroke-width="${value === 0 ? 1 : .6}"/>
          <text class="screen-y-tick" x="${margin.left - 9}" y="${yy + 5}" font-size="${font}" text-anchor="end" fill="#655f55">${escape(tickLabel(value))}</text>`;
      }
      if (dated) {
        const ordered = [...new Map(points.map(p => [position(p), p])).values()]
          .sort((a, b) => position(a) - position(b));
        const periodLabel = (point, endpoint = false) => {
          const value = periodValue(point);
          const label = value.endsWith(daily ? "-01-01" : "-01") && !(daily && endpoint) ? value.slice(0, 4) :
            new Date(value + (daily ? "T00:00:00Z" : "-01T00:00:00Z")).toLocaleDateString("en-US",
              {month: "short", ...(daily ? {day: "numeric"} : {}), year: "numeric", timeZone: "UTC"});
          return label + (point.partial_window ? "*" : "");
        };
        const finalWidth = measure.measureText(periodLabel(ordered.at(-1), true)).width;
        const finalLeft = x(position(ordered.at(-1))) - finalWidth;
        const labels = [ordered[0]];
        let previousRight = x(position(ordered[0])) + measure.measureText(periodLabel(ordered[0], true)).width;
        for (const point of ordered.slice(1, -1)) {
          const textWidth = measure.measureText(periodLabel(point)).width;
          const left = x(position(point)) - textWidth / 2, right = left + textWidth;
          if (periodValue(point).endsWith(daily ? "-01-01" : "-01") && model.last - position(point) >= (daily ? 365 : 12) &&
              left >= previousRight + 14 && right <= finalLeft - 14) {
            labels.push(point);
            previousRight = right;
          }
        }
        if (ordered.length > 1) labels.push(ordered.at(-1));
        for (const [i, point] of labels.entries()) {
          const label = periodLabel(point, i === 0 || i === labels.length - 1);
          const anchor = i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle";
          content += `<text class="screen-month" data-period="${escape(periodValue(point))}" x="${x(position(point))}" y="${height - 7}" font-size="${font}"
            text-anchor="${anchor}" fill="#655f55">${escape(label)}</text>`;
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
        const retained = [years[0]];
        let previousRight = x(years[0]) + measure.measureText(String(years[0])).width / 2;
        const finalLeft = x(years.at(-1)) - measure.measureText(String(years.at(-1))).width / 2;
        for (const year of years.slice(1, -1)) {
          const half = measure.measureText(String(year)).width / 2;
          if (x(year) - half >= previousRight + 8 && x(year) + half <= finalLeft - 8) {
            retained.push(year);
            previousRight = x(year) + half;
          }
        }
        if (years.length > 1) retained.push(years.at(-1));
        for (const year of retained) {
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
        if (!columns) content += `<path class="screen-line" data-series-id="${escape(group.id)}" d="${path}" fill="none"
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
          if (columns) {
            const barWidth = Math.min(42, plotWidth / (model.last - first + 1) * .72);
            content += `<rect class="screen-column" data-series-id="${escape(group.id)}" data-year="${point.year}" data-value="${point.value}"
              x="${x(point.year) - barWidth / 2}" y="${y(point.value)}" width="${barWidth}" height="${y(0) - y(point.value)}"
              fill="${color(group.color)}" aria-label="${escape(point.label)}"></rect>`;
          }
          const period = dated ? `data-${daily ? "date" : "month"}="${escape(periodValue(point))}" data-partial-window="${point.partial_window}"` : `data-year="${point.year}"`;
          const fill = dated && point.partial_window ? "#f7f5f0" : color(group.color);
          const stroke = dated ? ` stroke="${color(group.color)}" stroke-width="1.3"` : "";
          const radius = columns ? 0 : point === group.points.at(-1) ? 4 : daily ? 0 : monthly ? 1.8 : 2.4;
          content += `<circle class="screen-point" data-series-id="${escape(group.id)}" ${period} data-value="${point.value}"
            cx="${x(position(point))}" cy="${y(point.value)}" r="${radius}" fill="${fill}"${stroke}
            tabindex="-1" aria-label="${escape(point.label || `${group.label} ${point.year}: ${point.value.toLocaleString("en-US")} ${model.unit}`)}"></circle>`;
        }
        if (!snapshot && !columns && model.groups.length === 1) {
          const point = group.points.at(-1);
          content += `<text class="screen-end-label" x="${x(position(point)) - 9}" y="${y(point.value) - 12}"
            text-anchor="end" font-size="${font}" font-weight="bold" fill="${color(group.color)}"
            stroke="#f2efe7" stroke-width="4" paint-order="stroke">${escape(compact(point.value, model.unit))}</text>`;
        }
      }
      const indexedGroups = model.groups.map(group => ({group, points: new Map(group.points.map(point => [position(point), point]))}));
      selections = [...new Set(points.map(position))].sort((a, b) => a - b).map(period => {
        const rows = indexedGroups.map(({group, points}) => ({
          id: group.id, label: group.label || model.title, color: group.color, point: points.get(period)}));
        return {position: x(period), heading: periodLabel(rows.find(row => row.point).point), rows,
          markers: rows.filter(row => row.point).map(row => ({
            id: row.id, x: x(period), y: y(row.point.value), color: row.color}))};
      });
      guide = {top: margin.top, bottom: height - margin.bottom};
    }
    const keys = model.legend || model.groups;
    const legend = keys?.length && (keys.length > 1 || model.show_legend) ? '<div class="plot-legend">' + keys.map(group =>
      `<span><i style="${group.dash ? `border-top:2px dashed ${color(group.color)}` : `background:${color(group.color)}`}"></i>${escape(group.label)}</span>`).join("") + "</div>" : "";
    container.innerHTML = `${model.kind === "bars" ? `<p class="plot-unit">${escape(model.unit)}</p>` : ""}${legend}<svg class="screen-chart" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}"
      role="img" aria-label="${escape(model.title)}"${model.axis_max ? ` data-axis-max="${model.axis_max}"` : ""}${model.columns ? ' data-plot-style="columns"' : ""}><desc>${escape(model.description)} Use arrow keys to inspect observations; Escape closes the value tooltip.</desc>
      <g font-family="Georgia,serif" fill="#171713">${content}</g></svg>
      <p class="plot-interaction-hint">Hover, tap or use arrow keys for values.</p>`;
    enableHover(container, model, selections, hoverAxis, guide);
  };
  const observe = new ResizeObserver(entries => {
    for (const {target} of entries) {
      if (!visible(target)) {
        hoverCleanup.get(target)?.();
        hoverCleanup.delete(target);
        delete target.dataset.plotWidth;
        continue;
      }
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
  for (const details of document.querySelectorAll("details")) {
    if (details.querySelector(".native-chart,#chart")) details.addEventListener("toggle", () => {
      for (const container of details.querySelectorAll(".native-chart,#chart")) {
        if (models.has(container)) draw(container, models.get(container));
      }
    });
  }
  const moduleSelector = document.getElementById("module-chart");
  if (moduleSelector) {
    const requested = new URLSearchParams(location.search).get("indicator");
    if ([...moduleSelector.options].some(option => option.value === requested)) {
      moduleSelector.value = requested;
      const parent = moduleSelector.closest("details");
      if (parent) parent.open = true;
    }
    const select = (updateURL = false) => {
      for (const section of document.querySelectorAll("[data-module-chart]")) {
        section.hidden = section.dataset.moduleChart !== moduleSelector.value;
      }
      for (const container of document.querySelectorAll(".native-chart")) {
        draw(container, models.get(container));
      }
      if (updateURL && location.protocol !== "file:") {
        const url = new URL(location.href);
        url.searchParams.set("indicator", moduleSelector.value);
        history.replaceState(null, "", url);
      }
    };
    moduleSelector.addEventListener("change", () => select(true));
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
      const preferred = data.primary_series?.[`${origin}:${destination}:${get("measure").value}`];
      const rows = data.observations.filter(r => r.origin === origin && r.destination === destination &&
        r.measure === get("measure").value && r.frequency === "annual" &&
        (!data.visible_series || data.visible_series.includes(r.series_id)) &&
        (!preferred || r.series_id === preferred)).sort((a, b) => a.year - b.year);
      const present = rows.filter(r => r.value !== null);
      const chart = get("chart");
      if (chart.querySelector("svg") && present.length) {
        const sourceSVG = chart.querySelector("svg");
        const indexed = get("chart-mode").value === "index";
        const reference = present.find(r => r.year === (present[0].measure === "air_visitors" ? 2019 : 2020));
        let previous;
        const points = present.map(row => {
          const value = indexed ? row.value / reference.value * 100 : row.value;
          const reported = `${row.unit === "USD" ? "$" : ""}${row.value.toLocaleString("en-US")} ${row.unit === "USD" ? "" : row.unit}`;
          const point = {year: row.year, value,
            period: row.period, reported_value: row.value, reported_unit: row.unit, status: row.status,
            connect: !!previous && row.year === previous.year + 1 && row.comparability === previous.comparability,
            label: indexed ? `${row.period}: index ${value.toLocaleString("en-US", {maximumFractionDigits: 2})} (${reference.year} = 100); reported ${reported}` :
              `${row.period}: ${reported}`};
          previous = row;
          return point;
        });
        const colors = {CHN: "#7B2D26", HKG: "#3D6F8C", MAC: "#C2993E"};
        const snapshots = present.length === 2 && present[0].source_id === "ustr" &&
          new Set(present.map(row => row.comparability)).size === 2;
        const model = {kind: "line", title: `${data.measures[get("measure").value]}: ${data.geographies[origin]} to ${data.geographies[destination]}`,
          covid_context: data.covid_context,
          description: sourceSVG.querySelector("desc")?.textContent || (snapshots ? "Separate annual snapshots; release vintages are not connected or used for growth." :
            "Reported observations only. Missing years and changes in definition break the line. Exact values and complete downloads follow."),
          columns: !indexed && sourceSVG.dataset.plotStyle === "columns",
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
        hoverCleanup.get(chart)?.();
        hoverCleanup.delete(chart);
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
  document.documentElement.classList.add("plot-js");
})();
