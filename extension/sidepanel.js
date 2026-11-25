const API = "http://localhost:8000";

const $messages = document.getElementById("messages");
const $status = document.getElementById("status");
const $input = document.getElementById("input");
const $send = document.getElementById("send");
const $chips = document.getElementById("chips");

let currentVideoId = null;
let ready = false;
let busy = false;
let history = [];

function getVideoId(url) {
  try {
    const u = new URL(url);
    if (!/(^|\.)youtube\.com$/.test(u.hostname)) return null;
    if (u.pathname === "/watch") return u.searchParams.get("v");
    const m = u.pathname.match(/^\/(shorts|live)\/([\w-]{11})/);
    return m ? m[2] : null;
  } catch { return null; }
}

function setStatus(text, isError = false) {
  $status.textContent = text;
  $status.classList.toggle("error", isError);
}

function setReady(isReady) {
  ready = isReady;
  $input.disabled = !isReady || busy;
  $send.disabled = !isReady || busy;
  $chips.hidden = !isReady;
}

function addMessage(text, kind) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.textContent = text;
  $messages.appendChild(el);
  $messages.scrollTop = $messages.scrollHeight;
  return el;
}

async function post(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Server error (${res.status})`);
  return data;
}

async function loadVideo(videoId) {
  currentVideoId = videoId;
  $messages.innerHTML = "";
  history = [];
  setReady(false);

  if (!videoId) {
    setStatus("Open a YouTube video to start.");
    return;
  }

  setStatus("Reading the transcript and indexing… (first time takes a few seconds)");
  try {
    await post("/index", { video_id: videoId });
    if (currentVideoId !== videoId) return; // user switched videos meanwhile
    setStatus("Ready. Ask anything about this video.");
    setReady(true);
    $input.focus();
  } catch (err) {
    if (currentVideoId !== videoId) return;
    const offline = err instanceof TypeError;
    setStatus(
      offline ? "Can't reach the backend. Is it running on localhost:8000?" : err.message,
      true
    );
  }
}

async function ask(question) {
  question = question.trim();
  if (!question || !ready || busy) return;
  const videoId = currentVideoId;

  busy = true; setReady(true);
  addMessage(question, "user");
  $input.value = ""; $input.style.height = "auto";
  const typing = addMessage("Thinking…", "bot typing");

  try {
    const { answer } = await post("/ask", { video_id: videoId, question, history: history.slice(-8) });
    if (videoId !== currentVideoId) return;
    history.push({ role: "user", text: question }, { role: "assistant", text: answer });
    typing.remove();
    addMessage(answer, "bot");
  } catch (err) {
    typing.remove();
    addMessage(err.message || "Something went wrong.", "bot error");
  } finally {
    busy = false; setReady(ready);
    if (ready) $input.focus();
  }
}

async function syncWithActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const id = tab ? getVideoId(tab.url || "") : null;
  if (id !== currentVideoId) loadVideo(id);
}

// YouTube is a single-page app, so watch for URL changes and tab switches.
chrome.tabs.onActivated.addListener(syncWithActiveTab);
chrome.tabs.onUpdated.addListener((_id, info) => {
  if (info.url || info.status === "complete") syncWithActiveTab();
});

$send.addEventListener("click", () => ask($input.value));
$input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask($input.value); }
});
$input.addEventListener("input", () => {
  $input.style.height = "auto";
  $input.style.height = Math.min($input.scrollHeight, 120) + "px";
});
$chips.addEventListener("click", (e) => {
  const q = e.target.dataset?.q;
  if (q) ask(q);
});

syncWithActiveTab();
