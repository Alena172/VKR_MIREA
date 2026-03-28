import LoadingSpinner from "../components/LoadingSpinner";
import DefinitionMatchExercise from "../components/training/DefinitionMatchExercise";
import SentenceTranslationExercise from "../components/training/SentenceTranslationExercise";
import WordScrambleExercise from "../components/training/WordScrambleExercise";
import { useTrainingSession } from "../hooks/useTrainingSession";

const MODE_META = {
  sentence_translation_full: {
    title: "Перевод предложения",
    hint: "Пиши полный перевод предложения на русский язык.",
  },
  word_definition_match: {
    title: "Сопоставление с определением",
    hint: "Выбери определение, которое подходит к слову.",
  },
  word_scramble: {
    title: "Собери слово",
    hint: "Нажимай на буквы, чтобы собрать английское слово.",
  },
};

const EXERCISE_TYPE_META = {
  sentence_translation_full: "Перевод предложения",
  word_definition_match: "Сопоставление с определением",
  word_scramble: "Собери слово",
};

function buildTrainingInsights(sessionResult, submittedAnswers) {
  if (!sessionResult || !submittedAnswers.length) {
    return null;
  }

  const incorrectById = new Map(
    (sessionResult.incorrect_feedback || []).map((item) => [item.exercise_id, item.explanation_ru]),
  );
  const adviceById = new Map(
    (sessionResult.advice_feedback || []).map((item) => [item.exercise_id, item.explanation_ru]),
  );

  const reviewedAnswers = submittedAnswers.map((answer) => {
    const incorrectFeedback = incorrectById.get(answer.exercise_id) || null;
    const adviceFeedback = adviceById.get(answer.exercise_id) || null;
    return {
      ...answer,
      incorrectFeedback,
      adviceFeedback,
      wasIncorrect: Boolean(incorrectFeedback),
      hasAdvice: Boolean(adviceFeedback),
    };
  });

  const weakAreas = new Map();
  reviewedAnswers.forEach((answer) => {
    const key = answer.exercise_type || "unknown";
    const current = weakAreas.get(key) || { incorrect: 0, advice: 0, total: 0 };
    weakAreas.set(key, {
      incorrect: current.incorrect + (answer.wasIncorrect ? 1 : 0),
      advice: current.advice + (answer.hasAdvice ? 1 : 0),
      total: current.total + 1,
    });
  });

  const rankedWeakAreas = [...weakAreas.entries()]
    .map(([exerciseType, stats]) => ({
      exerciseType,
      label: EXERCISE_TYPE_META[exerciseType] || exerciseType,
      score: stats.incorrect * 3 + stats.advice,
      ...stats,
    }))
    .sort((a, b) => b.score - a.score || b.incorrect - a.incorrect || a.label.localeCompare(b.label));

  const weakestArea = rankedWeakAreas.find((item) => item.score > 0) || null;
  const accuracyPercent = Math.round(Number(sessionResult.session.accuracy || 0) * 100);

  let nextStep = "Повтори тренировку в том же режиме, чтобы закрепить текущий результат.";
  if (accuracyPercent < 50) {
    nextStep = "Сначала вернись в повторение SRS, затем запусти короткую тренировку на 3-5 заданий.";
  } else if (weakestArea?.exerciseType === "sentence_translation_full") {
    nextStep = "Сфокусируйся на переводе предложений: полезно пройти ещё одну короткую сессию в этом режиме.";
  } else if (weakestArea?.exerciseType === "word_definition_match") {
    nextStep = "Повтори сопоставление с определениями: это поможет лучше различать значения похожих слов.";
  } else if (weakestArea?.exerciseType === "word_scramble") {
    nextStep = "Сделай ещё одну сессию на сборку слов, чтобы быстрее узнавать написание лемм.";
  } else if (accuracyPercent >= 85) {
    nextStep = "Результат уже сильный: можно перейти к следующему режиму тренировки или к SRS-повторению.";
  }

  return {
    accuracyPercent,
    weakestArea,
    incorrectAnswers: reviewedAnswers.filter((item) => item.wasIncorrect),
    adviceAnswers: reviewedAnswers.filter((item) => item.hasAdvice),
    nextStep,
  };
}

