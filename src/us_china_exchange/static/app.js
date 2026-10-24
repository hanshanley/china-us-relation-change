"use strict";
(() => {
  const data = JSON.parse(document.getElementById("exchange-data").textContent);
  const visibleSeries = data.visible_series ? new Set(data.visible_series) : null;
  const plotRows = data.observations.filter(r => {
    if (visibleSeries && !visibleSeries.has(r.series_id)) return false;
    const preferred = data.primary_series?.[`${r.origin}:${r.destination}:${r.measure}`];
    return !preferred || r.series_id === preferred;
  });
  const $ = id => document.getElementById(id);
  const format = (value, unit = "") => value === null ? "Not available" :
    (unit === "USD" ? "$" : "") + value.toLocaleString("en-US", {maximumFractionDigits: 20});
  const escape = value => String(value).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const find = (rows, year) => rows.find(r => r.year === year && r.value !== null);
  function difference(current, reference) {
    if (!reference || reference.value === null) return "Baseline unavailable";
    const keys = ["series_id", "frequency", "period_basis", "comparability", "unit"];
    if (keys.some(k => current[k] !== reference[k]) ||
        ["period_start", "period_end"].some(k =>
          (current[k] || "").slice(5, 7) !== (reference[k] || "").slice(5, 7))) {
      return "Definitions or periods differ";
    }
    const absolute = current.value - reference.value;
    const prefix = absolute > 0 ? "+" : absolute < 0 ? "\u2212" : "";
    const percent = reference.value ? absolute / reference.value * 100 : null;
    return prefix + format(Math.abs(absolute), current.unit) +
      (percent === null ? " \u00b7 Zero baseline; percentage undefined" :
        ` (${percent > 0 ? "+" : ""}${percent.toFixed(1)}%)`);
  }
  function render(event) {
    const geo = $("geography").value;
    const outgoing = $("direction").value === "from_us";
    const origin = outgoing ? "USA" : geo, destination = outgoing ? geo : "USA";
    const selectionNotes = [];
    if (data.prefer_current_travel && outgoing && geo === "CHN" &&
        $("measure").value === "visitors" && ["geography", "direction"].includes(event?.target.id)) {
      $("measure").value = "air_visitors";
      selectionNotes.push(data.freshness_policy ? "Showing U.S.-resident air-travel estimates." :
        "Showing current U.S.-resident air-travel estimates. The separate all-mode arrival history ends in 2018 and remains available in the indicator menu.");
    }
    const arrivalOption = $("measure").querySelector('option[value="visitors"]');
    if (arrivalOption) {
      arrivalOption.dataset.defaultLabel ||= arrivalOption.textContent;
      arrivalOption.textContent = outgoing && geo === "CHN" ?
        "All-mode arrivals (through 2018)" : arrivalOption.dataset.defaultLabel;
    }
    if (data.restrict_to_available) {
      const available = new Set(plotRows.filter(r => r.origin === origin &&
        r.destination === destination && r.frequency === "annual" && r.value !== null).map(r => r.measure));
      const selected = $("measure").value;
      for (const option of $("measure").options) {
        option.disabled = !available.has(option.value);
        if (data.freshness_policy) option.hidden = option.disabled;
      }
      if (!available.has(selected)) {
        const families = [["visitors", "air_visitors", "leisure_visitors"],
          ["international_students", "enrolled_students", "study_abroad", "degree_students"],
          ["goods", "services"]];
        const family = families.find(values => values.includes(selected)) || [];
        const replacement = [...family, ...[...$("measure").options].map(o => o.value)]
          .find(value => available.has(value) && [...$("measure").options].some(o => o.value === value));
        if (replacement) {
          $("measure").value = replacement;
          selectionNotes.push(`${data.measures[selected]} has no verified annual series for this route. Showing ${data.measures[replacement]} instead; its population is defined below.`);
        }
      }
    }
    const measure = $("measure").value;
    const rows = plotRows.filter(r =>
      r.origin === origin && r.destination === destination && r.measure === measure);
    const estimatePanel = $("student-estimates");
    const showEstimates = !!estimatePanel && outgoing && geo === "CHN" &&
      ["international_students", "enrolled_students", "degree_students", "study_abroad"].includes(measure);
    if (estimatePanel) estimatePanel.hidden = !showEstimates;
    const annual = rows.filter(r => r.frequency === "annual").sort((a, b) => a.year - b.year);
    const current = annual.filter(r => r.value !== null).at(-1);
    if (data.restrict_to_available) {
      const indexOption = $("chart-mode").querySelector('option[value="index"]');
      const canIndex = !!current && data.charts[current.series_id].index.trimStart().startsWith("<svg");
      indexOption.disabled = !canIndex;
      if (!canIndex && $("chart-mode").value === "index") {
        $("chart-mode").value = "levels";
        selectionNotes.push("A comparable baseline index is unavailable for this series. Showing reported levels, without hiding the observations.");
      }
      $("selection-note").hidden = !selectionNotes.length;
      $("selection-note").textContent = selectionNotes.join(" ");
      const related = $("related-series");
      related.hidden = true;
      let alternative, explanation;
      if (outgoing && measure === "visitors") {
        alternative = "air_visitors";
        explanation = `This all-mode history ends in ${current?.year}. A separate U.S.-resident air-travel survey has newer observations. These populations are not combined.`;
      } else if (outgoing && measure === "air_visitors") {
        alternative = "visitors";
        explanation = "Historical all-mode arrivals are also available, under a different definition. They are not spliced into this air-travel survey.";
      } else if (outgoing && measure === "enrolled_students") {
        alternative = "study_abroad";
        explanation = "A separate academic-credit study-abroad series has newer observations. It is not a replacement for all U.S.-nationality enrollments.";
      } else if (!outgoing && measure === "enrolled_students") {
        alternative = "international_students";
        explanation = "A broader student series has a longer history, but includes graduates on OPT as well as enrolled students.";
      }
      const other = rows.length && alternative && plotRows.filter(r => r.origin === origin &&
        r.destination === destination && r.measure === alternative && r.frequency === "annual" && r.value !== null);
      const latestOther = other?.length ? Math.max(...other.map(r => r.year)) : null;
      if (other?.length && current && (measure === "air_visitors" || latestOther > current.year || (
          measure === "enrolled_students" && !outgoing && other.length > annual.length))) {
        related.hidden = false;
        related.innerHTML = `${escape(explanation)} <button type="button" class="series-alternative">View ${escape(data.measures[alternative])} (${Math.min(...other.map(r => r.year))}\u2013${latestOther})</button>`;
        related.querySelector("button").addEventListener("click", () => {
          $("measure").value = alternative;
          $("measure").dispatchEvent(new Event("change", {bubbles: true}));
        });
      }
      if (showEstimates) {
        related.hidden = false;
        related.innerHTML += ' <a href="#student-estimates">Separate dated estimates through 2026, including reported bounds</a>.';
      }
    }
    $("series-title").textContent = measure === "air_visitors" ?
      `U.S. travel to ${geo === "CHN" ? "mainland China" : data.geographies[geo]}` :
      `${data.geographies[origin]} \u2192 ${data.geographies[destination]}`;
    $("series-category").textContent = measure === "air_visitors" ? "Air-travel estimates" : data.measures[measure];
    const population = $("series-population");
    if (population) {
      const travel = ["visitors", "air_visitors", "leisure_visitors"].includes(measure) && !!current;
      population.hidden = !travel;
      if (travel) {
        const scope = measure === "air_visitors" ? "U.S. residents; annual survey estimates" :
          current.source_id === "ntto" ? "Overnight visitor arrivals by country of residence" :
          current.source_id === "nbs_tourism" ? "Historical all-mode visitor arrivals" :
          "Visitor arrivals; source-specific country attribution";
        population.textContent = `${scope} \u00b7 ${annual[0].year}\u2013${current.year}`;
      }
    }
    const continuity = $("series-continuity");
    if (continuity) {
      continuity.hidden = measure !== "air_visitors";
      continuity.textContent = data.public_display ? "A comparable 2021 estimate is unavailable from this source." :
        "2021 is not plotted: the monitor reports zero volume despite positive survey responses. That is not treated as zero actual travel.";
    }
    $("partial-panel").hidden = true;
    $("figure-link").hidden = !current;
    if (!current) {
      const coverage = data.coverage.find(c => c.origin === origin &&
        c.destination === destination && c.measure === measure);
      $("annual-headlines").innerHTML = `<p class="gap">${escape(coverage.reason)}</p>`;
      $("definition").textContent = "No compatible annual observations verified. This is not a zero.";
      $("chart").innerHTML = "";
      $("series-table").innerHTML = "<p>No verified values. See the coverage table and source limitations.</p>";
      $("series-source").textContent = "Missing coverage is retained explicitly in the complete dataset.";
      $("series-notes").textContent = "";
      $("chart-mode").disabled = true;
      return;
    }
    $("chart-mode").disabled = false;
    const referenceYear = measure === "air_visitors" ? 2019 : 2020;
    const reference = find(annual, referenceYear), previous = find(annual, current.year - 1);
    $("annual-headlines").innerHTML = `<div class="headline-grid"><div>
      <p class="label">Latest complete annual observation</p>
      <p class="metric" id="latest-value">${escape(format(current.value, current.unit))}</p>
      <p id="latest-period">${escape(current.period)} \u00b7 ${escape(data.measures[measure])}</p></div>
      <div><p class="label" id="baseline-label">Change since ${escape(reference ? reference.period : String(referenceYear))}${measure === "air_visitors" ? " (pre-pandemic)" : ""}</p>
      <p class="delta" id="baseline-change">${escape(difference(current, reference))}</p>
      <p id="yoy-change">Prior year: ${escape(difference(current, previous))}</p></div></div>`;
    $("definition").textContent = current.definition;
    $("chart").innerHTML = data.charts[current.series_id][$("chart-mode").value];
    $("chart").scrollLeft = $("chart").scrollWidth;
    const chartBackground = $("chart").querySelector(".chart-background");
    if (chartBackground) {
      chartBackground.setAttribute("fill", data.chart_themes[$("chart-theme").value].background);
    }
    const variedDefinitions = new Set(annual.map(r => r.comparability)).size > 1;
    $("series-table").innerHTML = `<div class="table-scroll"><table><caption>Exact annual observations</caption>
      <thead><tr><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Status</th>` +
      (variedDefinitions ? '<th scope="col">Population definition</th>' : "") + "</tr></thead><tbody>" +
      annual.map(r => `<tr><th scope="row">${escape(r.period)}</th><td>${escape(format(r.value, r.unit))}</td><td>${escape(r.status)}</td>` +
        (variedDefinitions ? `<td>${escape(r.definition)}</td>` : "") + "</tr>").join("") +
      "</tbody></table></div>";
    const manifest = data.sources[current.source_id];
    $("series-source").innerHTML = `Source: <a href="${escape(data.source_pages?.[current.source_id] || current.source_url)}">${escape(data.source_names[current.source_id])}</a>` +
      ` \u00b7 ${escape(current.source_vintage)}` + (data.public_display ? "." :
        ` \u00b7 ${escape(manifest.status)}. Published retrieval: ${escape(current.retrieved_at)}. ${escape(manifest.notes || "")}`);
    const breaks = annual.filter((row, i) => i && row.comparability !== annual[i - 1].comparability).map(row => row.period);
    $("series-notes").textContent = data.public_display ?
      (breaks.length ? `Coverage changes in ${breaks.join(", ")}. Separate line segments preserve these boundaries.` : "") : current.notes;
    $("figure-link").innerHTML = "<p>Download reported values as a high-resolution PNG or editable SVG:</p><ul>" +
      Object.entries(data.figures[current.series_id]).map(([theme, files]) =>
        `<li>${escape(data.chart_themes[theme].label)}: ` +
        `<a href="${escape(files.png)}" download>PNG (3000 \u00d7 1800)</a> \u00b7 ` +
        `<a href="${escape(files.svg)}" download>SVG</a></li>`).join("") + "</ul>";
    const partials = rows.filter(r => r.frequency === "ytd" && r.value !== null)
      .sort((a, b) => a.period.localeCompare(b.period));
    const partial = partials.at(-1);
    if (partial && partial.year > current.year) {
      const end = partial.period.slice(5);
      const matched = partials.filter(r => r.period.endsWith(`-${end}`));
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const label = `Jan\u2013${months[Number(end) - 1]} ${partial.year}`;
      $("partial-panel").hidden = false;
      $("partial-panel").innerHTML = `<h3>Latest partial year \u00b7 ${escape(label)}</h3>
        <p><strong>${escape(format(partial.value, partial.unit))}</strong> \u00b7 ${escape(partial.status)}</p>
        <p>Same interval in 2020: ${escape(difference(partial, find(matched, 2020)))}</p>
        <p>Same interval in ${partial.year - 1}: ${escape(difference(partial, find(matched, partial.year - 1)))}</p>
        <p>${escape(partial.definition)}. ${escape(partial.notes)}</p>
        <p>Source vintage: ${escape(partial.source_vintage)}. No annualization or full-year comparison.</p>`;
    }
  }
  for (const id of ["geography", "direction", "measure", "chart-mode", "chart-theme"]) {
    $(id).addEventListener("change", render);
  }
  render();
})();
