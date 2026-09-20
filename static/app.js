const weatherEl = document.getElementById("weather-content");
const issEl = document.getElementById("iss-content");
const triviaEl = document.getElementById("trivia-content");
const aiBriefEl = document.getElementById("ai-brief-content");
const aiProviderSelect = document.getElementById("ai-provider");
const generateAiBtn = document.getElementById("generate-ai-brief");
const lastUpdated = document.getElementById("last-updated");
const themeToggle = document.getElementById("theme-toggle");
const locationSubtitle = document.getElementById("location-subtitle");
const geoBanner = document.getElementById("geo-banner");
const geoBannerText = document.getElementById("geo-banner-text");
const outsideIndiaModal = document.getElementById("outside-india-modal");

const HEADLINE_SOURCES = new Set(["news", "ai-dev", "entertainment"]);

const DEFAULT_LAT = 12.7081;
const DEFAULT_LNG = 77.6953;
const DEFAULT_LABEL = "Anekal, Bengaluru";
const INDIA_LAT_MIN = 6.5;
const INDIA_LAT_MAX = 35.5;
const INDIA_LNG_MIN = 68.0;
const INDIA_LNG_MAX = 97.5;

let briefCache = null;
let userLocation = {
  lat: DEFAULT_LAT,
  lng: DEFAULT_LNG,
  label: DEFAULT_LABEL,
  source: "default",
  outsideIndia: false,
};

function fmt(value, fallback = "—") {
  return value === null || value === undefined ? fallback : value;
}

function isIndiaCoordinates(lat, lng) {
  return (
    lat >= INDIA_LAT_MIN &&
    lat <= INDIA_LAT_MAX &&
    lng >= INDIA_LNG_MIN &&
    lng <= INDIA_LNG_MAX
  );
}

function geoQueryString() {
  if (userLocation.outsideIndia) return "";
  return `lat=${encodeURIComponent(userLocation.lat)}&lng=${encodeURIComponent(userLocation.lng)}`;
}

function geoQueryPrefix() {
  const qs = geoQueryString();
  return qs ? `?${qs}` : "";
}

function setGeoBanner(message, { notice = false } = {}) {
  if (!message) {
    geoBanner.classList.add("hidden");
    geoBannerText.textContent = "";
    return;
  }
  geoBanner.classList.remove("hidden");
  geoBanner.classList.toggle("is-notice", notice);
  geoBannerText.textContent = message;
}

function updateLocationSubtitle() {
  if (userLocation.outsideIndia) {
    locationSubtitle.textContent = "India-only weather & ISS · Fetch · Cache · Analyze";
    return;
  }
  locationSubtitle.textContent = `${userLocation.label} · Fetch · Cache · Analyze`;
}

function showOutsideIndiaModal() {
  if (typeof outsideIndiaModal.showModal === "function") {
    outsideIndiaModal.showModal();
  } else {
    window.alert(
      "Geographic location is not covered. This service currently supports locations within India only."
    );
  }
}

function setOutsideIndiaState() {
  userLocation.outsideIndia = true;
  updateLocationSubtitle();
  weatherEl.innerHTML =
    `<p class="empty-state">Weather is unavailable outside India.</p>`;
  issEl.innerHTML =
    `<p class="empty-state">ISS distance is unavailable outside India.</p>`;
}

