import { useEffect, useMemo, useRef, useState } from "react";
import { api, getErrorMessage, isAbortError } from "../lib/api";
import { useAbortControllers } from "./useAbortControllers";
import { usePendingReview } from "../context/PendingReviewContext";

/** Управляет тренировкой: генерацией батча, буфером и отправкой ответов. */
export function useTrainingSession({ onError }) {
  const [size, setSize] = useState(5);
  const [mode, setMode] = useState("sentence_translation_full");
  const [selectedVocabularyIds, setSelectedVocabularyIds] = useState([]);
  const [focusLabel, setFocusLabel] = useState("");
  const [currentExercise, setCurrentExercise] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [bufferExercises, setBufferExercises] = useState([]);
  const [submittedAnswers, setSubmittedAnswers] = useState([]);
  const [loadingCurrent, setLoadingCurrent] = useState(false);
  const [submittingCurrent, setSubmittingCurrent] = useState(false);
  const [sessionResult, setSessionResult] = useState(null);
  const [llmPending, setLlmPending] = useState(false);
  const [isTrainingActive, setIsTrainingActive] = useState(false);
  const { abortAllRequests, registerController, releaseController } = useAbortControllers();
  const bgFetchControllerRef = useRef(null);
  const { registerPendingSession, getResolvedResult } = usePendingReview();

  const progressPercent = size > 0 ? Math.round((currentIndex / size) * 100) : 0;

  function cancelBgFetch() {
    if (bgFetchControllerRef.current) {
      bgFetchControllerRef.current.abort();
      bgFetchControllerRef.current = null;
    }
  }

  function resetSessionState() {
    cancelBgFetch();
    abortAllRequests();
    setCurrentExercise(null);
    setCurrentIndex(0);
    setCurrentAnswer("");
    setBufferExercises([]);
    setSubmittedAnswers([]);
    setSessionResult(null);
    setLlmPending(false); // локальный флаг — сбрасываем, polling в PendingReviewContext продолжается независимо
    setIsTrainingActive(false);
    setLoadingCurrent(false);
    setSubmittingCurrent(false);
  }

  async function submitSession(answersPayload, signal) {
    const result = await api.submitSession({ answers: answersPayload }, { signal });
    setSessionResult(result);
    if (result.llm_pending_count > 0) {
      setLlmPending(true);
      registerPendingSession(result.session.id, result, result.llm_pending_count);
    }
  }


  /** Поллит буфер раз в 2 секунды пока не появятся упражнения (буфер заполняется Celery в фоне). */
  async function pollUntilBufferReady(nextMode, nextVocabularyIds, nextSize, signal) {
    const POLL_INTERVAL = 2000;
    const MAX_ATTEMPTS = 30; // до 60 секунд
    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      if (signal.aborted) throw new DOMException("Aborted", "AbortError");
      await new Promise((resolve, reject) => {
        const t = setTimeout(resolve, POLL_INTERVAL);
        signal.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
      });
      const result = await api.generateExercisesMe(
        { size: nextSize, mode: nextMode, vocabulary_ids: nextVocabularyIds || [], fast_start: false, incremental: true },
        { signal },
      );
      const exercises = result?.exercises || [];
      if (exercises.length > 0) return exercises;
    }
    return [];
  }

  /** Запускает тренировку: берёт из буфера мгновенно, при пустом буфере поллит пока Celery не заполнит. */
  async function startTraining(options = {}) {
    const nextMode = options.overrideMode || mode;
    const nextSize = options.overrideSize || size;
    const nextVocabularyIds = options.overrideVocabularyIds || selectedVocabularyIds;
    const nextFocusLabel = options.focusLabel || focusLabel;

    cancelBgFetch();
    abortAllRequests();
    onError("");
    setLoadingCurrent(true);

    try {
      const controller = registerController();
      try {
        const useBuffer = nextMode === "sentence_translation_full" && !(nextVocabularyIds?.length);
        let allExercises = [];

        if (useBuffer) {
          // Буферный режим: берём из серверного буфера мгновенно, поллим если пуст
          const incrementalResult = await api.generateExercisesMe(
            { size: nextSize, mode: nextMode, vocabulary_ids: [], fast_start: false, incremental: true },
            { signal: controller.signal },
          );
          allExercises = incrementalResult?.exercises || [];
          if (allExercises.length === 0) {
            allExercises = await pollUntilBufferReady(nextMode, [], nextSize, controller.signal);
          }
        } else {
          // Быстрые режимы: синхронная генерация без буфера
          const result = await api.generateExercisesMe(
            { size: nextSize, mode: nextMode, vocabulary_ids: nextVocabularyIds || [], fast_start: false, incremental: false },
            { signal: controller.signal },
          );
          allExercises = result?.exercises || [];
        }

        if (!allExercises.length) throw new Error("Не удалось получить задание. Попробуйте позже.");

        setMode(nextMode);
        setSize(nextSize);
        setSelectedVocabularyIds(nextVocabularyIds);
        setFocusLabel(nextFocusLabel);
        setCurrentExercise(allExercises[0]);
        setCurrentIndex(0);
        setCurrentAnswer("");
        setSubmittedAnswers([]);
        setBufferExercises(allExercises.slice(1));
        setSessionResult(null);
        setIsTrainingActive(true);
      } finally {
        releaseController(controller);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        onError(
          getErrorMessage(error).includes("Vocabulary is empty")
            ? "Словарь пуст. Сначала добавьте слова на странице словаря."
            : getErrorMessage(error),
        );
      }
    } finally {
      setLoadingCurrent(false);
    }
  }

  async function submitCurrentAndContinue() {
    if (!currentExercise || submittingCurrent) {
      return;
    }
    setSubmittingCurrent(true);

    const nextAnswers = [
      ...submittedAnswers,
      {
        exercise_id: currentIndex + 1,
        exercise_type: currentExercise.exercise_type,
        target_word: currentExercise.target_word || null,
        prompt: currentExercise.prompt,
        expected_answer: currentExercise.answer,
        user_answer: (currentAnswer || "-").trim() || "-",
        is_correct: false,
      },
    ];
    setSubmittedAnswers(nextAnswers);

    const nextIndex = currentIndex + 1;
    if (nextIndex >= size) {
      cancelBgFetch();
      const controller = registerController();
      try {
        await submitSession(nextAnswers, controller.signal);
        setIsTrainingActive(false);
        setCurrentExercise(null);
        setBufferExercises([]);
      } catch (error) {
        if (!isAbortError(error)) {
          onError(getErrorMessage(error));
        }
      } finally {
        releaseController(controller);
        setSubmittingCurrent(false);
      }
      return;
    }

    const [nextExercise, ...rest] = bufferExercises;
    if (nextExercise) {
      setCurrentExercise(nextExercise);
      setBufferExercises(rest);
      setCurrentIndex(nextIndex);
      setCurrentAnswer("");
      setSubmittingCurrent(false);
      return;
    }

    // Локальный буфер пуст — догружаем следующее упражнение
    setCurrentExercise(null);
    setLoadingCurrent(true);
    setCurrentIndex(nextIndex);
    setCurrentAnswer("");
    setSubmittingCurrent(false);

    const useBuffer = mode === "sentence_translation_full" && !selectedVocabularyIds?.length;
    const controller = registerController();
    (async () => {
      try {
        let exercises = [];
        if (useBuffer) {
          exercises = await pollUntilBufferReady(mode, [], size, controller.signal);
        } else {
          const result = await api.generateExercisesMe(
            { size: size - nextIndex, mode, vocabulary_ids: selectedVocabularyIds || [], fast_start: false, incremental: false },
            { signal: controller.signal },
          );
          exercises = result?.exercises || [];
        }
        if (exercises.length > 0) {
          setCurrentExercise(exercises[0]);
          setBufferExercises(exercises.slice(1));
        } else {
          onError("Не удалось загрузить следующее задание. Попробуйте позже.");
        }
      } catch (error) {
        if (!isAbortError(error)) onError(getErrorMessage(error));
      } finally {
        releaseController(controller);
        setLoadingCurrent(false);
      }
    })();
  }


  // Когда LLM завершила проверку — обновляем sessionResult актуальными данными
  useEffect(() => {
    if (!sessionResult || !llmPending) return;
    const resolved = getResolvedResult(sessionResult.session.id);
    if (resolved) {
      setSessionResult((prev) => ({
        ...prev,
        session: resolved.session,
        answers: resolved.answers,
      }));
      setLlmPending(false);
      return;
    }
    // Проверяем каждые 2с пока pending
    const timer = setInterval(() => {
      const r = getResolvedResult(sessionResult.session.id);
      if (r) {
        setSessionResult((prev) => ({
          ...prev,
          session: r.session,
          answers: r.answers,
        }));
        setLlmPending(false);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [sessionResult?.session?.id, llmPending, getResolvedResult]);

  const answerReady = useMemo(() => {
    if (!currentExercise) return false;
    return currentAnswer.trim().length > 0;
  }, [currentAnswer, currentExercise]);

  return {
    answerReady,
    currentAnswer,
    currentExercise,
    currentIndex,
    focusLabel,
    isTrainingActive,
    llmPending,
    loadingCurrent,
    loadingPrefetch: false,
    mode,
    progressPercent,
    resetSessionState,
    sessionResult,
    setCurrentAnswer,
    setMode,
    setSize,
    setSelectedVocabularyIds,
    setFocusLabel,
    selectedVocabularyIds,
    size,
    startTraining,
    submittingCurrent,
    submittedAnswers,
    submitCurrentAndContinue,
  };
}
