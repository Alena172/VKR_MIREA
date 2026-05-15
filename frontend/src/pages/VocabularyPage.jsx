import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getErrorMessage, isAbortError } from "../lib/api";
import LoadingSpinner from "../components/LoadingSpinner";
import { useAbortControllers } from "../hooks/useAbortControllers";
import { saveReviewFocus, saveTrainingPreset } from "../lib/studyPresets";

const FILTER_OPTIONS = [
  { value: "all", label: "Все слова" },
  { value: "due", label: "К повторению" },
  { value: "troubled", label: "Трудные" },
  { value: "mastered", label: "Закрепленные" },
  { value: "new", label: "Новые" },
  { value: "no_definition", label: "Без определения" },
  { value: "no_context", label: "Без контекста" },
];

const SORT_OPTIONS = [
  { value: "alpha", label: "По алфавиту" },
  { value: "recent", label: "Сначала новые" },
  { value: "review_priority", label: "По приоритету повторения" },
];

function getVocabularyState(item, progress) {
  if (!progress || (progress.correct_streak === 0 && progress.error_count === 0)) {
    return {
      key: "new",
      label: "Новое",
      toneClass: "bg-slate-100 text-slate-700",
      description: "Ещё не попало в активный цикл повторения.",
      priority: 2,
    };
  }

  if (progress.status === "troubled") {
    return {
      key: "troubled",
      label: "Трудное",
      toneClass: "bg-red-100 text-red-700",
      description: "Накопилось много ошибок, стоит повторить в первую очередь.",
      priority: 5,
    };
  }
  if (progress.status === "due") {
    return {
      key: "due",
      label: "Пора повторять",
      toneClass: "bg-amber-100 text-amber-700",
      description: "Слово уже подошло к следующему окну повторения.",
      priority: 4,
    };
  }
  if (progress.status === "mastered") {
    return {
      key: "mastered",
      label: "Закрепляется",
      toneClass: "bg-emerald-100 text-emerald-700",
      description: "У слова уже хорошая серия верных ответов.",
      priority: 1,
    };
  }
  return {
    key: "learning",
    label: "В изучении",
    toneClass: "bg-blue-100 text-blue-700",
    description: "Слово уже в SRS, но ещё не закрепилось.",
    priority: 3,
  };
}

function matchesFilter(item, progress, filterValue) {
  const state = getVocabularyState(item, progress);
  if (filterValue === "all") {
    return true;
  }
  if (filterValue === "no_definition") {
    return !item.context_definition_ru;
  }
  if (filterValue === "no_context") {
    return !item.source_sentence;
  }
  return state.key === filterValue;
}

function sortVocabularyItems(items, progressById, sortValue) {
  const collator = new Intl.Collator("ru", { sensitivity: "base" });
  const getProgress = (item) => progressById[item.id] || null;

  return [...items].sort((a, b) => {
    if (sortValue === "recent") {
      return b.id - a.id;
    }

    if (sortValue === "review_priority") {
      const stateA = getVocabularyState(a, getProgress(a));
      const stateB = getVocabularyState(b, getProgress(b));
      if (stateA.priority !== stateB.priority) {
        return stateB.priority - stateA.priority;
      }
    }

    return collator.compare(a.english_lemma, b.english_lemma);
  });
}

