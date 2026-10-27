const api = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
};
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));
const today = new Date().toISOString().slice(0, 10);
const showError = (error) => alert(error.message);

async function loadSubjects() {
  const subjects = await api("/subjects").catch((error) => { showError(error); return []; });
  document.querySelectorAll("[data-subject-options]").forEach((select) => { select.innerHTML = '<option value="">Choose a subject</option>' + subjects.map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join(""); });
  const list = document.querySelector("#subject-list");
  if (list) list.innerHTML = subjects.length ? subjects.map((s) => `<article class="item-card"><span class="color-dot" style="background:${escapeHtml(s.color)}"></span><strong>${escapeHtml(s.name)}</strong><button class="icon-button" data-delete-subject="${s.id}">Delete</button></article>`).join("") : '<p class="empty">No subjects yet. Add your first one above.</p>';
}
async function loadCollection(path, target, render) { const data = await api(path); const element = document.querySelector(target); if (element) element.innerHTML = data.length ? data.map(render).join("") : '<p class="empty">Nothing here yet.</p>'; }
async function loadDashboard() {
  const data = await api("/dashboard"), main = document.querySelector("main");
  if (!main) return;
  main.innerHTML = `<section class="page-heading"><span class="eyebrow">YOUR OVERVIEW</span><h1>Good study starts with a clear plan.</h1><p>Track your momentum and choose your next focused session.</p></section><section class="stats-grid"><article class="stat-card"><span>Completed hours</span><strong>${Number(data.summary.completed_hours || 0).toFixed(1)}</strong><small>This week</small></article><article class="stat-card"><span>Pending sessions</span><strong>${data.summary.pending_sessions || 0}</strong><small>Ready to schedule</small></article><article class="stat-card"><span>Goal hours left</span><strong>${Number(data.summary.pending_goal_hours || 0).toFixed(1)}</strong><small>For today</small></article></section><section class="panel"><div class="panel-heading"><div><span class="eyebrow">SUBJECT PROGRESS</span><h2>Where your time is going</h2></div><a class="button primary" href="/schedule.html">Plan a session</a></div><div class="progress-list">${data.subject_progress.length ? data.subject_progress.map((s) => `<div class="progress-row"><div><strong>${escapeHtml(s.name)}</strong><span>${Number(s.study_hours || 0).toFixed(1)} hours completed</span></div><div class="progress-track"><i style="width:${Math.min(Number(s.study_hours || 0) * 10, 100)}%;background:${escapeHtml(s.color)}"></i></div></div>`).join("") : '<p class="empty">Add a subject to start tracking progress.</p>'}</div></section>`;
}
async function loadProgress() {
  const data = await api("/dashboard");
  const list = document.querySelector("#progress-list");
  if (!list) return;
  list.innerHTML = data.subject_progress.length ? data.subject_progress.map((s) => `<article class="item-card"><div><strong>${escapeHtml(s.name)}</strong><span>${Number(s.study_hours || 0).toFixed(1)} hours completed</span></div><div class="progress-track"><i style="width:${Math.min(Number(s.study_hours || 0) * 10, 100)}%;background:${escapeHtml(s.color)}"></i></div></article>`).join("") : '<p class="empty">Complete a scheduled session to see progress here.</p>';
}
document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll("input[type=date]").forEach((input) => { if (!input.value) input.value = today; });
  document.querySelectorAll("[data-logout]").forEach((b) => b.addEventListener("click", async () => { await api("/logout", { method: "POST" }); location.href = "/"; }));
  try { if (location.pathname.endsWith("progress.html") || location.pathname === "/progress") await loadProgress(); } catch (error) { if (error.message.includes("Authentication")) location.href = "/login.html"; else showError(error); }
  try { if (location.pathname.endsWith("dashboard.html") || location.pathname === "/dashboard") await loadDashboard(); if (document.querySelector("[data-subject-options], #subject-list")) await loadSubjects(); if (document.querySelector("#goal-list")) await loadCollection("/goals", "#goal-list", (x) => `<article class="item-card"><div><strong>${escapeHtml(x.title)}</strong><span>${x.goal_date} · ${x.completed_hours}/${x.target_hours} hours</span></div><button class="icon-button" data-delete-goal="${x.id}">Delete</button></article>`); if (document.querySelector("#session-list")) await loadCollection("/sessions", "#session-list", (x) => `<article class="item-card"><div><strong>${escapeHtml(x.title)}</strong><span>${x.session_date} at ${x.start_time} · ${x.duration_hours} hours</span></div><button class="icon-button" data-delete-session="${x.id}">${x.completed ? "Completed" : "Mark done"}</button></article>`); } catch (error) { if (error.message.includes("Authentication")) location.href = "/login.html"; else showError(error); }
});
document.addEventListener("submit", async (event) => { const form = event.target; if (!(form instanceof HTMLFormElement)) return; event.preventDefault(); const data = Object.fromEntries(new FormData(form)); try { if (form.id === "subject-form") await api("/subjects", { method: "POST", body: JSON.stringify(data) }); if (form.id === "goal-form") await api("/goals", { method: "POST", body: JSON.stringify(data) }); if (form.id === "session-form") await api("/sessions", { method: "POST", body: JSON.stringify(data) }); if (form.id === "login-form") { await api("/login", { method: "POST", body: JSON.stringify(data) }); location.href = "/dashboard.html"; return; } if (form.id === "register-form") { await api("/register", { method: "POST", body: JSON.stringify(data) }); location.href = "/dashboard.html"; return; } form.reset(); await loadSubjects(); if (form.id === "goal-form" || form.id === "session-form") location.reload(); } catch (error) { showError(error); } });
document.addEventListener("click", async (event) => { const button = event.target.closest("button"); if (!button) return; try { if (button.dataset.deleteSubject) await api(`/subjects/${button.dataset.deleteSubject}`, { method: "DELETE" }); if (button.dataset.deleteGoal) await api(`/goals/${button.dataset.deleteGoal}`, { method: "DELETE" }); if (button.dataset.deleteSession) await api(`/sessions/${button.dataset.deleteSession}`, { method: "PUT", body: JSON.stringify({ completed: true }) }); if (button.dataset.deleteSubject || button.dataset.deleteGoal || button.dataset.deleteSession) location.reload(); } catch (error) { showError(error); } });
