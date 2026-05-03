/* omon dashboard — vanilla JS */

// ─── Helpers ────────────────────────────

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let val = bytes;
  for (const u of units) {
    val /= 1024;
    if (val < 1024 || u === "TB") return val.toFixed(1) + " " + u;
  }
  return val.toFixed(1) + " TB";
}

function formatCtx(n) {
  if (n <= 0) return "?";
  if (n >= 1048576) return Math.floor(n / 1048576) + "M";
  if (n >= 1024) return Math.floor(n / 1024) + "K";
  return String(n);
}

function timeAgo(iso) {
  if (!iso) return "unknown";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) { const m = Math.floor(seconds / 60); return m + (m === 1 ? " min" : " mins") + " ago"; }
  if (seconds < 86400) { const h = Math.floor(seconds / 3600); return h + (h === 1 ? " hour" : " hours") + " ago"; }
  if (seconds < 604800) { const d = Math.floor(seconds / 86400); return d + (d === 1 ? " day" : " days") + " ago"; }
  const w = Math.floor(seconds / 604800);
  return w + (w === 1 ? " week" : " weeks") + " ago";
}

function barColor(pct) {
  if (pct > 90) return "bar-fill-red";
  if (pct > 70) return "bar-fill-yellow";
  return "bar-fill-blue";
}

function pressureColor(level) {
  const map = { normal: "status-ok", warn: "status-warn", critical: "status-bad" };
  return map[level] || "";
}

function ratingLabel(tokS) {
  if (tokS >= 60) return ["Excellent", "status-ok"];
  if (tokS >= 30) return ["Good", "status-ok"];
  if (tokS >= 15) return ["Moderate", "status-warn"];
  if (tokS >= 5) return ["Slow", "status-warn"];
  return ["Very slow", "status-bad"];
}

function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ─── State ──────────────────────────────

let allModels = [];

// ─── Renderers ──────────────────────────

function renderStatus(data) {
  const el = document.getElementById("status-content");
  const srv = data.server;

  const statusClass = srv.running ? "status-ok" : "status-bad";
  const statusText = srv.running ? "running" : "stopped";

  el.innerHTML = `
    <div class="status-row">
      <span class="status-label">Status</span>
      <span class="status-value ${statusClass}">${statusText}</span>
    </div>
    ${srv.version ? `
    <div class="status-row">
      <span class="status-label">Version</span>
      <span class="status-value">v${escapeHTML(srv.version)}</span>
    </div>` : ""}
    <div class="status-row">
      <span class="status-label">Models</span>
      <span class="status-value">${data.models_count} installed</span>
    </div>
    <div class="status-row">
      <span class="status-label">Total size</span>
      <span class="status-value">${data.models_total_size_human}</span>
    </div>
    <div class="status-row">
      <span class="status-label">Loaded</span>
      <span class="status-value">${data.running.length} model${data.running.length !== 1 ? "s" : ""}</span>
    </div>
  `;

  // Hardware info in header
  const hw = data.hardware;
  document.getElementById("hw-info").textContent =
    `${hw.chip} · ${formatSize(hw.total_memory)} · ${hw.cpu_cores} cores`;
}

function renderMemory(data) {
  const el = document.getElementById("memory-content");
  const p = data;

  const usedPct = p.memory_total > 0 ? (p.memory_used / p.memory_total * 100) : 0;
  const modelPct = p.memory_total > 0 ? (p.model_memory / p.memory_total * 100) : 0;

  let html = `
    <div class="status-row">
      <span class="status-label">Pressure</span>
      <span class="status-value ${pressureColor(p.level)}">${p.level}</span>
    </div>
    <div class="bar-container">
      <div class="bar-label">
        <span class="bar-label-name">System</span>
        <span class="bar-label-value">${p.memory_used_human} / ${p.memory_total_human} (${usedPct.toFixed(0)}%)</span>
      </div>
      <div class="bar-track"><div class="bar-fill ${barColor(usedPct)}" style="width:${usedPct}%"></div></div>
    </div>
    <div class="bar-container">
      <div class="bar-label">
        <span class="bar-label-name">Models</span>
        <span class="bar-label-value">${p.model_memory_human} (${modelPct.toFixed(1)}%)</span>
      </div>
      <div class="bar-track"><div class="bar-fill bar-fill-cyan" style="width:${modelPct}%"></div></div>
    </div>
  `;

  if (p.swap_used > 0) {
    html += `<div class="status-row"><span class="status-warn">Swap in use: ${formatSize(p.swap_used)}</span></div>`;
  }

  el.innerHTML = html;
}

