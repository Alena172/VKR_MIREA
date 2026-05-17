const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

const STORAGE_KEYS = {
  apiBase: "vkrApiBase",
  authToken: "vkrAuthToken",
  email: "vkrAuthEmail",
  userId: "vkrUserId",
  studyingEnabled: "vkrStudyingEnabled",
  activeContentVersion: "vkrActiveContentVersion",
};

const elements = {
  studyingEnabled: document.getElementById("studyingEnabled"),
  studyingBadge: document.getElementById("studyingBadge"),
  authBadge: document.getElementById("authBadge"),
  authForm: document.getElementById("authForm"),
  authSession: document.getElementById("authSession"),
  // Вход
  loginForm: document.getElementById("loginForm"),
  email: document.getElementById("email"),
  password: document.getElementById("password"),
  loginBtn: document.getElementById("loginBtn"),
  // Регистрация
  registerForm: document.getElementById("registerForm"),
  regEmail: document.getElementById("regEmail"),
  fullName: document.getElementById("fullName"),
  regPassword: document.getElementById("regPassword"),
  registerBtn: document.getElementById("registerBtn"),
  // Табы
  tabLoginBtn: document.getElementById("tabLoginBtn"),
  tabRegisterBtn: document.getElementById("tabRegisterBtn"),
  // Сессия
  logoutBtn: document.getElementById("logoutBtn"),
  userEmailValue: document.getElementById("userEmailValue"),
};

let currentToken = null;
let currentApiBase = DEFAULT_API_BASE;
const EXTENSION_VERSION = chrome.runtime.getManifest().version;

function storageGet(keys) {
  return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
}

function storageSet(data) {
  return new Promise((resolve) => chrome.storage.local.set(data, resolve));
}

function storageRemove(keys) {
  return new Promise((resolve) => chrome.storage.local.remove(keys, resolve));
}

function getActiveTab() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      const tab = tabs?.[0];
      if (!tab?.id) {
        reject(new Error("Активная вкладка не найдена."));
        return;
      }
      resolve(tab);
    });
  });
}

async function ensureContentScriptInjected() {
  const tab = await getActiveTab();
  if (!tab.id) return;
  if (!tab.url || !/^https?:/i.test(tab.url)) return;

  await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ["content.css"] });
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
}

async function ensureActiveTabUsesCurrentExtensionVersion() {
  const tab = await getActiveTab();
  if (!tab.id || !tab.url || !/^https?:/i.test(tab.url)) return false;

  const stored = await storageGet([STORAGE_KEYS.activeContentVersion]);
  if (stored[STORAGE_KEYS.activeContentVersion] === EXTENSION_VERSION) return false;

  await chrome.tabs.reload(tab.id);
  await storageSet({ [STORAGE_KEYS.activeContentVersion]: EXTENSION_VERSION });
  return true;
}

