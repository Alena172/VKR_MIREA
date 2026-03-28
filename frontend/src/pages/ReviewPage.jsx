import { useEffect, useState } from "react";
import { useReviewSession } from "../hooks/useReviewSession";
import { clearReviewFocus, loadReviewFocus } from "../lib/studyPresets";

const STRATEGY_LABELS = {
  NeighborExpansion: "Соседние связи",
  ClusterDeepening: "Углубление кластера",
  WeakNodeReinforcement: "Усиление слабых узлов",
};

const DATE_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function formatReviewMoment(value) {
  if (!value) {
    return "Без даты";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Без даты";
  }

  return DATE_FORMATTER.format(date);
}

function getTimingMeta(nextReviewAt) {
  if (!nextReviewAt) {
    return {
      label: "Без расписания",
      toneClass: "bg-slate-100 text-slate-700",
    };
  }

  const target = new Date(nextReviewAt);
  const diffMs = target.getTime() - Date.now();

  if (diffMs <= 0) {
    return {
      label: "Пора повторять сейчас",
      toneClass: "bg-red-100 text-red-700",
    };
  }

  const diffHours = diffMs / (1000 * 60 * 60);
  if (diffHours < 6) {
    return {
      label: "Скоро потребуется",
      toneClass: "bg-amber-100 text-amber-700",
    };
  }

  return {
    label: "Есть запас времени",
    toneClass: "bg-emerald-100 text-emerald-700",
  };
}

function getDifficultyMeta(errorCount, correctStreak) {
  if (errorCount >= 3) {
    return {
      label: "Трудное слово",
      toneClass: "bg-red-100 text-red-700",
      description: "Часто вызывает ошибки и требует более частого повторения.",
    };
  }

  if (correctStreak >= 3) {
    return {
      label: "Закрепляется",
      toneClass: "bg-emerald-100 text-emerald-700",
      description: "Слово уже запоминается лучше, но его важно периодически освежать.",
    };
  }

  return {
    label: "В работе",
    toneClass: "bg-blue-100 text-blue-700",
    description: "Нужна ещё пара повторений, чтобы слово стало устойчивым.",
  };
}

function getSessionProgress(currentIndex, total) {
  if (!total) {
    return 0;
  }
  return Math.min(100, Math.round((currentIndex / total) * 100));
}

