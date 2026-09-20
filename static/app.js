const weatherEl = document.getElementById("weather-content");
const issEl = document.getElementById("iss-content");
const triviaEl = document.getElementById("trivia-content");
const aiBriefEl = document.getElementById("ai-brief-content");
const aiProviderSelect = document.getElementById("ai-provider");
const generateAiBtn = document.getElementById("generate-ai-brief");
const lastUpdated = document.getElementById("last-updated");
const themeToggle = document.getElementById("theme-toggle");

let briefCache = null;

function fmt(value, fallback = "—") {
  return value === null || value === undefined ? fallback : value;
}

async function parseApiError(res) {
  try {
    const data = await res.json();
    if (data.detail) {
      return data.hint ? `${data.detail} ${data.hint}` : data.detail;
    }
  } catch (_) {
    /* response may not be JSON */
  }
  if (res.status === 429) {
    return "Weather service is temporarily rate-limited. Cached data is shown when available.";
  }
  if (res.status === 502) {
    return "A data source is temporarily unavailable. Try again shortly.";
  }
  if (res.status === 503) {
    return "This feature is not configured on the server yet.";
  }
  return `Request failed (HTTP ${res.status}). Try again shortly.`;
}

function skeletonMarkup(lines = 3) {
  const widths = ["wide", "", "short"];
  return `<div class="skeleton-stack" aria-hidden="true">${Array.from({ length: lines })
    .map((_, i) => `<div class="skeleton skeleton-line ${widths[i % widths.length]}"></div>`)
    .join("")}</div>`;
}

function setLoading(el, message) {
  el.innerHTML = `${skeletonMarkup()}<p class="sr-only">${message}</p>`;
}

function setCardRefreshing(source, refreshing) {
  const card = document.querySelector(`[data-source="${source}"]`);
  const btn = document.querySelector(`[data-refresh="${source}"]`);
  if (card) card.classList.toggle("is-refreshing", refreshing);
  if (btn) btn.disabled = refreshing;
}

function renderWeather(weather) {
  if (!weather) {
    weatherEl.innerHTML = `<p class="empty-state">No weather cached yet. Hit refresh to fetch Anekal/Bengaluru forecast.</p>`;
    return;
  }

  weatherEl.innerHTML = `
    <p class="location-label">${fmt(weather.location)}</p>
    <p class="stat-highlight">${fmt(weather.current?.condition)} · ${fmt(weather.current?.temperature_c)}°C</p>
    <p class="detail-row">Today: high ${fmt(weather.today?.high_c)}°C / low ${fmt(weather.today?.low_c)}°C</p>
    <p class="meta-row">Cached ${new Date(weather.cached_at).toLocaleString()}</p>
  `;
}

function renderIss(iss) {
  if (!iss) {
    issEl.innerHTML = `<p class="empty-state">No ISS data cached yet. Hit refresh to fetch the latest position.</p>`;
    return;
  }

  const nearClass = iss.near_reference ? "ok" : "warn";
  const nearLabel = iss.near_reference ? "Near reference" : "Far from reference";

  issEl.innerHTML = `
    <p class="stat-highlight">Lat ${fmt(iss.latitude)} · Lng ${fmt(iss.longitude)}</p>
    <p class="detail-row">Distance to ${fmt(iss.reference_point?.label, "reference")}: ${fmt(iss.distance_km)} km</p>
    <p><span class="badge ${nearClass}">${nearLabel}</span></p>
    <p class="meta-row">Cached ${new Date(iss.cached_at).toLocaleString()}</p>
  `;
}

function renderTrivia(trivia) {
  if (!trivia) {
    triviaEl.innerHTML = `<p class="empty-state">No trivia cached yet. Hit refresh to pull a new question batch.</p>`;
    return;
  }

  triviaEl.innerHTML = `
    <p class="trivia-question">${trivia.question}</p>
    <p class="detail-row">${fmt(trivia.category)} · ${fmt(trivia.difficulty)}</p>
    <p class="meta-row">Cached ${new Date(trivia.cached_at).toLocaleString()}</p>
  `;
}

function renderBrief(data) {
  briefCache = data;
  renderWeather(data.weather);
  renderIss(data.iss);
  renderTrivia(data.trivia);
  lastUpdated.textContent = `Updated ${new Date(data.generated_at).toLocaleTimeString()}`;
}