export default function VocabularyPage({ onError }) {
  const navigate = useNavigate();
  const [selectedText, setSelectedText] = useState("apple");
  const [sourceSentence, setSourceSentence] = useState("I eat an apple every day.");
  const [translateText, setTranslateText] = useState("book");
  const [translateContext, setTranslateContext] = useState("I read a book before sleep.");
  const [translationResult, setTranslationResult] = useState("");
  const [items, setItems] = useState([]);
  const [progressById, setProgressById] = useState({});
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [addingLemmas, setAddingLemmas] = useState(new Set());
  const [addedLemmas, setAddedLemmas] = useState(new Set());
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const [sortBy, setSortBy] = useState("review_priority");
  const [editingId, setEditingId] = useState(null);
  const [editEnglish, setEditEnglish] = useState("");
  const [editRussian, setEditRussian] = useState("");
  const [editSentence, setEditSentence] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [studyFlowLoading, setStudyFlowLoading] = useState(false);
  const [studyFlowStatus, setStudyFlowStatus] = useState("");
  const [translateLoading, setTranslateLoading] = useState(false);
  const { registerController, releaseController } = useAbortControllers();

  async function loadVocabulary() {
    setLoading(true);
    const controller = registerController();
    try {
      const [data, progressData] = await Promise.all([
        api.listVocabularyMe({ signal: controller.signal }),
        api.listWordProgressMe({ limit: 200, offset: 0, status: "all" }, { signal: controller.signal }),
      ]);
      setItems(data);
      const nextProgressById = Object.fromEntries(
        (progressData?.items || [])
          .filter((p) => p.vocabulary_id != null)
          .map((p) => [p.vocabulary_id, p]),
      );
      setProgressById(nextProgressById);
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setLoading(false);
    }
  }

  async function addViaStudyFlow(event) {
    event.preventDefault();
    setStudyFlowLoading(true);
    setStudyFlowStatus("Добавляю слово...");
    onError("");
    const controller = registerController();
    try {
      const result = await api.studyFlowCaptureToVocabularyMe({
        selected_text: selectedText,
        source_sentence: sourceSentence,
      }, { signal: controller.signal });
      const addedWord = result?.vocabulary?.english_lemma || selectedText;
      const isNew = result?.created_new_vocabulary_item;
      setStudyFlowStatus(isNew ? `Добавлено: ${addedWord}` : `Уже есть: ${addedWord}`);
      await loadVocabulary();
      window.setTimeout(() => setStudyFlowStatus(""), 3000);
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setStudyFlowLoading(false);
    }
  }

  async function translateInContext(event) {
    event.preventDefault();
    setTranslationResult("");
    setTranslateLoading(true);
    onError("");
    const controller = registerController();
    try {
      const data = await api.translateMe({ text: translateText, source_context: translateContext }, { signal: controller.signal });
      setTranslationResult(data.translated_text);
    } catch (error) {
      if (!isAbortError(error)) {
        onError(getErrorMessage(error));
      }
    } finally {
      releaseController(controller);
      setTranslateLoading(false);
    }
  }

  function startEdit(item) {
    setEditingId(item.id);
    setEditEnglish(item.english_lemma);
    setEditRussian(item.russian_translation);
    setEditSentence(item.source_sentence || "");
    setEditUrl(item.source_url || "");
  }

  function cancelEdit() {
    setEditingId(null);
    setEditEnglish("");
    setEditRussian("");
    setEditSentence("");
    setEditUrl("");
  }

  async function saveEdit(event) {
    event.preventDefault();
    if (!editingId) {
      return;
    }
    try {
      await api.updateVocabularyMe(editingId, {
        english_lemma: editEnglish,
        russian_translation: editRussian,
        source_sentence: editSentence || null,
        source_url: editUrl || null,
      });
      cancelEdit();
      await loadVocabulary();
    } catch (error) {
      onError(getErrorMessage(error));
    }
  }

  function openTrainingForWord(item) {
    saveTrainingPreset({
      vocabularyIds: [item.id],
      mode: "sentence_translation_full",
      size: 3,
      focusLabel: `${item.english_lemma} - ${item.russian_translation}`,
    });
    navigate("/exercises");
  }

  function openReviewForWord(item, progress) {
    saveReviewFocus({
      word: item.english_lemma,
      translation: item.russian_translation,
      stateLabel: getVocabularyState(item, progress).label,
      hasProgress: Boolean(progress),
    });
    navigate("/review");
  }

  async function addFromRecommendation(rec) {
    setAddingLemmas((prev) => new Set(prev).add(rec.english_lemma));
    const controller = registerController();
    try {
      await api.addVocabularyMe(
        { english_lemma: rec.english_lemma, russian_translation: rec.russian_translation },
        { signal: controller.signal },
      );
      setAddedLemmas((prev) => new Set(prev).add(rec.english_lemma));
      await loadVocabulary();
    } catch (error) {
      if (!isAbortError(error)) onError(getErrorMessage(error));
    } finally {
      releaseController(controller);
      setAddingLemmas((prev) => { const next = new Set(prev); next.delete(rec.english_lemma); return next; });
    }
  }

  async function loadRecommendations() {
    setRecommendationsLoading(true);
    const controller = registerController();
    try {
      const data = await api.learningGraphInterestWords(6, { signal: controller.signal });
      setRecommendations(data?.items || []);
    } catch (error) {
      if (!isAbortError(error)) {
        setRecommendations([]);
      }
    } finally {
      releaseController(controller);
      setRecommendationsLoading(false);
    }
  }

  async function deleteItem(itemId) {
    try {
      await api.deleteVocabularyMe(itemId);
      if (editingId === itemId) {
        cancelEdit();
      }
      await loadVocabulary();
    } catch (error) {
      onError(getErrorMessage(error));
    }
  }

  useEffect(() => {
    loadVocabulary();
    loadRecommendations();
  }, []);

  const filteredItems = items.filter((item) => {
    const q = search.trim().toLowerCase();
    const progress = progressById[item.id] || null;
    if (!matchesFilter(item, progress, activeFilter)) {
      return false;
    }
    if (!q) {
      return true;
    }
    return (
      item.english_lemma.toLowerCase().includes(q) ||
      item.russian_translation.toLowerCase().includes(q) ||
      (item.context_definition_ru || "").toLowerCase().includes(q)
    );
  });
  const sortedItems = sortVocabularyItems(filteredItems, progressById, sortBy);

  return (
    <section className="space-y-4">
      {studyFlowLoading && (
        <LoadingSpinner
          message={studyFlowStatus || "Добавляю слово в словарь..."}
          estimatedSeconds="2-5"
        />
      )}
      {translateLoading && <LoadingSpinner message="Перевожу текст..." estimatedSeconds="2-4" />}

      <header className="surface p-4 md:p-5">
        <p className="kicker">Vocabulary</p>
        <h2 className="section-title">Словарь и контекстный перевод</h2>
        <p className="muted mt-1 text-sm">Добавляйте новые слова и сразу проверяйте перевод в нужном контексте.</p>
      </header>

      {(recommendations.length > 0 || recommendationsLoading) && (
        <section className="surface p-4 md:p-5">
          <div className="mb-1 flex items-center gap-2">
            <p className="kicker">Для вас</p>
          </div>
          <h3 className="text-base font-extrabold text-gray-900 mb-0.5">Рекомендации по интересам</h3>
          <p className="muted mb-4 text-sm">Слова из тематик, которыми вы уже интересуетесь.</p>
          {recommendationsLoading ? (
            <p className="muted text-sm">Загружаю рекомендации...</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {recommendations.map((rec) => {
                const isAdding = addingLemmas.has(rec.english_lemma);
                const isAdded = addedLemmas.has(rec.english_lemma);
                return (
                  <div
                    key={rec.english_lemma}
                    className={`flex flex-col gap-1.5 rounded-2xl border px-5 py-4 transition-colors ${isAdded ? "border-green-200 bg-green-50" : "border-blue-100 bg-blue-50"}`}
                  >
                    <div className="flex items-baseline gap-2">
                      <span className={`text-lg font-extrabold ${isAdded ? "text-green-900" : "text-blue-900"}`}>{rec.english_lemma}</span>
                      <span className={`text-sm ${isAdded ? "text-green-700" : "text-blue-700"}`}>{rec.russian_translation}</span>
                    </div>
                    <button
                      type="button"
                      disabled={isAdding || isAdded}
                      onClick={() => addFromRecommendation(rec)}
                      className={`mt-1 self-start text-xs transition-colors disabled:opacity-50 ${isAdded ? "text-green-600 cursor-default" : "text-blue-500 hover:text-blue-800"}`}
                    >
                      {isAdding ? "Добавляю..." : isAdded ? "✓ Добавлено" : "+ В словарь"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <form onSubmit={addViaStudyFlow} className="surface p-4 md:p-5 space-y-3">
          <h3 className="text-base font-extrabold text-gray-900">Добавить слово из контекста</h3>
          <input className="field" value={selectedText} onChange={(e) => setSelectedText(e.target.value)} placeholder="Выделенное слово" />
          <textarea
            className="field"
            value={sourceSentence}
            onChange={(e) => setSourceSentence(e.target.value)}
            rows={3}
            placeholder="Контекст предложения"
          />
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-primary" type="submit" disabled={studyFlowLoading}>
              {studyFlowLoading ? "Добавляю..." : "Добавить слово"}
            </button>
            {studyFlowStatus && !studyFlowLoading ? <span className="chip">{studyFlowStatus}</span> : null}
          </div>
        </form>

        <form onSubmit={translateInContext} className="surface p-4 md:p-5 space-y-3">
          <h3 className="text-base font-extrabold text-gray-900">Перевод в контексте</h3>
          <input className="field" value={translateText} onChange={(e) => setTranslateText(e.target.value)} placeholder="Что перевести" />
          <textarea
            className="field"
            value={translateContext}
            onChange={(e) => setTranslateContext(e.target.value)}
            rows={3}
            placeholder="Контекст"
          />
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-primary" type="submit">Перевести</button>
            {translationResult ? <span className="chip">{translationResult}</span> : null}
          </div>
        </form>
      </div>

      <section className="surface p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-extrabold text-gray-900">Слова пользователя</h3>
            <p className="muted mt-1 text-sm">Фильтруй словарь по состоянию изучения и быстро находи проблемные карточки.</p>
          </div>
          <input className="field max-w-xs" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Поиск EN/RU/определение" />
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          {FILTER_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setActiveFilter(option.value)}
              className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${
                activeFilter === option.value
                  ? "bg-blue-600 text-white"
                  : "border border-[var(--line)] bg-white text-slate-700 hover:bg-blue-50"
              }`}
            >
              {option.label}
            </button>
          ))}
          <select className="field ml-auto max-w-xs" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <ul className="space-y-3">
          {sortedItems.map((item) => {
            const progress = progressById[item.id] || null;
            const state = getVocabularyState(item, progress);
            return (
            <li key={item.id} className="surface p-4 md:p-5">
              {editingId === item.id ? (
                <form className="grid gap-2" onSubmit={saveEdit}>
                  <input className="field" value={editEnglish} onChange={(e) => setEditEnglish(e.target.value)} placeholder="English lemma" />
                  <input className="field" value={editRussian} onChange={(e) => setEditRussian(e.target.value)} placeholder="Перевод" />
                  <textarea className="field" rows={2} value={editSentence} onChange={(e) => setEditSentence(e.target.value)} placeholder="Контекст" />
                  <input className="field" value={editUrl} onChange={(e) => setEditUrl(e.target.value)} placeholder="URL источника" />
                  <div className="flex gap-2">
                    <button className="btn-primary" type="submit">Сохранить</button>
                    <button className="btn-secondary" type="button" onClick={cancelEdit}>Отмена</button>
                  </div>
                </form>
              ) : (
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
                  <div className="min-w-0">
                    <div className="text-base font-extrabold text-gray-900">{item.english_lemma} <span className="font-medium text-[var(--text)]">- {item.russian_translation}</span></div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${state.toneClass}`}>
                        {state.label}
                      </span>
                      {progress ? (
                        <>
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                            Ошибок: {progress.error_count}
                          </span>
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                            Серия: {progress.correct_streak}
                          </span>
                        </>
                      ) : null}
                    </div>
                    {item.context_definition_ru ? (
                      <div className="mt-2 text-sm text-gray-700">{item.context_definition_ru}</div>
                    ) : null}
                    {item.source_sentence ? <div className="muted mt-2 text-sm">{item.source_sentence}</div> : null}
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 self-start">
                    <button className="btn-primary !px-3.5 !py-2 !text-sm" type="button" onClick={() => startEdit(item)}>Редактировать</button>
                    <button className="btn-danger !px-3.5 !py-2 !text-sm" type="button" onClick={() => deleteItem(item.id)}>Удалить</button>
                  </div>
                </div>
              )}
            </li>
            );
          })}
          {!loading && sortedItems.length === 0 ? <li className="muted text-sm">По текущему фильтру слов нет.</li> : null}
          {loading ? <li className="muted text-sm">Загрузка...</li> : null}
        </ul>
      </section>
    </section>
  );
}
