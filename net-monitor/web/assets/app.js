async function getJSON(url){
  const res = await fetch(url, { cache: "no-store" });
  return await res.json();
}

function badgeHTML(status){
  const s = (status || "UNKNOWN").toUpperCase();
  if(s === "UP") return `<span class="badge up"><span class="dot"></span>UP</span>`;
  if(s === "DEGRADED") return `<span class="badge degraded"><span class="dot"></span>DEGRADED</span>`;
  if(s === "DOWN") return `<span class="badge down"><span class="dot"></span>DOWN</span>`;
  return `<span class="badge"><span class="dot"></span>${s}</span>`;
}

function safe(v){ return (v === null || v === undefined) ? "" : String(v); }

function buildKPIs(items){
  let up=0, down=0, degraded=0;
  let avgLat = 0, latCount = 0;

  for(const it of items){
    const s = (it.status||"").toUpperCase();
    if(s==="UP") up++;
    else if(s==="DOWN") down++;
    else if(s==="DEGRADED") degraded++;

    if(typeof it.last_latency_ms === "number"){
      avgLat += it.last_latency_ms;
      latCount++;
    }
  }
  const avg = latCount ? (avgLat/latCount).toFixed(1) : "-";
  return [
    {k:"Total Targets", v: items.length},
    {k:"UP", v: up},
    {k:"DEGRADED", v: degraded},
    {k:"DOWN", v: down},
    {k:"Avg Latency (ms)", v: avg}
  ];
}

function renderKPIs(kpis){
  const el = document.getElementById("kpis");
  el.innerHTML = kpis.map(x => `
    <div class="kpi">
      <div class="k">${x.k}</div>
      <div class="v">${x.v}</div>
    </div>
  `).join("");
}

function applySearchSort(items){
  const q = (document.getElementById("q").value || "").toLowerCase().trim();
  const sort = document.getElementById("sort").value;

  let filtered = items;
  if(q){
    filtered = items.filter(it =>
      (it.name||"").toLowerCase().includes(q) ||
      (it.host||"").toLowerCase().includes(q)
    );
  }

  const statusRank = (s)=>{
    s = (s||"").toUpperCase();
    if(s==="DOWN") return 0;
    if(s==="DEGRADED") return 1;
    if(s==="UP") return 2;
    return 3;
  };

  filtered.sort((a,b)=>{
    if(sort==="status") return statusRank(a.status) - statusRank(b.status);
    if(sort==="latency"){
      const al = (typeof a.last_latency_ms==="number") ? a.last_latency_ms : 999999;
      const bl = (typeof b.last_latency_ms==="number") ? b.last_latency_ms : 999999;
      return al - bl;
    }
    if(sort==="failures") return (b.failures||0) - (a.failures||0);
    return (a.name||"").localeCompare(b.name||"");
  });

  return filtered;
}

function renderTable(items){
  const rows = document.getElementById("rows");
  const countText = document.getElementById("countText");
  countText.textContent = `${items.length} shown`;

  if(!items.length){
    rows.innerHTML = `<tr><td colspan="6">No results</td></tr>`;
    return;
  }

  rows.innerHTML = items.map(it => `
    <tr>
      <td>${safe(it.name)}</td>
      <td>${safe(it.host)}</td>
      <td>${badgeHTML(it.status)}</td>
      <td>${it.last_latency_ms === null ? "-" : safe(it.last_latency_ms)}</td>
      <td>${safe(it.failures)}</td>
      <td>${safe(it.last_seen) || "-"}</td>
    </tr>
  `).join("");
}

function renderAlerts(alerts){
  const el = document.getElementById("alerts");
  if(!alerts || !alerts.length){
    el.innerHTML = `<div class="muted">No alerts yet</div>`;
    return;
  }
  el.innerHTML = alerts.map(a => `
    <div class="alertItem">
      <div class="alertTop">
        <div>${safe(a.name)} • ${safe(a.host)}</div>
        <div>${new Date(a.ts).toLocaleString()}</div>
      </div>
      <div class="alertMain">${safe(a.from)} → ${safe(a.to)}</div>
    </div>
  `).join("");
}

let lastData = [];

async function refresh(){
  const lastUpdate = document.getElementById("lastUpdate");

  try{
    const data = await getJSON("api.php");
    if(!data.ok){
      lastUpdate.textContent = "API error";
      renderTable([]);
      return;
    }

    lastData = data.items || [];
    lastUpdate.textContent = "Updated: " + new Date().toLocaleTimeString();

    renderKPIs(buildKPIs(lastData));
    renderTable(applySearchSort([...lastData]));

    // alerts feed
    const alerts = await getJSON("alerts.php?limit=25");
    if(alerts.ok) renderAlerts(alerts.items || []);
  }catch(e){
    lastUpdate.textContent = "Fetch failed";
  }
}

document.getElementById("q").addEventListener("input", ()=> renderTable(applySearchSort([...lastData])));
document.getElementById("sort").addEventListener("change", ()=> renderTable(applySearchSort([...lastData])));
document.getElementById("refreshBtn").addEventListener("click", refresh);

refresh();
setInterval(refresh, 3000);
