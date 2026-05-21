import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Activity, Award, BarChart3, BookMarked, BookOpen, ChevronDown, Clock, Flame, Home, Plus, Star, Target, TrendingUp, Trophy } from "lucide-react";
import VocabularyPage from "./pages/VocabularyPage";
import ReviewPage from "./pages/ReviewPage";
import TrainingPage from "./pages/TrainingPage";
import SessionsHistoryPage from "./pages/SessionsHistoryPage";
import { useAbortControllers } from "./hooks/useAbortControllers";
import { api, clearAuthToken, getErrorMessage, isAbortError, setAuthToken } from "./lib/api";

const USER_ID_KEY = "vkr_user_id";
const AUTH_TOKEN_KEY = "vkr_auth_token";

const NAVIGATION = [
  { name: "Главная", href: "/", icon: Home },
  { name: "Словарь", href: "/vocabulary", icon: BookMarked },
  { name: "Упражнения", href: "/exercises", icon: Activity },
  { name: "Повторение", href: "/review", icon: BookOpen },
  { name: "История", href: "/history", icon: BarChart3 },
];

function AuthPage({ onAuth }) {
  const [authMode, setAuthMode] = useState("login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (authMode === "register" && password !== passwordConfirm) {
      setError("Пароли не совпадают.");
      return;
    }
    try {
      const authData =
        authMode === "register"
          ? await api.authRegister({ email, password, full_name: name, cefr_level: "A2" })
          : await api.authLogin({ email, password });
      setAuthToken(authData.access_token);
      localStorage.setItem(USER_ID_KEY, String(authData.user_id));
      onAuth(authData);
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4 sm:p-6">
      <div className="card w-full max-w-sm">
        <div className="card-header text-center">
          <h1 className="text-2xl font-bold text-primary-600">Учебная система</h1>
          <p className="text-sm text-gray-500 mt-1">Платформа изучения английского</p>
        </div>
        <div className="card-body">
          <div className="mb-5 inline-flex w-full rounded-lg bg-gray-100 p-1">
            <button
              type="button"
              onClick={() => { setAuthMode("login"); setError(""); }}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${authMode === "login" ? "bg-white text-primary-700 shadow-sm" : "text-gray-600 hover:text-gray-800"}`}
            >
              Вход
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode("register"); setError(""); }}
              className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${authMode === "register" ? "bg-white text-primary-700 shadow-sm" : "text-gray-600 hover:text-gray-800"}`}
            >
              Регистрация
            </button>
          </div>

          <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
            <input
              className="form-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
            />
            {authMode === "register" && (
              <input
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Имя (необязательно)"
              />
            )}
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Пароль"
              required
            />
            {authMode === "register" && (
              <input
                className="form-input"
                type="password"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                placeholder="Повторите пароль"
                required
              />
            )}
            <button className="btn-primary mt-1" type="submit">
              {authMode === "register" ? "Создать аккаунт" : "Войти"}
            </button>
          </form>

          {error && (
            <p className="mt-3 rounded-lg border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [error, setError] = useState("");
  const [authToken, setAuthTokenState] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY) || "");
  const [userId, setUserId] = useState(() => {
    const stored = localStorage.getItem(USER_ID_KEY);
    return stored ? Number(stored) : 0;
  });
  const [userEmail, setUserEmail] = useState("");
  const [userName, setUserName] = useState("");
  const [userCefr, setUserCefr] = useState("A1");

  function handleAuth(authData) {
    setAuthTokenState(authData.access_token);
    setUserId(authData.user_id);
    if (authData.user) {
      setUserEmail(authData.user.email || "");
      setUserName(authData.user.full_name || "");
      setUserCefr(authData.user.cefr_level || "A2");
    }
  }

  function logout() {
    clearAuthToken();
    setAuthTokenState("");
    setUserId(0);
    setUserEmail("");
    setUserName("");
    setUserCefr("A1");
    localStorage.removeItem(USER_ID_KEY);
  }

  useEffect(() => {
    if (authToken && userId && !userEmail) {
      api
        .authMe()
        .then((data) => {
          setUserEmail(data.email);
          setUserName(data.full_name || "");
          setUserCefr(data.cefr_level);
        })
        .catch(() => {});
    }
  }, [authToken, userId, userEmail]);

  if (!userId) {
    return (
      <Routes>
        <Route path="*" element={<AuthPage onAuth={handleAuth} />} />
      </Routes>
    );
  }

  return (
    <AppShell
      userEmail={userEmail}
      userName={userName}
      userCefr={userCefr}
      setUserCefr={setUserCefr}
      error={error}
      setError={setError}
      logout={logout}
    />
  );
}