function renderDisk(data) {
  const el = document.getElementById("disk-content");
  if (!data.models.length) { el.innerHTML = '<div class="empty">No models</div>'; return; }

  const maxSize = Math.max(...data.models.map(m => m.size));
  let html = "";

  for (const m of data.models) {
    const pct = maxSize > 0 ? (m.size / maxSize * 100) : 0;
    const name = m.name.length > 28 ? m.name.slice(0, 27) + "…" : m.name;
    html += `
      <div class="bar-container">
        <div class="bar-label">
          <span class="bar-label-name">${escapeHTML(name)}</span>
          <span class="bar-label-value">${m.size_human}</span>
        </div>
        <div class="bar-track"><div class="bar-fill bar-fill-cyan" style="width:${pct}%"></div></div>
      </div>
    `;
  }

  html += `<div style="margin-top:8px;color:var(--text-dim);font-size:12px">
    Free: ${data.disk_free_human}
  </div>`;

  el.innerHTML = html;
}

function renderRunning(data) {
  const el = document.getElementById("running-content");
  const countEl = document.getElementById("running-count");
  const models = data.models || [];

  countEl.textContent = models.length > 0 ? `(${models.length})` : "";

  if (!models.length) {
    el.innerHTML = '<div class="empty">No models loaded · Waiting for activity...</div>';
    return;
  }

  let html = "";
  for (const m of models) {
    const pct = m.memory_pct || 0;
    html += `
      <div class="running-model">
        <div class="running-model-name">${escapeHTML(m.name)}</div>
        <div class="running-model-mem">${m.size_human} (${pct.toFixed(1)}%)</div>
        <div class="running-model-bar">
          <div class="bar-track"><div class="bar-fill bar-fill-green" style="width:${pct}%"></div></div>
        </div>
      </div>
    `;
  }
  el.innerHTML = html;
}

function renderModels(models) {
  const el = document.getElementById("models-content");
  if (!models.length) { el.innerHTML = '<div class="empty">No models match</div>'; return; }

  let html = "";
  for (const m of models) {
    const caps = (m.capabilities || []).map(c => `<span class="model-tag">${escapeHTML(c)}</span>`).join(" ");
    const ftunes = (m.fine_tunes || []).map(f => `<span class="model-tag">${escapeHTML(f)}</span>`).join(" ");
    const successor = m.successor ? `<span class="model-tag successor">successor: ${escapeHTML(m.successor)}</span>` : "";
    const running = m.running ? '<span class="model-running">running</span>' : "";

    let line1Parts = [];
    if (m.family) line1Parts.push(escapeHTML(m.family));
    if (m.parameter_count) {
      let p = m.parameter_count;
      if (m.active_params) p += ` (${m.active_params} active)`;
      line1Parts.push(p);
    }
    if (m.quantization) line1Parts.push(m.quantization + " quant");
    if (m.context_length) line1Parts.push(formatCtx(m.context_length) + " ctx");

    const line1 = line1Parts.join('<span class="sep">·</span>');
    const desc = m.description ? `<div style="color:var(--text);font-size:12px;margin:4px 0">${escapeHTML(m.description)}</div>` : "";
    const license = m.license ? `<span style="margin-right:8px">${escapeHTML(m.license)}</span>` : "";

    html += `
      <div class="model-card">
        <div class="model-card-header">
          <div><span class="model-name">${escapeHTML(m.name)}</span>${running}</div>
          <span class="model-size">${m.size_human}</span>
        </div>
        <div class="model-details">
          <div>${line1}</div>
          ${desc}
          <div>${license}${caps} ${ftunes} ${successor}</div>
          <div style="margin-top:4px">${timeAgo(m.modified_at)}</div>
        </div>
      </div>
    `;
  }
  el.innerHTML = html;
}