function ResultStatCard({ title, value, tone = "default" }) {
  const toneClass =
    tone === "good"
      ? "border-green-200 bg-green-50"
      : tone === "warn"
        ? "border-amber-200 bg-amber-50"
        : "border-slate-200 bg-slate-50";

  return (
    <div className={`rounded-xl border p-3 ${toneClass}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-1 text-2xl font-extrabold text-slate-900">{value}</p>
    </div>
  );
}

function TrainingFeedbackCard({ item, kind }) {
  const title = kind === "incorrect" ? "Нужно доработать" : "Можно улучшить";
  const toneClass =
    kind === "incorrect"
      ? "border-red-200 bg-red-50"
      : "border-amber-200 bg-amber-50";
  const feedback = kind === "incorrect" ? item.incorrectFeedback : item.adviceFeedback;

  return (
    <article className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-900">{EXERCISE_TYPE_META[item.exercise_type] || "Упражнение"}</p>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
          #{item.exercise_id}
        </span>
      </div>
      <p className="mt-3 text-sm font-medium text-slate-800">{item.prompt}</p>
      <div className="mt-3 space-y-1 text-sm text-slate-700">
        <p><strong>Твой ответ:</strong> {item.user_answer}</p>
        <p><strong>Ожидаемый ответ:</strong> {item.expected_answer}</p>
      </div>
      <div className="mt-3 rounded-lg bg-white/80 p-3 text-sm text-slate-700">
        <p className="font-semibold text-slate-900">{title}</p>
        <p className="mt-1">{feedback}</p>
      </div>
    </article>
  );
}

export default function TrainingPage({ onError }) {
  const {
    answerReady,
    currentAnswer,
    currentExercise,
    currentIndex,
    generationNote,
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
    size,
    startTraining,
    submitCurrentAndContinue,
    submittedAnswers,
  } = useTrainingSession({ onError });

  const trainingInsights = buildTrainingInsights(sessionResult, submittedAnswers);

  function renderExercise() {
    if (!currentExercise) {
      return null;
    }

    if (currentExercise.exercise_type === "word_scramble") {
      return (
        <WordScrambleExercise
          exercise={currentExercise}
          exercisePosition={currentIndex}
          onAnswerChange={setCurrentAnswer}
        />
      );
    }

    if (currentExercise.exercise_type === "word_definition_match") {
      return (
        <DefinitionMatchExercise
          exercise={currentExercise}
          exercisePosition={currentIndex}
          onAnswerChange={setCurrentAnswer}
        />
      );
    }

    return (
      <SentenceTranslationExercise
        exercise={currentExercise}
        answer={currentAnswer}
        onAnswerChange={setCurrentAnswer}
        exercisePosition={currentIndex}
      />
    );
  }

  return (
    <section className="space-y-4">
      {loadingCurrent ? <LoadingSpinner message="Генерирую упражнения..." estimatedSeconds="3-8" /> : null}

      <header className="surface p-4 md:p-5">
        <p className="kicker">Training</p>
        <h2 className="section-title">Тренировка</h2>
        <p className="muted mt-1 text-sm">Выберите формат, количество заданий и пройдите сессию без ожиданий: следующие упражнения подгружаются заранее.</p>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <label className="text-sm">
            Количество упражнений
            <input
              type="number"
              min={1}
              max={30}
              value={size}
              onChange={(event) => setSize(Number(event.target.value || 1))}
              className="field mt-1"
              disabled={isTrainingActive}
            />
          </label>
          <label className="text-sm md:col-span-2">
            Тип упражнений
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value)}
              className="field mt-1"
              disabled={isTrainingActive}
            >
              <option value="sentence_translation_full">Перевод предложения</option>
              <option value="word_definition_match">Сопоставление с определением</option>
              <option value="word_scramble">Собери слово</option>
            </select>
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button onClick={startTraining} className="btn-primary disabled:opacity-50" type="button" disabled={loadingCurrent || isTrainingActive}>
            {loadingCurrent ? "Подготовка..." : "Начать тренировку"}
          </button>
          {sessionResult ? (
            <button className="btn-secondary" type="button" onClick={resetSessionState}>
              Новая сессия
            </button>
          ) : null}
          {isTrainingActive ? <span className="chip">Задание {currentIndex + 1} из {size}</span> : null}
          {generationNote ? <span className="chip">{generationNote}</span> : null}
        </div>
      </header>

      {isTrainingActive ? (
        <section className="surface p-4 md:p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="kicker">Текущий режим</p>
              <h3 className="text-lg font-extrabold text-gray-900">{MODE_META[mode].title}</h3>
              <p className="muted text-sm">{MODE_META[mode].hint}</p>
            </div>
            <span className="chip">{progressPercent}%</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-gray-200">
            <div className="h-2 rounded-full bg-blue-600 transition-all" style={{ width: `${progressPercent}%` }} />
          </div>
        </section>
      ) : null}

      {isTrainingActive && currentExercise ? (
        <article className="surface p-4 md:p-5">
          <p className="text-base font-semibold">{currentExercise.prompt}</p>
          {renderExercise()}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button onClick={submitCurrentAndContinue} className="btn-primary disabled:opacity-50" type="button" disabled={loadingCurrent || !answerReady}>
              {currentIndex + 1 >= size ? "Завершить и отправить" : "Следующее задание"}
            </button>
            {loadingPrefetch ? <span className="chip">Подгружаю следующую партию...</span> : null}
          </div>
        </article>
      ) : null}

      {sessionResult ? (
        <section className="surface p-4 md:p-5">
          <p className="text-lg font-extrabold text-gray-900">
            Результат: {sessionResult.session.correct}/{sessionResult.session.total}
          </p>
          <p className="muted mt-1 text-sm">Разбор завершён. Ниже видно, что получилось хорошо и что стоит повторить следующим шагом.</p>

          {trainingInsights ? (
            <>
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <ResultStatCard title="Точность" value={`${trainingInsights.accuracyPercent}%`} tone={trainingInsights.accuracyPercent >= 80 ? "good" : trainingInsights.accuracyPercent >= 50 ? "warn" : "default"} />
                <ResultStatCard title="Ошибки" value={trainingInsights.incorrectAnswers.length} tone={trainingInsights.incorrectAnswers.length === 0 ? "good" : "warn"} />
                <ResultStatCard title="Подсказки по стилю" value={trainingInsights.adviceAnswers.length} />
                <ResultStatCard title="Слабый формат" value={trainingInsights.weakestArea?.label || "Не выделен"} tone={trainingInsights.weakestArea ? "warn" : "good"} />
              </div>

              <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
                <p className="text-sm font-semibold text-slate-900">Что делать дальше</p>
                <p className="mt-2 text-sm text-slate-700">{trainingInsights.nextStep}</p>
                {trainingInsights.weakestArea ? (
                  <p className="mt-2 text-sm text-slate-700">
                    Больше всего внимания сейчас требует режим <strong>{trainingInsights.weakestArea.label}</strong>: ошибок — {trainingInsights.weakestArea.incorrect}, замечаний — {trainingInsights.weakestArea.advice}.
                  </p>
                ) : null}
              </div>

              {trainingInsights.incorrectAnswers.length > 0 ? (
                <div className="mt-5">
                  <p className="text-sm font-semibold text-gray-900">Где были ошибки</p>
                  <div className="mt-3 space-y-3">
                    {trainingInsights.incorrectAnswers.map((item) => (
                      <TrainingFeedbackCard key={`incorrect-${item.exercise_id}`} item={item} kind="incorrect" />
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-4 text-sm text-green-700">Ошибок нет. Это хороший момент перейти к следующему режиму или к повторению SRS.</p>
              )}

              {trainingInsights.adviceAnswers.length > 0 ? (
                <div className="mt-5">
                  <p className="text-sm font-semibold text-gray-900">Что можно улучшить</p>
                  <div className="mt-3 space-y-3">
                    {trainingInsights.adviceAnswers.map((item) => (
                      <TrainingFeedbackCard key={`advice-${item.exercise_id}`} item={item} kind="advice" />
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
