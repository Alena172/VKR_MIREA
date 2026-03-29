import { useEffect, useMemo, useState } from "react";
import { api, getErrorMessage, isAbortError } from "../lib/api";
import { useAbortControllers } from "../hooks/useAbortControllers";

const ANALYTICS_SESSION_LIMIT = 12;
const WEEK_IN_MS = 7 * 24 * 60 * 60 * 1000;

const EXERCISE_LABELS = {
  sentence_translation_full: "Перевод предложения",
  word_definition_match: "Сопоставление с определением",
  word_scramble: "Собери слово",
  unknown: "Другой формат",
};

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
}

function getExerciseTypeFromPrompt(prompt) {
  const normalized = (prompt || "").toLowerCase();
  if (normalized.startsWith("translate sentence into russian:")) {
    return "sentence_translation_full";
  }
  if (normalized.startsWith("match each word with its definition:")) {
    return "word_definition_match";
  }
  if (normalized.startsWith("assemble the word from letters.")) {
    return "word_scramble";
  }
  return "unknown";
}

function normalizeWord(value) {
  return (value || "").trim().toLowerCase();
}

function findVocabularyWordInPrompt(prompt, vocabularyWords) {
  const normalizedPrompt = normalizeWord(prompt);
  if (!normalizedPrompt) {
    return null;
  }

  for (const word of vocabularyWords) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp(`\\b${escaped}\\b`, "i").test(normalizedPrompt)) {
      return word;
    }
  }
  return null;
}

