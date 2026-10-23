const assert = require("node:assert/strict");
const { sortRows, groupRows, sortsFor } = require("../web/analytics-table.js");
const rows = [
  {
    id: "a",
    characters: ["A", "B", "A"],
    tags: ["x", "y"],
    likes: 10,
    date: "2026-10-01",
    measured_at: "2026-10-01T23:30:00+09:00",
  },
  {
    id: "b",
    characters: ["A"],
    tags: ["y"],
    likes: 30,
    date: "2026-10-01",
    measured_at: "2026-10-01T15:30:00Z",
  },
  { id: "c", characters: [], tags: [], likes: null, date: "2026-10-02" },
  { id: "d", characters: ["B", "A"], likes: 20, date: "2026-10-02" },
];
let panel = {
  table_sorts: [
    { field: "date", desc: true },
    { field: "likes", desc: true },
  ],
};
assert.deepEqual(
  sortRows(rows, panel).map((row) => row.id),
  ["d", "c", "b", "a"],
);
assert.deepEqual(
  sortRows(rows, { table_sort: "likes", table_desc: true }).map(
    (row) => row.id,
  ),
  ["b", "d", "a", "c"],
);
assert.deepEqual(
  sortRows(rows, { table_sorts: [] }).map((row) => row.id),
  ["a", "b", "c", "d"],
);
assert.deepEqual(sortsFor({ table_sort: "likes", table_desc: false }), [
  { field: "likes", desc: false },
]);
assert.deepEqual(
  sortRows(
    rows,
    { table_sorts: [{ field: "measured_at", desc: false }] },
    { measured_at: "date" },
  ).map((row) => row.id),
  ["a", "b", "c", "d"],
);
let groups = groupRows(sortRows(rows, panel), { table_group: "character" });
assert.deepEqual(
  groups.map((group) => [group.label, group.rows.length]),
  [
    ["A", 3],
    ["B", 2],
    ["未設定", 1],
  ],
);
assert.deepEqual(
  groups[0].rows.map((row) => row.id),
  ["d", "b", "a"],
);
groups = groupRows(rows, {
  table_group: "character",
  table_group_multivalue: "combination",
});
assert.deepEqual(
  groups.map((group) => [group.label, group.rows.length]),
  [
    ["A", 1],
    ["A + B", 2],
    ["未設定", 1],
  ],
);
assert.deepEqual(
  groupRows(rows, { table_group: "character", table_group_order: "desc" }).map(
    (group) => group.label,
  ),
  ["B", "A", "未設定"],
);
assert.deepEqual(
  groupRows(rows, { table_group: "tags" }).map((group) => [
    group.label,
    group.rows.length,
  ]),
  [
    ["x", 1],
    ["y", 2],
    ["未設定", 2],
  ],
);
groups = groupRows(
  rows,
  { table_group: "measured_at", table_group_dates: "day" },
  { measured_at: "date" },
);
assert.deepEqual(
  groups.map((group) => [group.label, group.rows.length]),
  [
    ["2026-10-01", 1],
    ["2026-10-02", 1],
    ["未設定", 2],
  ],
);
assert.deepEqual(
  groupRows(
    rows,
    { table_group: "measured_at", table_group_dates: "month" },
    { measured_at: "date" },
  ).map((group) => [group.label, group.rows.length]),
  [
    ["2026-10", 2],
    ["未設定", 2],
  ],
);
assert.equal(
  groupRows(
    rows,
    { table_group: "date", table_group_dates: "week" },
    { date: "date" },
  )[0].label,
  "2026-09-28",
);
assert.equal(
  groupRows(
    Array.from({ length: 123 }, (_, i) => ({ id: i, characters: ["A"] })),
    { table_group: "character" },
  )[0].rows.length,
  123,
);
assert.deepEqual(groupRows(rows, {}), []);
assert.equal(rows[0].characters.length, 3); // No mutation of source records.
console.log("Table sorting/grouping assertions passed");
