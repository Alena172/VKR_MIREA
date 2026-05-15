if (!globalThis.__VKR_STUDYING_CONTENT_LOADED__) {
globalThis.__VKR_STUDYING_CONTENT_LOADED__ = true;

const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

const STORAGE_KEYS = {
  apiBase: "vkrApiBase",
  authToken: "vkrAuthToken",
  studyingEnabled: "vkrStudyingEnabled",
};

const MAX_SELECTION_LENGTH = 120;
const MIN_SELECTION_LENGTH = 2;

let studyingEnabled = false;
let currentApiBase = DEFAULT_API_BASE;
let currentToken = null;
let activeBubble = null;
let activeSelectionSignature = "";
let pendingTranslateAbortController = null;

function storageGet(keys) {
  return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
}

function isEnglishSelection(text) {
  const normalized = text.trim();
  if (!normalized) {
    return false;
  }
  if (normalized.length < MIN_SELECTION_LENGTH || normalized.length > MAX_SELECTION_LENGTH) {
    return false;
  }
  return /^[A-Za-z][A-Za-z\s'’-]*[A-Za-z]$/.test(normalized);
}

function normalizeSpaces(text) {
  return (text || "").replace(/\s+/g, " ").trim();
}

function isBlockContextElement(element) {
  if (!(element instanceof Element)) {
    return false;
  }

  const blockTags = new Set([
    "P",
    "DIV",
    "LI",
    "ARTICLE",
    "SECTION",
    "MAIN",
    "ASIDE",
    "TD",
    "TH",
    "BLOCKQUOTE",
    "FIGCAPTION",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
  ]);

  if (blockTags.has(element.tagName)) {
    return true;
  }

  const display = window.getComputedStyle(element).display;
  return display === "block" || display === "list-item" || display === "table-cell";
}

function getSelectionContainer(range) {
  const baseNode = range?.commonAncestorContainer;
  let current =
    baseNode?.nodeType === Node.ELEMENT_NODE ? baseNode : baseNode?.parentElement || null;

  // Поднимаемся к ближайшему блочному контейнеру, чтобы контекст не обрывался
  // на одном текстовом узле внутри `span`, `a` или другого inline-элемента.
  while (current && current !== document.body) {
    if (isBlockContextElement(current)) {
      return current;
    }
    current = current.parentElement;
  }

  return current || document.body;
}

function getSelectionContainerText(range) {
  const container = getSelectionContainer(range);
  // `innerText` лучше отражает видимый пользователю текст и склеивает inline-узлы
  // в цельную строку; `textContent` оставляем как запасной вариант.
  const rawText = container?.innerText || container?.textContent || "";
  return normalizeSpaces(rawText);
}

function extractSentenceFromText(fullText, selectedText) {
  if (!fullText || !selectedText) {
    return "";
  }

  const normalizedFull = normalizeSpaces(fullText);
  const normalizedSelected = normalizeSpaces(selectedText);
  const idx = normalizedFull.toLowerCase().indexOf(normalizedSelected.toLowerCase());

  if (idx < 0) {
    return normalizedFull.slice(0, 500);
  }

  // Ищем естественные границы предложения вокруг выделения.
  const separators = [".", "!", "?", "\n"];
  let start = 0;
  let end = normalizedFull.length;

  for (const separator of separators) {
    const leftIndex = normalizedFull.lastIndexOf(separator, idx);
    if (leftIndex >= 0) {
      start = Math.max(start, leftIndex + 1);
    }
  }

  let rightCandidates = separators
    .map((separator) => normalizedFull.indexOf(separator, idx + normalizedSelected.length))
    .filter((value) => value >= 0);

  if (rightCandidates.length > 0) {
    end = Math.min(...rightCandidates) + 1;
  } else {
    end = Math.min(normalizedFull.length, idx + 260);
  }

  return normalizedFull.slice(start, end).trim();
}

function getSelectionContext() {
  const selection = window.getSelection();
  const selectedText = normalizeSpaces(selection?.toString() || "");

  if (!selectedText) {
    return null;
  }

  const range = selection && selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
  if (!range) {
    return null;
  }

  const rect = range.getBoundingClientRect();
  const containerText = getSelectionContainerText(range);
  const sourceSentence = extractSentenceFromText(containerText, selectedText);
  // Сигнатура помогает не запрашивать перевод повторно для того же выделения,
  // если пользователь случайно кликает рядом с уже открытым пузырем.
  const signature = `${selectedText}::${sourceSentence}::${Math.round(rect.left)}::${Math.round(rect.top)}`;

  return {
    selectedText,
    sourceSentence,
    sourceUrl: window.location.href,
    pageTitle: document.title,
    rect,
    signature,
  };
}

function closeActiveBubble() {
  if (pendingTranslateAbortController) {
    pendingTranslateAbortController.abort();
    pendingTranslateAbortController = null;
  }
  if (activeBubble) {
    activeBubble.remove();
    activeBubble = null;
  }
  activeSelectionSignature = "";
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (typeof text === "string") {
    element.textContent = text;
  }
  return element;
}

function positionBubble(bubble, rect) {
  const bubbleWidth = 340;
  const scrollX = window.scrollX;
  const scrollY = window.scrollY;
  const preferredTop = scrollY + rect.bottom + 10;
  const preferredLeft = scrollX + rect.left + rect.width / 2 - bubbleWidth / 2;
  const minLeft = scrollX + 12;
  const maxLeft = scrollX + window.innerWidth - bubbleWidth - 12;
  const left = Math.max(minLeft, Math.min(preferredLeft, maxLeft));

  bubble.style.top = `${preferredTop}px`;
  bubble.style.left = `${left}px`;
}

function setBubbleStatus(bubble, message, kind = "muted") {
  const status = bubble.querySelector("[data-role='status']");
  status.textContent = message;
  status.className = `vkr-study-bubble__status vkr-study-bubble__status--${kind}`;
}

function setBubbleTranslation(bubble, translation, note) {
  bubble.querySelector("[data-role='translation']").textContent = translation;
  bubble.querySelector("[data-role='note']").textContent = note || "";
}

async function requestBackend(path, { method = "GET", payload = null, signal } = {}) {
  if (signal?.aborted) {
    throw new DOMException("The operation was aborted.", "AbortError");
  }

  return await new Promise((resolve, reject) => {
    const onAbort = () => {
      reject(new DOMException("The operation was aborted.", "AbortError"));
    };

    signal?.addEventListener("abort", onAbort, { once: true });

    chrome.runtime.sendMessage(
      {
        type: "VKR_API_REQUEST",
        path,
        method,
        payload,
      },
      (response) => {
        signal?.removeEventListener("abort", onAbort);

        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response?.ok) {
          reject(new Error(response?.error || "Backend request failed"));
          return;
        }
        resolve(response.data);
      },
    );
  });
}

function renderBubble(selectionContext) {
  closeActiveBubble();

  const bubble = createElement("div", "vkr-study-bubble");
  bubble.setAttribute("data-vkr-bubble", "true");

  const header = createElement("div", "vkr-study-bubble__header");
  const titleWrap = createElement("div");
  titleWrap.append(
    createElement("p", "vkr-study-bubble__title", "Перевод выделения"),
    createElement("p", "vkr-study-bubble__selection", selectionContext.selectedText),
  );
  header.append(titleWrap);

  const body = createElement("div", "vkr-study-bubble__body");
  const translationBox = createElement("div", "vkr-study-bubble__translation");
  const translationLabel = createElement("p", "vkr-study-bubble__translation-label", "Перевод");
  const translationValue = createElement("p", "vkr-study-bubble__translation-value", "Загрузка...");
  translationValue.setAttribute("data-role", "translation");
  const note = createElement("p", "vkr-study-bubble__note", "Отправляем выделение на backend...");
  note.setAttribute("data-role", "note");
  translationBox.append(translationLabel, translationValue, note);

  const actions = createElement("div", "vkr-study-bubble__actions");
  const addButton = createElement("button", "vkr-study-bubble__button vkr-study-bubble__button--primary", "Добавить в словарь");
  addButton.type = "button";
  addButton.disabled = true;
  actions.append(addButton);

  const status = createElement("p", "vkr-study-bubble__status vkr-study-bubble__status--muted", "");
  status.setAttribute("data-role", "status");

  body.append(translationBox, actions, status);
  bubble.append(header, body);
  document.body.appendChild(bubble);
  positionBubble(bubble, selectionContext.rect);

  addButton.addEventListener("click", async () => {
    addButton.disabled = true;
    setBubbleStatus(bubble, "Добавляем в словарь...", "muted");
    try {
      const result = await requestBackend("/vocabulary/me/from-capture", {
        method: "POST",
        payload: {
          selected_text: selectionContext.selectedText,
          source_sentence: selectionContext.sourceSentence || null,
          source_url: selectionContext.sourceUrl || null,
          force_new_vocabulary_item: false,
        },
      });
      const translation = result?.vocabulary?.russian_translation || "Добавлено";
      setBubbleTranslation(bubble, translation, "Слово сохранено в личный словарь.");
      setBubbleStatus(
        bubble,
        result?.created_new_vocabulary_item
          ? "Слово добавлено в словарь."
          : "Это слово уже было в словаре пользователя.",
        "success",
      );
    } catch (error) {
      addButton.disabled = false;
      setBubbleStatus(bubble, `Ошибка добавления: ${error.message}`, "error");
    }
  });

  activeBubble = bubble;
  activeSelectionSignature = selectionContext.signature;
  return bubble;
}

async function translateSelection(selectionContext) {
  if (!currentToken) {
    const bubble = renderBubble(selectionContext);
    setBubbleTranslation(bubble, "Требуется вход", "Откройте popup расширения и выполните авторизацию.");
    setBubbleStatus(bubble, "Расширение не авторизовано.", "error");
    return;
  }

  const bubble = renderBubble(selectionContext);
  pendingTranslateAbortController = new AbortController();

  try {
    const result = await requestBackend("/translate/me", {
      method: "POST",
      payload: {
        text: selectionContext.selectedText,
        source_context: selectionContext.sourceSentence || null,
      },
      signal: pendingTranslateAbortController.signal,
    });

    if (!activeBubble || activeSelectionSignature !== selectionContext.signature) {
      return;
    }

    setBubbleTranslation(
      bubble,
      result?.translated_text || "Перевод не найден",
      selectionContext.sourceSentence || "Контекст не найден на странице.",
    );
    setBubbleStatus(bubble, "Перевод готов. Можно добавить в словарь.", "success");
    bubble.querySelector(".vkr-study-bubble__button--primary").disabled = false;
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    if (!activeBubble || activeSelectionSignature !== selectionContext.signature) {
      return;
    }
    const message = String(error?.message || "Unknown error");
    const invalidated = message.includes("Extension context invalidated");
    setBubbleTranslation(bubble, "Не удалось перевести", "Попробуйте выделить более короткую фразу или проверьте backend.");
    setBubbleStatus(
      bubble,
      invalidated
        ? "Расширение было обновлено. Обновите вкладку и повторите выделение."
        : `Ошибка перевода: ${message}`,
      "error",
    );
  } finally {
    pendingTranslateAbortController = null;
  }
}

async function handleSelectionGesture() {
  if (!studyingEnabled) {
    return;
  }

  const selectionContext = getSelectionContext();
  if (!selectionContext) {
    closeActiveBubble();
    return;
  }

  if (!isEnglishSelection(selectionContext.selectedText)) {
    closeActiveBubble();
    return;
  }

  if (selectionContext.signature === activeSelectionSignature) {
    return;
  }

  await translateSelection(selectionContext);
}

async function loadSettings() {
  const stored = await storageGet(Object.values(STORAGE_KEYS));
  studyingEnabled = Boolean(stored[STORAGE_KEYS.studyingEnabled]);
  currentApiBase = stored[STORAGE_KEYS.apiBase] || DEFAULT_API_BASE;
  currentToken = stored[STORAGE_KEYS.authToken] || null;
}

function onDocumentPointerDown(event) {
  if (!activeBubble) {
    return;
  }
  const target = event.target;
  if (target instanceof Node && activeBubble.contains(target)) {
    return;
  }
  closeActiveBubble();
}

function onKeyDown(event) {
  if (event.key === "Escape") {
    closeActiveBubble();
  }
}

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local") {
    return;
  }

  if (changes[STORAGE_KEYS.studyingEnabled]) {
    studyingEnabled = Boolean(changes[STORAGE_KEYS.studyingEnabled].newValue);
    if (!studyingEnabled) {
      closeActiveBubble();
    }
  }
  if (changes[STORAGE_KEYS.authToken]) {
    currentToken = changes[STORAGE_KEYS.authToken].newValue || null;
  }
  if (changes[STORAGE_KEYS.apiBase]) {
    currentApiBase = changes[STORAGE_KEYS.apiBase].newValue || DEFAULT_API_BASE;
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "VKR_GET_SELECTION") {
    sendResponse({ ok: true, payload: getSelectionContext() });
    return true;
  }
  return false;
});

document.addEventListener("mouseup", () => {
  window.setTimeout(() => {
    handleSelectionGesture().catch(() => {});
  }, 10);
});
document.addEventListener("pointerdown", onDocumentPointerDown, true);
document.addEventListener("keydown", onKeyDown, true);
window.addEventListener("scroll", () => {
  if (!activeBubble) {
    return;
  }
  const selectionContext = getSelectionContext();
  if (selectionContext && selectionContext.signature === activeSelectionSignature) {
    positionBubble(activeBubble, selectionContext.rect);
  }
}, true);

loadSettings().catch(() => {});
}
