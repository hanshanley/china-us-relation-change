"use strict";
(() => {
  const data = JSON.parse(document.getElementById("exchange-data").textContent);
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
  function render() {
    const geo = $("geography").value;
    const outgoing = $("direction").value === "from_us";
    const origin = outgoing ? "USA" : geo, destination = outgoing ? geo : "USA";
    const measure = $("measure").value;
    const rows = data.observations.filter(r =>
      r.origin === origin && r.destination === destination && r.measure === measure);
    const annual = rows.filter(r => r.frequency === "annual").sort((a, b) => a.year - b.year);
    const current = annual.filter(r => r.value !== null).at(-1);
    $("series-title").textContent = `${data.geographies[origin]} \u2192 ${data.geographies[destination]}`;
    $("series-category").textContent = data.measures[measure];
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
    const reference = find(annual, 2020), previous = find(annual, current.year - 1);
    $("annual-headlines").innerHTML = `<div class="headline-grid"><div>
      <p class="label">Latest complete annual observation</p>
      <p class="metric" id="latest-value">${escape(format(current.value, current.unit))}</p>
      <p id="latest-period">${escape(current.period)} \u00b7 ${escape(data.measures[measure])}</p></div>
      <div><p class="label" id="baseline-label">Change since ${escape(reference ? reference.period : "2020")}</p>
      <p class="delta" id="baseline-change">${escape(difference(current, reference))}</p>
      <p id="yoy-change">Prior year: ${escape(difference(current, previous))}</p></div></div>`;
    $("definition").textContent = current.definition;
    $("chart").innerHTML = data.charts[current.series_id][$("chart-mode").value];
    $("chart").scrollLeft = $("chart").scrollWidth;
    const chartBackground = $("chart").querySelector(".chart-background");
    if (chartBackground) {
      chartBackground.setAttribute("fill", data.chart_themes[$("chart-theme").value].background);
    }
    $("series-table").innerHTML = `<div class="table-scroll"><table><caption>Exact annual observations</caption>
      <thead><tr><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Status</th></tr></thead><tbody>` +
      annual.map(r => `<tr><th scope="row">${escape(r.period)}</th><td>${escape(format(r.value, r.unit))}</td><td>${escape(r.status)}</td></tr>`).join("") +
      "</tbody></table></div>";
    const manifest = data.sources[current.source_id];
    $("series-source").innerHTML = `Source: <a href="${escape(current.source_url)}">${escape(data.source_names[current.source_id])}</a>` +
      ` \u00b7 ${escape(current.source_vintage)} \u00b7 ${escape(manifest.status)}. ` +
      `Published retrieval: ${escape(current.retrieved_at)}. ${escape(manifest.notes || "")}`;
    $("series-notes").textContent = current.notes;
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