async function parseApiError(res) {
  try {
    const data = await res.json();
    if (data.error === "outside_india") {
      return data.message;
    }
    if (data.detail) {
      return data.hint ? `${data.detail} ${data.hint}` : data.detail;
    }
    if (data.message) {
      return data.message;
    }
  } catch (_) {
    /* response may not be JSON */
  }
  if (res.status === 403) {
    return "This service currently supports locations within India only.";
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

function timeAgo(iso) {
  if (!iso) return "—";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "—";
  const seconds = Math.floor((Date.now() - then.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function renderHeadlines(headlines) {
  if (!headlines?.length) {
    return `<p class="empty-state">No headlines cached yet. Hit refresh to fetch the latest.</p>`;
  }

  return `
    <ul class="headline-list">
      ${headlines
        .slice(0, 5)
        .map(
          (item) => `
        <li class="headline-item">
          <a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>
          <div class="headline-meta">
            <span>${fmt(item.source)}</span>
            <span>${timeAgo(item.published_at)}</span>
          </div>
        </li>
      `
        )
        .join("")}
    </ul>
  `;
}

function renderWeather(weather) {
  if (!weather) {
    weatherEl.innerHTML = `<p class="empty-state">No weather cached yet. Hit refresh to fetch forecast for your location.</p>`;
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

async function loadHeadlineCard(source, refresh = false) {
  const container = document.getElementById(`${source}-content`);
  setLoading(container, `Loading ${source}`);

  const url = refresh ? `/${source}?refresh=true` : `/${source}`;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      const message = await parseApiError(res);
      throw new Error(message);
    }
    const payload = await res.json();
    container.innerHTML = renderHeadlines(payload.data?.headlines || []);
  } catch (err) {
    container.innerHTML = `<p class="error-state">Could not load headlines. ${err.message || "Try again shortly."}</p>`;
    console.error(`${source} load error`, err);
  }
}

async function loadDailyBrief() {
  if (userLocation.outsideIndia) {
    setOutsideIndiaState();
    return;
  }

  setLoading(weatherEl, "Loading weather");
  setLoading(issEl, "Loading ISS");
  setLoading(triviaEl, "Loading trivia");

  try {
    const res = await fetch(`/analytics/daily-brief?${geoQueryString()}`);
    if (!res.ok) {
      const message = await parseApiError(res);
      throw new Error(message);
    }
    renderBrief(await res.json());
  } catch (err) {
    const message = `<p class="error-state">Could not load daily brief. ${err.message || "Try again shortly."}</p>`;
    weatherEl.innerHTML = message;
    issEl.innerHTML = message;
    triviaEl.innerHTML = message;
    console.error("daily-brief error", err);
  }
}

async function refreshSource(source) {
  if (userLocation.outsideIndia && (source === "weather" || source === "iss")) {
    setOutsideIndiaState();
    return;
  }

  setCardRefreshing(source, true);
  setLoading(document.getElementById(`${source}-content`), `Refreshing ${source}`);

  try {
    const geoSuffix = HEADLINE_SOURCES.has(source) ? "" : geoQueryPrefix();
    const res = await fetch(`/${source}/refresh${geoSuffix}`, { method: "POST" });
    if (!res.ok) {
      const message = await parseApiError(res);
      throw new Error(message);
    }

    if (HEADLINE_SOURCES.has(source)) {
      const payload = await res.json();
      document.getElementById(`${source}-content`).innerHTML = renderHeadlines(
        payload.data?.headlines || []
      );
    } else {
      await loadDailyBrief();
    }
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
  if (userLocation.outsideIndia) {
    showOutsideIndiaModal();
    return;
  }

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
    const res = await fetch(
      `/analytics/ai-brief?provider=${encodeURIComponent(provider)}&${geoQueryString()}`,
      { method: "POST" }
    );
    const data = await res.json();

    if (res.status === 503) {
      aiBriefEl.innerHTML = `
        <p class="setup-hint">${data.detail}</p>
        <p class="muted">Set env vars on Render (or locally) and redeploy to enable this feature.</p>`;
      return;
    }

    if (!res.ok) {
      throw new Error(data.message || data.detail || `Request failed (HTTP ${res.status}). Try again shortly.`);
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

function requestUserLocation() {
  setGeoBanner(
    "We use your approximate location to show weather and ISS distance for where you are in India. Your coordinates are sent only to this hub — not stored permanently.",
    { notice: true }
  );

  if (!navigator.geolocation) {
    userLocation = {
      lat: DEFAULT_LAT,
      lng: DEFAULT_LNG,
      label: DEFAULT_LABEL,
      source: "default",
      outsideIndia: false,
    };
    setGeoBanner(
      "Geolocation is not supported in this browser. Showing weather and ISS for Anekal, Bengaluru.",
      { notice: true }
    );
    updateLocationSubtitle();
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        if (!isIndiaCoordinates(latitude, longitude)) {
          userLocation = {
            lat: latitude,
            lng: longitude,
            label: "Outside India",
            source: "geolocation",
            outsideIndia: true,
          };
          setGeoBanner("");
          updateLocationSubtitle();
          showOutsideIndiaModal();
          resolve();
          return;
        }

        userLocation = {
          lat: latitude,
          lng: longitude,
          label: `Your location (${latitude.toFixed(2)}°, ${longitude.toFixed(2)}°)`,
          source: "geolocation",
          outsideIndia: false,
        };
        setGeoBanner("");
        updateLocationSubtitle();
        resolve();
      },
      () => {
        userLocation = {
          lat: DEFAULT_LAT,
          lng: DEFAULT_LNG,
          label: DEFAULT_LABEL,
          source: "default",
          outsideIndia: false,
        };
        setGeoBanner(
          "Location access was denied or unavailable. Showing weather and ISS for Anekal, Bengaluru.",
          { notice: true }
        );
        updateLocationSubtitle();
        resolve();
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 }
    );
  });
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

(async function bootstrap() {
  await requestUserLocation();
  if (userLocation.outsideIndia) {
    setOutsideIndiaState();
    await loadAiProviders();
    loadHeadlineCard("news");
    loadHeadlineCard("ai-dev");
    loadHeadlineCard("entertainment");
    return;
  }
  loadDailyBrief();
  loadAiProviders();
  loadHeadlineCard("news");
  loadHeadlineCard("ai-dev");
  loadHeadlineCard("entertainment");
})();
