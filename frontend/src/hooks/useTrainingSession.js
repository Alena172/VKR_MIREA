import { useEffect, useMemo, useState } from "react";
import { api, getErrorMessage, isAbortError, pollTask } from "../lib/api";
import { useAbortControllers } from "./useAbortControllers";

const PREFETCH_BATCH_SIZE = 2;

export function useTrainingSession({ onError }) {
  const [size, setSize] = useState(6);
  const [mode, setMode] = useState("sentence_translation_full");
  const [selectedVocabularyIds, setSelectedVocabularyIds] = useState([]);
  const [focusLabel, setFocusLabel] = useState("");
  const [currentExercise, setCurrentExercise] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [bufferExercises, setBufferExercises] = useState([]);
  const [fetchedCount, setFetchedCount] = useState(0);
  const [submittedAnswers, setSubmittedAnswers] = useState([]);
  const [loadingCurrent, setLoadingCurrent] = useState(false);
  const [loadingPrefetch, setLoadingPrefetch] = useState(false);
  const [submittingCurrent, setSubmittingCurrent] = useState(false);
  const [sessionResult, setSessionResult] = useState(null);
  const [isTrainingActive, setIsTrainingActive] = useState(false);
  const [generationNote, setGenerationNote] = useState("");
  const { abortAllRequests, registerController, releaseController } = useAbortControllers();

  const progressPercent = size > 0 ? Math.round((currentIndex / size) * 100) : 0;

  async function generateBatch(targetMode, batchSize, vocabularyIds, signal) {
    const { task_id } = await api.generateExercisesMe(
      { size: batchSize, mode: targetMode, vocabulary_ids: vocabularyIds || [] },
      { signal },
    );
    const result = await pollTask(task_id, {
      intervalMs: 700,
      maxAttempts: 90,
      maxIntervalMs: 3000,
      backoffFactor: 1.4,
      signal,
    });
    if (!result || !result.exercises || result.exercises.length === 0) {
      throw new Error("Не удалось получить задание.");
    }
    return { exercises: result.exercises, note: result.note || "" };
  }

  function resetSessionState() {
    abortAllRequests();
    setCurrentExercise(null);
    setCurrentIndex(0);
    setCurrentAnswer("");
    setBufferExercises([]);
    setFetchedCount(0);
    setSubmittedAnswers([]);
    setSessionResult(null);
    setIsTrainingActive(false);
    setGenerationNote("");
    setLoadingCurrent(false);
    setLoadingPrefetch(false);
    setSubmittingCurrent(false);
  }

  async function submitSession(answersPayload, signal) {
    const requestAnswers = answersPayload.map(({ exercise_type, ...answer }) => answer);
    const result = await api.submitSession({ answers: requestAnswers }, { signal });
    setSessionResult(result);
  }

  async function startTraining(options = {}) {
    const nextMode = options.overrideMode || mode;
    const nextSize = options.overrideSize || size;
    const nextVocabularyIds = options.overrideVocabularyIds || selectedVocabularyIds;
    const nextFocusLabel = options.focusLabel || focusLabel;

    abortAllRequests();
    setLoadingCurrent(true);
    onError("");
    try {
      const initialBatchSize = Math.min(PREFETCH_BATCH_SIZE, nextSize);
      const controller = registerController();
      try {
        const { exercises: initialExercises, note } = await generateBatch(
          nextMode,
          initialBatchSize,
          nextVocabularyIds,
          controller.signal,
        );
        setMode(nextMode);
        setSize(nextSize);
        setSelectedVocabularyIds(nextVocabularyIds);
        setFocusLabel(nextFocusLabel);
        setCurrentExercise(initialExercises[0]);
        setCurrentIndex(0);
        setCurrentAnswer("");
        setSubmittedAnswers([]);
        setBufferExercises(initialExercises.slice(1));
        setFetchedCount(initialExercises.length);
        setGenerationNote(note);
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
        prompt: currentExercise.prompt,
        expected_answer: currentExercise.answer,
        user_answer: (currentAnswer || "-").trim() || "-",
        is_correct: false,
        exercise_type: currentExercise.exercise_type,
      },
    ];
    setSubmittedAnswers(nextAnswers);

    const nextIndex = currentIndex + 1;
    if (nextIndex >= size) {
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

    if (bufferExercises.length > 0) {
      const [nextExercise, ...rest] = bufferExercises;
      setCurrentExercise(nextExercise);
      setBufferExercises(rest);
      setCurrentIndex(nextIndex);
      setCurrentAnswer("");
      setSubmittingCurrent(false);
      return;
    }

    setLoadingCurrent(true);
    try {
      const remaining = size - fetchedCount;
      const batchSize = Math.max(1, Math.min(PREFETCH_BATCH_SIZE, remaining));
      const controller = registerController();
      try {
        const { exercises: generatedBatch, note } = await generateBatch(
          mode,
          batchSize,
          selectedVocabularyIds,
          controller.signal,
        );
        const [nextExercise, ...rest] = generatedBatch;
        setCurrentExercise(nextExercise);
        setBufferExercises(rest);
        setFetchedCount((prev) => prev + generatedBatch.length);
        setCurrentIndex(nextIndex);
        setCurrentAnswer("");
        setGenerationNote(note);
      } finally {
        releaseController(controller);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      setLoadingCurrent(false);
      setSubmittingCurrent(false);
    }
  }

  useEffect(() => {
    if (!isTrainingActive || loadingCurrent || loadingPrefetch) {
      return undefined;
    }

    const remaining = size - fetchedCount;
    if (remaining <= 0 || bufferExercises.length >= PREFETCH_BATCH_SIZE) {
      return undefined;
    }

    const controller = registerController();
    setLoadingPrefetch(true);
    const batchSize = Math.min(PREFETCH_BATCH_SIZE, remaining);

    generateBatch(mode, batchSize, selectedVocabularyIds, controller.signal)
      .then(({ exercises: batch, note }) => {
        setBufferExercises((prev) => [...prev, ...batch]);
        setFetchedCount((prev) => prev + batch.length);
        if (note) {
          setGenerationNote(note);
        }
      })
      .catch((error) => {
        if (!isAbortError(error)) {
          onError(getErrorMessage(error));
        }
      })
      .finally(() => {
        releaseController(controller);
        setLoadingPrefetch(false);
      });

    return () => {
      controller.abort();
      releaseController(controller);
    };
  }, [bufferExercises.length, fetchedCount, isTrainingActive, loadingCurrent, mode, onError, selectedVocabularyIds, size]);
  const answerReady = useMemo(() => {
    if (!currentExercise) {
      return false;
    }
    return currentAnswer.trim().length > 0;
  }, [currentAnswer, currentExercise]);

  return {
    answerReady,
    bufferExercises,
    currentAnswer,
    currentExercise,
    currentIndex,
    generationNote,
    focusLabel,
    isTrainingActive,
    loadingCurrent,
    loadingPrefetch,
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
