/* Shared pure table operations: group the complete result before pagination. */
(() => {
  const collator = new Intl.Collator("ja", {
    numeric: true,
    sensitivity: "base",
  });
  const missing = (value) =>
    value == null || value === "" || (Array.isArray(value) && !value.length);
  const normalizedList = (values) =>
    [...new Set(values.filter((value) => !missing(value)))].sort(
      collator.compare,
    );
  const fieldValue = (row, field) =>
    field === "character" && Array.isArray(row.characters)
      ? row.characters.length
        ? normalizedList(row.characters).join(" + ")
        : null
      : row[field];
  const sortsFor = (panel) =>
    panel.table_sorts ?? [
      { field: panel.table_sort || "date", desc: panel.table_desc ?? true },
    ];
  function compare(a, b, kind = "text") {
    if (missing(a) && missing(b)) return 0;
    if (missing(a)) return 1;
    if (missing(b)) return -1;
    if (typeof a === "number" && typeof b === "number") return a - b;
    if (
      kind === "date" &&
      Number.isFinite(Date.parse(a)) &&
      Number.isFinite(Date.parse(b))
    )
      return Date.parse(a) - Date.parse(b);
    return collator.compare(
      Array.isArray(a) ? normalizedList(a).join(" / ") : String(a),
      Array.isArray(b) ? normalizedList(b).join(" / ") : String(b),
    );
  }
  function sortRows(rows, panel, kinds = {}) {
    const sorts = sortsFor(panel);
    return [...rows].sort((a, b) => {
      for (const sort of sorts) {
        const av = fieldValue(a, sort.field),
          bv = fieldValue(b, sort.field);
        const result = compare(av, bv, kinds[sort.field]);
        // Missing values stay at the end in both directions.
        if (result)
          return missing(av) || missing(bv)
            ? result
            : sort.desc
              ? -result
              : result;
      }
      return 0;
    });
  }
  function dateBucket(value, unit) {
    if (unit === "exact") return value;
    const time = new Date(value);
    if (!Number.isFinite(time.getTime())) return value;
    const parts = new Intl.DateTimeFormat("en", {
      timeZone: "Asia/Tokyo",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(time);
    const part = (type) => parts.find((p) => p.type === type).value;
    const day = `${part("year")}-${part("month")}-${part("day")}`;
    if (unit === "year") return day.slice(0, 4);
    if (unit === "month") return day.slice(0, 7);
    if (unit === "week") {
      const monday = new Date(day + "T00:00:00Z");
      monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
      return monday.toISOString().slice(0, 10);
    }
    return day;
  }
  function groupRows(rows, panel, kinds = {}) {
    const field = panel.table_group;
    if (!field) return [];
    const groups = new Map();
    for (const row of rows) {
      let value =
        field === "character" && Array.isArray(row.characters)
          ? row.characters
          : row[field];
      if (kinds[field] === "date" && !missing(value))
        value = dateBucket(value, panel.table_group_dates || "day");
      let values;
      if (Array.isArray(value)) {
        const list = normalizedList(value);
        values = !list.length
          ? [null]
          : panel.table_group_multivalue === "combination"
            ? [list]
            : list;
      } else values = [missing(value) ? null : value];
      for (const item of values) {
        const key = JSON.stringify([
          field,
          panel.table_group_dates || "day",
          item,
        ]);
        if (!groups.has(key))
          groups.set(key, {
            key,
            value: item,
            label: missing(item)
              ? "未設定"
              : Array.isArray(item)
                ? item.join(" + ")
                : String(item),
            rows: [],
          });
        groups.get(key).rows.push(row);
      }
    }
    return [...groups.values()].sort((a, b) => {
      const result = compare(
        a.value,
        b.value,
        kinds[field] === "date" ? "date" : "text",
      );
      return missing(a.value) || missing(b.value)
        ? result
        : panel.table_group_order === "desc"
          ? -result
          : result;
    });
  }
  const api = { sortsFor, sortRows, groupRows };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.AnalysisTable = api;
})();
