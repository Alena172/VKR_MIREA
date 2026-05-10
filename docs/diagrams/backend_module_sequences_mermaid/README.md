# Диаграммы последовательности модулей серверной части в Mermaid

Этот каталог содержит `Mermaid`-версии модульных диаграмм верхнего уровня.

Основной набор для отчёта:

- `01_identity_module_sequence.mmd` — модуль `identity`
- `02_vocabulary_module_sequence.mmd` — модуль `vocabulary`
- `03_training_module_sequence.mmd` — модуль `training`
- `04_graph_module_sequence.mmd` — модуль `graph`
- `05_ai_module_sequence.mmd` — AI-адаптер `ai`
- `06_tasks_platform_sequence.mmd` — технический слой `tasks`

Они соответствуют той же укрупнённой архитектуре, что и `PlantUML`-файлы из каталога `docs/diagrams/backend_module_sequences`: четыре доменных модуля, AI-адаптер и инфраструктура задач.

Старые `.mmd`-файлы по подмодулям и детализированным сценариям сохранены как вспомогательный материал и могут использоваться как приложение.

Дополнительно добавлены компактные сценарии словарного модуля:

- `13_vocabulary_delete_sequence.mmd`
- `14_vocabulary_ai_add_sequence.mmd`
