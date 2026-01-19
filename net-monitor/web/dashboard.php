<?php
// dashboard.php (UI only)
// Note: JS still fetches data via your existing API endpoint (web.api.php / api.php) inside assets/app.js
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Z • Net Monitor Dashboard</title>

  <!-- Optional: nicer font (safe to remove if you want fully offline) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <div class="app">
    <div class="wrap">

      <!-- TOP BAR -->
      <header class="topbar">
        <div class="brand">
          <div class="logo">Z</div>
          <div class="brandText">
            <div class="brandTitle">Z • Net Monitor</div>
            <div class="brandSub">Live uptime + latency monitoring (authorized networks only)</div>
          </div>
        </div>

        <div class="topActions">
          <div class="pill" id="lastUpdate">Loading…</div>
          <button class="btn primary" id="refreshBtn" type="button">Refresh</button>
        </div>
      </header>

      <!-- KPIs + CONTROLS -->
      <section class="card controls">
        <div class="controlsRow">
          <div class="field">
            <span class="icon">⌕</span>
            <input id="q" class="search" placeholder="Search by name / host…" autocomplete="off" />
          </div>

          <select id="sort" class="select">
            <option value="status">Sort: Status</option>
            <option value="latency">Sort: Latency</option>
            <option value="failures">Sort: Failures</option>
            <option value="name">Sort: Name</option>
          </select>

          <div class="seg">
            <button class="segBtn active" id="filterAll" type="button">All</button>
            <button class="segBtn" id="filterUp" type="button">Up</button>
            <button class="segBtn" id="filterDegraded" type="button">Degraded</button>
            <button class="segBtn" id="filterDown" type="button">Down</button>
          </div>
        </div>

        <div class="kpis" id="kpis">
          <!-- app.js will fill -->
        </div>
      </section>

      <!-- MAIN GRID -->
      <div class="grid2">
        <!-- TARGETS -->
        <section class="card">
          <div class="cardHead">
            <div>
              <div class="cardTitle">Targets</div>
              <div class="muted" id="countText">Loading…</div>
            </div>
            <div class="rightMeta">
              <div class="miniPill" id="modePill">PING</div>
            </div>
          </div>

          <div class="tableWrap">
            <table class="table">
              <thead>
                <tr>
                  <th style="width:26%">Name</th>
                  <th style="width:18%">Host</th>
                  <th style="width:14%">Status</th>
                  <th style="width:14%">Latency</th>
                  <th style="width:12%">Failures</th>
                  <th style="width:16%">Last Seen</th>
                </tr>
              </thead>
              <tbody id="rows">
                <tr><td colspan="6" class="loadingRow">Loading…</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- ALERTS -->
        <section class="card">
          <div class="cardHead">
            <div>
              <div class="cardTitle">Recent Alerts</div>
              <div class="muted">Status changes</div>
            </div>
            <button class="btn ghost" id="clearAlertsBtn" type="button">Clear UI</button>
          </div>

          <div class="alerts" id="alerts">
            <div class="muted">Loading…</div>
          </div>

          <div class="cardFoot muted">
            Alerts are generated when a target status changes (UP/DEGRADED/DOWN).
          </div>
        </section>
      </div>

      <footer class="footer">
        <div>© Zee • Z • Net Monitor</div>
        <div class="muted">For authorized networks only</div>
      </footer>
    </div>
  </div>

  <script src="assets/app.js"></script>

  <!-- Small UI helpers (won’t break your JS) -->
  <script>
    // Optional filter buttons (only changes UI state; your app.js can choose to read window.Z_FILTER)
    window.Z_FILTER = "all";

    const setActive = (id) => {
      document.querySelectorAll(".segBtn").forEach(b => b.classList.remove("active"));
      document.getElementById(id).classList.add("active");
    };

    const bind = (id, value) => {
      const el = document.getElementById(id);
      if(!el) return;
      el.addEventListener("click", () => {
        window.Z_FILTER = value;
        setActive(id);
        // If your app.js has a global render function, call it safely:
        if (typeof window.renderNetMonitor === "function") window.renderNetMonitor();
      });
    };

    bind("filterAll", "all");
    bind("filterUp", "UP");
    bind("filterDegraded", "DEGRADED");
    bind("filterDown", "DOWN");

    // Optional “clear alerts UI” (does not delete server logs)
    const clearBtn = document.getElementById("clearAlertsBtn");
    if(clearBtn){
      clearBtn.addEventListener("click", () => {
        const box = document.getElementById("alerts");
        if(box) box.innerHTML = '<div class="muted">Cleared (UI only)</div>';
      });
    }
  </script>
</body>
</html>
