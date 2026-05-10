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
  email: document.getElementById("email"),
  fullName: document.getElementById("fullName"),
  password: document.getElementById("password"),
  registerBtn: document.getElementById("registerBtn"),
  loginBtn: document.getElementById("loginBtn"),
  logoutBtn: document.getElementById("logoutBtn"),
  userEmailValue: document.getElementById("userEmailValue"),
  userIdValue: document.getElementById("userIdValue"),
  output: document.getElementById("output"),
};

let currentToken = null;
let currentApiBase = DEFAULT_API_BASE;
const EXTENSION_VERSION = chrome.runtime.getManifest().version;

function setOutput(data) {
  elements.output.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

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
  if (!tab.id) {
    return;
  }

  if (!tab.url || !/^https?:/i.test(tab.url)) {
    setOutput("Studying активирован, но текущая вкладка не поддерживает инъекцию скрипта.");
    return;
  }

  await chrome.scripting.insertCSS({
    target: { tabId: tab.id },
    files: ["content.css"],
  });
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"],
  });
}

async function ensureActiveTabUsesCurrentExtensionVersion() {
  const tab = await getActiveTab();
  if (!tab.id || !tab.url || !/^https?:/i.test(tab.url)) {
    return false;
  }

  const stored = await storageGet([STORAGE_KEYS.activeContentVersion]);
  if (stored[STORAGE_KEYS.activeContentVersion] === EXTENSION_VERSION) {
    return false;
  }

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
  const parsed = text ? (() => {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  })() : null;

  if (!response.ok) {
    const detail =
      (typeof parsed?.detail === "string" && parsed.detail) ||
      text ||
      `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return parsed;
}

function updateStudyingUi(enabled) {
  elements.studyingEnabled.checked = enabled;
  elements.studyingBadge.textContent = enabled ? "Активно" : "Выключено";
  elements.studyingBadge.className = `badge ${enabled ? "badge-on" : "badge-off"}`;
}

function updateAuthUi({ loggedIn, email = "-", userId = "-" }) {
  elements.authBadge.textContent = loggedIn ? "Выполнена" : "Не выполнена";
  elements.authBadge.className = `badge ${loggedIn ? "badge-ok" : "badge-idle"}`;
  elements.userEmailValue.textContent = email || "-";
  elements.userIdValue.textContent = userId ? String(userId) : "-";
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
  updateAuthUi({
    loggedIn: true,
    email: identity.email,
    userId: identity.user_id,
  });
  return identity;
}

async function loadState() {
  const stored = await storageGet(Object.values(STORAGE_KEYS));
  currentApiBase = stored[STORAGE_KEYS.apiBase] || DEFAULT_API_BASE;
  currentToken = stored[STORAGE_KEYS.authToken] || null;

  elements.email.value = stored[STORAGE_KEYS.email] || "";
  updateStudyingUi(Boolean(stored[STORAGE_KEYS.studyingEnabled]));

  if (!currentToken) {
    updateAuthUi({ loggedIn: false });
    setOutput("Войдите и включите режим Studying.");
    return;
  }

  try {
    await syncIdentity();
    setOutput("Расширение готово. Выделите слово на странице.");
  } catch (error) {
    currentToken = null;
    await storageRemove([STORAGE_KEYS.authToken, STORAGE_KEYS.userId]);
    updateAuthUi({ loggedIn: false });
    setOutput(`Сессия сброшена: ${error.message}`);
  }
}

async function toggleStudying() {
  const enabled = elements.studyingEnabled.checked;
  await storageSet({ [STORAGE_KEYS.studyingEnabled]: enabled });
  updateStudyingUi(enabled);
  if (enabled) {
    try {
      const reloaded = await ensureActiveTabUsesCurrentExtensionVersion();
      await ensureContentScriptInjected();
      setOutput(
        reloaded
          ? "Studying включен. Активная вкладка была перезагружена после обновления расширения. Подождите загрузку страницы и повторите выделение."
          : "Studying включен. Теперь можно выделять текст на странице.",
      );
    } catch (error) {
      setOutput(`Studying включен, но не удалось подготовить вкладку: ${error.message}`);
    }
    return;
  }
  setOutput("Studying выключен.");
}

async function login() {
  const email = elements.email.value.trim();
  const password = elements.password.value;

  if (!email) {
    setOutput("Укажите email.");
    return;
  }
  if (!password || password.length < 8) {
    setOutput("Пароль должен содержать минимум 8 символов.");
    return;
  }

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
    updateAuthUi({
      loggedIn: true,
      email: auth.user.email,
      userId: auth.user_id,
    });
    elements.password.value = "";
    await ensureActiveTabUsesCurrentExtensionVersion().catch(() => false);
    await ensureContentScriptInjected().catch(() => {});
    setOutput(`Вход выполнен. Пользователь #${auth.user_id}.`);
  } catch (error) {
    updateAuthUi({ loggedIn: false });
    setOutput(`Ошибка входа: ${error.message}`);
  }
}

async function register() {
  const email = elements.email.value.trim();
  const fullName = elements.fullName.value.trim();
  const password = elements.password.value;

  if (!email) {
    setOutput("Укажите email.");
    return;
  }
  if (!password || password.length < 8) {
    setOutput("Пароль должен содержать минимум 8 символов.");
    return;
  }

  try {
    const auth = await requestJson("/auth/register", {
      method: "POST",
      payload: {
        email,
        password,
        full_name: fullName || null,
        cefr_level: "A1",
      },
      token: null,
    });
    currentToken = auth.access_token;
    await storageSet({
      [STORAGE_KEYS.authToken]: auth.access_token,
      [STORAGE_KEYS.email]: auth.user.email,
      [STORAGE_KEYS.userId]: auth.user_id,
    });
    updateAuthUi({
      loggedIn: true,
      email: auth.user.email,
      userId: auth.user_id,
    });
    elements.password.value = "";
    await ensureActiveTabUsesCurrentExtensionVersion().catch(() => false);
    await ensureContentScriptInjected().catch(() => {});
    setOutput(`Аккаунт создан. Пользователь #${auth.user_id}.`);
  } catch (error) {
    updateAuthUi({ loggedIn: false });
    setOutput(`Ошибка регистрации: ${error.message}`);
  }
}

async function logout() {
  currentToken = null;
  elements.password.value = "";
  await storageRemove([STORAGE_KEYS.authToken, STORAGE_KEYS.userId]);
  updateAuthUi({ loggedIn: false });
  setOutput("Сессия очищена.");
}

elements.studyingEnabled.addEventListener("change", toggleStudying);
elements.registerBtn.addEventListener("click", register);
elements.loginBtn.addEventListener("click", login);
elements.logoutBtn.addEventListener("click", logout);

loadState();
