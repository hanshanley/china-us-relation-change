const form = document.getElementById("business-controls");
if (form) {
  const origin = document.getElementById("business-origin");
  const start = document.getElementById("business-start");
  const end = document.getElementById("business-end");
  const status = document.getElementById("business-filter-status");
  const rows = [...document.querySelectorAll("#annual-values [data-business-year]")];
  const update = () => {
    const first = start.valueAsNumber, last = end.valueAsNumber;
    if (!Number.isInteger(first) || !Number.isInteger(last) ||
        first < Number(start.min) || last > Number(end.max) || first > last) {
      status.textContent = `Choose whole table years between ${start.min} and ${end.max}, with start no later than end.`;
      return;
    }
    for (const node of document.querySelectorAll("[data-business-origin]")) {
      node.hidden = origin.value !== "all" && node.dataset.businessOrigin !== origin.value;
    }
    document.getElementById("business-benchmark-background").hidden = !["all", "us"].includes(origin.value);
    let shown = 0;
    for (const row of rows) {
      const year = Number(row.dataset.businessYear);
      row.hidden = year < first || year > last;
      if (!row.hidden) shown += 1;
    }
    status.textContent = `${shown} table years shown. Charts retain their full reported history; year filters affect the table only. Downloads always contain the complete dataset.`;
  };
  form.addEventListener("submit", (event) => event.preventDefault());
  for (const control of [origin, start, end]) control.addEventListener("change", update);
  form.hidden = false;
  update();
}