async function requestJson(path, { method = "GET", payload = null, token = currentToken } = {}) {
  const response = await fetch(`${currentApiBase}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const text = await response.text();
  const parsed = text ? (() => { try { return JSON.parse(text); } catch { return null; } })() : null;

  if (!response.ok) {
    const detail = (typeof parsed?.detail === "string" && parsed.detail) || text || `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return parsed;
}

function updateStudyingUi(enabled) {
  elements.studyingEnabled.checked = enabled;
  elements.studyingBadge.textContent = enabled ? "Активно" : "Выключено";
  elements.studyingBadge.className = `badge ${enabled ? "badge-on" : "badge-off"}`;
}

function updateAuthUi({ loggedIn, email = "-" }) {
  elements.authBadge.textContent = loggedIn ? "Выполнена" : "Не выполнена";
  elements.authBadge.className = `badge ${loggedIn ? "badge-ok" : "badge-idle"}`;
  elements.authForm.hidden = loggedIn;
  elements.authSession.classList.toggle("auth-session-hidden", !loggedIn);
  elements.userEmailValue.textContent = email || "-";

  if (!loggedIn) {
    elements.password.value = "";
    elements.regPassword.value = "";
    elements.fullName.value = "";
  }
}

async function syncIdentity() {
  if (!currentToken) {
    updateAuthUi({ loggedIn: false });
    return null;
  }

  const identity = await requestJson("/auth/me");
  await storageSet({
    [STORAGE_KEYS.userId]: identity.user_id,
    [STORAGE_KEYS.email]: identity.email,
  });
  updateAuthUi({ loggedIn: true, email: identity.email });
  return identity;
}

async function loadState() {
  const stored = await storageGet(Object.values(STORAGE_KEYS));
  currentApiBase = stored[STORAGE_KEYS.apiBase] || DEFAULT_API_BASE;
  currentToken = stored[STORAGE_KEYS.authToken] || null;

  const savedEmail = stored[STORAGE_KEYS.email] || "";
  elements.email.value = savedEmail;
  elements.regEmail.value = savedEmail;
  updateStudyingUi(Boolean(stored[STORAGE_KEYS.studyingEnabled]));

  if (!currentToken) {
    updateAuthUi({ loggedIn: false });
    return;
  }

  try {
    await syncIdentity();
  } catch {
    currentToken = null;
    await storageRemove([STORAGE_KEYS.authToken, STORAGE_KEYS.userId]);
    updateAuthUi({ loggedIn: false });
  }
}

async function toggleStudying() {
  const enabled = elements.studyingEnabled.checked;
  await storageSet({ [STORAGE_KEYS.studyingEnabled]: enabled });
  updateStudyingUi(enabled);
  if (enabled) {
    await ensureActiveTabUsesCurrentExtensionVersion().catch(() => false);
    await ensureContentScriptInjected().catch(() => {});
  }
}

async function login() {
  const email = elements.email.value.trim();
  const password = elements.password.value;

  if (!email || !password || password.length < 8) return;

  try {
    const auth = await requestJson("/auth/login", {
      method: "POST",
      payload: { email, password },
      token: null,
    });
    currentToken = auth.access_token;
    await storageSet({
      [STORAGE_KEYS.authToken]: auth.access_token,
      [STORAGE_KEYS.email]: auth.user.email,
      [STORAGE_KEYS.userId]: auth.user_id,
    });
    updateAuthUi({ loggedIn: true, email: auth.user.email });
    elements.password.value = "";
    await ensureActiveTabUsesCurrentExtensionVersion().catch(() => false);
    await ensureContentScriptInjected().catch(() => {});
  } catch {
    updateAuthUi({ loggedIn: false });
  }
}

async function register() {
  const email = elements.regEmail.value.trim();
  const fullName = elements.fullName.value.trim();
  const password = elements.regPassword.value;

  if (!email || !password || password.length < 8) return;

  try {
    const auth = await requestJson("/auth/register", {
      method: "POST",
      payload: { email, password, full_name: fullName || null, cefr_level: "A1" },
      token: null,
    });
    currentToken = auth.access_token;
    await storageSet({
      [STORAGE_KEYS.authToken]: auth.access_token,
      [STORAGE_KEYS.email]: auth.user.email,
      [STORAGE_KEYS.userId]: auth.user_id,
    });
    updateAuthUi({ loggedIn: true, email: auth.user.email });
    elements.regPassword.value = "";
    await ensureActiveTabUsesCurrentExtensionVersion().catch(() => false);
    await ensureContentScriptInjected().catch(() => {});
  } catch {
    updateAuthUi({ loggedIn: false });
  }
}

async function logout() {
  currentToken = null;
  await storageRemove([STORAGE_KEYS.authToken, STORAGE_KEYS.userId]);
  updateAuthUi({ loggedIn: false });
}

function switchTab(tab) {
  const isLogin = tab === "login";
  elements.loginForm.classList.toggle("form-hidden", !isLogin);
  elements.registerForm.classList.toggle("form-hidden", isLogin);
  elements.tabLoginBtn.classList.toggle("tab-btn-active", isLogin);
  elements.tabRegisterBtn.classList.toggle("tab-btn-active", !isLogin);
}

document.getElementById("openAppLink").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: "http://localhost:5173/" });
});

elements.tabLoginBtn.addEventListener("click", () => switchTab("login"));
elements.tabRegisterBtn.addEventListener("click", () => switchTab("register"));
elements.studyingEnabled.addEventListener("change", toggleStudying);
elements.loginBtn.addEventListener("click", login);
elements.registerBtn.addEventListener("click", register);
elements.logoutBtn.addEventListener("click", logout);

loadState();
