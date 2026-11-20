/* SmartCare frontend - vanilla JS. Login page first; the website opens only after login. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let currentUser = null, bookingDoctor = null, selectedSlot = null, doctorsLoaded = false;

/* ---------------- helpers ---------------- */
function countUp(el, to) {
  to = Number(to) || 0; const t0 = performance.now();
  (function step(t) { const p = Math.min(1, (t - t0) / 600); el.textContent = Math.round(to * p); if (p < 1) requestAnimationFrame(step); })(t0);
}
async function api(url, opts = {}) {
  const res = await fetch(url, opts.body && !(opts.body instanceof FormData)
    ? { ...opts, headers: { "Content-Type": "application/json" }, body: JSON.stringify(opts.body) } : opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || "Something went wrong"), { status: res.status });
  return data;
}
function toast(msg, bad = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "show" + (bad ? " bad" : "");
  setTimeout(() => (t.className = ""), 3200);
}
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

/* ---------------- screens: login <-> website ---------------- */
function showAuthScreen() {
  currentUser = null; chatReady = false; chatHistory = []; $("#chatBox").innerHTML = "";
  hide($("#appShell")); show($("#authScreen")); setAuthMode("login");
}
function showApp() {
  hide($("#authScreen")); show($("#appShell"));
  $("#userArea").innerHTML = `<span>Hi, <b>${esc(currentUser.name)}</b></span><button class="btn small outline" id="logoutBtn">Logout</button>`;
  $("#logoutBtn").onclick = async () => { await api("/api/logout", { method: "POST" }); showAuthScreen(); toast("Logged out"); };
  $("#homeGreeting").textContent = `Welcome, ${currentUser.name}`;
  if (!doctorsLoaded) { initDoctors(); doctorsLoaded = true; }
  goto("home");
}

/* ---------------- navigation ---------------- */
function goto(page) {
  $$(".page").forEach(hide); show($("#page-" + page));
  $$("#menu a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  if (page === "history") loadHistory();
  if (page === "dashboard") loadDashboard();
  if (page === "assistant") initChat();
  window.scrollTo(0, 0);
}
$$("#menu a").forEach((a) => a.addEventListener("click", () => goto(a.dataset.page)));
$$("[data-go]").forEach((el) => el.addEventListener("click", () => goto(el.dataset.go)));

/* ---------------- login / register ---------------- */
let authMode = "login";
function setAuthMode(mode) {
  authMode = mode; const login = mode === "login";
  $("#tabLogin").classList.toggle("active", login); $("#tabRegister").classList.toggle("active", !login);
  $("#regOnly").classList.toggle("hidden", login);
  $("#authTitle").textContent = login ? "Welcome back" : "Create your account";
  $("#authSub").textContent = login ? "Please log in to continue" : "Register to start booking appointments";
  $("#authSubmit").textContent = login ? "Login" : "Create account";
  $("#authSwitch").innerHTML = login ? `New here? <a id="swLink">Create an account</a>` : `Already registered? <a id="swLink">Login</a>`;
  $("#swLink").onclick = () => setAuthMode(login ? "register" : "login");
  $("#authError").textContent = "";
}
$("#tabLogin").onclick = () => setAuthMode("login");
$("#tabRegister").onclick = () => setAuthMode("register");
$("#aPhone").addEventListener("input", (e) => (e.target.value = e.target.value.replace(/\D/g, "").slice(0, 10)));   // digits only, max 10
$("#authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { email: $("#aEmail").value, password: $("#aPass").value };
  if (authMode === "register") Object.assign(body, { name: $("#aName").value, phone: $("#aPhone").value });
  if (authMode === "register" && !/^\d{10}$/.test($("#aPhone").value.trim())) {
    $("#authError").textContent = "Phone number must be exactly 10 digits."; return;
  }
  const btn = $("#authSubmit"); btn.disabled = true;
  try {
    const r = await api(authMode === "login" ? "/api/login" : "/api/register", { method: "POST", body });
    currentUser = r.user; $("#authForm").reset();
    if (currentUser.role === "admin") { location.href = "/admin"; return; }   // admin -> Admin Portal
    showApp(); toast(`Welcome, ${currentUser.name}!`);
  } catch (err) { $("#authError").textContent = err.message; }
  btn.disabled = false;
});
$$("[data-close]").forEach((b) => (b.onclick = () => hide(b.closest(".modal"))));

