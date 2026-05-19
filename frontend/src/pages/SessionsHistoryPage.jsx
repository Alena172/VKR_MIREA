import { useEffect, useMemo, useState } from "react";
import { Trophy } from "lucide-react";
import { api, getErrorMessage, isAbortError } from "../lib/api";
import { useAbortControllers } from "../hooks/useAbortControllers";

const ANALYTICS_SESSION_LIMIT = 12;
const HEATMAP_SESSION_LIMIT = 200;
const SPARKLINE_LIMIT = 10;
const WEEK_IN_MS = 7 * 24 * 60 * 60 * 1000;

const EXERCISE_LABELS = {
  sentence_translation_full: "Перевод предложения",
  word_definition_match: "Сопоставление с определением",
  word_scramble: "Собери слово",
  unknown: "Другой формат",
};

const EXERCISE_COLORS = {
  sentence_translation_full: "bg-violet-100 text-violet-700",
  word_definition_match: "bg-sky-100 text-sky-700",
  word_scramble: "bg-orange-100 text-orange-700",
  unknown: "bg-slate-100 text-slate-600",
};

function safeParseJsonArray(value) {
  try { const p = JSON.parse(value); return Array.isArray(p) ? p : []; } catch { return []; }
}

function DefinitionMatchAnswerDetail({ answer }) {
  const expected = safeParseJsonArray(answer.expected_answer);
  const user = safeParseJsonArray(answer.user_answer);
  const userByWord = new Map(user.map((p) => [p.word?.toLowerCase(), p.definition]));
  return (
    <div className="mt-2 space-y-2">
      {expected.map((pair) => {
        const userDef = userByWord.get(pair.word?.toLowerCase());
        const correct = userDef === pair.definition;
        return (
          <div key={pair.word} className="rounded-lg border border-slate-200 bg-white overflow-hidden">
            <div className={`flex items-center gap-2 px-3 py-1.5 ${correct ? "bg-green-50" : "bg-red-50"}`}>
              <span className={`text-sm font-bold ${correct ? "text-green-600" : "text-red-500"}`}>{correct ? "✓" : "✗"}</span>
              <span className="font-bold text-slate-900 text-sm">{pair.word}</span>
            </div>
            <div className="px-3 py-2 text-sm space-y-1">
              {correct ? (
                <p className="text-slate-600">{pair.definition}</p>
              ) : (
                <>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-red-400 mb-0.5">Твой вариант</p><p className="text-slate-600">{userDef || "—"}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-green-600 mb-0.5">Правильно</p><p className="text-slate-700">{pair.definition}</p></div>
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU");
}

function getExerciseTypeFromPrompt(prompt) {
  const normalized = (prompt || "").toLowerCase();
  if (normalized.startsWith("translate sentence into russian:")) return "sentence_translation_full";
  if (normalized.startsWith("match each word with its definition:")) return "word_definition_match";
  if (normalized.startsWith("assemble the word from letters.")) return "word_scramble";
  return "unknown";
}

function getExerciseType(answer) {
  return answer.exercise_type || getExerciseTypeFromPrompt(answer.prompt);
}

function normalizeWord(value) {
  return (value || "").trim().toLowerCase();
}

function findVocabularyWordInPrompt(prompt, vocabularyWords) {
  const normalizedPrompt = normalizeWord(prompt);
  if (!normalizedPrompt) return null;
  for (const word of vocabularyWords) {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp(`\\b${escaped}\\b`, "i").test(normalizedPrompt)) return word;
  }
  return null;
}

function findTrackedWord(answer, vocabularyWords) {
  const explicitWord = normalizeWord(answer.target_word);
  if (explicitWord) return explicitWord;
  return findVocabularyWordInPrompt(answer.prompt, vocabularyWords);
}

/** Считает максимальную серию активных дней из списка сессий. */
function calcMaxStreak(sessions) {
  if (!sessions || sessions.length === 0) return 0;
  const toDay = (iso) => {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth()).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  const days = [...new Set(sessions.map((s) => toDay(s.created_at)))].sort();
  let maxStreak = 1;
  let cur = 1;
  for (let i = 1; i < days.length; i++) {
    const prev = new Date(days[i - 1]);
    const curr = new Date(days[i]);
    const diff = (curr - prev) / (1000 * 60 * 60 * 24);
    if (diff === 1) {
      cur += 1;
      maxStreak = Math.max(maxStreak, cur);
    } else {
      cur = 1;
    }
  }
  return maxStreak;
}

/** Строит данные тепловой карты точности: средний accuracy за день, за последние 16 недель. */
function buildAccuracyHeatmapData(sessions) {
  const dayTotals = new Map(); // date -> { sum, count }
  sessions.forEach((s) => {
    const d = new Date(s.created_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const prev = dayTotals.get(key) || { sum: 0, count: 0 };
    dayTotals.set(key, { sum: prev.sum + Number(s.accuracy || 0), count: prev.count + 1 });
  });

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const startDay = new Date(today);
  startDay.setDate(startDay.getDate() - 111 - ((today.getDay() + 6) % 7));

  const weeks = [];
  let week = [];
  let cursor = new Date(startDay);
  while (cursor <= today) {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(cursor.getDate()).padStart(2, "0")}`;
    const entry = dayTotals.get(key);
    const avgAccuracy = entry ? entry.sum / entry.count : null;
    week.push({ date: key, avgAccuracy, isFuture: cursor > today });
    if (week.length === 7) { weeks.push(week); week = []; }
    cursor.setDate(cursor.getDate() + 1);
  }
  if (week.length > 0) weeks.push(week);
  return weeks;
}

/** Строит данные тепловой карты: Map<"YYYY-MM-DD", count> за последние 16 недель. */
function buildHeatmapData(sessions) {
  const counts = new Map();
  sessions.forEach((s) => {
    const d = new Date(s.created_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  });

  // 16 недель назад от сегодня (112 дней)
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  // Сдвигаем начало к ближайшему понедельнику назад
  const startDay = new Date(today);
  startDay.setDate(startDay.getDate() - 111 - ((today.getDay() + 6) % 7));

  const weeks = [];
  let week = [];
  let cursor = new Date(startDay);
  while (cursor <= today) {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, "0")}-${String(cursor.getDate()).padStart(2, "0")}`;
    week.push({ date: key, count: counts.get(key) || 0, isFuture: cursor > today });
    if (week.length === 7) {
      weeks.push(week);
      week = [];
    }
    cursor.setDate(cursor.getDate() + 1);
  }
  if (week.length > 0) weeks.push(week);
  return weeks;
}

// analyticsSessions — dedicated list from loadAnalyticsData, not the paginated view
function buildAnalytics({ analyticsSessions, allSessions, answersBySessionId, vocabularyWords, masteredCount }) {
  if (!analyticsSessions.length) return null;

  const sorted = [...analyticsSessions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  // Compare the most recent half against the older half for trend
  const splitAt = Math.max(1, Math.ceil(sorted.length / 2));
  const recentHalf = sorted.slice(0, splitAt);
  const previousHalf = sorted.slice(splitAt);

  const averageAccuracy = (items) => {
    if (!items.length) return null;
    return items.reduce((sum, s) => sum + Number(s.accuracy || 0), 0) / items.length;
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

  sorted.forEach((session) => {
    const sessionTime = new Date(session.created_at).getTime() || 0;
    const sessionAnswers = answersBySessionId[session.id] || [];

    sessionAnswers.forEach((answer) => {
      if (answer.is_correct) return;

      const exerciseType = getExerciseType(answer);
      const fs = weakFormats.get(exerciseType) || {
        exerciseType,
        label: EXERCISE_LABELS[exerciseType] || EXERCISE_LABELS.unknown,
        totalMistakes: 0,
      };
      fs.totalMistakes += 1;
      weakFormats.set(exerciseType, fs);

      if (sessionTime < weekBoundary) return;
      const matchedWord = findTrackedWord(answer, vocabularyWords);
      if (!matchedWord) return;
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

  // Sparkline data: last SPARKLINE_LIMIT sessions ordered oldest→newest
  const sparklineData = sorted
    .slice(0, SPARKLINE_LIMIT)
    .reverse()
    .map((s) => ({
      id: s.id,
      accuracy: Number(s.accuracy || 0),
      label: `#${s.id} — ${Math.round(Number(s.accuracy || 0) * 100)}%`,
    }));

  // Personal records
  const allForRecords = allSessions.length ? allSessions : analyticsSessions;
  const bestAccuracy = allForRecords.length
    ? allForRecords.reduce((sum, s) => sum + Number(s.accuracy || 0), 0) / allForRecords.length
    : 0;
  const maxStreak = calcMaxStreak(allForRecords);

  // Heatmaps
  const heatmapWeeks = buildHeatmapData(allForRecords);
  const accuracyHeatmapWeeks = buildAccuracyHeatmapData(allForRecords);

  return {
    trendDelta,
    recentAccuracy,
    previousAccuracy,
    recentSessionCount: sorted.length,
    rankedFormats,
    rankedWords,
    sparklineData,
    records: { bestAccuracy, maxStreak, masteredWords: masteredCount, totalSessions: allForRecords.length },
    heatmapWeeks,
    accuracyHeatmapWeeks,
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

const RECORD_ITEMS = [
  {
    key: "bestAccuracy",
    label: "Средняя точность",
    icon: "🏆",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "maxStreak",
    label: "Макс. серия дней",
    icon: "🔥",
    format: (v) => `${v} ${v === 1 ? "день" : v >= 2 && v <= 4 ? "дня" : "дней"}`,
  },
  {
    key: "masteredWords",
    label: "Освоено слов",
    icon: "⚡",
    format: (v) => `${v} ${v === 1 ? "слово" : v >= 2 && v <= 4 ? "слова" : "слов"}`,
  },
  {
    key: "totalSessions",
    label: "Всего сессий",
    icon: "📈",
    format: (v) => `${v}`,
  },
];

function RecordsBlock({ records }) {
  if (!records) return null;
  return (
    <section className="surface p-4 md:p-5">
      <div className="flex items-center gap-2 mb-4">
        <Trophy className="h-5 w-5 text-amber-500" />
        <h3 className="text-base font-extrabold text-gray-900">Личные рекорды</h3>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {RECORD_ITEMS.map(({ key, label, icon, format }) => (
          <div key={key} className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
            <p className="text-2xl">{icon}</p>
            <p className="mt-1 text-xl font-extrabold text-gray-900">{format(records[key] ?? 0)}</p>
            <p className="mt-0.5 text-xs font-medium text-slate-500 leading-tight">{label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const HEATMAP_COLORS = [
  "bg-slate-100",       // 0 сессий
  "bg-emerald-200",     // 1
  "bg-emerald-400",     // 2
  "bg-emerald-600",     // 3+
];

function heatColor(count) {
  if (count === 0) return HEATMAP_COLORS[0];
  if (count === 1) return HEATMAP_COLORS[1];
  if (count === 2) return HEATMAP_COLORS[2];
  return HEATMAP_COLORS[3];
}

const DAY_LABELS = ["Пн", "", "Ср", "", "Пт", "", "Вс"];

const ACCURACY_COLORS = [
  "bg-slate-100",      // нет данных
  "bg-red-300",        // < 50%
  "bg-amber-300",      // 50–74%
  "bg-emerald-300",    // 75–89%
  "bg-emerald-600",    // 90–100%
];

function accuracyColor(avgAccuracy) {
  if (avgAccuracy === null) return ACCURACY_COLORS[0];
  if (avgAccuracy < 0.5) return ACCURACY_COLORS[1];
  if (avgAccuracy < 0.75) return ACCURACY_COLORS[2];
  if (avgAccuracy < 0.9) return ACCURACY_COLORS[3];
  return ACCURACY_COLORS[4];
}

function HeatmapGrid({ weeks, colorFn, tooltipFn, hasDataFn }) {
  return (
    <div className="w-full overflow-hidden">
      <div className="flex gap-[3px] sm:gap-1.5 w-full">
        <div className="flex flex-col gap-[3px] sm:gap-1.5 mr-0.5 sm:mr-1 shrink-0">
          {DAY_LABELS.map((label, i) => (
            <div key={i} className="h-[10px] sm:h-4 w-4 sm:w-6 flex items-center justify-end">
              <span className="text-[7px] sm:text-[9px] text-slate-400 font-medium">{label}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-[3px] sm:gap-1.5 flex-1 min-w-0">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[3px] sm:gap-1.5 flex-1">
              {week.map((day, di) => (
                <div
                  key={di}
                  className={`group relative rounded-sm w-full aspect-square ${day.isFuture ? "bg-transparent" : colorFn(day)}`}
                >
                  {!day.isFuture && hasDataFn(day) && (
                    <div className="pointer-events-none absolute top-full left-1/2 z-10 mt-1 hidden -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[10px] text-white group-hover:block">
                      {tooltipFn(day)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HeatmapsBlock({ activityWeeks, accuracyWeeks }) {
  if (!activityWeeks?.length && !accuracyWeeks?.length) return null;
  return (
    <section className="surface p-4 md:p-5">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="text-sm font-extrabold text-gray-900 mb-3">Активность за 16 недель</h3>
          <HeatmapGrid
            weeks={activityWeeks}
            colorFn={(day) => heatColor(day.count)}
            hasDataFn={(day) => day.count > 0}
            tooltipFn={(day) => `${day.date}: ${day.count} ${day.count === 1 ? "сессия" : day.count < 5 ? "сессии" : "сессий"}`}
          />
          <div className="mt-2 flex items-center gap-1 sm:gap-1.5 text-[10px] text-slate-400">
            <span>Меньше</span>
            {HEATMAP_COLORS.map((c, i) => <div key={i} className={`h-3 w-3 sm:h-4 sm:w-4 rounded-sm ${c}`} />)}
            <span>Больше</span>
          </div>
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-extrabold text-gray-900 mb-3">Точность по дням за 16 недель</h3>
          <HeatmapGrid
            weeks={accuracyWeeks}
            colorFn={(day) => accuracyColor(day.avgAccuracy)}
            hasDataFn={(day) => day.avgAccuracy !== null}
            tooltipFn={(day) => `${day.date}: ${Math.round(day.avgAccuracy * 100)}%`}
          />
          <div className="mt-2 flex items-center gap-1 sm:gap-1.5 text-[10px] text-slate-400">
            <span>Хуже</span>
            {ACCURACY_COLORS.slice(1).map((c, i) => <div key={i} className={`h-3 w-3 sm:h-4 sm:w-4 rounded-sm ${c}`} />)}
            <span>Лучше</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function TrendBadge({ trendDelta }) {
  if (trendDelta === null)
    return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Нужно больше данных</span>;
  if (trendDelta > 0)
    return <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">↑ Точность растёт: +{trendDelta}%</span>;
  if (trendDelta < 0)
    return <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">↓ Точность просела: {trendDelta}%</span>;
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">→ Точность без изменений</span>;
}

// Pure-CSS sparkline — no external chart library
function AccuracySparkline({ data }) {
  if (!data || data.length === 0) return null;
  const maxVal = 1; // accuracy is 0–1
  return (
    <div className="mt-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Точность по последним сессиям
      </p>
      <div className="flex items-end gap-1" style={{ height: 48 }}>
        {data.map((point) => {
          const heightPct = Math.max(4, Math.round((point.accuracy / maxVal) * 100));
          const isGood = point.accuracy >= 0.7;
          const isMid = point.accuracy >= 0.4;
          const barColor = isGood ? "bg-emerald-400" : isMid ? "bg-amber-400" : "bg-red-400";
          return (
            <div
              key={point.id}
              className="group relative flex-1"
              style={{ height: "100%" }}
              title={point.label}
            >
              <div
                className={`absolute bottom-0 w-full rounded-sm ${barColor} transition-all`}
                style={{ height: `${heightPct}%` }}
              />
              {/* tooltip on hover */}
              <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[10px] text-white group-hover:block">
                {point.label}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-400">
        <span>старее</span>
        <span>новее</span>
      </div>
    </div>
  );
}

// Inline accuracy bar for a session row
function AccuracyBar({ accuracy }) {
  const pct = Math.round(Number(accuracy || 0) * 100);
  const color = pct >= 70 ? "bg-emerald-400" : pct >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-semibold text-slate-700">{pct}%</span>
    </div>
  );
}

// Exercise type chip for an answer card
function ExerciseChip({ exerciseType }) {
  const label = EXERCISE_LABELS[exerciseType] || EXERCISE_LABELS.unknown;
  const color = EXERCISE_COLORS[exerciseType] || EXERCISE_COLORS.unknown;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${color}`}>
      {label}
    </span>
  );
}

export default function SessionsHistoryPage({ onError }) {
  const [sessions, setSessions] = useState([]);
  // Separate state for analytics — always holds the last ANALYTICS_SESSION_LIMIT sessions
  const [analyticsSessions, setAnalyticsSessions] = useState([]);
  // All sessions for heatmap and records (up to HEATMAP_SESSION_LIMIT)
  const [allSessions, setAllSessions] = useState([]);
  const [masteredCount, setMasteredCount] = useState(0);
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

  // Analytics always uses the dedicated analyticsSessions, never the paginated view
  const analytics = useMemo(
    () => buildAnalytics({ analyticsSessions, allSessions, answersBySessionId, vocabularyWords, masteredCount }),
    [analyticsSessions, allSessions, answersBySessionId, vocabularyWords, masteredCount],
  );

  async function loadSessions(targetPage = safePage) {
    setLoadingSessions(true);
    const controller = registerController();
    try {
      const offset = (targetPage - 1) * pageSize;
      const data = await api.listSessionsMe(
        { limit: pageSize, offset, min_accuracy: minAccuracy, max_accuracy: maxAccuracy, date_from: dateFrom, date_to: dateTo },
        { signal: controller.signal },
      );
      setSessions(data.items);
      setTotal(data.total);
      const nextTotalPages = Math.max(1, Math.ceil(data.total / pageSize));
      if (targetPage > nextTotalPages) setPage(nextTotalPages);
      if (data.items.length === 0) {
        setSelectedSessionId(null);
        setAnswers([]);
      }
    } catch (error) {
      if (!isAbortError(error)) onError(getErrorMessage(error));
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
      if (!isAbortError(error)) onError(getErrorMessage(error));
    } finally {
      releaseController(controller);
      setLoadingAnswers(false);
    }
  }

  async function loadAnalyticsData() {
    setLoadingAnalytics(true);
    const controller = registerController();
    try {
      const [recentSessions, allSessionsResp, vocabulary, reviewSummary] = await Promise.all([
        api.listSessionsMe({ limit: ANALYTICS_SESSION_LIMIT, offset: 0 }, { signal: controller.signal }),
        api.listSessionsMe({ limit: HEATMAP_SESSION_LIMIT, offset: 0 }, { signal: controller.signal }),
        api.listVocabularyMe({ signal: controller.signal }),
        api.reviewSummary({ signal: controller.signal }),
      ]);

      const recentItems = recentSessions.items || [];
      setAnalyticsSessions(recentItems);
      setAllSessions(allSessionsResp.items || []);
      setMasteredCount(reviewSummary?.mastered ?? 0);
      setVocabularyWords(
        vocabulary
          .map((item) => normalizeWord(item.english_lemma))
          .filter(Boolean)
          .sort((a, b) => b.length - a.length),
      );

      const missingSessionIds = recentItems
        .map((item) => item.id)
        .filter((id) => !answersBySessionId[id]);

      if (missingSessionIds.length) {
        const results = await Promise.all(
          missingSessionIds.map((id) => api.listSessionAnswersMe(id, { signal: controller.signal })),
        );
        setAnswersBySessionId((prev) => {
          const next = { ...prev };
          missingSessionIds.forEach((id, idx) => { next[id] = results[idx]; });
          return next;
        });
      }
    } catch (error) {
      if (!isAbortError(error)) onError(getErrorMessage(error));
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
            <p className="muted mt-1 text-sm">Отслеживай прогресс и находи слова, которые стоит повторить.</p>
          </div>
          <button
            className="btn-secondary"
            onClick={() => { loadSessions(safePage); loadAnalyticsData(); }}
            type="button"
          >
            Обновить
          </button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <AnalyticsCard title="Точность по недавним сессиям">
          {loadingAnalytics ? (
            <p className="muted text-sm">Собираю аналитику...</p>
          ) : analytics ? (
            <div className="space-y-3">
              <TrendBadge trendDelta={analytics.trendDelta} />
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Средняя точность</p>
                <p className="mt-1 text-2xl font-extrabold text-slate-900">
                  {analytics.recentAccuracy !== null ? `${Math.round(analytics.recentAccuracy * 100)}%` : "-"}
                </p>
              </div>
              <AccuracySparkline data={analytics.sparklineData} />
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

      {!loadingAnalytics && analytics?.records && (
        <RecordsBlock records={analytics.records} />
      )}

      {!loadingAnalytics && (analytics?.heatmapWeeks || analytics?.accuracyHeatmapWeeks) && (
        <HeatmapsBlock activityWeeks={analytics.heatmapWeeks} accuracyWeeks={analytics.accuracyHeatmapWeeks} />
      )}

      <section className="surface p-4 md:p-5">
        <div className="grid gap-3 grid-cols-2 md:grid-cols-5">
          <label className="text-sm">
            Мин. точность
            <input
              type="number" min={0} max={1} step="0.01" value={minAccuracy}
              onChange={(e) => setMinAccuracy(e.target.value)}
              className="field mt-1" placeholder="0.0"
            />
          </label>
          <label className="text-sm">
            Макс. точность
            <input
              type="number" min={0} max={1} step="0.01" value={maxAccuracy}
              onChange={(e) => setMaxAccuracy(e.target.value)}
              className="field mt-1" placeholder="1.0"
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
            <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="field mt-1">
              {[5, 10, 20, 50].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-3">
          <button type="button" className="btn-secondary" onClick={resetFilters}>Сбросить</button>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="surface p-4 md:p-5">
          <h3 className="text-base font-extrabold text-gray-900">Сессии ({total})</h3>
          {loadingSessions ? <p className="muted mb-2 mt-2 text-sm">Загрузка...</p> : null}
          <ul className="mt-2 space-y-2">
            {sessions.map((session) => {
              const pct = Math.round(Number(session.accuracy || 0) * 100);
              const trendIcon = (() => {
                const idx = analyticsSessions.findIndex((s) => s.id === session.id);
                if (idx < 0 || idx >= analyticsSessions.length - 1) return null;
                const prev = analyticsSessions[idx + 1];
                const delta = Number(session.accuracy || 0) - Number(prev.accuracy || 0);
                if (delta > 0.02) return <span className="text-emerald-600 font-bold">↑</span>;
                if (delta < -0.02) return <span className="text-red-500 font-bold">↓</span>;
                return <span className="text-slate-400">→</span>;
              })();
              return (
                <li
                  key={session.id}
                  className={`rounded-xl border p-3 ${
                    selectedSessionId === session.id ? "border-blue-600 bg-blue-50" : "border-[var(--line)] bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 text-sm">
                      <div className="flex items-center gap-2 font-extrabold text-gray-900">
                        Сессия #{session.id}
                        {trendIcon}
                      </div>
                      <div className="muted">{formatDate(session.created_at)}</div>
                      <div className="text-[var(--text)]">
                        {session.correct}/{session.total} правильно
                      </div>
                      <AccuracyBar accuracy={session.accuracy} />
                    </div>
                    <button type="button" className="btn-secondary shrink-0" onClick={() => loadAnswers(session.id)}>
                      Ответы
                    </button>
                  </div>
                </li>
              );
            })}
            {!loadingSessions && sessions.length === 0 ? <li className="muted text-sm">Сессий по фильтрам нет.</li> : null}
          </ul>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="muted">Страница {safePage}/{totalPages}</span>
            <div className="flex gap-2">
              <button
                type="button" className="btn-secondary disabled:opacity-50"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={safePage <= 1}
              >
                Назад
              </button>
              <button
                type="button" className="btn-secondary disabled:opacity-50"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))} disabled={safePage >= totalPages}
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
              {answers.map((answer) => {
                const exerciseType = getExerciseType(answer);
                const cardBg = answer.is_correct
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-red-200 bg-red-50";
                return (
                  <li key={answer.id} className={`rounded-xl border p-3 text-sm ${cardBg}`}>
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <ExerciseChip exerciseType={exerciseType} />
                      <span className={`text-xs font-bold ${answer.is_correct ? "text-emerald-700" : "text-red-700"}`}>
                        {answer.is_correct ? "✓ Верно" : "✗ Ошибка"}
                      </span>
                    </div>
                    {exerciseType === "word_definition_match" ? (
                      <DefinitionMatchAnswerDetail answer={answer} />
                    ) : exerciseType === "word_scramble" ? (
                      <div className="space-y-1">
                        <p className="font-semibold text-slate-900">{answer.target_word || answer.prompt}</p>
                        <div className="flex gap-4 mt-1">
                          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-0.5">Твой ответ</p><p className="font-bold uppercase tracking-wide">{answer.user_answer || "—"}</p></div>
                          {!answer.is_correct && <div><p className="text-xs font-semibold uppercase tracking-wide text-green-600 mb-0.5">Правильно</p><p className="font-bold uppercase tracking-wide">{answer.expected_answer || "—"}</p></div>}
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className="font-semibold text-gray-900">{answer.prompt}</p>
                        <div className="mt-2 space-y-1 text-slate-600">
                          <p><span className="font-semibold text-slate-700">Ответ:</span> {answer.user_answer}</p>
                          {!answer.is_correct && <p><span className="font-semibold text-green-700">Правильно:</span> {answer.expected_answer}</p>}
                        </div>
                      </>
                    )}
                  </li>
                );
              })}
              {answers.length === 0 ? <li className="muted text-sm">В этой сессии нет ответов.</li> : null}
            </ul>
          ) : null}
        </section>
      </div>
    </section>
  );
}