async function loadDailyBrief() {
  setLoading(weatherEl, "Loading weather");
  setLoading(issEl, "Loading ISS");
  setLoading(triviaEl, "Loading trivia");

  try {
    const res = await fetch("/analytics/daily-brief");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderBrief(await res.json());
  } catch (err) {
    const message = `<p class="error-state">Could not load daily brief. Try again shortly.</p>`;
    weatherEl.innerHTML = message;
    issEl.innerHTML = message;
    triviaEl.innerHTML = message;
    console.error("daily-brief error", err);
  }
}

async function refreshSource(source) {
  setCardRefreshing(source, true);
  setLoading(document.getElementById(`${source}-content`), `Refreshing ${source}`);

  try {
    const res = await fetch(`/${source}/refresh`, { method: "POST" });
    if (!res.ok) {
      const message = await parseApiError(res);
      throw new Error(message);
    }
    await loadDailyBrief();
  } catch (err) {
    const message = err.message || "Check upstream availability.";
    document.getElementById(`${source}-content`).innerHTML =
      `<p class="error-state">${source === "weather" ? "Weather refresh failed." : `Refresh failed for ${source}.`} ${message}</p>`;
    console.error(`${source} refresh error`, err);
  } finally {
    setCardRefreshing(source, false);
  }
}

async function loadAiProviders() {
  try {
    const res = await fetch("/analytics/ai-brief/providers");
    const data = await res.json();
    const providers = data.providers || [];

    aiProviderSelect.innerHTML = "";
    if (!providers.length) {
      aiProviderSelect.innerHTML = `<option value="">No providers configured</option>`;
      aiProviderSelect.disabled = true;
      generateAiBtn.disabled = true;
      aiBriefEl.innerHTML = `
        <p class="setup-hint">
          Add <code>OPENAI_API_KEY</code>, <code>ANTHROPIC_API_KEY</code>, or
          <code>GEMINI_API_KEY</code> / <code>GOOGLE_API_KEY</code> on the server to enable AI summaries.
        </p>`;
      return;
    }

    providers.forEach((provider, index) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = `${provider.label} (${provider.model})`;
      if (index === 0) option.selected = true;
      aiProviderSelect.appendChild(option);
    });

    aiProviderSelect.disabled = false;
    generateAiBtn.disabled = false;
  } catch (err) {
    aiProviderSelect.innerHTML = `<option value="">Unavailable</option>`;
    generateAiBtn.disabled = true;
    console.error("ai providers error", err);
  }
}

async function generateAiBrief() {
  const provider = aiProviderSelect.value;
  if (!provider) return;

  generateAiBtn.disabled = true;
  aiProviderSelect.disabled = true;
  aiBriefEl.innerHTML = `
    <div class="ai-loading">
      ${skeletonMarkup(4)}
      <p class="loading-label"><span class="spinner" aria-hidden="true"></span> Generating brief…</p>
    </div>`;

  try {
    const res = await fetch(`/analytics/ai-brief?provider=${encodeURIComponent(provider)}`, {
      method: "POST",
    });
    const data = await res.json();

    if (res.status === 503) {
      aiBriefEl.innerHTML = `
        <p class="setup-hint">${data.detail}</p>
        <p class="muted">Set env vars on Render (or locally) and redeploy to enable this feature.</p>`;
      return;
    }

    if (!res.ok) {
      throw new Error(data.detail || `Request failed (HTTP ${res.status}). Try again shortly.`);
    }

    aiBriefEl.innerHTML = `
      <p class="ai-brief-text">${data.brief}</p>
      <p class="meta-row">${data.provider} · ${data.model} · ${data.location}</p>`;
  } catch (err) {
    aiBriefEl.innerHTML = `<p class="error-state">${err.message || "Could not generate AI brief. Try again."}</p>`;
    console.error("ai-brief error", err);
  } finally {
    generateAiBtn.disabled = false;
    aiProviderSelect.disabled = aiProviderSelect.options.length <= 1;
  }
}

function getStoredTheme() {
  return localStorage.getItem("pah-theme");
}

function getPreferredTheme() {
  const stored = getStoredTheme();
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggle.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
}

function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  localStorage.setItem("pah-theme", next);
  applyTheme(next);
}

document.querySelectorAll(".refresh-btn").forEach((btn) => {
  btn.addEventListener("click", () => refreshSource(btn.dataset.refresh));
});

generateAiBtn.addEventListener("click", generateAiBrief);
themeToggle.addEventListener("click", toggleTheme);

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
  if (!getStoredTheme()) {
    applyTheme(event.matches ? "dark" : "light");
  }
});

applyTheme(getPreferredTheme());
loadDailyBrief();
loadAiProviders();
