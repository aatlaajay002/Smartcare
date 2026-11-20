/* SmartCare Admin Portal. Every call below is checked on the server (HTTP 403 for non-admins). */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TITLES = { overview: "Overview", appointments: "Appointments", doctors: "Doctors", patients: "Patients", activity: "Activity Log" };
const ACTION = { login: "Login", register: "New registration", booking: "Appointment booked", cancel: "Appointment cancelled",
  symptom_check: "Symptom check (ML)", report_summary: "Report explained (GenAI)", assistant_chat: "AI assistant chat",
  admin_cancel: "Admin: cancelled appointment", admin_add_doctor: "Admin: added doctor", admin_edit_doctor: "Admin: edited doctor",
  admin_delete_doctor: "Admin: deleted doctor", admin_delete_user: "Admin: deleted patient" };
let section = "overview", cache = { appts: [], doctors: [], users: [] }, editingId = null;

async function api(url, opts = {}) {
  const res = await fetch(url, opts.body ? { ...opts, headers: { "Content-Type": "application/json" }, body: JSON.stringify(opts.body) } : opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 || res.status === 403) { location.href = "/"; throw new Error("Not allowed"); }
  if (!res.ok) throw new Error(data.error || "Something went wrong");
  return data;
}
function toast(msg, bad = false) { const t = $("#toast"); t.textContent = msg; t.className = "show" + (bad ? " bad" : ""); setTimeout(() => (t.className = ""), 3000); }
const table = (cols, rows, empty) => rows.length
  ? `<div class="tbl-wrap"><table><thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`
  : `<div class="card empty">${empty}</div>`;
const dayLabel = (d) => new Date(d + "T00:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric" });

/* ---------- navigation ---------- */
function go(sec) {
  section = sec; $("#secTitle").textContent = TITLES[sec];
  $$(".sec").forEach((e) => e.classList.add("hidden")); $("#sec-" + sec).classList.remove("hidden");
  $$("#sideNav a").forEach((a) => a.classList.toggle("active", a.dataset.sec === sec)); load();
}
$$("#sideNav a").forEach((a) => (a.onclick = () => go(a.dataset.sec)));
$("#refreshBtn").onclick = () => { load(); toast("Refreshed"); };
$("#logoutBtn").onclick = async () => { await fetch("/api/logout", { method: "POST" }); location.href = "/"; };
$$("[data-close]").forEach((b) => (b.onclick = () => b.closest(".modal").classList.add("hidden")));
const load = () => ({ overview: loadOverview, appointments: loadAppts, doctors: loadDoctors, patients: loadUsers, activity: loadActivity }[section])();

/* ---------- overview ---------- */
async function loadOverview() {
  const [s, act] = await Promise.all([api("/api/admin/stats"), api("/api/admin/activity?limit=6")]);
  $("#sysInfo").textContent = `DB: ${s.database} | LLM: ${s.llm_provider}`;
  const card = (n, l, c = "") => `<div class="stat ${c}"><b>${n}</b><span>${l}</span></div>`;
  $("#statCards").innerHTML = card(s.patients, "Registered patients") + card(s.doctors, "Doctors") + card(s.appointments, "Total appointments") +
    card(s.today, "Appointments today", "acc") + card(s.cancelled, "Cancelled", "bad");
  const max = Math.max(1, ...s.next7.map((d) => d.count));
  $("#chart7").innerHTML = s.next7.map((d) => `<div class="vbar"><b>${d.count}</b><i style="height:${(d.count / max) * 120}px"></i><span>${dayLabel(d.date)}</span></div>`).join("");
  const mx = Math.max(1, ...s.by_specialization.map((x) => x.count));
  $("#chartSpec").innerHTML = s.by_specialization.length ? s.by_specialization.map((x) =>
    `<div class="hrow"><span>${esc(x.specialization)}</span><div class="track"><div style="width:${(x.count / mx) * 100}%"></div></div><b>${x.count}</b></div>`).join("") : `<div class="empty">No bookings yet.</div>`;
  $("#aiUsage").innerHTML = `<div><b>${s.ai_usage.symptom_check}</b><span>Symptom checks (ML)</span></div><div><b>${s.ai_usage.assistant_chat}</b><span>Assistant chats</span></div><div><b>${s.ai_usage.report_summary}</b><span>Reports explained</span></div>`;
  $("#recentAct").innerHTML = act.length ? act.map((a) => `<div class="act"><span><b>${esc(a.user_name || "Visitor")}</b> - ${esc(ACTION[a.action] || a.action)}</span><small>${esc((a.created_at || "").slice(5, 16))}</small></div>`).join("") : `<div class="empty">No activity yet.</div>`;
}

/* ---------- appointments ---------- */
async function loadAppts() { cache.appts = await api("/api/admin/appointments"); renderAppts(); }
function renderAppts() {
  const q = $("#apSearch").value.toLowerCase(), st = $("#apStatus").value;
  const rows = cache.appts.filter((a) => (!st || a.status === st) && (`${a.patient} ${a.doctor_name} ${a.specialization}`).toLowerCase().includes(q));
  $("#apTable").innerHTML = table(["#", "Patient", "Doctor", "Specialization", "Date", "Time", "Reason", "Status", ""], rows.map((a) =>
    `<tr><td>${a.id}</td><td>${esc(a.patient)}<br><small class="muted">${esc(a.patient_email)}</small></td><td>${esc(a.doctor_name)}</td><td>${esc(a.specialization)}</td>
     <td>${esc(a.appt_date)}</td><td>${esc(a.appt_time)}</td><td>${esc(a.reason) || "-"}</td><td><span class="badge ${a.status}">${a.status}</span></td>
     <td>${a.status === "Booked" ? `<button class="btn small danger" data-cancel="${a.id}">Cancel</button>` : ""}</td></tr>`), "No appointments found.");
  $$("[data-cancel]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Cancel this appointment?")) return;
    try { toast((await api(`/api/admin/appointments/${b.dataset.cancel}/cancel`, { method: "POST" })).message); loadAppts(); } catch (e) { toast(e.message, true); }
  }));
}
$("#apSearch").oninput = renderAppts; $("#apStatus").onchange = renderAppts;

