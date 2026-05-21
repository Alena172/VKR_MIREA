import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  const { registerPendingSession, getResolvedResult, isPending } = usePendingReview();

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
    setLlmPending(false);
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

  /** Фоновая догрузка недостающих упражнений в буфер пока пользователь решает. */
  const fetchMissingInBackground = useCallback((missing, nextMode, nextVocabularyIds) => {
    cancelBgFetch();
    const controller = new AbortController();
    bgFetchControllerRef.current = controller;

    api
      .generateExercisesMe(
        { size: missing, mode: nextMode, vocabulary_ids: nextVocabularyIds || [], fast_start: false, incremental: false },
        { signal: controller.signal },
      )
      .then((result) => {
        if (result?.exercises?.length) {
          setBufferExercises((prev) => [...prev, ...result.exercises]);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (bgFetchControllerRef.current === controller) {
          bgFetchControllerRef.current = null;
        }
      });
  }, []);

  /** Запускает тренировку: сначала берёт из буфера (incremental), остаток догружает в фоне. */
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
        // Сначала пробуем взять из серверного буфера (incremental=true — отдаёт сразу)
        const incrementalResult = await api.generateExercisesMe(
          { size: nextSize, mode: nextMode, vocabulary_ids: nextVocabularyIds || [], fast_start: false, incremental: true },
          { signal: controller.signal },
        );

        let allExercises = incrementalResult?.exercises || [];

        // Если буфер был пуст или дал меньше одного — ждём синхронной генерации
        if (allExercises.length === 0) {
          const fullResult = await api.generateExercisesMe(
            { size: nextSize, mode: nextMode, vocabulary_ids: nextVocabularyIds || [], fast_start: false, incremental: false },
            { signal: controller.signal },
          );
          allExercises = fullResult?.exercises || [];
        }

        if (!allExercises.length) throw new Error("Не удалось получить задание.");

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

        // Если получили меньше запрошенного — догружаем остаток в фоне
        const missing = nextSize - allExercises.length;
        if (missing > 0) {
          fetchMissingInBackground(missing, nextMode, nextVocabularyIds);
        }
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
    if (!nextExercise) {
      // Буфер ещё не догрузился — показываем лоадер и ждём
      setCurrentExercise(null);
      setLoadingCurrent(true);
      setSubmittingCurrent(false);
      setCurrentIndex(nextIndex);
      setCurrentAnswer("");
      return;
    }
    setCurrentExercise(nextExercise);
    setBufferExercises(rest);
    setCurrentIndex(nextIndex);
    setCurrentAnswer("");
    setSubmittingCurrent(false);
  }

  // Когда фоновый запрос догрузил упражнения и мы ждали — берём следующее из буфера
  useEffect(() => {
    if (loadingCurrent && isTrainingActive && !currentExercise && bufferExercises.length > 0) {
      const [next, ...rest] = bufferExercises;
      setCurrentExercise(next);
      setBufferExercises(rest);
      setLoadingCurrent(false);
    }
  }, [bufferExercises, loadingCurrent, isTrainingActive, currentExercise]);

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