function buildAnalytics({ sessions, answersBySessionId, vocabularyWords }) {
  if (!sessions.length) {
    return null;
  }

  const recentSessions = [...sessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const recentHalf = recentSessions.slice(0, Math.max(1, Math.ceil(recentSessions.length / 2)));
  const previousHalf = recentSessions.slice(recentHalf.length);

  const averageAccuracy = (items) => {
    if (!items.length) {
      return null;
    }
    return items.reduce((sum, session) => sum + Number(session.accuracy || 0), 0) / items.length;
  };

  const recentAccuracy = averageAccuracy(recentHalf);
  const previousAccuracy = averageAccuracy(previousHalf);
  const trendDelta =
    recentAccuracy !== null && previousAccuracy !== null
      ? Math.round((recentAccuracy - previousAccuracy) * 100)
      : null;

  const weakFormats = new Map();
  const weakWords = new Map();
  const weekBoundary = Date.now() - WEEK_IN_MS;

  recentSessions.forEach((session) => {
    const sessionDate = new Date(session.created_at);
    const sessionTime = Number.isNaN(sessionDate.getTime()) ? 0 : sessionDate.getTime();
    const answers = answersBySessionId[session.id] || [];

    answers.forEach((answer) => {
      if (answer.is_correct) {
        return;
      }

      const exerciseType = getExerciseTypeFromPrompt(answer.prompt);
      const formatStats = weakFormats.get(exerciseType) || {
        exerciseType,
        label: EXERCISE_LABELS[exerciseType] || EXERCISE_LABELS.unknown,
        totalMistakes: 0,
      };
      formatStats.totalMistakes += 1;
      weakFormats.set(exerciseType, formatStats);

      if (sessionTime < weekBoundary) {
        return;
      }

      const matchedWord = findVocabularyWordInPrompt(answer.prompt, vocabularyWords);
      if (!matchedWord) {
        return;
      }
      const current = weakWords.get(matchedWord) || { word: matchedWord, mistakes: 0 };
      current.mistakes += 1;
      weakWords.set(matchedWord, current);
    });
  });

  const rankedFormats = [...weakFormats.values()]
    .sort((a, b) => b.totalMistakes - a.totalMistakes || a.label.localeCompare(b.label))
    .slice(0, 3);
  const rankedWords = [...weakWords.values()]
    .sort((a, b) => b.mistakes - a.mistakes || a.word.localeCompare(b.word))
    .slice(0, 5);

  return {
    trendDelta,
    recentAccuracy,
    previousAccuracy,
    recentSessionCount: recentSessions.length,
    rankedFormats,
    rankedWords,
  };
}

function AnalyticsCard({ title, children }) {
  return (
    <section className="surface p-4 md:p-5">
      <h3 className="text-base font-extrabold text-gray-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function TrendBadge({ trendDelta }) {
  if (trendDelta === null) {
    return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Нужно больше данных</span>;
  }
  if (trendDelta > 0) {
    return <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">Точность растёт: +{trendDelta}%</span>;
  }
  if (trendDelta < 0) {
    return <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">Точность просела: {trendDelta}%</span>;
  }
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Точность без изменений</span>;
}

export default function SessionsHistoryPage({ onError }) {
  const [sessions, setSessions] = useState([]);
  const [total, setTotal] = useState(0);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [answersBySessionId, setAnswersBySessionId] = useState({});
  const [vocabularyWords, setVocabularyWords] = useState([]);
  const [loadingAnswers, setLoadingAnswers] = useState(false);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [minAccuracy, setMinAccuracy] = useState("");
  const [maxAccuracy, setMaxAccuracy] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const { registerController, releaseController } = useAbortControllers();

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, totalPages);

  const analytics = useMemo(
    () => buildAnalytics({ sessions, answersBySessionId, vocabularyWords }),
    [answersBySessionId, sessions, vocabularyWords],
  );

  async function loadSessions(targetPage = safePage) {
    setLoadingSessions(true);
    const controller = registerController();
    try {
      const offset = (targetPage - 1) * pageSize;
      const data = await api.listSessionsMe(
        {
          limit: pageSize,
          offset,
          min_accuracy: minAccuracy,
          max_accuracy: maxAccuracy,
          date_from: dateFrom,
          date_to: dateTo,
        },
        { signal: controller.signal },
      );
      setSessions(data.items);
      setTotal(data.total);
      const nextTotalPages = Math.max(1, Math.ceil(data.total / pageSize));
      if (targetPage > nextTotalPages) {
        setPage(nextTotalPages);
      }
      if (data.items.length === 0) {
        setSelectedSessionId(null);
        setAnswers([]);
      }
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setLoadingSessions(false);
    }
  }

  async function loadAnswers(sessionId) {
    setLoadingAnswers(true);
    const controller = registerController();
    try {
      const data = await api.listSessionAnswersMe(sessionId, { signal: controller.signal });
      setSelectedSessionId(sessionId);
      setAnswers(data);
      setAnswersBySessionId((prev) => ({ ...prev, [sessionId]: data }));
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setLoadingAnswers(false);
    }
  }

  async function loadAnalyticsData() {
    setLoadingAnalytics(true);
    const controller = registerController();
    try {
      const [recentSessions, vocabulary] = await Promise.all([
        api.listSessionsMe({ limit: ANALYTICS_SESSION_LIMIT, offset: 0 }, { signal: controller.signal }),
        api.listVocabularyMe({ signal: controller.signal }),
      ]);

      const recentItems = recentSessions.items || [];
      setSessions((prev) => {
        const currentIds = new Set(prev.map((item) => item.id));
        const merged = [...prev];
        recentItems.forEach((item) => {
          if (!currentIds.has(item.id)) {
            merged.push(item);
          }
        });
        return merged;
      });
      setVocabularyWords(
        vocabulary
          .map((item) => normalizeWord(item.english_lemma))
          .filter(Boolean)
          .sort((a, b) => b.length - a.length),
      );

      const missingSessionIds = recentItems
        .map((item) => item.id)
        .filter((sessionId) => !answersBySessionId[sessionId]);

      if (missingSessionIds.length) {
        const results = await Promise.all(
          missingSessionIds.map((sessionId) => api.listSessionAnswersMe(sessionId, { signal: controller.signal })),
        );
        setAnswersBySessionId((prev) => {
          const next = { ...prev };
          missingSessionIds.forEach((sessionId, index) => {
            next[sessionId] = results[index];
          });
          return next;
        });
      }
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setLoadingAnalytics(false);
    }
  }

  function resetFilters() {
    setMinAccuracy("");
    setMaxAccuracy("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  }

  useEffect(() => {
    loadSessions(safePage);
  }, [page, pageSize, minAccuracy, maxAccuracy, dateFrom, dateTo]);

  useEffect(() => {
    loadAnalyticsData();
  }, []);

  return (
    <section className="space-y-4">
      <header className="surface p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="kicker">History</p>
            <h2 className="section-title">История сессий</h2>
            <p className="muted mt-1 text-sm">Смотри не только список попыток, но и то, где обучение реально буксует.</p>
          </div>
          <button
            className="btn-secondary"
            onClick={() => {
              loadSessions(safePage);
              loadAnalyticsData();
            }}
            type="button"
          >
            Обновить
          </button>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-3">
        <AnalyticsCard title="Точность по недавним сессиям">
          {loadingAnalytics ? (
            <p className="muted text-sm">Собираю аналитику...</p>
          ) : analytics ? (
            <div className="space-y-3">
              <TrendBadge trendDelta={analytics.trendDelta} />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Последние сессии</p>
                  <p className="mt-1 text-2xl font-extrabold text-slate-900">
                    {analytics.recentAccuracy !== null ? `${Math.round(analytics.recentAccuracy * 100)}%` : "-"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Окно анализа</p>
                  <p className="mt-1 text-2xl font-extrabold text-slate-900">{analytics.recentSessionCount}</p>
                </div>
              </div>
            </div>
          ) : (
            <p className="muted text-sm">Пока недостаточно данных для тренда.</p>
          )}
        </AnalyticsCard>

        <AnalyticsCard title="Чаще всего ошибки здесь">
          {loadingAnalytics ? (
            <p className="muted text-sm">Собираю аналитику...</p>
          ) : analytics?.rankedFormats?.length ? (
            <div className="space-y-2">
              {analytics.rankedFormats.map((item) => (
                <div key={item.exerciseType} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{item.label}</p>
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                      ошибок: {item.totalMistakes}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted text-sm">Пока не видно устойчивого слабого формата.</p>
          )}
        </AnalyticsCard>

        <AnalyticsCard title="Самые проблемные слова недели">
          {loadingAnalytics ? (
            <p className="muted text-sm">Собираю аналитику...</p>
          ) : analytics?.rankedWords?.length ? (
            <div className="space-y-2">
              {analytics.rankedWords.map((item) => (
                <div key={item.word} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{item.word}</p>
                    <span className="rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700">
                      ошибок: {item.mistakes}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted text-sm">За последнюю неделю ещё не накопилось явных проблемных слов.</p>
          )}
        </AnalyticsCard>
      </div>

      <section className="surface p-4 md:p-5">
        <div className="grid gap-3 md:grid-cols-5">
          <label className="text-sm">
            Мин. точность
            <input
              type="number"
              min={0}
              max={1}
              step="0.01"
              value={minAccuracy}
              onChange={(e) => setMinAccuracy(e.target.value)}
              className="field mt-1"
              placeholder="0.0"
            />
          </label>
          <label className="text-sm">
            Макс. точность
            <input
              type="number"
              min={0}
              max={1}
              step="0.01"
              value={maxAccuracy}
              onChange={(e) => setMaxAccuracy(e.target.value)}
              className="field mt-1"
              placeholder="1.0"
            />
          </label>
          <label className="text-sm">
            Дата с
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="field mt-1" />
          </label>
          <label className="text-sm">
            Дата по
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="field mt-1" />
          </label>
          <label className="text-sm">
            На страницу
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="field mt-1"
            >
              {[5, 10, 20, 50].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3">
          <button type="button" className="btn-secondary" onClick={resetFilters}>
            Сбросить
          </button>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="surface p-4 md:p-5">
          <h3 className="text-base font-extrabold text-gray-900">Сессии ({total})</h3>
          {loadingSessions ? <p className="muted mb-2 mt-2 text-sm">Загрузка...</p> : null}
          <ul className="mt-2 space-y-2">
            {sessions.map((session) => (
              <li
                key={session.id}
                className={`rounded-xl border p-3 ${
                  selectedSessionId === session.id ? "border-blue-600 bg-blue-50" : "border-[var(--line)] bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm">
                    <div className="font-extrabold text-gray-900">Сессия #{session.id}</div>
                    <div className="muted">{formatDate(session.created_at)}</div>
                    <div className="text-[var(--text)]">
                      {session.correct}/{session.total} (точность {Math.round(Number(session.accuracy || 0) * 100)}%)
                    </div>
                  </div>
                  <button type="button" className="btn-secondary" onClick={() => loadAnswers(session.id)}>
                    Ответы
                  </button>
                </div>
              </li>
            ))}
            {!loadingSessions && sessions.length === 0 ? <li className="muted text-sm">Сессий по фильтрам нет.</li> : null}
          </ul>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="muted">Страница {safePage}/{totalPages}</span>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary disabled:opacity-50"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={safePage <= 1}
              >
                Назад
              </button>
              <button
                type="button"
                className="btn-secondary disabled:opacity-50"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={safePage >= totalPages}
              >
                Вперед
              </button>
            </div>
          </div>
        </section>

        <section className="surface p-4 md:p-5">
          <h3 className="text-base font-extrabold text-gray-900">Ответы</h3>
          {loadingAnswers ? <p className="muted mt-2 text-sm">Загрузка...</p> : null}
          {!loadingAnswers && selectedSessionId === null ? (
            <p className="muted mt-2 text-sm">Выберите сессию, чтобы посмотреть ответы.</p>
          ) : null}
          {!loadingAnswers && selectedSessionId !== null ? (
            <ul className="mt-2 space-y-2">
              {answers.map((answer) => (
                <li key={answer.id} className="rounded-xl border border-[var(--line)] bg-white p-3 text-sm">
                  <div className="font-semibold">{answer.prompt || "Без prompt"}</div>
                  <div className="mt-1 muted">
                    Ожидалось: <span className="font-medium text-[var(--text)]">{answer.expected_answer || "-"}</span>
                  </div>
                  <div className="muted">
                    Ответ: <span className="font-medium text-[var(--text)]">{answer.user_answer}</span>
                  </div>
                  <div className={answer.is_correct ? "text-green-700" : "text-red-700"}>
                    {answer.is_correct ? "Верно" : "Ошибка"}
                  </div>
                  {answer.explanation_ru ? <div className="mt-1 text-[var(--text)]">{answer.explanation_ru}</div> : null}
                </li>
              ))}
              {answers.length === 0 ? <li className="muted text-sm">В этой сессии нет ответов.</li> : null}
            </ul>
          ) : null}
        </section>
      </div>
    </section>
  );
}
