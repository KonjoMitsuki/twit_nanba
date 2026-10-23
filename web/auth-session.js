/* Let the existing calendar/detail pages use the authenticated API unchanged. */
(() => {
  const originalFetch = window.fetch.bind(window);
  const ready = originalFetch("/auth/me")
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null);
  window.fetch = async (input, options = {}) => {
    const target = new URL(
      typeof input === "string" ? input : input.url,
      location.href,
    );
    if (
      target.origin !== location.origin ||
      !target.pathname.startsWith("/api/")
    )
      return originalFetch(input, options);
    const auth = await ready;
    const headers = new Headers(
      options.headers || (input instanceof Request ? input.headers : undefined),
    );
    if (auth?.csrf) headers.set("X-CSRF-Token", auth.csrf);
    const response = await originalFetch(input, { ...options, headers });
    if (response.status === 401) location.assign("/analytics");
    return response;
  };
})();
