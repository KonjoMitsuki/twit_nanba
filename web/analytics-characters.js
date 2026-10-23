/* Character suggestion ranking shared by the analytics editor. */
(() => {
  const LIMIT = 5;
  const normalize = (value) =>
    String(value ?? "")
      .trim()
      .normalize("NFKC")
      .toLocaleLowerCase("ja");

  function suggest(
    names,
    { selected = [], counts = {}, query = "", max = LIMIT } = {},
  ) {
    const selectedKeys = new Set(selected.map(normalize));
    const countByKey = new Map(
      Object.entries(counts).map(([name, count]) => [
        normalize(name),
        Number(count) || 0,
      ]),
    );
    const needle = normalize(query);
    const unique = [];
    const seen = new Set();
    for (const raw of names) {
      const name = String(raw ?? "").trim();
      const key = normalize(name);
      if (!name || seen.has(key)) continue;
      seen.add(key);
      unique.push({ name, key });
    }
    return unique
      .filter(({ key }) => !selectedKeys.has(key))
      .map(({ name, key }) => {
        const rank = !needle
          ? 0
          : key === needle
            ? 0
            : key.startsWith(needle)
              ? 1
              : key.includes(needle)
                ? 2
                : -1;
        return { name, rank, count: countByKey.get(key) || 0 };
      })
      .filter((item) => item.rank >= 0)
      .sort(
        (a, b) =>
          a.rank - b.rank ||
          b.count - a.count ||
          a.name.localeCompare(b.name, "ja"),
      )
      .slice(0, Math.max(0, max))
      .map((item) => item.name);
  }

  const api = { suggest, normalize, LIMIT };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.AnalysisCharacters = api;
})();
