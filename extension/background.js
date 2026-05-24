const LEGACY_API_BASE = "http://localhost:8000/api/v1";
const DEFAULT_API_BASE = "http://localhost:8080/api/v1";

const STORAGE_KEYS = {
  apiBase: "vkrApiBase",
  authToken: "vkrAuthToken",
};

function storageGet(keys) {
  return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
}

async function getApiContext() {
  const stored = await storageGet([STORAGE_KEYS.apiBase, STORAGE_KEYS.authToken]);
  const storedApiBase = stored[STORAGE_KEYS.apiBase];
  return {
    apiBase: !storedApiBase || storedApiBase === LEGACY_API_BASE ? DEFAULT_API_BASE : storedApiBase,
    authToken: stored[STORAGE_KEYS.authToken] || null,
  };
}

async function requestJson(path, { method = "GET", payload = null } = {}) {
  const { apiBase, authToken } = await getApiContext();
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const text = await response.text();
  let parsed = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const detail =
      (typeof parsed?.detail === "string" && parsed.detail) ||
      text ||
      `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return parsed;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "VKR_API_REQUEST") {
    return false;
  }

  // Все сетевые запросы к backend выполняем из service worker расширения,
  // чтобы не зависеть от origin текущей веб-страницы и ее CORS-ограничений.
  requestJson(message.path, {
    method: message.method || "GET",
    payload: message.payload || null,
  })
    .then((data) => sendResponse({ ok: true, data }))
    .catch((error) => sendResponse({ ok: false, error: error.message || "Unknown error" }));

  return true;
});
