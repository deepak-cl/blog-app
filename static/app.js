const briefEl = document.getElementById("brief-content");
const cacheEl = document.getElementById("cache-content");
const feedEl = document.getElementById("feed-content");
const sseStatus = document.getElementById("sse-status");
const lastUpdated = document.getElementById("last-updated");

function fmt(value, fallback = "—") {
  return value === null || value === undefined ? fallback : value;
}

function badgeClass(status) {
  if (status === "hit_friendly" || status === "optimal") return "ok";
  if (status === "stale_serves_fallback" || status === "partial") return "warn";
  return "bad";
}

async function loadDailyBrief() {
  briefEl.innerHTML = '<p class="muted">Loading daily brief…</p>';
  const res = await fetch("/analytics/daily-brief");
  const data = await res.json();

  const weather = data.weather;
  const iss = data.iss;
  const trivia = data.trivia;

  briefEl.innerHTML = `
    <div class="brief-grid">
      <div class="panel">
        <h3>Weather</h3>
        ${
          weather
            ? `<p><strong>${fmt(weather.location)}</strong></p>
               <p>${fmt(weather.current?.condition)} · ${fmt(weather.current?.temperature_c)}°C</p>
               <p>Today: high ${fmt(weather.today?.high_c)}°C / low ${fmt(weather.today?.low_c)}°C</p>`
            : "<p class='muted'>No weather cached</p>"
        }
      </div>
      <div class="panel">
        <h3>ISS</h3>
        ${
          iss
            ? `<p>Lat ${fmt(iss.latitude)} · Lng ${fmt(iss.longitude)}</p>
               <p>Distance to NYC: ${fmt(iss.distance_km)} km</p>
               <p><span class="badge ${iss.near_reference ? "ok" : "warn"}">${iss.near_reference ? "Near reference" : "Far from reference"}</span></p>`
            : "<p class='muted'>No ISS cached</p>"
        }
      </div>
      <div class="panel">
        <h3>Trivia</h3>
        ${
          trivia
            ? `<p>${trivia.question}</p>
               <p class="muted">${fmt(trivia.category)} · ${fmt(trivia.difficulty)}</p>`
            : "<p class='muted'>No trivia cached</p>"
        }
      </div>
    </div>
    ${data.notes?.length ? `<p class="muted" style="margin-top:0.8rem">${data.notes.join(" ")}</p>` : ""}
  `;
}

async function loadCacheEfficiency() {
  cacheEl.innerHTML = '<p class="muted">Loading cache stats…</p>';
  const res = await fetch("/analytics/cache-efficiency");
  const data = await res.json();

  const rows = (data.sources || [])
    .map(
      (row) => `
      <div class="stat-row">
        <span>${row.source}</span>
        <span class="badge ${badgeClass(row.hit_friendly_status)}">${row.hit_friendly_status}</span>
      </div>
      <div class="stat-row"><span>Entries</span><span>${row.entry_count}</span></div>
      <div class="stat-row"><span>Age</span><span>${fmt(row.age_seconds, "—")}s / TTL ${row.ttl_seconds}s</span></div>
      <div class="stat-row"><span>Stale</span><span>${row.is_stale ? "yes" : "no"}</span></div>
      <hr style="border:none;border-top:1px solid rgba(255,255,255,0.06);margin:0.6rem 0" />
    `
    )
    .join("");

  cacheEl.innerHTML = `
    <p style="margin-top:0"><span class="badge ${badgeClass(data.summary?.overall_status)}">${fmt(data.summary?.overall_status)}</span></p>
    ${rows}
  `;
}

function prependFeedEntry(event) {
  const entry = document.createElement("div");
  entry.className = "feed-entry";
  entry.innerHTML = `<time>${event.timestamp || new Date().toISOString()}</time><br /><strong>${event.type}</strong><pre>${JSON.stringify(event.payload, null, 2)}</pre>`;
  if (feedEl.querySelector(".muted")) {
    feedEl.innerHTML = "";
  }
  feedEl.prepend(entry);
  while (feedEl.children.length > 30) {
    feedEl.removeChild(feedEl.lastChild);
  }
}

function connectSSE() {
  const source = new EventSource("/events/stream");

  source.onopen = () => {
    sseStatus.textContent = "live";
    sseStatus.className = "badge live";
  };

  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data);
      prependFeedEntry(event);
      lastUpdated.textContent = `Last event: ${new Date().toLocaleTimeString()}`;
    } catch (err) {
      console.error("SSE parse error", err);
    }
  };

  source.onerror = () => {
    sseStatus.textContent = "reconnecting";
    sseStatus.className = "badge warn";
  };
}

document.getElementById("refresh-brief").addEventListener("click", loadDailyBrief);
document.getElementById("refresh-cache").addEventListener("click", loadCacheEfficiency);

loadDailyBrief();
loadCacheEfficiency();
connectSSE();
