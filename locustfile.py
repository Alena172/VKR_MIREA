"""
Нагрузочное тестирование VKR English Learning API.

Установка:
    pip install locust

Запуск (веб-интерфейс):
    locust -f locustfile.py --host http://localhost:8080

Запуск без UI (headless), 50 пользователей, нарастание 5/сек, 3 минуты:
    locust -f locustfile.py --host http://localhost:8080 \
           --headless -u 50 -r 5 --run-time 3m \
           --html report.html

Сценарии:
  - ReaderUser     — читает словарь и историю сессий (лёгкая нагрузка)
  - TrainingUser   — генерирует упражнения и сдаёт сессию (тяжёлая нагрузка)
  - CaptureUser    — добавляет слова через capture-пайплайн (AI-нагрузка)
"""
from __future__ import annotations

import random
import string
import time

from locust import HttpUser, between, task


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

# Пул заранее созданных тестовых пользователей с наполненным словарём.
# Locust распределяет их между виртуальными пользователями через round-robin.
_SHARED_USERS = [f"load_user_{i:02d}@example.com" for i in range(1, 11)]
_SHARED_USER_INDEX = 0


def _next_shared_email() -> str:
    global _SHARED_USER_INDEX
    email = _SHARED_USERS[_SHARED_USER_INDEX % len(_SHARED_USERS)]
    _SHARED_USER_INDEX += 1
    return email


def _random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"load_test_{suffix}@example.com"


def _random_word() -> str:
    """Случайное слово из реалистичного набора для capture-тестов."""
    words = [
        "book", "light", "run", "fast", "fair", "watch", "bank", "bear",
        "date", "match", "plant", "right", "kind", "fall", "lead", "last",
        "play", "stand", "turn", "work", "park", "file", "state", "course",
    ]
    return random.choice(words)


def _random_sentence(word: str) -> str:
    templates = [
        f"I need to {word} this as soon as possible.",
        f"She decided to {word} everything carefully.",
        f"The {word} was very important for the project.",
        f"They tried to {word} the situation.",
        f"He found a way to {word} it quickly.",
    ]
    return random.choice(templates)


# ---------------------------------------------------------------------------
# Базовый класс с аутентификацией
# ---------------------------------------------------------------------------

class AuthenticatedUser(HttpUser):
    abstract = True

    def on_start(self) -> None:
        self._token: str | None = None
        self._vocabulary_ids: list[int] = []
        # Случайная задержка перед логином растягивает пиковую нагрузку на аутентификацию
        time.sleep(random.uniform(0, 10))
        self._login(_next_shared_email())

    def _login(self, email: str) -> None:
        password = "LoadTest123!"
        resp = self.client.post(
            "/api/v1/auth/login-or-register",
            json={
                "email": email,
                "full_name": "Load Test User",
                "password": password,
                "cefr_level": random.choice(["A2", "B1", "B2"]),
            },
            name="/auth/login-or-register",
        )
        if resp.status_code == 200:
            self._token = resp.json().get("access_token")
            self._seed_vocabulary()

    def _headers(self) -> dict:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    def _seed_vocabulary(self) -> None:
        """Получает список уже существующих слов пользователя."""
        resp = self.client.get(
            "/api/v1/vocabulary/me",
            headers=self._headers(),
            name="/vocabulary/me/from-capture [seed]",
        )
        if resp.status_code == 200:
            items = resp.json()
            self._vocabulary_ids = [item["id"] for item in items if item.get("id")]


# ---------------------------------------------------------------------------
# Сценарий 1: ReaderUser — читает данные, не генерирует упражнения
# Имитирует пользователя, который просматривает словарь и историю.
# Вес: 40% пользователей.
# ---------------------------------------------------------------------------

class ReaderUser(AuthenticatedUser):
    weight = 40
    wait_time = between(2, 5)

    @task(3)
    def get_vocabulary(self) -> None:
        self.client.get(
            "/api/v1/vocabulary/me",
            headers=self._headers(),
            name="/vocabulary/me",
        )

    @task(2)
    def get_sessions_history(self) -> None:
        self.client.get(
            "/api/v1/sessions/me?limit=10&offset=0",
            headers=self._headers(),
            name="/sessions/me",
        )

    @task(1)
    def get_review_queue(self) -> None:
        self.client.get(
            "/api/v1/context/me/review-queue?limit=10",
            headers=self._headers(),
            name="/context/me/review-queue",
        )

    @task(1)
    def get_word_progress(self) -> None:
        self.client.get(
            "/api/v1/context/me/word-progress?limit=20&offset=0&status=all",
            headers=self._headers(),
            name="/context/me/word-progress",
        )

    @task(1)
    def healthcheck(self) -> None:
        self.client.get("/health", name="/health")


# ---------------------------------------------------------------------------
# Сценарий 2: TrainingUser — генерирует упражнения и сдаёт сессию.
# Самый тяжёлый сценарий: затрагивает буфер, Celery, LLM.
# Вес: 40% пользователей.
# ---------------------------------------------------------------------------

