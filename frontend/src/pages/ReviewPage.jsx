import { useEffect, useState } from "react";
import { useReviewSession } from "../hooks/useReviewSession";
import { clearReviewFocus, loadReviewFocus } from "../lib/studyPresets";

function getSessionProgress(currentIndex, total) {
  if (!total) return 0;
  return Math.min(100, Math.round((currentIndex / total) * 100));
}

const SESSION_MODES = [
  { value: "srs", label: "По расписанию", description: "Только слова, которые пора повторить сегодня" },
  { value: "troubled", label: "Трудные слова", description: "Слова с наибольшим числом ошибок" },
  { value: "random", label: "Случайные", description: "Произвольная выборка из всего словаря" },
];

export default function ReviewPage({ onError }) {
  const [reviewFocus, setReviewFocus] = useState(null);
  const [selectedMode, setSelectedMode] = useState("srs");
  const {
    currentIndex,
    currentItem,
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
  const dueCount = plan?.due_now?.length ?? summary?.due_now ?? 0;
  const troubledCount = summary?.troubled ?? 0;

  useEffect(() => {
    const focus = loadReviewFocus();
    if (!focus) return;
    setReviewFocus(focus);
    clearReviewFocus();
  }, []);

  return (
    <section className="space-y-6">
      {!isSessionActive ? (
        <>
          <header className="surface p-4 md:p-5">
            <p className="kicker">Spaced Repetition</p>
            <h2 className="section-title">Повторение</h2>
            <p className="muted mt-1 text-sm">Выберите режим и запустите сессию.</p>
          </header>

          {reviewFocus ? (
            <section className="rounded-xl border border-blue-200 bg-blue-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Фокус на слове</p>
                  <p className="mt-1 text-sm text-slate-700">
                    <strong>{reviewFocus.word}</strong> — {reviewFocus.translation}
                  </p>
                  <p className="mt-0.5 text-sm text-slate-600">
                    Статус: {reviewFocus.stateLabel || (reviewFocus.hasProgress ? "В повторении" : "Ещё не в SRS")}
                  </p>
                </div>
                <button type="button" className="btn-secondary" onClick={() => setReviewFocus(null)}>
                  Скрыть
                </button>
              </div>
            </section>
          ) : null}

          <section className="surface p-4 md:p-5 space-y-5">
            {dueCount > 0 ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 font-medium">
                Сейчас к повторению: <span className="font-extrabold text-amber-900">{dueCount}</span> {dueCount === 1 ? "слово" : dueCount >= 2 && dueCount <= 4 ? "слова" : "слов"}
              </div>
            ) : (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 font-medium">
                Всё повторено — новые слова подойдут позже.
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-3">
              {SESSION_MODES.map((mode) => {
                const isSelected = selectedMode === mode.value;
                const badge = mode.value === "srs" ? dueCount : mode.value === "troubled" ? troubledCount : null;
                return (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => setSelectedMode(mode.value)}
                    className={`rounded-xl border-2 p-4 text-left transition ${
                      isSelected
                        ? "border-blue-500 bg-blue-50"
                        : "border-[var(--line)] bg-white hover:border-blue-200 hover:bg-blue-50/40"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-sm font-semibold ${isSelected ? "text-blue-800" : "text-gray-800"}`}>
                        {mode.label}
                      </span>
                      {badge !== null && (
                        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${isSelected ? "bg-blue-200 text-blue-900" : "bg-slate-100 text-slate-700"}`}>
                          {badge}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">{mode.description}</p>
                  </button>
                );
              })}
            </div>

            <div className="flex flex-wrap items-end gap-4">
              <label className="text-sm text-gray-700">
                Слов в сессии
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={sessionSize}
                  onChange={(e) => setSessionSize(Number(e.target.value || 1))}
                  className="field mt-1 w-24"
                  disabled={starting}
                />
              </label>
              <button
                type="button"
                className="btn-primary"
                onClick={() => startSession(selectedMode)}
                disabled={starting}
              >
                {starting ? "Запускаю..." : "Начать повторение"}
              </button>
            </div>
          </section>
        </>
      ) : null}

      {isSessionActive ? (
        <section className="surface p-4 md:p-6">
          <div className="mx-auto max-w-3xl space-y-4">
            {/* Шапка сессии */}
            <div className="relative z-20 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-white/95 p-3 text-sm text-gray-600">
              <span>
                Режим: <strong>{sessionMode === "srs" ? "По расписанию" : sessionMode === "troubled" ? "Трудные слова" : "Случайные"}</strong>
              </span>
              <span>
                {Math.min(currentIndex, sessionItems.length)} / {sessionItems.length}
              </span>
              <span>
                Помню: <strong className="text-green-700">{sessionCorrect}</strong> · Не помню:{" "}
                <strong className="text-red-700">{sessionIncorrect}</strong>
              </span>
              <button type="button" className="btn-secondary" onClick={() => { resetSession(); loadReviewMeta(); }}>
                Завершить
              </button>
            </div>

            {/* Прогресс */}
            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
                <span>Прогресс сессии</span>
                <span>{progressPercent}%</span>
              </div>
              <div className="h-2 rounded-full bg-slate-200">
                <div className="h-2 rounded-full bg-blue-600 transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
              {currentItem ? (
                <div className="flex flex-wrap gap-2 pt-1">
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

            {/* Карточка + кнопки — на мобиле в одном блоке, кнопки сразу под карточкой */}
            {currentItem ? (
              <div className="flex flex-col gap-3">
                <div className="relative z-0 flex w-full justify-center">
                  <div className="w-full max-w-2xl">
                    <div
                      className="relative isolate h-52 sm:h-80 md:h-[22rem] w-full cursor-pointer overflow-hidden rounded-xl perspective-1000"
                      onClick={() => !submitting && setIsFlipped((f) => !f)}
                      title={isFlipped ? "Нажмите, чтобы скрыть перевод" : "Нажмите, чтобы показать перевод"}
                    >
                      <div
                        className="relative h-full w-full preserve-3d transition-transform duration-500"
                        style={{ transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
                      >
                        <div className="absolute inset-0 backface-hidden rounded-xl">
                          <div className="h-full rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-lg">
                            <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
                              <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800">
                                Слово для изучения
                              </span>
                              <p className="break-all text-2xl sm:text-4xl font-bold text-gray-900">{currentItem.word}</p>
                              {currentItem.source_sentence ? (
                                <p className="max-w-xl text-sm sm:text-base italic leading-relaxed text-gray-600">
                                  &ldquo;{currentItem.source_sentence}&rdquo;
                                </p>
                              ) : null}
                              <p className="text-xs sm:text-sm text-slate-400">Нажмите, чтобы показать перевод</p>
                            </div>
                          </div>
                        </div>

                        <div className="absolute inset-0 backface-hidden rotate-y-180 rounded-xl">
                          <div className="h-full rounded-xl border border-green-200 bg-gradient-to-br from-green-50 to-emerald-50 shadow-lg">
                            <div className="flex h-full flex-col items-center justify-center gap-3 p-4 sm:p-8 text-center">
                              <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
                                Перевод
                              </span>
                              <p className="break-all text-2xl sm:text-4xl font-bold text-gray-900">{currentItem.word}</p>
                              <p className="break-all text-xl sm:text-2xl font-semibold text-green-700">
                                {currentItem.russian_translation || "Перевод не найден"}
                              </p>
                              {currentItem.context_definition ? (
                                <p className="max-w-xl text-sm sm:text-base leading-relaxed text-gray-700">{currentItem.context_definition}</p>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Кнопки ответа — всегда под карточкой, скрыты до переворота */}
                {!sessionFinished ? (
                  <div className={`grid grid-cols-2 gap-3 transition-all duration-300 ${isFlipped ? "opacity-100" : "pointer-events-none opacity-0"}`}>
                    <button
                      type="button"
                      className="rounded-xl border-2 border-red-200 bg-red-50 p-4 text-center transition hover:bg-red-100 active:bg-red-100 disabled:opacity-50"
                      onClick={() => submitAnswer(false)}
                      disabled={submitting || !isFlipped}
                    >
                      <p className="text-base font-semibold text-red-700">Не помню</p>
                      <p className="mt-0.5 hidden text-sm text-red-600 sm:block">Совсем не вспомнил перевод</p>
                    </button>
                    <button
                      type="button"
                      className="rounded-xl border-2 border-green-200 bg-green-50 p-4 text-center transition hover:bg-green-100 active:bg-green-100 disabled:opacity-50"
                      onClick={() => submitAnswer(true)}
                      disabled={submitting || !isFlipped}
                    >
                      <p className="text-base font-semibold text-green-700">Помню</p>
                      <p className="mt-0.5 hidden text-sm text-green-600 sm:block">Сразу вспомнил перевод</p>
                    </button>
                  </div>
                ) : null}
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
                  <button type="button" className="btn-secondary" onClick={() => { resetSession(); loadReviewMeta(); }}>
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