function renderBenchmarks(data) {
  const el = document.getElementById("bench-content");
  if (!data.length) {
    el.innerHTML = '<div class="empty">No benchmarks yet. Run: omon bench &lt;model&gt;</div>';
    return;
  }

  // Show latest benchmark per model
  const latest = {};
  for (const r of data) {
    if (!latest[r.model] || r.timestamp > latest[r.model].timestamp) {
      latest[r.model] = r;
    }
  }

  const runs = Object.values(latest).sort((a, b) => b.avg_gen_tok_s - a.avg_gen_tok_s);
  const maxSpeed = Math.max(...runs.map(r => r.avg_gen_tok_s));

  let html = "";
  for (const r of runs) {
    const pct = maxSpeed > 0 ? (r.avg_gen_tok_s / maxSpeed * 100) : 0;
    const [label, cls] = ratingLabel(r.avg_gen_tok_s);
    const name = r.model.length > 28 ? r.model.slice(0, 27) + "…" : r.model;

    html += `
      <div class="bench-row">
        <div class="bench-model" title="${escapeHTML(r.model)}">${escapeHTML(name)}</div>
        <div class="bench-bar-track"><div class="bench-bar-fill" style="width:${pct}%"></div></div>
        <div class="bench-value">${r.avg_gen_tok_s.toFixed(1)} tok/s</div>
      </div>
      <div class="bench-row" style="border-bottom:1px solid var(--border);padding-top:0">
        <div class="bench-meta">
          <span class="${cls}">${label}</span>
          ${r.memory_human ? " · " + r.memory_human : ""}
          · cold: ${(r.cold_load_ms / 1000).toFixed(1)}s
          · warm: ${r.warm_load_ms.toFixed(0)}ms
        </div>
      </div>
    `;
  }
  el.innerHTML = html;
}

// ─── Filtering ──────────────────────────

function applyFilters() {
  const search = document.getElementById("model-search").value.toLowerCase();
  const cap = document.getElementById("cap-filter").value;

  let filtered = allModels;

  if (search) {
    filtered = filtered.filter(m =>
      m.name.toLowerCase().includes(search) ||
      (m.family || "").toLowerCase().includes(search) ||
      (m.description || "").toLowerCase().includes(search) ||
      (m.publisher || "").toLowerCase().includes(search)
    );
  }

  if (cap) {
    filtered = filtered.filter(m =>
      (m.capabilities || []).some(c => c.toLowerCase() === cap)
    );
  }

  renderModels(filtered);
}

document.getElementById("model-search").addEventListener("input", applyFilters);
document.getElementById("cap-filter").addEventListener("change", applyFilters);

// ─── Data loading ───────────────────────

async function loadStatus() {
  try {
    const data = await fetchJSON("/api/status");
    renderStatus(data);
  } catch (e) {
    document.getElementById("status-content").innerHTML =
      '<div class="empty status-bad">Cannot reach omon server</div>';
  }
}

async function loadPressure() {
  try {
    const data = await fetchJSON("/api/pressure");
    renderMemory(data);
  } catch (e) {}
}

async function loadDisk() {
  try {
    const data = await fetchJSON("/api/disk");
    renderDisk(data);
  } catch (e) {}
}

async function loadModels() {
  try {
    allModels = await fetchJSON("/api/models");
    applyFilters();
  } catch (e) {
    document.getElementById("models-content").innerHTML =
      '<div class="empty">Failed to load models</div>';
  }
}

async function loadRunning() {
  try {
    const data = await fetchJSON("/api/running");
    renderRunning(data);
  } catch (e) {}
}

async function loadBenchmarks() {
  try {
    const data = await fetchJSON("/api/benchmarks");
    renderBenchmarks(data);
  } catch (e) {}
}

// ─── Init ───────────────────────────────

async function init() {
  // Load everything in parallel
  await Promise.all([
    loadStatus(),
    loadPressure(),
    loadDisk(),
    loadModels(),
    loadRunning(),
    loadBenchmarks(),
  ]);

  // Poll running models and pressure every 2s
  setInterval(loadRunning, 2000);
  setInterval(loadPressure, 5000);
}

init();
