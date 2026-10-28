const assert = require("node:assert/strict");
const {
  ticks,
  zoom,
  pan,
  scaleY,
} = require("../web/analytics-chart-interactions.js");
assert.deepEqual(ticks(0, 100, null), [0, 25, 50, 75, 100]);
assert.deepEqual(ticks(3, 32, 10), [10, 20, 30]);
assert.deepEqual(ticks(-12, 12, 5), [-10, -5, 0, 5, 10]);
assert.deepEqual(ticks(0.03, 0.08, 0.02), [0.04, 0.06, 0.08]);
assert.deepEqual(ticks(2, 2, 1), [2]);
assert.ok(ticks(0, 100, 1e-300).length <= 201);
assert.ok(ticks(0, 100, 1e-300).every(Number.isFinite));
const base = { xmin: 0, xmax: 100, ymin: -50, ymax: 50 };
const view = zoom(base, base, 0.5);
assert.deepEqual(view, { xmin: 25, xmax: 75, ymin: -50, ymax: 50 });
assert.deepEqual(zoom(base, base, 0.5, 0), {
  xmin: 0,
  xmax: 50,
  ymin: -50,
  ymax: 50,
});
assert.deepEqual(zoom(view, base, 10), base);
assert.deepEqual(pan(view, base, 100), {
  xmin: 50,
  xmax: 100,
  ymin: -50,
  ymax: 50,
});
assert.ok(
  zoom(view, base, 1e-10).xmax - zoom(view, base, 1e-10).xmin >= 0.09999999,
);
assert.deepEqual(base, { xmin: 0, xmax: 100, ymin: -50, ymax: 50 });

// Cursor anchoring is stable even when several wheel events share one frame.
let cursorView = base;
for (let i = 0; i < 10; i++) cursorView = zoom(cursorView, base, 0.9, 0.2);
assert.ok(
  Math.abs(cursorView.xmin + (cursorView.xmax - cursorView.xmin) * 0.2 - 20) <
    1e-10,
);
const manual = scaleY(base, base, 0.5);
assert.deepEqual(manual, { xmin: 0, xmax: 100, ymin: -25, ymax: 25 });
// Pinching away from the center keeps the touched Y value anchored.
const anchoredY = scaleY(base, base, 0.5, 0.8);
assert.deepEqual(anchoredY, { xmin: 0, xmax: 100, ymin: -10, ymax: 40 });
assert.equal(anchoredY.ymin + (anchoredY.ymax - anchoredY.ymin) * 0.8, 30);
assert.deepEqual(zoom(manual, base, 0.5), { ...manual, xmin: 25, xmax: 75 });
assert.deepEqual(pan({ ...manual, xmin: 20, xmax: 80 }, base, -100), {
  ...manual,
  xmin: 0,
  xmax: 60,
});
assert.ok(scaleY(base, base, 1e100).ymax <= 500000);
assert.ok(scaleY(base, base, 1e-100).ymax > 0);

console.log("Independent axis tick/zoom/pan assertions passed");
