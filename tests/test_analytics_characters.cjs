const assert = require("node:assert/strict");
const {
  suggest,
  normalize,
  LIMIT,
} = require("../web/analytics-characters.js");

const names = ["A", "B", "C", "D", "E", "F", "G"];
assert.equal(LIMIT, 5);
assert.deepEqual(
  suggest(names, { counts: { B: 9, A: 10, C: 8, D: 7, E: 6, F: 5, G: 4 } }),
  ["A", "B", "C", "D", "E"],
);
assert.deepEqual(
  suggest(names, {
    selected: ["C", "D"],
    counts: { C: 100, D: 90 },
  }),
  ["A", "B", "E", "F", "G"],
);
assert.deepEqual(
  suggest(names, {
    query: "b",
    selected: ["B"],
    counts: { A: 10 },
  }),
  [],
);
assert.deepEqual(suggest(["初音ミク", "巡音ルカ", "鏡音リン"], { query: "ミク" }), [
  "初音ミク",
]);
assert.deepEqual(
  suggest(["ミク", "初音ミク", "ミクライブ"], {
    query: "ミク",
    counts: { "ミクライブ": 100 },
  }),
  ["ミク", "ミクライブ", "初音ミク"],
);
assert.deepEqual(suggest(["A", "A", "B"], {}), ["A", "B"]);
assert.deepEqual(suggest(["Foo", "foo", "Bar"], { counts: { FOO: 2 } }), [
  "Foo",
  "Bar",
]);
assert.deepEqual(suggest(names, { query: "  " }), ["A", "B", "C", "D", "E"]);
assert.deepEqual(suggest(["Ａ"], { query: "a" }), ["Ａ"]);
assert.equal(normalize("  Ａ "), "a");
console.log("Character suggestion assertions passed");
