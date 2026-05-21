import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";

/**
 * Хранит сессии, ожидающие LLM-перепроверки.
 * Когда результат готов — обновляет данные и показывает уведомление.
 */

const PendingReviewContext = createContext(null);

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 40; // ~2 минуты

export function PendingReviewProvider({ children }) {
  // { sessionId, initialResult, resolvedResult, toast }
  const [pendingSessions, setPendingSessions] = useState([]);
  // Тост: { sessionId, correct, total, changed }
  const [toast, setToast] = useState(null);
  const pollTimers = useRef({});
  const pollAttempts = useRef({});

  const dismissToast = useCallback(() => setToast(null), []);

  const stopPolling = useCallback((sessionId) => {
    if (pollTimers.current[sessionId]) {
      clearTimeout(pollTimers.current[sessionId]);
      delete pollTimers.current[sessionId];
    }
    delete pollAttempts.current[sessionId];
  }, []);

  const pollSession = useCallback(
    async (sessionId) => {
      pollAttempts.current[sessionId] = (pollAttempts.current[sessionId] || 0) + 1;
      if (pollAttempts.current[sessionId] > MAX_POLL_ATTEMPTS) {
        // Слишком долго — убираем из pending без тоста
        setPendingSessions((prev) => prev.filter((s) => s.sessionId !== sessionId));
        stopPolling(sessionId);
        return;
      }

      try {
        const data = await api.getSessionMe(sessionId);
        const newCorrect = data.session.correct;
        const newTotal = data.session.total;
        const newAnswers = data.answers || [];

        setPendingSessions((prev) => {
          const entry = prev.find((s) => s.sessionId === sessionId);
          if (!entry) return prev;

          const changed = newCorrect !== entry.initialResult.session.correct;
          if (changed) {
            // Результат изменился — показываем тост и убираем из pending
            setToast({ sessionId, correct: newCorrect, total: newTotal, changed: newCorrect - entry.initialResult.session.correct });
            stopPolling(sessionId);
            return prev.map((s) =>
              s.sessionId === sessionId
                ? { ...s, resolvedResult: { session: data.session, answers: newAnswers }, pending: false }
                : s,
            );
          }

          // Результат не изменился, но проверка завершилась (нет pending)
          // Планируем следующий poll
          pollTimers.current[sessionId] = setTimeout(() => pollSession(sessionId), POLL_INTERVAL_MS);
          return prev;
        });
      } catch {
        // Ошибка сети — пробуем ещё раз
        pollTimers.current[sessionId] = setTimeout(() => pollSession(sessionId), POLL_INTERVAL_MS * 2);
      }
    },
    [stopPolling],
  );

  const registerPendingSession = useCallback(
    (sessionId, initialResult, llmPendingCount) => {
      if (!llmPendingCount || llmPendingCount <= 0) return;

      setPendingSessions((prev) => {
        if (prev.find((s) => s.sessionId === sessionId)) return prev;
        return [...prev, { sessionId, initialResult, resolvedResult: null, pending: true }];
      });

      pollAttempts.current[sessionId] = 0;
      pollTimers.current[sessionId] = setTimeout(() => pollSession(sessionId), POLL_INTERVAL_MS);
    },
    [pollSession],
  );

  const getResolvedResult = useCallback(
    (sessionId) => {
      const entry = pendingSessions.find((s) => s.sessionId === sessionId);
      return entry?.resolvedResult || null;
    },
    [pendingSessions],
  );

  const isPending = useCallback(
    (sessionId) => {
      const entry = pendingSessions.find((s) => s.sessionId === sessionId);
      return entry?.pending ?? false;
    },
    [pendingSessions],
  );

  // Очистка таймеров при размонтировании
  useEffect(() => {
    return () => {
      Object.values(pollTimers.current).forEach(clearTimeout);
    };
  }, []);

  return (
    <PendingReviewContext.Provider value={{ registerPendingSession, getResolvedResult, isPending, toast, dismissToast }}>
      {children}
      {toast ? <LlmResultToast toast={toast} onDismiss={dismissToast} /> : null}
    </PendingReviewContext.Provider>
  );
}

export function usePendingReview() {
  const ctx = useContext(PendingReviewContext);
  if (!ctx) throw new Error("usePendingReview must be used inside PendingReviewProvider");
  return ctx;
}

function LlmResultToast({ toast, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 6000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const changed = toast.changed;
  const isImproved = changed > 0;

  return (
    <div className="fixed bottom-24 md:bottom-6 left-1/2 z-50 -translate-x-1/2 w-[calc(100%-2rem)] max-w-sm animate-slide-up">
      <div className={`rounded-xl border shadow-lg px-4 py-3 flex items-start gap-3 ${isImproved ? "border-green-200 bg-green-50" : "border-slate-200 bg-white"}`}>
        <span className={`text-lg shrink-0 mt-0.5 ${isImproved ? "text-green-600" : "text-slate-400"}`}>
          {isImproved ? "✓" : "ℹ"}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900">
            {isImproved ? "Проверка завершена — результат улучшен!" : "Проверка завершена"}
          </p>
          <p className="text-xs text-slate-600 mt-0.5">
            Итог: {toast.correct} / {toast.total}
            {isImproved ? ` (+${changed} засчитано после семантической проверки)` : " — изменений нет"}
          </p>
        </div>
        <button type="button" onClick={onDismiss} className="shrink-0 text-slate-400 hover:text-slate-600 text-lg leading-none">
          ×
        </button>
      </div>
    </div>
  );
}
