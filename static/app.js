"use strict";
// Search-first client for the Claude Code history/memory viewer. Vanilla, no deps.

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const state = { projects: [], activeProject: null, engine: "", page: 1 };

// ---------- boot ----------
init();
async function init() {
  const projects = await api("/api/projects");
  state.projects = projects;
  renderRail();
  await renderSources();
  bindSearch();
  bindChips();
  bindDrawer();
  bindSources();
  const eng = (await api("/api/search?q=")).engine;
  $("#engine").textContent = eng;
  $("#q").focus();
}

// ---------- custom sources (generic folders) ----------
async function renderSources() {
  const list = await api("/api/sources");
  const ul = $("#sources");
  ul.innerHTML = "";
  for (const s of list) {
    const li = document.createElement("li");
    li.dataset.dir = s.path;
    li.dataset.path = s.path;
    li.innerHTML =
      `<span class="nm"><span class="dot files"></span>${esc(s.label)}</span>` +
      `<span class="ct"><button class="rm" title="Remove">✕</button></span>`;
    li.querySelector(".nm").onclick = () => {
      const same = state.activeProject === s.path;
      state.activeProject = same ? null : s.path;
      $$("#projects li, #sources li").forEach((x) => x.classList.toggle("on", x.dataset.dir === state.activeProject));
      runSearch();
    };
    li.querySelector(".rm").onclick = async (e) => {
      e.stopPropagation();
      await api(`/api/sources/remove?id=${encodeURIComponent(s.id)}`);
      await renderSources();
      runSearch();
    };
    ul.appendChild(li);
  }
}

function bindSources() {
  $("#add-source").onclick = async () => {
    const path = prompt("Folder path to add as a search source:");
    if (!path) return;
    const label = prompt("Label (optional):", "") || "";
    const res = await api(`/api/sources/add?path=${encodeURIComponent(path)}&label=${encodeURIComponent(label)}`);
    if (res && res.error) { alert("Could not add: " + res.error); return; }
    await renderSources();
  };
}

// ---------- project rail (filter) ----------
function renderRail() {
  const ul = $("#projects");
  ul.innerHTML = "";
  for (const p of state.projects) {
    const li = document.createElement("li");
    li.dataset.dir = p.realPath;                 // canonical filter key = real working dir
    li.dataset.path = p.realPath;
    const dots = Object.keys(p.providers || {}).map((pr) => `<span class="dot ${pr}"></span>`).join("");
    li.innerHTML =
      `<span class="nm">${dots}${esc(shortName(p.realPath))}</span>` +
      `<span class="ct">${p.hasMemory ? '<span class="mem">◆</span> ' : ""}${p.sessionCount}</span>`;
    li.onclick = () => {
      const same = state.activeProject === p.realPath;
      state.activeProject = same ? null : p.realPath;
      $$("#projects li").forEach((x) => x.classList.toggle("on", x.dataset.dir === state.activeProject));
      runSearch();
    };
    ul.appendChild(li);
  }
}
function shortName(path) {
  const parts = (path || "").split("/").filter(Boolean);
  return parts.slice(-2).join("/") || path;
}

// ---------- search ----------
function bindSearch() {
  let t;
  const go = () => { clearTimeout(t); t = setTimeout(() => runSearch(), 400); };
  $("#q").addEventListener("input", go);
  $("#since").addEventListener("change", () => runSearch());
  $("#until").addEventListener("change", () => runSearch());
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#q").focus(); $("#q").select(); }
    if (e.key === "Escape") closeDrawer();
  });
}
function bindChips() {
  // generic on/off chips (source, role, whole-word)
  $$(".chip").filter((c) => c.id !== "matchmode").forEach((c) =>
    c.addEventListener("click", () => { c.classList.toggle("on"); runSearch(); }));
  // AND/OR is a two-state toggle, not on/off
  const mm = $("#matchmode");
  mm.addEventListener("click", () => {
    const or = mm.dataset.mode === "or";
    mm.dataset.mode = or ? "and" : "or";
    mm.textContent = or ? "All words" : "Any word";
    runSearch();
  });
}
function chipVals(group) {
  return $$(`.chipset[data-group="${group}"] .chip.on`).map((c) => c.dataset.val);
}

