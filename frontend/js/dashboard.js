import { api, requireAuth, clearToken } from "./api.js";

if (!requireAuth()) throw new Error("redirect");

const grid = document.getElementById("grid");
const empty = document.getElementById("empty");
const statusEl = document.getElementById("status");
const searchInput = document.getElementById("search");
const fileInput = document.getElementById("file-input");
const uploadZone = document.getElementById("upload-zone");
const docCountEl = document.getElementById("doc-count");
const resultsNote = document.getElementById("results-note");

let allPdfs = [];
let searchTimer;

function formatDate(value) {
  if (!value) return "Recently uploaded";
  const date = new Date(value);
  const now = new Date();
  const diffMs = now - date;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return `Today · ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function setStatus(message, type = "info") {
  if (!message) {
    statusEl.classList.add("hidden");
    statusEl.textContent = "";
    return;
  }
  statusEl.textContent = message;
  statusEl.className = `status-banner status-${type}`;
  statusEl.classList.remove("hidden");
}

function getInitials(filename) {
  const base = filename.replace(/\.pdf$/i, "").trim();
  const parts = base.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase() || "PD";
}

function renderPdfs(pdfs, note = "") {
  grid.innerHTML = "";
  docCountEl.textContent = String(pdfs.length);
  resultsNote.textContent = note;
  empty.classList.toggle("hidden", pdfs.length > 0);
  grid.classList.toggle("hidden", pdfs.length === 0);

  for (const pdf of pdfs) {
    const card = document.createElement("article");
    card.className = "pdf-card";
    card.innerHTML = `
      <div class="pdf-card-top">
        <div class="pdf-thumb">${getInitials(pdf.filename)}</div>
        <div class="pdf-card-head">
          <h3></h3>
          <span class="pdf-badge">PDF</span>
        </div>
      </div>
      <p class="pdf-summary"></p>
      <div class="pdf-card-foot">
        <span class="meta"></span>
        <span class="pdf-open">Open →</span>
      </div>
    `;
    card.querySelector("h3").textContent = pdf.filename;
    card.querySelector(".pdf-summary").textContent =
      pdf.summary || "Summary will appear here once processing finishes.";
    card.querySelector(".meta").textContent = formatDate(pdf.upload_date);
    card.addEventListener("click", () => {
      window.location.href = `/viewer/${pdf.id}`;
    });
    grid.appendChild(card);
  }
}

async function loadAll() {
  setStatus("");
  allPdfs = await api.listPdfs() || [];
  renderPdfs(allPdfs);
}

async function runSearch() {
  const q = searchInput.value.trim();
  try {
    if (!q) {
      await loadAll();
      return;
    }
    const pdfs = await api.searchPdfs(q);
    renderPdfs(pdfs || [], `${(pdfs || []).length} result${(pdfs || []).length === 1 ? "" : "s"} for “${q}”`);
  } catch (err) {
    setStatus(err.message, "error");
  }
}

async function handleUpload(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    setStatus("Only PDF files are allowed.", "error");
    return;
  }

  uploadZone.classList.add("is-uploading");
  setStatus(`Uploading “${file.name}” — parsing, summarizing, and indexing…`, "loading");

  try {
    const uploaded = await api.uploadPdf(file);
    setStatus(`“${uploaded.filename}” is ready.`, "success");
    searchInput.value = "";
    await loadAll();
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    uploadZone.classList.remove("is-uploading");
  }
}

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 280);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    searchInput.value = "";
    loadAll();
  }
});

document.getElementById("upload-btn").addEventListener("click", () => fileInput.click());
document.getElementById("empty-upload-btn").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileInput.value = "";
  handleUpload(file);
});

uploadZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadZone.classList.add("is-dragover");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("is-dragover");
});

uploadZone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadZone.classList.remove("is-dragover");
  handleUpload(event.dataTransfer.files[0]);
});

document.getElementById("logout-btn").addEventListener("click", () => {
  clearToken();
  window.location.replace("/");
});

loadAll().catch((err) => setStatus(err.message, "error"));
