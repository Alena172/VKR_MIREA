const TRAINING_PRESET_KEY = "vkr_training_preset";
const REVIEW_FOCUS_KEY = "vkr_review_focus";

function safeReadJson(key) {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function safeWriteJson(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

export function saveTrainingPreset(preset) {
  safeWriteJson(TRAINING_PRESET_KEY, preset);
}

export function loadTrainingPreset() {
  return safeReadJson(TRAINING_PRESET_KEY);
}

export function clearTrainingPreset() {
  sessionStorage.removeItem(TRAINING_PRESET_KEY);
}

export function saveReviewFocus(focus) {
  safeWriteJson(REVIEW_FOCUS_KEY, focus);
}

export function loadReviewFocus() {
  return safeReadJson(REVIEW_FOCUS_KEY);
}

export function clearReviewFocus() {
  sessionStorage.removeItem(REVIEW_FOCUS_KEY);
}
