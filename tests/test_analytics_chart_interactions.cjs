const assert = require("node:assert/strict");
const { ticks, zoom, pan } = require("../web/analytics-chart-interactions.js");
assert.deepEqual(ticks(0, 100, null), [0, 25, 50, 75, 100]);
assert.deepEqual(ticks(3, 32, 10), [10, 20, 30]);
assert.deepEqual(ticks(-12, 12, 5), [-10, -5, 0, 5, 10]);
assert.deepEqual(ticks(0.03, 0.08, 0.02), [0.04, 0.06, 0.08]);
assert.deepEqual(ticks(2, 2, 1), [2]);
assert.ok(ticks(0, 100, 1e-300).length <= 201);
assert.ok(ticks(0, 100, 1e-300).every(Number.isFinite));
const base = { xmin: 0, xmax: 100, ymin: -50, ymax: 50 };
const view = zoom(base, base, 0.5);
assert.deepEqual(view, { xmin: 25, xmax: 75, ymin: -25, ymax: 25 });
assert.deepEqual(zoom(base, base, 0.5, 0, 1), {
  xmin: 0,
  xmax: 50,
  ymin: 0,
  ymax: 50,
});
assert.deepEqual(zoom(view, base, 10), base);
assert.deepEqual(pan(view, base, 100, -100), {
  xmin: 50,
  xmax: 100,
  ymin: -50,
  ymax: 0,
});
assert.ok(
  zoom(view, base, 1e-10).xmax - zoom(view, base, 1e-10).xmin >= 0.09999999,
);
assert.deepEqual(base, { xmin: 0, xmax: 100, ymin: -50, ymax: 50 });
console.log("Chart tick/zoom/pan assertions passed");
