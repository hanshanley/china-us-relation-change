(() => {
  "use strict";
  const containers = [...document.querySelectorAll(".confucius-chart")];
  if (!containers.length) return;
  const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const models = new WeakMap();
  const tips = new WeakMap();

  function hide(container) {
    const tip = tips.get(container);
    if (tip) tip.hidden = true;
    container.querySelectorAll("[data-hovered]").forEach(n => n.removeAttribute("data-hovered"));
  }
  function show(container, row, target, pointer) {
    const tip = tips.get(container);
    hide(container);
    target.setAttribute("data-hovered", "");
    tip.dataset.observationId = row.id;
    tip.innerHTML = `<p><strong>${escape(row.label)} · ${escape(row.reported)} ${escape(row.unit)}</strong></p>` +
      `<p>${escape(row.source_name)}</p><p class="confucius-tip-scope">${escape(row.scope)}</p>` +
      `<p class="confucius-tip-scope">${escape(row.notes)}</p>`;
    tip.hidden = false;
    const anchor = models.get(container).layout === "timeline" ?
      target.querySelector(".confucius-bar,.confucius-boundary") : target;
    const box = (anchor || target).getBoundingClientRect();
    const bounds = tip.getBoundingClientRect();
    const x = pointer?.clientX ?? box.left + box.width / 2;
    const y = pointer?.clientY ?? (models.get(container).layout === "timeline" ? box.top : box.bottom);
    tip.style.left = `${Math.max(12, Math.min(innerWidth - bounds.width - 12, x + 12))}px`;
    tip.style.top = `${Math.max(12, Math.min(innerHeight - bounds.height - 12, y + 14))}px`;
  }
  function timeline(model, width, background) {
    const height = width < 480 ? 320 : 340;
    const left = 48, right = width - 18, top = 34, bottom = height - 54;
    const calendar = model.calendar;
    const span = calendar.end - calendar.start;
    const px = year => left + (year - calendar.start) / span * (right - left);
    const py = amount => bottom - amount / model.maximum * (bottom - top);
    let markup = `<text class="confucius-unit" x="${left}" y="18" font-size="12" fill="#655F55">${escape(model.unit)}</text>`;
    for (const tick of model.ticks) {
      const y = py(tick);
      markup += `<path class="confucius-grid" data-tick="${tick}" d="M${left},${y}H${right}" stroke="#B8B0A2" stroke-width=".6"/>` +
        `<text class="confucius-count-tick" x="${left - 10}" y="${y + 4}" text-anchor="end" font-size="11" fill="#655F55">${tick}</text>`;
    }
    let previous = -Infinity;
    for (const year of calendar.ticks) {
      const x = px(year), last = year === calendar.last;
      if (!last && (x - previous < 50 || (year !== calendar.first && px(calendar.last) - x < 50))) continue;
      markup += `<text class="confucius-year" x="${x}" y="${bottom + 22}" text-anchor="middle" font-size="11" fill="#655F55">${year}</text>`;
      previous = x;
    }
    markup += `<text x="${(left + right) / 2}" y="${height - 8}" text-anchor="middle" font-size="11" fill="#655F55">Observation year</text>`;
    const labels = [], placed = [], accepted = new Set();
    model.rows.forEach((row, i) => {
      const x = px(row.calendar_position), y = py((row.value ?? row.bound) || 0);
      const text = row.bound == null ? row.reported :
        `${row.qualifier === "less_than" ? "<" : "\u2265"}${row.bound.toLocaleString("en-US")}`;
      const labelWidth = text.length * 7 + 8;
      const labelX = Math.max(left + labelWidth / 2, Math.min(right - labelWidth / 2, x));
      labels.push({i, text, x: labelX, y: y - 10, left: labelX - labelWidth / 2, right: labelX + labelWidth / 2,
        priority: row.bound != null ? 3 : i === model.rows.length - 1 ? 2 : 1});
    });
    for (const label of [...labels].sort((a, b) => b.priority - a.priority || b.i - a.i)) {
      if (placed.some(other => label.left < other.right + 4 && label.right > other.left - 4 &&
          Math.abs(label.y - other.y) < 17)) continue;
      accepted.add(label.i);
      placed.push(label);
    }
    model.rows.forEach((row, i) => {
      const x = px(row.calendar_position), y = py((row.value ?? row.bound) || 0);
      const start = i ? (px(model.rows[i - 1].calendar_position) + x) / 2 : left;
      const end = i + 1 < model.rows.length ? (x + px(model.rows[i + 1].calendar_position)) / 2 : right;
      const barWidth = Math.min(38, .62 * (right - left) / span / row.observations_in_year);
      const accessible = `${row.label}: ${row.reported} ${row.unit}. ${row.source_name}. ${row.notes}`;
      markup += `<g class="confucius-hit confucius-mark" role="button" tabindex="0" aria-label="${escape(accessible)}"` +
        ` data-observation-id="${row.id}" data-value="${row.value ?? ""}" data-bound="${row.bound ?? ""}"` +
        ` data-qualifier="${row.qualifier}" data-reference="${row.reference}" data-observation-year="${row.observation_year}">` +
        `<title>${escape(accessible)}</title>` +
        `<rect class="confucius-hit-area" x="${start}" y="${top}" width="${end - start}" height="${bottom - top}" fill="transparent"/>`;
      if (row.qualifier === "exact" || row.qualifier === "approximate") {
        markup += `<rect class="confucius-focus" x="${x - barWidth / 2 - 3}" y="${y - 3}" width="${barWidth + 6}" height="${bottom - y + 6}"/>` +
          `<rect class="confucius-bar" x="${x - barWidth / 2}" y="${y}" width="${barWidth}" height="${bottom - y}"` +
          ` fill="#7B2D26" opacity="${row.qualifier === "approximate" ? .6 : 1}"/>`;
      } else if (row.bound != null) {
        const limit = row.qualifier === "less_than" ? bottom : top;
        markup += `<rect class="confucius-focus" x="${x - 8}" y="${y - 8}" width="16" height="16"/>` +
          `<path class="confucius-bound" d="M${x},${y}V${limit}" fill="none" stroke="#7B2D26" stroke-width="2" stroke-dasharray="4 4"/>` +
          `<circle class="confucius-boundary" cx="${x}" cy="${y}" r="4" fill="${background}" stroke="#7B2D26" stroke-width="2"/>`;
      }
      if (accepted.has(i)) {
        markup += `<text class="confucius-reported" x="${labels[i].x}" y="${labels[i].y}" text-anchor="middle" ` +
          `font-size="12" font-weight="600" fill="#171713">${escape(labels[i].text)}</text>`;
      }
      markup += "</g>";
    });
    return {markup, height};
  }
  function bars(model, width, background) {
    const left = 10, right = width - 12, top = model.maximum;
    const step = 57, first = 19, bottom = model.rows.length * step + 2;
    const grid = "#B8B0A2", color = "#7B2D26";
    let markup = "";
    const amountX = row => left + ((row.value ?? row.bound) || 0) / top * (right - left);
    model.rows.forEach((row, i) => {
      const y = first + i * step;
      const x = amountX(row);
      const amount = row.value == null ? "" : row.value;
      const bound = row.bound == null ? "" : row.bound;
      const shortLabel = model.id === "confucius-directory" ? row.label : row.reference;
      const label = `${width < 360 ? shortLabel : row.label} · ${row.source_short}`;
      const accessible = `${row.label}: ${row.reported} ${row.unit}. ${row.source_name}. ${row.notes}`;
      markup += `<g class="confucius-hit confucius-mark" role="button" tabindex="0" aria-label="${escape(accessible)}"` +
        ` data-observation-id="${row.id}" data-value="${amount}" data-bound="${bound}"` +
        ` data-qualifier="${row.qualifier}" data-reference="${row.reference}">` +
        `<title>${escape(accessible)}</title>` +
        `<rect class="confucius-focus" x="1" y="${y - 17}" width="${width - 2}" height="49" rx="2"/>` +
        `<text x="${left}" y="${y}" font-size="${width < 480 ? 12 : 14}" fill="#171713">${escape(label)}</text>` +
        `<text class="confucius-reported" x="${right}" y="${y}" text-anchor="end" font-size="14" font-weight="600" fill="#171713">${escape(row.reported)}</text>` +
        `<path d="M${left},${y + 18}H${right}" stroke="${grid}" stroke-width=".5"/>`;
      if (row.qualifier === "exact" || row.qualifier === "approximate") {
        markup += `<rect class="confucius-bar" x="${left}" y="${y + 12}" width="${x - left}" height="11"` +
          ` fill="${color}" opacity="${row.qualifier === "approximate" ? .6 : 1}"/>`;
      } else if (row.qualifier === "less_than" || row.qualifier === "at_least") {
        const start = row.qualifier === "less_than" ? left : x;
        const end = row.qualifier === "less_than" ? x : right;
        markup += `<path class="confucius-bound" d="M${start},${y + 18}H${end}" fill="none" stroke="${color}"` +
          ` stroke-width="2" stroke-dasharray="4 4"/><circle class="confucius-boundary" cx="${x}" cy="${y + 18}" r="4"` +
          ` fill="${background}" stroke="${color}" stroke-width="2"/>`;
      }
      markup += "</g>";
    });
    for (const tick of model.ticks) {
      const x = left + tick / top * (right - left);
      markup += `<text x="${x}" y="${bottom + 18}" text-anchor="middle" font-size="11" fill="#655F55">${tick.toLocaleString("en-US")}</text>`;
    }
    return {markup, height: bottom + 30};
  }
  function render(container) {
    const model = models.get(container);
    const width = Math.floor(container.getBoundingClientRect().width);
    if (width < 100 || model.width === width) return;
    model.width = width;
    hide(container);
    const background = getComputedStyle(document.body).backgroundColor;
    const plot = model.layout === "timeline" ? timeline(model, width, background) : bars(model, width, background);
    const svg = container.querySelector("svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${plot.height}`);
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", model.title);
    svg.setAttribute("aria-keyshortcuts", "ArrowLeft ArrowRight ArrowUp ArrowDown Home End Escape");
    svg.innerHTML = `<title>${escape(model.title)}</title><desc>${escape(model.note)}</desc>${plot.markup}`;
    const targets = [...svg.querySelectorAll(".confucius-hit")];
    targets.forEach((target, i) => {
      const row = model.rows[i];
      target.addEventListener("pointerenter", event => {
        if (event.pointerType !== "touch") show(container, row, target, event);
      });
      target.addEventListener("pointermove", event => {
        if (event.pointerType === "mouse") show(container, row, target, event);
      });
      target.addEventListener("pointerleave", () => hide(container));
      target.addEventListener("focus", () => show(container, row, target));
      target.addEventListener("blur", () => hide(container));
      target.addEventListener("click", event => {
        event.stopPropagation();
        show(container, row, target, event);
      });
      target.addEventListener("keydown", event => {
        if (["Enter", " "].includes(event.key)) {
          event.preventDefault();
          show(container, row, target);
        } else if (event.key === "Escape") {
          event.preventDefault();
          hide(container);
        } else if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const next = event.key === "Home" ? 0 : event.key === "End" ? targets.length - 1 :
            Math.max(0, Math.min(targets.length - 1, i + (["ArrowDown", "ArrowRight"].includes(event.key) ? 1 : -1)));
          targets[next].focus();
        }
      });
    });
    container.classList.add("js-ready");
  }
  for (const container of containers) {
    const model = JSON.parse(container.querySelector(".confucius-plot-data").textContent);
    const source = container.querySelector("svg");
    if (model.maximum !== Number(source.dataset.axisMax)) throw new Error("Confucius chart axis mismatch");
    if (model.layout !== source.dataset.chartLayout) throw new Error("Confucius chart layout mismatch");
    models.set(container, model);
    const tip = document.createElement("div");
    tip.className = "plot-tooltip confucius-tooltip";
    tip.setAttribute("role", "status");
    tip.setAttribute("aria-live", "polite");
    tip.hidden = true;
    document.body.append(tip);
    tips.set(container, tip);
    new ResizeObserver(() => render(container)).observe(container);
    render(container);
  }
  document.addEventListener("pointerdown", event => {
    if (!event.target.closest(".confucius-hit")) containers.forEach(hide);
  });
  document.addEventListener("scroll", () => {
    const active = document.activeElement;
    for (const container of containers) {
      const tip = tips.get(container);
      if (tip.hidden) continue;
      if (active?.matches(".confucius-hit") && container.contains(active) &&
          tip.dataset.observationId === active.dataset.observationId) {
        const row = models.get(container).rows.find(row => row.id === active.dataset.observationId);
        show(container, row, active);
      } else {
        hide(container);
      }
    }
  }, { passive: true });
  document.addEventListener("change", () => containers.forEach(hide));
  document.addEventListener("toggle", () => containers.forEach(hide), true);
})();
