import { useMemo, useState } from "react";
import { api, getErrorMessage, isAbortError } from "../lib/api";
import { useAbortControllers } from "./useAbortControllers";

/** Управляет тренировкой: генерацией батча, буфером и отправкой ответов. */
export function useTrainingSession({ onError }) {
  const [size, setSize] = useState(6);
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
  const [isTrainingActive, setIsTrainingActive] = useState(false);
  const [generationNote, setGenerationNote] = useState("");
  const { abortAllRequests, registerController, releaseController } = useAbortControllers();

  const progressPercent = size > 0 ? Math.round((currentIndex / size) * 100) : 0;

  async function generateBatch(targetMode, batchSize, vocabularyIds, signal) {
    const result = await api.generateExercisesMe(
      {
        size: batchSize,
        mode: targetMode,
        vocabulary_ids: vocabularyIds || [],
        fast_start: false,
        incremental: false,
      },
      { signal },
    );
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
    setSubmittedAnswers([]);
    setSessionResult(null);
    setIsTrainingActive(false);
    setGenerationNote("");
    setLoadingCurrent(false);
    setSubmittingCurrent(false);
  }

  async function submitSession(answersPayload, signal) {
    const result = await api.submitSession({ answers: answersPayload }, { signal });
    setSessionResult(result);
  }

  /** Загружает все упражнения одним запросом — между заданиями ожидания нет. */
  async function startTraining(options = {}) {
    const nextMode = options.overrideMode || mode;
    const nextSize = options.overrideSize || size;
    const nextVocabularyIds = options.overrideVocabularyIds || selectedVocabularyIds;
    const nextFocusLabel = options.focusLabel || focusLabel;

    abortAllRequests();
    setLoadingCurrent(true);
    onError("");
    try {
      const controller = registerController();
      try {
        const { exercises: allExercises, note } = await generateBatch(
          nextMode,
          nextSize,
          nextVocabularyIds,
          controller.signal,
        );
        setMode(nextMode);
        setSize(nextSize);
        setSelectedVocabularyIds(nextVocabularyIds);
        setFocusLabel(nextFocusLabel);
        setCurrentExercise(allExercises[0]);
        setCurrentIndex(0);
        setCurrentAnswer("");
        setSubmittedAnswers([]);
        setBufferExercises(allExercises.slice(1));
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
    setCurrentExercise(nextExercise);
    setBufferExercises(rest);
    setCurrentIndex(nextIndex);
    setCurrentAnswer("");
    setSubmittingCurrent(false);
  }

  const answerReady = useMemo(() => {
    if (!currentExercise) {
      return false;
    }
    return currentAnswer.trim().length > 0;
  }, [currentAnswer, currentExercise]);

  return {
    answerReady,
    currentAnswer,
    currentExercise,
    currentIndex,
    generationNote,
    focusLabel,
    isTrainingActive,
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