/* ---------------- doctors ---------------- */
const hue = (t) => [...t].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
function doctorCard(d) {
  const ini = d.name.replace(/^Dr\.?\s*/i, "").split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return `<div class="card doc">
    <div class="doc-head"><div class="avatar" style="background:hsl(${hue(d.specialization)} 62% 48%)">${esc(ini)}</div>
      <div><h3>${esc(d.name)}</h3><div class="spec">${esc(d.specialization)}</div></div></div>
    <div class="meta">${d.experience_years} yrs experience &middot; Fee: &#8377;${d.fee}</div>
    <div class="days">${d.available_days.map((x) => `<span class="day">${x}</span>`).join("")}</div>
    <div class="meta">Timing: ${esc(d.timing)}</div>
    <div><button class="btn small" data-book='${d.id}'>Book Appointment</button></div>
  </div>`;
}
function bindBookButtons(container, doctors) {
  $$("[data-book]", container).forEach((b) => (b.onclick = () => openBooking(doctors.find((x) => x.id == b.dataset.book))));
}
async function loadDoctors() {
  const q = $("#docSearch").value, spec = $("#docSpec").value;
  const list = await api(`/api/doctors?q=${encodeURIComponent(q)}&specialization=${encodeURIComponent(spec)}`);
  $("#doctorList").innerHTML = list.length ? list.map(doctorCard).join("") : `<p class="muted">No doctors found.</p>`;
  bindBookButtons($("#doctorList"), list);
}
async function initDoctors() {
  const specs = await api("/api/specializations");
  $("#docSpec").innerHTML = `<option value="">All specializations</option>` + specs.map((s) => `<option>${esc(s)}</option>`).join("");
  countUp($("#statSpecs"), specs.length);
  $("#docSpec").onchange = loadDoctors;
  let timer; $("#docSearch").oninput = () => { clearTimeout(timer); timer = setTimeout(loadDoctors, 250); };
  countUp($("#statDocs"), (await api("/api/doctors")).length);
  loadDoctors();
}

/* ---------------- booking ---------------- */
function openBooking(doc) {
  bookingDoctor = doc; selectedSlot = null;
  $("#bookTitle").textContent = "Book with " + doc.name;
  $("#bookInfo").textContent = `${doc.specialization} - Available: ${doc.available_days.join(", ")} (${doc.timing})`;
  const localISO = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  $("#bookDate").min = localISO(new Date()); $("#bookDate").max = localISO(new Date(Date.now() + 60 * 864e5)); $("#bookDate").value = "";
  $("#slotBox").innerHTML = `<p class="muted">Select a date to see available time slots.</p>`;
  $("#bookReason").value = ""; $("#bookError").textContent = ""; $("#bookConfirm").disabled = true;
  show($("#bookModal"));
}
$("#bookDate").onchange = async () => {
  selectedSlot = null; $("#bookConfirm").disabled = true; $("#bookError").textContent = "";
  if (!$("#bookDate").value) return;
  try {
    const r = await api(`/api/doctors/${bookingDoctor.id}/slots?date=${$("#bookDate").value}`);
    $("#slotBox").innerHTML = r.slots.length
      ? `<div class="slots">${r.slots.map((s) => `<div class="slot" data-t="${s}">${s}</div>`).join("")}</div>`
      : `<p class="error">No slots available on this date. Doctor is available on: ${r.available_days.join(", ")}.</p>`;
    $$(".slot").forEach((el) => (el.onclick = () => {
      $$(".slot").forEach((x) => x.classList.remove("sel")); el.classList.add("sel");
      selectedSlot = el.dataset.t; $("#bookConfirm").disabled = false;
    }));
  } catch (e) { $("#bookError").textContent = e.message; }
};
$("#bookConfirm").onclick = async () => {
  try {
    const r = await api("/api/appointments", { method: "POST", body: {
      doctor_id: bookingDoctor.id, date: $("#bookDate").value, time: selectedSlot, reason: $("#bookReason").value } });
    hide($("#bookModal")); toast(r.message); goto("history");
  } catch (e) {
    if (e.status === 401) { hide($("#bookModal")); showAuthScreen(); toast("Session expired. Please log in again.", true); return; }
    $("#bookError").textContent = e.message; $("#bookDate").onchange();
  }
};

