"""Наполнение dictionary_entries через внутренние модули системы.

Скрипт работает напрямую с БД (не через HTTP), но использует те же функции,
что и основное приложение:
  - resolve_context_definition  (Free Dictionary API → AI fallback)
  - infer_topic                 (тематические маркеры → topic_cluster_key)
  - get_or_create_dictionary_entry

Запуск из папки backend:
    python seed_dictionary.py

Переменные окружения (опционально):
    DATABASE_URL  — по умолчанию postgresql+psycopg://postgres:postgres@localhost:15432/vkr_db
    DELAY         — пауза между словами в секундах (по умолчанию 0.5)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Добавляем корень backend в путь, чтобы импортировать app.*
sys.path.insert(0, os.path.dirname(__file__))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:15432/vkr_db",
)
DELAY = float(os.environ.get("DELAY", "0.5"))

# ---------------------------------------------------------------------------
# Слова: (english_lemma, russian_translation)
# ---------------------------------------------------------------------------

WORDS = [
    # Общеупотребительная лексика (A2–B1)
    ("ability", "способность"),
    ("accept", "принимать"),
    ("achieve", "достигать"),
    ("action", "действие"),
    ("activity", "деятельность"),
    ("actually", "на самом деле"),
    ("advantage", "преимущество"),
    ("affect", "влиять"),
    ("agree", "соглашаться"),
    ("allow", "позволять"),
    ("amount", "количество"),
    ("apply", "применять"),
    ("argue", "спорить"),
    ("aspect", "аспект"),
    ("assume", "предполагать"),
    ("attempt", "попытка"),
    ("attitude", "отношение"),
    ("available", "доступный"),
    ("avoid", "избегать"),
    ("aware", "осознающий"),
    ("balance", "баланс"),
    ("behavior", "поведение"),
    ("benefit", "польза"),
    ("beyond", "за пределами"),
    ("cause", "причина"),
    ("challenge", "вызов"),
    ("change", "изменение"),
    ("character", "характер"),
    ("claim", "утверждать"),
    ("clear", "ясный"),
    ("compare", "сравнивать"),
    ("complete", "завершать"),
    ("complex", "сложный"),
    ("concept", "концепция"),
    ("concern", "беспокойство"),
    ("condition", "условие"),
    ("consider", "рассматривать"),
    ("continue", "продолжать"),
    ("control", "контроль"),
    ("create", "создавать"),
    ("culture", "культура"),
    ("current", "текущий"),
    ("decision", "решение"),
    ("define", "определять"),
    ("describe", "описывать"),
    ("develop", "развивать"),
    ("difference", "разница"),
    ("difficult", "трудный"),
    ("discuss", "обсуждать"),
    ("effect", "эффект"),
    ("effort", "усилие"),
    ("element", "элемент"),
    ("enable", "позволять"),
    ("environment", "окружающая среда"),
    ("establish", "устанавливать"),
    ("evaluate", "оценивать"),
    ("evidence", "доказательство"),
    ("examine", "исследовать"),
    ("exist", "существовать"),
    ("expect", "ожидать"),
    ("experience", "опыт"),
    ("explain", "объяснять"),
    ("factor", "фактор"),
    ("feature", "особенность"),
    ("focus", "фокус"),
    ("follow", "следовать"),
    ("force", "сила"),
    ("form", "форма"),
    ("goal", "цель"),
    ("growth", "рост"),
    ("identify", "определять"),
    ("impact", "воздействие"),
    ("important", "важный"),
    ("improve", "улучшать"),
    ("include", "включать"),
    ("increase", "увеличивать"),
    ("individual", "индивидуальный"),
    ("influence", "влияние"),
    ("information", "информация"),
    ("interest", "интерес"),
    ("involve", "вовлекать"),
    ("issue", "проблема"),
    ("knowledge", "знание"),
    ("language", "язык"),
    ("level", "уровень"),
    ("likely", "вероятный"),
    ("limit", "ограничивать"),
    ("maintain", "поддерживать"),
    ("manage", "управлять"),
    ("matter", "иметь значение"),
    ("meaning", "значение"),
    ("measure", "измерять"),
    ("method", "метод"),
    ("mind", "разум"),
    ("model", "модель"),
    ("nature", "природа"),
    ("necessary", "необходимый"),
    ("objective", "цель"),
    ("opinion", "мнение"),
    ("opportunity", "возможность"),
    ("order", "порядок"),
    ("overall", "в целом"),
    ("participate", "участвовать"),
    ("particular", "особый"),
    ("pattern", "закономерность"),
    ("perform", "выполнять"),
    ("period", "период"),
    ("perspective", "перспектива"),
    ("policy", "политика"),
    ("position", "позиция"),
    ("positive", "положительный"),
    ("possible", "возможный"),
    ("practice", "практика"),
    ("prepare", "готовить"),
    ("present", "представлять"),
    ("prevent", "предотвращать"),
    ("principle", "принцип"),
    ("process", "процесс"),
    ("produce", "производить"),
    ("provide", "обеспечивать"),
    ("purpose", "цель"),
    ("quality", "качество"),
    ("range", "диапазон"),
    ("reason", "причина"),
    ("reduce", "уменьшать"),
    ("relate", "относиться"),
    ("relevant", "актуальный"),
    ("require", "требовать"),
    ("research", "исследование"),
    ("resource", "ресурс"),
    ("respond", "отвечать"),
    ("result", "результат"),
    ("role", "роль"),
    ("situation", "ситуация"),
    ("skill", "навык"),
    ("society", "общество"),
    ("solution", "решение"),
    ("source", "источник"),
    ("specific", "конкретный"),
    ("strategy", "стратегия"),
    ("structure", "структура"),
    ("suggest", "предлагать"),
    ("support", "поддерживать"),
    ("system", "система"),
    ("theory", "теория"),
    ("therefore", "поэтому"),
    ("understand", "понимать"),
    ("value", "ценность"),
    ("various", "различный"),
    ("view", "точка зрения"),
    # Академическая лексика
    ("abstract", "абстрактный"),
    ("accuracy", "точность"),
    ("analyze", "анализировать"),
    ("approach", "подход"),
    ("assess", "оценивать"),
    ("category", "категория"),
    ("clarify", "уточнять"),
    ("classify", "классифицировать"),
    ("conclude", "делать вывод"),
    ("confirm", "подтверждать"),
    ("consistent", "последовательный"),
    ("construct", "конструировать"),
    ("contribute", "вносить вклад"),
    ("critical", "критический"),
    ("demonstrate", "демонстрировать"),
    ("derive", "выводить"),
    ("determine", "определять"),
    ("distribute", "распределять"),
    ("domain", "область"),
    ("emphasize", "подчёркивать"),
    ("empirical", "эмпирический"),
    ("framework", "структура"),
    ("generate", "генерировать"),
    ("hypothesis", "гипотеза"),
    ("indicate", "указывать"),
    ("interpret", "интерпретировать"),
    ("investigate", "исследовать"),
    ("justify", "обосновывать"),
    ("methodology", "методология"),
    ("observation", "наблюдение"),
    ("outcome", "результат"),
    ("parameter", "параметр"),
    ("phenomenon", "явление"),
    ("propose", "предлагать"),
    ("review", "обзор"),
    ("significant", "значительный"),
    ("synthesize", "синтезировать"),
    ("validate", "проверять"),
    ("variable", "переменная"),
    # IT-лексика
    ("algorithm", "алгоритм"),
    ("application", "приложение"),
    ("architecture", "архитектура"),
    ("array", "массив"),
    ("authentication", "аутентификация"),
    ("backend", "бэкенд"),
    ("browser", "браузер"),
    ("cache", "кэш"),
    ("callback", "обратный вызов"),
    ("compile", "компилировать"),
    ("component", "компонент"),
    ("database", "база данных"),
    ("debug", "отлаживать"),
    ("deploy", "развёртывать"),
    ("endpoint", "конечная точка"),
    ("execute", "выполнять"),
    ("frontend", "фронтенд"),
    ("implement", "реализовывать"),
    ("index", "индекс"),
    ("integrate", "интегрировать"),
    ("interface", "интерфейс"),
    ("library", "библиотека"),
    ("loop", "цикл"),
    ("memory", "память"),
    ("merge", "объединять"),
    ("migrate", "мигрировать"),
    ("module", "модуль"),
    ("network", "сеть"),
    ("optimize", "оптимизировать"),
    ("output", "вывод"),
    ("parse", "разбирать"),
    ("pipeline", "конвейер"),
    ("query", "запрос"),
    ("repository", "репозиторий"),
    ("request", "запрос"),
    ("response", "ответ"),
    ("runtime", "время выполнения"),
    ("schema", "схема"),
    ("server", "сервер"),
    ("session", "сессия"),
    ("syntax", "синтаксис"),
    ("token", "токен"),
    ("version", "версия"),
    # Повседневная лексика
    ("appointment", "встреча"),
    ("arrange", "организовывать"),
    ("attend", "посещать"),
    ("budget", "бюджет"),
    ("cancel", "отменять"),
    ("complain", "жаловаться"),
    ("convenient", "удобный"),
    ("deadline", "срок"),
    ("delay", "задержка"),
    ("deliver", "доставлять"),
    ("discount", "скидка"),
    ("document", "документ"),
    ("emergency", "чрезвычайная ситуация"),
    ("estimate", "оценивать"),
    ("exchange", "обменивать"),
    ("flexible", "гибкий"),
    ("handle", "справляться"),
    ("invoice", "счёт"),
    ("negotiate", "договариваться"),
    ("organize", "организовывать"),
    ("payment", "оплата"),
    ("priority", "приоритет"),
    ("professional", "профессиональный"),
    ("progress", "прогресс"),
    ("project", "проект"),
    ("refund", "возврат"),
    ("reliable", "надёжный"),
    ("remind", "напоминать"),
    ("schedule", "расписание"),
    ("succeed", "преуспевать"),
    ("sufficient", "достаточный"),
    ("task", "задача"),
    ("urgent", "срочный"),
    ("variety", "разнообразие"),
    ("volunteer", "волонтёр"),
    ("workplace", "рабочее место"),
]


async def seed_words(db_url: str) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    # Подменяем DATABASE_URL в конфиге приложения до импорта зависимых модулей
    os.environ.setdefault("DATABASE_URL", db_url)
    # Если уже установлена другая — перезаписываем
    os.environ["DATABASE_URL"] = db_url

    from app.modules.vocabulary.repository import VocabularyRepository
    from app.modules.vocabulary.service.definition import resolve_context_definition
    from app.modules.graph.repository import GraphRepository

    engine = create_engine(db_url, future=True)

    inserted = 0
    skipped = 0
    errors = 0
    total = len(WORDS)

    for i, (lemma, translation) in enumerate(WORDS, 1):
        try:
            with Session(engine) as db:
                vocab_repo = VocabularyRepository(db=db)
                graph_repo = GraphRepository(db=db)

                # Определение через Free Dictionary API или AI
                definition_result = await resolve_context_definition(
                    repo=vocab_repo,
                    english_lemma=lemma,
                    russian_translation=translation,
                    source_sentence=None,
                )
                definition = definition_result.context_definition

                # Тема через маркерный граф
                cluster_key, display_name = graph_repo.infer_topic(
                    english_lemma=lemma,
                    russian_translation=translation,
                    context_definition_ru=definition,
                    source_sentence=None,
                )
                graph_repo.ensure_cluster(
                    cluster_key=cluster_key,
                    display_name=display_name,
                )

                # Вставка в dictionary_entries
                _, created = vocab_repo.get_or_create_dictionary_entry(
                    english_lemma=lemma,
                    russian_translation=translation,
                    context_definition_ru=definition,
                    topic_cluster_key=cluster_key,
                )
                db.commit()

            if created:
                inserted += 1
                src = definition_result.source
                print(f"[{i}/{total}] + {lemma} ({src}, тема: {cluster_key})")
            else:
                skipped += 1
                print(f"[{i}/{total}] = {lemma} (уже есть)")

        except Exception as e:
            errors += 1
            print(f"[{i}/{total}] ! {lemma}: {e}")

        if i < total and DELAY > 0:
            time.sleep(DELAY)

    print(f"\nГотово: добавлено {inserted}, пропущено {skipped}, ошибок {errors}.")


if __name__ == "__main__":
    asyncio.run(seed_words(DATABASE_URL))
