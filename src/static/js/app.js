(() => {
  const POLL_MS = 15000; // 15s (ajustable)

  const endpoints = {
    counts: "/api/pending-counts/",
    status: "/api/live-status/",
  };

  async function fetchJSON(url) {
    const res = await fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  }

  function setNavBadge(el, value) {
    if (!el) return;
    const n = Number(value || 0);
    if (n > 0) {
      el.hidden = false;
      el.textContent = String(n);
    } else {
      el.hidden = true;
      el.textContent = "";
    }
  }

  async function updateCounts() {
    try {
      const data = await fetchJSON(endpoints.counts);
      setNavBadge(document.getElementById("nav-badge-cc"), data.cc_pending);
      setNavBadge(document.getElementById("nav-badge-op"), data.op_pending);
    } catch (_) {
      // silencioso
    }
  }

  function applyStatusToTable(table, items) {
    const byId = new Map(items.map((it) => [String(it.id), it]));
    const filter = table.dataset.liveFilter || "all";

    table.querySelectorAll("tr[data-live-id]").forEach((tr) => {
      const id = tr.dataset.liveId;
      const it = byId.get(String(id));
      if (!it) return;

      tr.dataset.liveEstado = it.estado || "";
      tr.dataset.liveBucket = it.bucket || "";

      const badge = tr.querySelector("[data-live-status]");
      if (badge) {
        badge.className = `badge ${it.badge_class || ""}`.trim();
        badge.textContent = it.label || "";
      }

      // Si estás en tab filtrado (pending/draft/approved), y el registro ya no pertenece, lo quitamos.
      if (filter !== "all" && it.bucket && it.bucket !== filter) {
        tr.remove();
      }
    });
  }

  async function refreshTables() {
    const tables = document.querySelectorAll("table[data-live-kind]");
    for (const table of tables) {
      const kind = table.dataset.liveKind;
      const ids = Array.from(table.querySelectorAll("tr[data-live-id]"))
        .map((tr) => tr.dataset.liveId)
        .filter(Boolean);

      if (!kind || ids.length === 0) continue;

      const url =
        endpoints.status +
        `?kind=${encodeURIComponent(kind)}&ids=${encodeURIComponent(ids.join(","))}`;

      try {
        const data = await fetchJSON(url);
        if (data && Array.isArray(data.items)) {
          applyStatusToTable(table, data.items);
        }
      } catch (_) {
        // silencioso
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    updateCounts();
    refreshTables();

    setInterval(() => {
      updateCounts();
      refreshTables();
    }, POLL_MS);
  });
})();