async function runSearch(page = 1) {
  const q = $("#q").value.trim();
  const res = $("#results");
  if (!q) { res.innerHTML = `<div class="empty">Type to search across every session and memory file.</div>`; return; }
  state.page = page;

  const params = new URLSearchParams();
  params.set("q", q);
  params.set("page", page);
  params.set("per", "50");
  if (state.activeProject) params.set("project", state.activeProject);
  const prov = chipVals("provider"); if (prov.length) params.set("provider", prov.join(","));
  const src = chipVals("source"); if (src.length) params.set("source", src.join(","));
  const role = chipVals("role"); if (role.length) params.set("role", role.join(","));
  const wholeWord = $("#wholeword").classList.contains("on");
  if (!wholeWord) params.set("word", "0");
  const mode = $("#matchmode").dataset.mode;      // "and" | "or"
  params.set("mode", mode);
  if ($("#hidesingle").classList.contains("on")) params.set("min", "2");
  if ($("#since").value) params.set("since", $("#since").value);
  if ($("#until").value) params.set("until", $("#until").value);

  res.innerHTML = `<div class="empty">Searching…</div>`;
  const data = await api("/api/search?" + params.toString());
  renderResults(data, q, wholeWord);
}

// One card per session/memory file (grouped). Keywords highlighted in every snippet.
function renderResults(data, q, wholeWord) {
  const res = $("#results");
  const items = data.results || [];
  const kws = data.keywords || [q];
  if (!items.length) { res.innerHTML = `<div class="empty">No matches for “${esc(q)}”.</div>`; return; }
  const noun = data.mode === "or" ? "any" : "all";
  const total = data.total != null ? data.total : items.length;
  const page = data.page || 1, pages = data.pages || 1;
  const label = `${total} file${total === 1 ? "" : "s"} · ${esc(kws.join(" " + noun + " "))}${data.engine === "python" ? " · python fallback" : ""}`;
  const pager = pages > 1
    ? `<span class="pager">
         <button class="pg" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""}>← Prev</button>
         <span class="pgnum">${page} / ${pages}</span>
         <button class="pg" data-page="${page + 1}" ${page >= pages ? "disabled" : ""}>Next →</button>
       </span>`
    : "";
  let html = `<div class="count"><span>${label}</span>${pager}</div>`;
  for (const r of items) {
    const proj = esc(shortName(r.project));
    const when = r.ts ? new Date(r.ts).toLocaleString() : "";
    const title = esc(r.title || r.file || (r.sessionId || "").slice(0, 8));
    const kwChips = (r.keywords || []).map((k) => `<span class="kw">${esc(k)}</span>`).join("");
    const snips = (r.snippets || []).map((s) =>
      `<div class="snip">${highlight(s.text, kws, wholeWord)}</div>`).join("");
    html += `<div class="result" data-json='${esc(JSON.stringify(r))}'>
      <div class="meta">
        <span class="tag ${r.provider}">${r.provider}</span>
        <span class="rtitle">${title}</span>
        <span>· ${proj}</span>${when ? `<span>· ${when}</span>` : ""}
        <span class="mcount">${r.count} match${r.count === 1 ? "" : "es"}</span>
        <span class="src">${r.source}</span>
        ${kwChips}
        ${r.path ? `<button class="reveal" data-path="${esc(r.path)}" title="Reveal in Finder / Explorer">Reveal ↗</button>` : ""}
      </div>
      ${snips}
    </div>`;
  }
  res.innerHTML = html;
  $$(".pg", res).forEach((b) => b.onclick = () => { runSearch(+b.dataset.page); res.scrollTop = 0; });
  $$(".result", res).forEach((el) => el.onclick = () => openHit(JSON.parse(el.dataset.json)));
  $$(".reveal", res).forEach((b) => b.onclick = async (e) => {
    e.stopPropagation();                       // don't also open the preview
    b.textContent = "Revealing…";
    await api(`/api/reveal?path=${encodeURIComponent(b.dataset.path)}`);
    b.textContent = "Reveal ↗";
  });
}

// highlight every keyword (terms may be a string or array)
function highlight(text, terms, wholeWord) {
  let e = esc(text);
  const list = (Array.isArray(terms) ? terms : [terms]).filter(Boolean);
  for (const t of list) {
    const body = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = new RegExp(wholeWord ? `(\\b${body}\\b)` : `(${body})`, "ig");
    e = e.replace(re, "<mark>$1</mark>");
  }
  return e;
}

// ---------- drawer: transcript or memory ----------
async function openHit(r) {
  if (r.provider === "files") return openFile(r.locator, r.keywords);
  if (r.source === "memory") return openMemory(r.locator, r.file);
  const firstSnip = (r.snippets && r.snippets[0] && r.snippets[0].text) || "";
  return openSession(r.provider, r.locator, r.sessionId, r.project, firstSnip);
}