function AppShell({ userEmail, userName, userCefr, setUserCefr, error, setError, logout }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Прогреваем буфер переводов при логине и каждые 90 секунд.
  // Только sentence_translation_full — остальные режимы генерируются быстро без буфера.
  useEffect(() => {
    let controller = new AbortController();

    function ping() {
      controller.abort();
      controller = new AbortController();
      api
        .generateExercisesMe(
          { size: 10, mode: "sentence_translation_full", vocabulary_ids: [], fast_start: false, incremental: true },
          { signal: controller.signal },
        )
        .catch(() => {});
    }

    ping();
    const interval = setInterval(ping, 90_000);
    return () => {
      clearInterval(interval);
      controller.abort();
    };
  }, []);

  async function updateCefr(level) {
    try {
      const data = await api.updateMe({ cefr_level: level });
      setUserCefr(data.cefr_level);
      setProfileOpen(false);
    } catch (e) {
      setError(getErrorMessage(e));
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Боковая навигация — только на планшете и десктопе */}
      <aside className="hidden md:flex w-56 lg:w-64 bg-white shadow-lg border-r border-gray-200 flex-col h-screen sticky top-0 shrink-0">
        <div className="p-4 lg:p-6 border-b border-gray-200">
          <h1 className="text-xl lg:text-2xl font-bold text-primary-600">Учебная система</h1>
          <p className="text-sm text-gray-600 mt-1">Умный словарь</p>

          <div className="mt-4 relative" ref={profileRef}>
            <button
              type="button"
              onClick={() => setProfileOpen((v) => !v)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-left hover:bg-gray-50 transition-colors"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700 font-bold text-sm">
                {(userName || userEmail)?.[0]?.toUpperCase() ?? "?"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-800 truncate">{userName || userEmail || "—"}</p>
                <p className="text-xs text-gray-500">Уровень: {userCefr}</p>
              </div>
              <ChevronDown className={`h-4 w-4 text-gray-400 shrink-0 transition-transform ${profileOpen ? "rotate-180" : ""}`} />
            </button>

            {profileOpen && (
              <div className="absolute left-4 right-4 z-50 mt-1 rounded-lg border border-gray-200 bg-white shadow-lg overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Уровень языка</p>
                </div>
                <div className="p-1">
                  {["A1", "A2", "B1", "B2", "C1", "C2"].map((level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => updateCefr(level)}
                      className={`w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors ${
                        level === userCefr
                          ? "bg-primary-50 text-primary-700 font-semibold"
                          : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {level}
                      {level === userCefr && <span className="ml-2 text-primary-400">✓</span>}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <nav className="p-3 lg:p-4 flex-1 overflow-y-auto">
          {NAVIGATION.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.href}
                to={item.href}
                end={item.href === "/"}
                className={({ isActive }) =>
                  `flex items-center px-3 lg:px-4 py-3 mb-1 rounded-lg transition-colors ${
                    isActive
                      ? "bg-primary-50 text-primary-600 border-r-2 border-primary-600"
                      : "text-gray-600 hover:bg-gray-100"
                  }`
                }
              >
                <Icon className="h-5 w-5 mr-3 shrink-0" />
                <span className="font-medium text-sm lg:text-base truncate">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="px-3 lg:px-4 pb-4 border-t border-gray-200 pt-4">
          <button type="button" onClick={logout} className="btn-secondary w-full text-sm">
            Выйти
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {/* Верхняя шапка — только на мобильном */}
        <header className="md:hidden sticky top-0 z-30 flex items-center justify-between bg-white border-b border-gray-200 px-4 py-3 shadow-sm">
          <h1 className="text-lg font-bold text-primary-600">Учебная система</h1>
          <div className="relative" ref={profileRef}>
            <button
              type="button"
              onClick={() => setProfileOpen((v) => !v)}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700 font-bold text-sm">
                {(userName || userEmail)?.[0]?.toUpperCase() ?? "?"}
              </div>
              <span className="text-xs text-gray-500">{userCefr}</span>
              <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${profileOpen ? "rotate-180" : ""}`} />
            </button>
            {profileOpen && (
              <div className="absolute right-0 z-50 mt-1 w-48 rounded-lg border border-gray-200 bg-white shadow-lg overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Уровень языка</p>
                </div>
                <div className="p-1">
                  {["A1", "A2", "B1", "B2", "C1", "C2"].map((level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => updateCefr(level)}
                      className={`w-full text-left px-3 py-1.5 rounded-md text-sm transition-colors ${
                        level === userCefr ? "bg-primary-50 text-primary-700 font-semibold" : "text-gray-700 hover:bg-gray-50"
                      }`}
                    >
                      {level}{level === userCefr && <span className="ml-2 text-primary-400">✓</span>}
                    </button>
                  ))}
                </div>
                <div className="p-2 border-t border-gray-100">
                  <button type="button" onClick={logout} className="btn-secondary w-full text-sm">Выйти</button>
                </div>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-auto pb-20 md:pb-0">
          <div className="p-4 md:p-6 lg:p-8">
            <Routes>
              <Route path="/" element={<HomePage onError={setError} />} />
              <Route path="/vocabulary" element={<VocabularyPage onError={setError} />} />
              <Route path="/exercises" element={<TrainingPage onError={setError} />} />
              <Route path="/review" element={<ReviewPage onError={setError} />} />
              <Route path="/history" element={<SessionsHistoryPage onError={setError} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>

            {error ? (
              <div className="mt-6 rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700">{error}</div>
            ) : null}
          </div>
        </main>

        {/* Нижняя навигация — только на мобильном */}
        <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-gray-200 bg-white px-1 py-2 shadow-[0_-2px_8px_rgba(0,0,0,0.06)]">
          {NAVIGATION.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.href}
                to={item.href}
                end={item.href === "/"}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg transition-colors min-w-0 flex-1 ${
                    isActive ? "text-primary-600" : "text-gray-500"
                  }`
                }
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span className="text-[10px] font-medium leading-tight truncate max-w-full">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

/** Считает streak активных дней подряд до сегодня (включительно). */
function calcStreak(sessions) {
  if (!sessions || sessions.length === 0) return 0;

  const toDay = (iso) => {
    const d = new Date(iso);
    return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
  };

  const activeDays = new Set(sessions.map((s) => toDay(s.created_at)));
  const today = new Date();
  let streak = 0;

  for (let i = 0; i < 365; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    if (activeDays.has(toDay(d.toISOString()))) {
      streak += 1;
    } else {
      break;
    }
  }
  return streak;
}

/**
 * Уровни по абсолютному количеству освоенных слов.
 * threshold — минимальное число слов со статусом "закрепляется" для входа в уровень.
 */
const LEVELS = [
  { label: "Старт",       threshold: 0,   color: "bg-blue-400"  },
  { label: "Базовый",     threshold: 10,  color: "bg-blue-500"  },
  { label: "Средний",     threshold: 30,  color: "bg-blue-600"  },
  { label: "Продвинутый", threshold: 75,  color: "bg-blue-700"  },
  { label: "Мастер",      threshold: 150, color: "bg-blue-800"  },
];

function vocabLevel(mastered) {
  let tier = 0;
  for (let i = LEVELS.length - 1; i >= 0; i--) {
    if (mastered >= LEVELS[i].threshold) { tier = i; break; }
  }
  const current = LEVELS[tier];
  const next = LEVELS[tier + 1] ?? null;
  return { label: current.label, tier, color: current.color, next };
}

function StreakBlock({ streak, sessionsTotal }) {
  const todayHasSession = streak > 0;
  const isAtRisk = !todayHasSession && sessionsTotal > 0;

  return (
    <div className={`card p-5 flex items-center gap-4 ${isAtRisk ? "border-amber-300 bg-amber-50" : ""}`}>
      <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-3xl
        ${streak >= 7 ? "bg-orange-100" : streak > 0 ? "bg-amber-100" : "bg-slate-100"}`}>
        <Flame className={`h-7 w-7 ${streak >= 7 ? "text-orange-500" : streak > 0 ? "text-amber-500" : "text-slate-400"}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-gray-500">Серия активности</p>
        <p className="text-3xl font-extrabold text-gray-900 leading-none mt-0.5">
          {streak} <span className="text-base font-medium text-gray-500">{streak === 1 ? "день" : streak >= 2 && streak <= 4 ? "дня" : "дней"}</span>
        </p>
        {isAtRisk && (
          <p className="mt-1 text-xs font-semibold text-amber-700">
            ⚠ Сегодня ещё не занимался — серия прервётся!
          </p>
        )}
        {streak >= 7 && (
          <p className="mt-1 text-xs font-semibold text-orange-600">🔥 Отличная серия, не останавливайся!</p>
        )}
      </div>
    </div>
  );
}

function VocabLevelBlock({ mastered, total }) {
  const level = vocabLevel(mastered);
  const prevThreshold = LEVELS[level.tier].threshold;
  const nextThreshold = level.next ? level.next.threshold : null;
  const range = nextThreshold !== null ? nextThreshold - prevThreshold : 1;
  const pctInRange = nextThreshold !== null
    ? Math.min(100, Math.round(((mastered - prevThreshold) / range) * 100))
    : 100;

  const wordsToNext = level.next ? level.next.threshold - mastered : 0;

  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100">
          <Star className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-500">Уровень словаря</p>
          <p className="text-xl font-extrabold text-gray-900 leading-none">{level.label}</p>
        </div>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all duration-500 ${level.color}`}
          style={{ width: `${pctInRange}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-slate-500">
        <span>{mastered} из {total} слов освоено</span>
        {level.next && wordsToNext > 0 && (
          <span>до «{level.next.label}»: ещё {wordsToNext} {wordsToNext === 1 ? "слово" : wordsToNext >= 2 && wordsToNext <= 4 ? "слова" : "слов"}</span>
        )}
      </div>
    </div>
  );
}

function HomePage({ onError }) {
  const [stats, setStats] = useState({
    total_words: 0,
    in_learning: 0,
    due_now: 0,
    mastered: 0,
    sessions_total: 0,
    streak: 0,
    recentSessions: [],
  });
  const [loading, setLoading] = useState(true);
  const { registerController, releaseController } = useAbortControllers();

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      const controller = registerController();
      try {
        const [vocabulary, reviewSummary, sessions, recentSessions] = await Promise.all([
          api.listVocabularyMe({ signal: controller.signal }),
          api.reviewSummary({ signal: controller.signal }),
          api.listSessionsMe({ limit: 1, offset: 0 }, { signal: controller.signal }),
          api.listSessionsMe({ limit: 60, offset: 0 }, { signal: controller.signal }),
        ]);
        setStats({
          total_words: vocabulary.length,
          in_learning: Math.max(vocabulary.length - reviewSummary.mastered, 0),
          due_now: reviewSummary.due_now,
          mastered: reviewSummary.mastered,
          sessions_total: sessions.total,
          streak: calcStreak(recentSessions.items || []),
          recentSessions: recentSessions.items || [],
        });
      } catch (e) {
        if (!isAbortError(e)) {
          onError(getErrorMessage(e));
        }
      } finally {
        releaseController(controller);
        setLoading(false);
      }
    }
    loadDashboard();
  }, [onError]);

  const statsCards = [
    { name: "Всего слов", value: stats.total_words, icon: BookOpen, iconWrap: "bg-blue-100", iconColor: "text-blue-600", description: "Слов в вашем словаре" },
    { name: "На изучении", value: stats.in_learning, icon: Clock, iconWrap: "bg-yellow-100", iconColor: "text-yellow-600", description: "Слов еще не выучено" },
    { name: "Для повторения", value: stats.due_now, icon: Target, iconWrap: "bg-orange-100", iconColor: "text-orange-600", description: "Слов готовы к повторению" },
    { name: "Выучено", value: stats.mastered, icon: Award, iconWrap: "bg-green-100", iconColor: "text-green-600", description: "Освоенные слова" },
  ];

  const quickActions = [
    { label: "Добавить слово", path: "/vocabulary", icon: Plus, description: "Добавить новое слово в словарь" },
    { label: "Начать тренировку", path: "/exercises", icon: Activity, description: "Продолжить практику упражнений" },
    { label: "Посмотреть прогресс", path: "/history", icon: TrendingUp, description: "Анализ ваших сессий и ошибок" },
  ];

  return (
    <div className="space-y-6 md:space-y-8">
      <header>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Добро пожаловать!</h1>
        <p className="text-gray-600 mt-1 text-sm md:mt-2 md:text-base">Начните изучать английские слова с умным подходом</p>
      </header>

      {!loading && (
        <section className="grid gap-3 sm:grid-cols-2 md:gap-4">
          <StreakBlock streak={stats.streak} sessionsTotal={stats.sessions_total} />
          <VocabLevelBlock mastered={stats.mastered} total={stats.total_words} />
        </section>
      )}

      <section>
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900 mb-4 md:mb-6">Ваша статистика</h2>
        {loading ? (
          <div className="card p-6 text-gray-600">Загрузка...</div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6">
            {statsCards.map((stat, index) => {
              const Icon = stat.icon;
              return (
                <div key={stat.name} className="card p-4 md:p-6 animate-fade-in" style={{ animationDelay: `${index * 100}ms` }}>
                  <div className="flex items-center">
                    <div className={`p-2 md:p-3 rounded-lg ${stat.iconWrap}`}>
                      <Icon className={`h-5 w-5 md:h-6 md:w-6 ${stat.iconColor}`} />
                    </div>
                    <div className="ml-3 md:ml-4 min-w-0">
                      <p className="text-xs md:text-sm font-medium text-gray-600 truncate">{stat.name}</p>
                      <p className="text-xl md:text-2xl font-bold text-gray-900">{stat.value}</p>
                      <p className="text-xs text-gray-500 mt-0.5 hidden sm:block">{stat.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="actions-section">
        <h2 className="text-xl md:text-2xl font-semibold text-gray-900 mb-4 md:mb-6">Быстрые действия</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-6">
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.label}
                to={action.path}
                className="card p-4 md:p-6 hover:shadow-md transition-shadow duration-200 animate-slide-up block"
                style={{ animationDelay: `${index * 100}ms` }}
              >
                <div className="flex items-center mb-2 md:mb-4">
                  <div className="p-2 rounded-lg bg-primary-100">
                    <Icon className="h-5 w-5 text-primary-600" />
                  </div>
                  <h3 className="text-base md:text-lg font-semibold text-gray-900 ml-3">{action.label}</h3>
                </div>
                <p className="text-gray-600 text-sm hidden sm:block">{action.description}</p>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