class TrainingUser(AuthenticatedUser):
    weight = 40
    wait_time = between(5, 15)

    @task(2)
    def training_word_scramble(self) -> None:
        """Быстрый режим — без LLM, только локальная генерация."""
        resp = self.client.post(
            "/api/v1/exercises/me/generate",
            json={
                "mode": "word_scramble",
                "size": 5,
                "vocabulary_ids": [],
                "fast_start": False,
                "incremental": False,
            },
            headers=self._headers(),
            name="/exercises/me/generate [word_scramble]",
        )
        if resp.status_code == 200:
            exercises = resp.json().get("exercises", [])
            if exercises:
                self._submit_session(exercises, mode="word_scramble")

    @task(2)
    def training_sentence_incremental(self) -> None:
        """Инкрементальный режим — берёт из буфера мгновенно."""
        resp = self.client.post(
            "/api/v1/exercises/me/generate",
            json={
                "mode": "sentence_translation_full",
                "size": 5,
                "vocabulary_ids": [],
                "fast_start": False,
                "incremental": True,
            },
            headers=self._headers(),
            name="/exercises/me/generate [sentence_incremental]",
        )
        if resp.status_code == 200:
            exercises = resp.json().get("exercises", [])
            if exercises:
                self._submit_session(exercises, mode="sentence_translation_full")

    @task(1)
    def training_definition_match(self) -> None:
        """Упражнение на определения — требует минимум 4 слова с определениями.
        У новых тестовых пользователей определения могут ещё не сгенерироваться —
        4xx в этом случае не считается ошибкой теста.
        """
        with self.client.post(
            "/api/v1/exercises/me/generate",
            json={
                "mode": "word_definition_match",
                "size": 4,
                "vocabulary_ids": [],
                "fast_start": False,
                "incremental": False,
            },
            headers=self._headers(),
            name="/exercises/me/generate [definition_match]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                exercises = resp.json().get("exercises", [])
                if exercises:
                    self._submit_session(exercises, mode="word_definition_match")
                resp.success()
            elif resp.status_code in (400, 422):
                # Недостаточно слов с определениями — ожидаемо для новых пользователей
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    def _submit_session(self, exercises: list, mode: str) -> None:
        answers = []
        for i, ex in enumerate(exercises, start=1):
            if mode == "word_scramble":
                # Правильный ответ — просто правильный (тестируем submission, не LLM)
                user_answer = ex.get("answer", "test")
            elif mode == "word_definition_match":
                user_answer = ex.get("answer", "[]")
            else:
                # sentence_translation — имитируем реальный ответ пользователя
                user_answer = ex.get("answer", "тест")

            answers.append({
                "exercise_id": i,
                "exercise_type": ex.get("exercise_type"),
                "target_word": ex.get("target_word"),
                "vocabulary_id": None,
                "prompt": ex.get("prompt"),
                "expected_answer": ex.get("answer"),
                "user_answer": user_answer,
                "is_correct": None,
            })

        self.client.post(
            "/api/v1/sessions/submit",
            json={"answers": answers},
            headers=self._headers(),
            name="/sessions/submit",
        )


# ---------------------------------------------------------------------------
# Сценарий 3: CaptureUser — добавляет слова через capture-пайплайн.
# Имитирует пользователя с расширением браузера, который активно добавляет слова.
# Затрагивает: перевод (LibreTranslate/LLM), определения (Free Dictionary/LLM).
# Вес: 20% пользователей.
# ---------------------------------------------------------------------------

class CaptureUser(AuthenticatedUser):
    weight = 20
    wait_time = between(3, 8)

    def on_start(self) -> None:
        self._token: str | None = None
        self._vocabulary_ids: list[int] = []
        self._login(_random_email())

    @task(3)
    def capture_word(self) -> None:
        word = _random_word()
        resp = self.client.post(
            "/api/v1/vocabulary/me/from-capture",
            json={
                "selected_text": word,
                "source_sentence": _random_sentence(word),
                "source_url": "https://example.com/news",
                "force_new_vocabulary_item": False,
            },
            headers=self._headers(),
            name="/vocabulary/me/from-capture",
        )
        if resp.status_code == 200:
            vid = resp.json().get("vocabulary", {}).get("id")
            if vid and vid not in self._vocabulary_ids:
                self._vocabulary_ids.append(vid)

    @task(2)
    def translate_word(self) -> None:
        word = _random_word()
        self.client.post(
            "/api/v1/translate/me",
            json={
                "text": word,
                "source_context": _random_sentence(word),
            },
            headers=self._headers(),
            name="/translate/me",
        )

    @task(1)
    def review_single_word(self) -> None:
        # Берём актуальную очередь повторения — только слова, уже попавшие в SRS.
        resp = self.client.get(
            "/api/v1/context/me/review-queue?limit=5",
            headers=self._headers(),
            name="/context/me/review-queue",
        )
        if resp.status_code != 200:
            return
        items = resp.json().get("items", [])
        if not items:
            return
        word = random.choice(items).get("word")
        if not word:
            return
        self.client.post(
            "/api/v1/context/me/review-queue/submit",
            json={
                "word": word,
                "is_correct": random.choice([True, False]),
            },
            headers=self._headers(),
            name="/context/me/review-queue/submit",
        )