async function openFile(path, keywords) {
  showDrawer(path.split("/").slice(-1)[0]);
  const data = await api(`/api/file?path=${encodeURIComponent(path)}`);
  const body = $("#drawer-body");
  if (!data || !data.text) { body.innerHTML = `<div class="empty">Cannot preview this file.</div>`; return; }
  body.innerHTML = `<div class="filepath">${esc(data.path)}${data.truncated ? " · truncated" : ""}</div>` +
    `<pre class="filebody">${highlight(data.text, keywords || [], false)}</pre>`;
  const mark = body.querySelector("mark");
  if (mark) mark.scrollIntoView({ block: "center" });
}

async function openSession(provider, locator, id, displayPath, hitSnippet) {
  showDrawer(`${provider} · ${shortName(displayPath)} · ${id.slice(0, 8)}`);
  const msgs = await api(`/api/session?provider=${encodeURIComponent(provider)}&project=${encodeURIComponent(locator)}&id=${encodeURIComponent(id)}`);
  const needle = (hitSnippet || "").replace(/…/g, "").trim().slice(0, 40).toLowerCase();
  const body = $("#drawer-body");
  body.innerHTML = "";
  let firstHit = null;
  for (const m of msgs) {
    const isHit = needle && (m.text || "").toLowerCase().includes(needle);
    const div = document.createElement("div");
    div.className = `msg ${m.role}` + (isHit ? " hit" : "");
    let inner = `<div class="who">${m.role}${m.ts ? " · " + new Date(m.ts).toLocaleTimeString() : ""}</div>`;
    if (m.text) inner += `<div class="bubble md">${md(m.text)}</div>`;
    for (const c of m.toolCalls || []) inner += `<details class="tool"><summary>🔧 ${esc(c.name)}</summary><pre>${esc(c.input)}</pre></details>`;
    for (const tr of m.toolResults || []) inner += `<details class="tool"><summary>↩ result</summary><pre>${esc(tr)}</pre></details>`;
    div.innerHTML = inner;
    body.appendChild(div);
    if (isHit && !firstHit) firstHit = div;
  }
  if (firstHit) firstHit.scrollIntoView({ block: "center" });
}

async function openMemory(dir, file) {
  showDrawer(`memory · ${file || ""}`);
  const mem = await api(`/api/memory?project=${encodeURIComponent(dir)}`);
  const body = $("#drawer-body");
  let html = "";
  if (mem.indexMd) html += `<div class="mem-idx md">${md(mem.indexMd)}</div>`;
  for (const f of mem.files || []) {
    const focus = f.name + ".md" === file;
    html += `<div class="mem-card" ${focus ? 'style="border-color:var(--mark)"' : ""} id="mc-${esc(f.name)}">
      <h4>${esc(f.title)}${f.type ? `<span class="type-badge">${esc(f.type)}</span>` : ""}</h4>
      ${f.description ? `<div class="desc">${esc(f.description)}</div>` : ""}
      <div class="body md">${md(f.body)}</div></div>`;
  }
  body.innerHTML = html || `<div class="empty">No memory files.</div>`;
  const target = file && $("#mc-" + CSS.escape(file.replace(/\.md$/, "")));
  if (target) target.scrollIntoView({ block: "center" });
}

// tiny markdown: headings, bold, inline code, links, lists
function md(src) {
  let h = esc(src || "");
  h = h.replace(/^### (.*)$/gm, "<h4>$1</h4>")
       .replace(/^## (.*)$/gm, "<h3>$1</h3>")
       .replace(/^# (.*)$/gm, "<h2>$1</h2>")
       .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
       .replace(/`([^`]+)`/g, "<code>$1</code>")
       .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
       .replace(/\[\[([^\]]+)\]\]/g, "<code>$1</code>")
       .replace(/^\s*[-*] (.*)$/gm, "• $1");
  return h.replace(/\n/g, "<br>");
}

// ---------- drawer plumbing ----------
function bindDrawer() {
  $("#drawer-close").onclick = closeDrawer;
  $("#scrim").onclick = closeDrawer;
}
function showDrawer(title) {
  $("#drawer-title").textContent = title;
  $("#drawer-body").innerHTML = `<div class="empty">Loading…</div>`;
  $("#drawer").classList.remove("hidden");
  $("#scrim").classList.remove("hidden");
}
function closeDrawer() {
  $("#drawer").classList.add("hidden");
  $("#scrim").classList.add("hidden");
}

async function api(url) {
  const r = await fetch(url);
  if (!r.ok) return url.includes("/api/search") ? { results: [], engine: state.engine } : [];
  return r.json();
}