/* ---------------- appointment history ---------------- */
async function loadHistory() {
  const box = $("#historyList"); box.innerHTML = `<p class="loading">Loading...</p>`;
  const rows = await api("/api/appointments");
  if (!rows.length) { box.innerHTML = `<div class="card">No appointments yet. Book your first one from the Doctors page.</div>`; return; }
  box.innerHTML = `<table><thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Specialization</th><th>Reason</th><th>Status</th><th></th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td>${esc(r.appt_date)}</td><td>${esc(r.appt_time)}</td><td>${esc(r.doctor_name)}</td><td>${esc(r.specialization)}</td>
      <td>${esc(r.reason) || "-"}</td><td><span class="badge ${r.status}">${r.status}</span></td>
      <td>${r.status === "Booked" ? `<button class="btn small danger" data-cancel="${r.id}">Cancel</button>` : ""}</td></tr>`).join("") + `</tbody></table>`;
  $$("[data-cancel]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Cancel this appointment?")) return;
    try { toast((await api(`/api/appointments/${b.dataset.cancel}/cancel`, { method: "POST" })).message); loadHistory(); }
    catch (e) { toast(e.message, true); }
  }));
}

/* ---------------- patient dashboard ---------------- */
async function loadDashboard() {
  try {
    const d = await api("/api/dashboard");
    countUp($("#dTotal"), d.total); countUp($("#dUpcoming"), d.upcoming);
    countUp($("#dDone"), d.completed); countUp($("#dCancelled"), d.cancelled);
    const n = d.next;
    $("#dNext").innerHTML = n
      ? `<div class="card next-card"><div class="muted">Next appointment</div><h3>${esc(n.doctor_name)} <span class="spec">&middot; ${esc(n.specialization)}</span></h3>
         <div>${esc(n.appt_date)} at <b>${esc(n.appt_time)}</b>${n.reason ? ` &middot; ${esc(n.reason)}` : ""}</div></div>
         ${d.upcoming_list.length > 1 ? `<h4>Upcoming</h4><table><thead><tr><th>Date</th><th>Time</th><th>Doctor</th><th>Specialization</th></tr></thead><tbody>` +
           d.upcoming_list.map((r) => `<tr><td>${esc(r.appt_date)}</td><td>${esc(r.appt_time)}</td><td>${esc(r.doctor_name)}</td><td>${esc(r.specialization)}</td></tr>`).join("") + `</tbody></table>` : ""}`
      : `<div class="card">You have no upcoming appointments. Book one from the Doctors page.</div>`;
  } catch (e) { toast(e.message, true); }
}