/* ---------- doctors ---------- */
async function loadDoctors() { cache.doctors = await api("/api/admin/doctors"); renderDoctors(); }
function renderDoctors() {
  const q = $("#dcSearch").value.toLowerCase();
  const rows = cache.doctors.filter((d) => `${d.name} ${d.specialization}`.toLowerCase().includes(q));
  $("#dcTable").innerHTML = table(["Name", "Specialization", "Exp.", "Fee", "Days", "Timing", "Booked", ""], rows.map((d) =>
    `<tr><td>${esc(d.name)}</td><td>${esc(d.specialization)}</td><td>${d.experience_years} yrs</td><td>&#8377;${d.fee}</td><td>${d.available_days.join(", ")}</td><td>${esc(d.timing)}</td><td>${d.booked}</td>
     <td style="white-space:nowrap"><button class="btn small outline icon-btn" data-edit="${d.id}">Edit</button><button class="btn small danger" data-del="${d.id}">Delete</button></td></tr>`), "No doctors found.");
  $$("[data-edit]").forEach((b) => (b.onclick = () => openDoctor(cache.doctors.find((d) => d.id == b.dataset.edit))));
  $$("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Delete this doctor?")) return;
    try { toast((await api(`/api/admin/doctors/${b.dataset.del}`, { method: "DELETE" })).message); loadDoctors(); } catch (e) { toast(e.message, true); }
  }));
}
$("#dcSearch").oninput = renderDoctors;
$("#fDays").innerHTML = DAYS.map((d) => `<label><input type="checkbox" value="${d}">${d}</label>`).join("");
function openDoctor(d) {
  editingId = d ? d.id : null; $("#docModalTitle").textContent = d ? "Edit doctor" : "Add doctor"; $("#docError").textContent = "";
  $("#specList").innerHTML = [...new Set(cache.doctors.map((x) => x.specialization))].map((s) => `<option value="${esc(s)}">`).join("");
  $("#fName").value = d?.name || ""; $("#fSpec").value = d?.specialization || ""; $("#fExp").value = d?.experience_years ?? ""; $("#fFee").value = d?.fee ?? "";
  $("#fStart").value = d?.start_time || "09:00"; $("#fEnd").value = d?.end_time || "13:00";
  $$("#fDays input").forEach((c) => (c.checked = d ? d.available_days.includes(c.value) : ["Mon", "Tue", "Wed", "Thu", "Fri"].includes(c.value)));
  $("#docModal").classList.remove("hidden");
}
$("#addDoctor").onclick = () => openDoctor(null);
$("#docSave").onclick = async () => {
  const body = { name: $("#fName").value, specialization: $("#fSpec").value, experience_years: $("#fExp").value, fee: $("#fFee").value,
    available_days: $$("#fDays input:checked").map((c) => c.value), start_time: $("#fStart").value, end_time: $("#fEnd").value };
  try {
    const r = await api(editingId ? `/api/admin/doctors/${editingId}` : "/api/admin/doctors", { method: editingId ? "PUT" : "POST", body });
    $("#docModal").classList.add("hidden"); toast(r.message); loadDoctors();
  } catch (e) { $("#docError").textContent = e.message; }
};

/* ---------- patients ---------- */
async function loadUsers() { cache.users = await api("/api/admin/users"); renderUsers(); }
function renderUsers() {
  const q = $("#ptSearch").value.toLowerCase();
  const rows = cache.users.filter((u) => `${u.name} ${u.email}`.toLowerCase().includes(q));
  $("#ptTable").innerHTML = table(["ID", "Name", "Email", "Phone", "Joined", "Appointments", ""], rows.map((u) =>
    `<tr><td>${u.id}</td><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${esc(u.phone) || "-"}</td><td>${esc((u.created_at || "").slice(0, 16))}</td><td>${u.appointments}</td>
     <td><button class="btn small danger" data-deluser="${u.id}">Delete</button></td></tr>`), "No patients registered yet.");
  $$("[data-deluser]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Delete this patient and all their appointments?")) return;
    try { toast((await api(`/api/admin/users/${b.dataset.deluser}`, { method: "DELETE" })).message); loadUsers(); } catch (e) { toast(e.message, true); }
  }));
}
$("#ptSearch").oninput = renderUsers;

/* ---------- activity ---------- */
async function loadActivity() {
  const rows = await api("/api/admin/activity?limit=100");
  $("#acTable").innerHTML = table(["Time", "User", "Action", "Details"], rows.map((a) =>
    `<tr><td>${esc((a.created_at || "").slice(0, 19))}</td><td>${esc(a.user_name || "Visitor")}</td><td>${esc(ACTION[a.action] || a.action)}</td><td>${esc(a.detail) || "-"}</td></tr>`), "No activity yet.");
}

/* ---------- start: verify admin, then show portal ---------- */
(async function init() {
  try {
    const { user } = await (await fetch("/api/me")).json();
    if (!user || user.role !== "admin") { location.href = "/"; return; }
    $("#adminName").textContent = `${user.name} (${user.email})`;
    $("#gate").classList.add("hidden"); $("#adm").classList.remove("hidden"); load();
    setInterval(() => { if (section === "overview" || section === "activity") load(); }, 15000);   // live monitoring
  } catch { location.href = "/"; }
})();
