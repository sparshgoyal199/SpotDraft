export function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(token) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

export function requireAuth() {
  if (!getToken()) {
    window.location.replace("/");
    return false;
  }
  return true;
}

async function parseError(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail || data);
  } catch {
    return res.statusText || "Request failed";
  }
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.json) {
    headers["Content-Type"] = "application/json";
  }
  if (options.auth !== false && getToken()) {
    headers.Authorization = `Bearer ${getToken()}`;
  }
  const res = await fetch(path, {
    ...options,
    headers,
    body: options.json ? JSON.stringify(options.json) : options.body,
  });
  if (res.status === 401 && options.auth !== false) {
    clearToken();
    window.location.replace("/");
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) throw new Error(await parseError(res));
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const api = {
  signup: (payload) => request("/auth/signup", { method: "POST", json: payload, auth: false }),
  login: (payload) => request("/auth/login", { method: "POST", json: payload, auth: false }),
  listPdfs: () => request("/pdfs"),
  searchPdfs: (q) => request(`/pdfs/search?q=${encodeURIComponent(q)}`),
  uploadPdf: (file) => {
    const body = new FormData();
    body.append("file", file);
    return request("/upload", { method: "POST", body });
  },
  getPdf: (id) => request(`/pdfs/${id}`),
  sharePdf: (id) => request(`/pdfs/${id}/share`, { method: "POST" }),
  getSharedPdf: (token) => request(`/pdfs/shared/${token}`, { auth: false }),
  listComments: (id) => request(`/pdfs/${id}/comments`),
  addComment: (id, content) => request(`/pdfs/${id}/comments`, { method: "POST", json: { content } }),
  listGuestComments: (token) => request(`/shared/${token}/comments`, { auth: false }),
  addGuestComment: (token, content, guest_name) =>
    request(`/shared/${token}/comments`, { method: "POST", json: { content, guest_name }, auth: false }),
  chatHistory: (id) => request(`/pdfs/${id}/chat/history`),
  guestChatHistory: (token, guest_name) =>
    request(`/shared/${token}/chat/history`, { method: "POST", json: { guest_name }, auth: false }),
};

function normalizeDelta(delta) {
  if (delta == null || delta === "done") return "";
  if (typeof delta === "string") return delta;
  if (Array.isArray(delta)) {
    return delta
      .map((block) => (typeof block === "string" ? block : block?.text || ""))
      .join("");
  }
  return String(delta);
}

function parseSseEvents(buffer) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const remainder = parts.pop() || "";
  const events = [];

  for (const part of parts) {
    if (!part.trim()) continue;
    for (const line of part.split("\n")) {
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      try {
        events.push(JSON.parse(payload));
      } catch {
        // Keep partial JSON in buffer for the next read.
        return { events, remainder: part };
      }
    }
  }

  return { events, remainder };
}

export async function streamChat({ path, json, auth = true, onDelta, onChunk }) {
  const headers = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`;

  const res = await fetch(path, { method: "POST", headers, body: JSON.stringify(json) });
  if (!res.ok) throw new Error(await parseError(res));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  const applyDelta = async (delta) => {
    if (!delta) return;
    full += delta;
    onChunk?.(delta, full);
    onDelta?.(full);
    // Yield so the browser can paint between batched SSE events.
    await new Promise((resolve) => requestAnimationFrame(resolve));
  };

  while (true) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });

    const { events, remainder } = parseSseEvents(buffer);
    buffer = remainder;

    for (const data of events) {
      if (data.delta === "done") return full;
      await applyDelta(normalizeDelta(data.delta));
    }

    if (done) break;
  }

  // Flush any trailing event that arrived without a final blank line.
  if (buffer.trim()) {
    const { events } = parseSseEvents(`${buffer}\n\n`);
    for (const data of events) {
      if (data.delta === "done") return full;
      await applyDelta(normalizeDelta(data.delta));
    }
  }

  return full;
}
