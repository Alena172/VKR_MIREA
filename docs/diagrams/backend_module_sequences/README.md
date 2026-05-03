# Диаграммы последовательности backend-модулей

Для отчета основными считаются диаграммы верхнего уровня по доменным модулям, AI adapter и инфраструктурному task layer:

- `01_identity_module_sequence.puml` - модуль `identity`
- `02_vocabulary_module_sequence.puml` - модуль `vocabulary`
- `03_learning_module_sequence.puml` - модуль `learning`
- `04_learning_graph_module_sequence.puml` - модуль `learning_graph`
- `05_ai_services_module_sequence.puml` - AI adapter `ai_services`
- `06_tasks_infrastructure_sequence.puml` - инфраструктурный слой `tasks`

Дополнительно в каталоге сохранены более подробные сценарные диаграммы по подмодулям и отдельным потокам:

- `01_auth_sequence.puml`
- `02_users_sequence.puml`
- `03_translation_sequence.puml`
- `04_vocabulary_sequence.puml`
- `05_capture_sequence.puml`
- `06_exercise_engine_sequence.puml`
- `07_learning_session_sequence.puml`
- `08_context_memory_sequence.puml`
- `09_learning_graph_sequence.puml`
- `10_tasks_sequence.puml`
- `11_ai_services_sequence.puml`
- `12_base_lexicon_sequence.puml`
- `13_vocabulary_delete_sequence.puml`
- `14_vocabulary_ai_add_sequence.puml`

Их можно использовать как приложение или как детализирующие иллюстрации. Основная схема для пояснительной записки задается четырьмя доменными модулями, AI adapter и task infrastructure.

Во всех диаграммах подписи шагов описывают смысл действия для продукта и пользователя.