export default function ReviewPage({ onError }) {
  const [reviewFocus, setReviewFocus] = useState(null);
  const {
    currentIndex,
    currentItem,
    graphAnchorsByLemma,
    graphRecommendations,
    isFlipped,
    isSessionActive,
    loadReviewMeta,
    plan,
    resetSession,
    sessionCorrect,
    sessionFinished,
    sessionIncorrect,
    sessionItems,
    sessionMessage,
    sessionMode,
    sessionSize,
    setIsFlipped,
    setSessionSize,
    startSession,
    starting,
    submitting,
    submitAnswer,
    summary,
  } = useReviewSession({ onError });

  const progressPercent = getSessionProgress(currentIndex, sessionItems.length);
  const currentTimingMeta = currentItem ? getTimingMeta(currentItem.next_review_at) : null;
  const currentDifficultyMeta = currentItem
    ? getDifficultyMeta(currentItem.error_count, currentItem.correct_streak)
    : null;

  useEffect(() => {
    const focus = loadReviewFocus();
    if (!focus) {
      return;
    }
    setReviewFocus(focus);
    clearReviewFocus();
  }, []);

  return (
    <section className="space-y-6">
      {!isSessionActive ? (
        <>
          <header className="surface p-4 md:p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="kicker">Spaced Repetition</p>
                <h2 className="section-title">Сессии повторения</h2>
                <p className="muted mt-1 text-sm">Запусти SRS-сессию или случайную сессию вне SRS.</p>
              </div>
              <button className="btn-secondary" onClick={loadReviewMeta} type="button">
                Обновить
              </button>
            </div>
          </header>

          {reviewFocus ? (
            <section className="rounded-xl border border-blue-200 bg-blue-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Фокус на слове</p>
                  <p className="mt-1 text-sm text-slate-700">
                    <strong>{reviewFocus.word}</strong> - {reviewFocus.translation}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    Текущий статус: {reviewFocus.stateLabel || (reviewFocus.hasProgress ? "В повторении" : "Ещё не в SRS")}.
                  </p>
                </div>
                <button type="button" className="btn-secondary" onClick={() => setReviewFocus(null)}>
                  Скрыть
                </button>
              </div>
            </section>
          ) : null}

          {summary ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard title="Всего слов в SRS" value={summary.total_tracked} />
              <StatCard title="К повторению сейчас" value={summary.due_now} />
              <StatCard title="Хорошо закреплены" value={summary.mastered} />
              <StatCard title="Вызывают трудности" value={summary.troubled} />
            </div>
          ) : null}

          <section className="surface space-y-4 p-4 md:p-5">
            <div className="grid gap-3 md:grid-cols-[220px_1fr]">
              <label className="text-sm">
                Размер сессии
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={sessionSize}
                  onChange={(event) => setSessionSize(Number(event.target.value || 1))}
                  className="field mt-1"
                  disabled={starting}
                />
              </label>
              <div className="flex flex-wrap items-end gap-2">
                <button type="button" className="btn-primary" onClick={() => startSession("srs")} disabled={starting}>
                  Запустить SRS-сессию
                </button>
                <button type="button" className="btn-secondary" onClick={() => startSession("random")} disabled={starting}>
                  Случайная сессия
                </button>
              </div>
            </div>

            {plan ? (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="chip">Сейчас к повторению: {plan.due_count}</span>
                  <span className="chip">На ближайшее время: {plan.upcoming_count}</span>
                  {plan.recommended_words.length ? <span className="chip">Фокус: {plan.recommended_words.slice(0, 3).join(", ")}</span> : null}
                </div>

                <div className="grid gap-3 lg:grid-cols-2">
                  <ReviewPlanColumn
                    title="Повторить сейчас"
                    emptyText="Сейчас нет срочных слов."
                    items={plan.due_now}
                  />
                  <ReviewPlanColumn
                    title="Скоро подойдут"
                    emptyText="В ближайшие часы новых слов не ожидается."
                    items={plan.upcoming}
                  />
                </div>
              </div>
            ) : null}

            {graphRecommendations.length ? (
              <div className="space-y-2 rounded-xl border border-blue-100 bg-blue-50/50 p-3">
                <p className="text-sm font-semibold text-gray-900">Рекомендации из learning graph</p>
                <div className="space-y-2">
                  {graphRecommendations.map((item) => {
                    const strategyLabel = STRATEGY_LABELS[item.primary_strategy] || item.primary_strategy || "Без стратегии";
                    const anchors = graphAnchorsByLemma[item.english_lemma] || [];
                    return (
                      <div key={`graph-rec-${item.english_lemma}`} className="rounded-lg border border-blue-100 bg-white p-2">
                        <p className="text-sm font-semibold text-gray-900">
                          {item.english_lemma} - {item.russian_translation}
                        </p>
                        <p className="mt-1 text-xs text-gray-600">
                          Strategy source: <span className="font-semibold text-blue-700">{strategyLabel}</span>
                        </p>
                        {anchors.length ? (
                          <p className="mt-1 text-xs text-gray-600">
                            Anchors: {anchors.map((anchor) => `${anchor.english_lemma} (${anchor.russian_translation})`).join(", ")}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </section>
        </>
      ) : null}

      {isSessionActive ? (
        <section className="surface p-4 md:p-6">
          <div className="mx-auto max-w-3xl space-y-4">
            <div className="relative z-20 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/95 p-3 text-sm text-gray-600">
              <span>
                Режим: <strong>{sessionMode === "srs" ? "Интервальное повторение (SRS)" : "Случайная сессия"}</strong>
              </span>
              <span>
                {Math.min(currentIndex, sessionItems.length)} / {sessionItems.length}
              </span>
              <span>
                Помню: <strong className="text-green-700">{sessionCorrect}</strong> · Не помню:{" "}
                <strong className="text-red-700">{sessionIncorrect}</strong>
              </span>
              <button type="button" className="btn-secondary" onClick={resetSession}>
                Завершить
              </button>
            </div>

            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
                <span>Прогресс сессии</span>
                <span>{progressPercent}%</span>
              </div>
              <div className="h-2 rounded-full bg-slate-200">
                <div className="h-2 rounded-full bg-blue-600 transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
              {currentItem && currentDifficultyMeta && currentTimingMeta ? (
                <div className="flex flex-wrap gap-2 pt-1">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${currentDifficultyMeta.toneClass}`}>
                    {currentDifficultyMeta.label}
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${currentTimingMeta.toneClass}`}>
                    {currentTimingMeta.label}
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                    Ошибок: {currentItem.error_count}
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                    Серия верных: {currentItem.correct_streak}
                  </span>
                </div>
              ) : null}
            </div>

            {sessionMessage ? <p className="text-sm text-gray-600">{sessionMessage}</p> : null}

            {currentItem ? (
              <div className="relative z-0 mt-2 flex w-full justify-center">
                <div className="w-full max-w-2xl">
                  <div className="relative isolate h-[22rem] w-full overflow-hidden rounded-xl perspective-1000">
                    <div
                      className="relative h-full w-full preserve-3d transition-transform duration-500"
                      style={{ transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
                    >
                      <div className="absolute inset-0 backface-hidden rounded-xl">
                        <div className="h-full rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-lg">
                          <div className="card-body flex h-full flex-col items-center justify-center p-8 text-center">
                            <span className="mb-4 rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800">
                              Слово для изучения
                            </span>
                            <p className="break-all text-4xl font-bold text-gray-900">{currentItem.word}</p>
                            {currentItem.context_definition ? (
                              <p className="mt-4 max-w-xl text-base leading-relaxed text-gray-700">{currentItem.context_definition}</p>
                            ) : null}
                            {currentDifficultyMeta ? (
                              <p className="mt-4 max-w-xl text-sm leading-relaxed text-gray-600">{currentDifficultyMeta.description}</p>
                            ) : null}
                            <button
                              type="button"
                              className="btn-primary mt-8"
                              onClick={() => setIsFlipped(true)}
                              disabled={submitting}
                            >
                              Показать перевод
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="absolute inset-0 backface-hidden rotate-y-180 rounded-xl">
                        <div className="h-full rounded-xl border border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 shadow-lg">
                          <div className="card-body flex h-full flex-col items-center justify-center p-8 text-center">
                            <span className="mb-4 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
                              Перевод
                            </span>
                            <p className="break-all text-2xl font-bold text-gray-900">{currentItem.word}</p>
                            <p className="mt-2 break-all text-2xl font-semibold text-green-700">
                              {currentItem.russian_translation || "Перевод не найден"}
                            </p>
                            {currentItem.context_definition ? (
                              <p className="mt-4 max-w-xl text-base leading-relaxed text-gray-700">{currentItem.context_definition}</p>
                            ) : null}
                            <div className="mt-4 flex flex-wrap justify-center gap-2">
                              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${currentTimingMeta?.toneClass || "bg-slate-100 text-slate-700"}`}>
                                {currentTimingMeta?.label || "Без расписания"}
                              </span>
                              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                                Следующее окно: {formatReviewMoment(currentItem.next_review_at)}
                              </span>
                            </div>
                            <button
                              type="button"
                              className="btn-secondary mt-6"
                              onClick={() => setIsFlipped(false)}
                              disabled={submitting}
                            >
                              Смотреть снова
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {currentItem && isFlipped && !sessionFinished ? (
              <div className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="mb-4 text-center">
                  <h3 className="text-lg font-semibold text-gray-900">Насколько легко вспомнить перевод?</h3>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <button
                    type="button"
                    className="rounded-xl border-2 border-red-200 bg-red-50 p-4 text-left transition hover:bg-red-100"
                    onClick={() => submitAnswer(false)}
                    disabled={submitting}
                  >
                    <p className="text-base font-semibold text-red-700">Не помню</p>
                    <p className="mt-1 text-sm text-red-600">Совсем не вспомнил перевод</p>
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border-2 border-green-200 bg-green-50 p-4 text-left transition hover:bg-green-100"
                    onClick={() => submitAnswer(true)}
                    disabled={submitting}
                  >
                    <p className="text-base font-semibold text-green-700">Помню</p>
                    <p className="mt-1 text-sm text-green-600">Сразу вспомнил перевод</p>
                  </button>
                </div>
              </div>
            ) : null}

            {sessionFinished ? (
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <h3 className="text-lg font-bold text-gray-900">Сессия завершена</h3>
                <p className="mt-2 text-sm text-gray-700">
                  Помню: <span className="font-semibold text-green-700">{sessionCorrect}</span>, не помню:{" "}
                  <span className="font-semibold text-red-700">{sessionIncorrect}</span>.
                </p>
                <div className="mt-3 flex gap-2">
                  <button type="button" className="btn-primary" onClick={() => startSession(sessionMode)}>
                    Повторить режим
                  </button>
                  <button type="button" className="btn-secondary" onClick={resetSession}>
                    Выйти
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </section>
  );
}

function StatCard({ title, value }) {
  return (
    <div className="surface p-3">
      <div className="muted text-xs">{title}</div>
      <div className="text-2xl font-extrabold text-gray-900">{value}</div>
    </div>
  );
}

function ReviewPlanColumn({ title, emptyText, items }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {items?.length ? (
        <div className="mt-3 space-y-2">
          {items.slice(0, 5).map((item) => (
            <ReviewPlanItemCard key={`${title}-${item.word}`} item={item} />
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}

function ReviewPlanItemCard({ item }) {
  const difficultyMeta = getDifficultyMeta(item.error_count, item.correct_streak);
  const timingMeta = getTimingMeta(item.next_review_at);

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-slate-900">{item.word}</p>
          <p className="text-sm text-slate-600">{item.russian_translation || "Перевод уточняется"}</p>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${difficultyMeta.toneClass}`}>
          {difficultyMeta.label}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs">
        <span className={`rounded-full px-2.5 py-1 font-semibold ${timingMeta.toneClass}`}>{timingMeta.label}</span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
          Ошибок: {item.error_count}
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-700">
          Серия: {item.correct_streak}
        </span>
      </div>
      <p className="mt-2 text-xs text-slate-500">Следующее повторение: {formatReviewMoment(item.next_review_at)}</p>
    </div>
  );
}
