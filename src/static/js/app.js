(() => {
  const POLL_MS = 8000; // más rápido (8s). Si quieres 5s lo bajamos.

  const endpoints = {
    counts: "/api/pending-counts/",
    status: "/api/live-status/",
  };

  let busy = false;

  async function fetchJSON(url) {
    const res = await fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      cache: "no-store",
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
      const url = `${endpoints.counts}?_=${Date.now()}`;
      const data = await fetchJSON(url);
      setNavBadge(document.getElementById("nav-badge-cc"), data.cc_pending);
      setNavBadge(document.getElementById("nav-badge-op"), data.op_pending);
    } catch (_) {
      // silencioso
    }
  }

  function applyStatusToTable(table, items) {
    const byId = new Map(items.map((it) => [String(it.id), it]));
    const filter = table.dataset.liveFilter || "all";

    // solo filas reales (no thead)
    table.querySelectorAll("tbody tr[data-live-id]").forEach((tr) => {
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

      // si estás filtrando, y ya no pertenece, se quita (evita “fantasmas”)
      if (filter !== "all" && it.bucket && it.bucket !== filter) {
        tr.remove();
      }
    });
  }

  async function refreshTables() {
    const tables = document.querySelectorAll("table[data-live-kind]");
    for (const table of tables) {
      const kind = table.dataset.liveKind;

      const ids = Array.from(table.querySelectorAll("tbody tr[data-live-id]"))
        .map((tr) => tr.dataset.liveId)
        .filter((v) => v && /^\d+$/.test(v));

      if (!kind || ids.length === 0) continue;

      const url =
        `${endpoints.status}?kind=${encodeURIComponent(kind)}` +
        `&ids=${encodeURIComponent(ids.join(","))}` +
        `&_=${Date.now()}`;

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

  async function tick() {
    if (busy) return;
    busy = true;
    try {
      await updateCounts();
      await refreshTables();
    } finally {
      busy = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    tick();
    setInterval(tick, POLL_MS);
  });
})();