/* ---------------- AI Health Assistant (chat) ---------------- */
let chatHistory = [], chatReady = false;
function addMsg(role, text, extra = "") {
  const el = document.createElement("div"); el.className = "msg " + role;
  el.innerHTML = esc(text) + extra; $("#chatBox").appendChild(el); $("#chatBox").scrollTop = 1e9; return el;
}
function fmtReply(t) {   // turns the plain-text answer into neat lines, bullets and bold section labels
  return t.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    const e = esc(l);
    if (l.startsWith("\u2022 ") || /^\d+\.\s/.test(l)) return `<span class="bul">${e}</span>`;
    if (/^[^\u2022].{0,45}:$/.test(l)) return `<span class="lbl">${e}</span>`;
    return `<span class="ln">${e}</span>`;
  }).join("");
}
function initChat() {
  if (chatReady) return; chatReady = true;
  addMsg("bot", `Hi ${currentUser.name.split(" ")[0]}! I'm your AI Health Assistant. Tell me your symptoms or ask a health question, and I'll guide you to the right doctor.`);
}
async function sendChat(text) {
  text = (text || $("#chatInput").value).trim(); if (!text) return;
  $("#chatInput").value = ""; addMsg("user", text);
  const wait = addMsg("bot", ""); wait.innerHTML = `<span class="typing"><i></i><i></i><i></i></span>`; $("#chatSend").disabled = true;
  try {
    const r = await api("/api/assistant", { method: "POST", body: { message: text, history: chatHistory } });
    wait.innerHTML = fmtReply(r.reply) + `<small>${r.source === "llm" ? "AI: " + esc(r.provider) : "Offline mode"} &middot; general guidance, not a diagnosis</small>`;
    $("#chatBox").scrollTop = 1e9;
    chatHistory.push({ role: "user", content: text }, { role: "assistant", content: r.reply }); chatHistory = chatHistory.slice(-8);
    if (r.recommended) {
      const rec = document.createElement("div"); rec.className = "rec";
      rec.innerHTML = `Book a doctor - suggested specialist: <b>${esc(r.recommended.specialization)}</b> ${r.recommended.probability ? `(${(r.recommended.probability * 100).toFixed(0)}% match)` : ""}
        <div class="recdocs">${r.recommended.doctors.map((d) => `<span>${esc(d.name)}</span><button class="btn small" data-book="${d.id}">Book</button>`).join("")}</div>`;
      $("#chatBox").appendChild(rec); bindBookButtons(rec, r.recommended.doctors); $("#chatBox").scrollTop = 1e9;
    }
  } catch (e) { wait.textContent = e.message; }
  $("#chatSend").disabled = false; $("#chatInput").focus();
}
$("#chatSend").onclick = () => sendChat();
$("#chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
$$("#chatExamples .chip").forEach((c) => (c.onclick = () => sendChat(c.textContent)));

/* ---------------- ML: symptom checker ---------------- */
$$("#examples .chip").forEach((c) => (c.onclick = () => ($("#symptomInput").value = c.textContent)));
$("#predictBtn").onclick = async () => {
  const out = $("#predictResult"), btn = $("#predictBtn");
  out.innerHTML = `<p class="loading">Analysing symptoms...</p>`; btn.disabled = true;
  try {
    const r = await api("/api/predict", { method: "POST", body: { symptoms: $("#symptomInput").value } });
    out.innerHTML = `<div class="card">
      <div class="result-head"><div><div class="muted">Recommended specialization</div><div class="big">${esc(r.recommended)}</div></div>
      <span class="badge ai">Logistic Regression</span></div>
      ${r.low_confidence ? `<div class="warn">The model is not very sure. If symptoms persist, consider a General Physician first.</div>` : ""}
      <h4>Model confidence</h4>
      ${r.predictions.map((p) => `<div class="pred"><span>${esc(p.specialization)}</span><b>${(p.probability * 100).toFixed(1)}%</b></div>
        <div class="bar"><div style="width:${p.probability * 100}%"></div></div>`).join("")}
    </div>
    <h3>${esc(r.recommended)}s available</h3><div class="grid" id="predDocs">${r.doctors.map(doctorCard).join("")}</div>`;
    bindBookButtons($("#predDocs"), r.doctors);
  } catch (e) { out.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  btn.disabled = false;
};

/* ---------------- GenAI: report explainer ---------------- */
$("#reportFile").onchange = () => ($("#fileName").textContent = $("#reportFile").files[0]?.name || "");
$("#summarizeBtn").onclick = async () => {
  const out = $("#reportResult"), btn = $("#summarizeBtn"), file = $("#reportFile").files[0];
  out.innerHTML = `<p class="loading">Generating simple explanation...</p>`; btn.disabled = true;
  try {
    let r;
    if (file) { const fd = new FormData(); fd.append("file", file); r = await api("/api/summarize", { method: "POST", body: fd }); }
    else r = await api("/api/summarize", { method: "POST", body: { text: $("#reportText").value } });
    const ai = r.source === "llm";
    out.innerHTML = `<div class="card"><div class="result-head"><h3 style="margin:0">In simple words</h3>
      <span class="badge ${ai ? "ai" : "off"}">${ai ? `Generated by ${esc(r.provider)} (${esc(r.model)})` : "Offline mode"}</span></div>
      <p class="summary">${esc(r.summary)}</p>${r.warning ? `<div class="warn">${esc(r.warning)}</div>` : ""}</div>`;
  } catch (e) { out.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
  btn.disabled = false;
};

/* ---------------- start: logged-in users go straight in, everyone else sees the login page ---------------- */
(async function init() {
  try { currentUser = (await api("/api/me")).user; } catch { currentUser = null; }
  if (currentUser && currentUser.role === "admin") { location.replace("/admin"); return; }   // admins never see the patient website
  currentUser ? showApp() : showAuthScreen();
})();
