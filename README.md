# Date Planner

Date Planner — веб-сервис для создания персональных приглашений на свидание и последующего совместного планирования. Сейчас проект предоставляет адаптивную интерактивную страницу, API создания и чтения приглашений и основу monorepo с запуском через Docker.

## Стек

- **Frontend:** Vue 3, Nuxt, TypeScript, Composition API, ESLint и Vitest.
- **Backend:** Python, Django, Django REST Framework, PostgreSQL, django-cors-headers, drf-spectacular, pytest и Ruff.
- **Инфраструктура:** Docker, Docker Compose, GitHub Actions и конфигурация через переменные окружения.

## Структура репозитория

```text
date-planner/
├── backend/                  # Django-проект, приложение common и API-тесты
├── frontend/                 # Nuxt-приложение, компоненты, composable-функции и тесты
├── .github/workflows/ci.yml  # CI-проверки backend и frontend
├── .env.example              # Безопасный шаблон локальной конфигурации
├── docker-compose.yml        # PostgreSQL, backend и frontend
├── Makefile                  # Частые команды разработки
└── AGENTS.md                 # Правила дальнейшей работы AI-агентов
```

## Требования

Для рекомендуемого локального запуска нужны только:

- Docker Engine с плагином Compose v2;
- Git;
- свободные порты `3000` и `8000`.

При работе через Docker Compose устанавливать Python, Node.js и PostgreSQL на хост не требуется.

## Первый запуск

Создайте локальный файл окружения из безопасного шаблона:

```bash
cp .env.example .env
```

Значения из `.env.example` предназначены только для локальной разработки. Для любого другого окружения обязательно замените секретный ключ и пароль базы данных.

Соберите и запустите все сервисы:

```bash
docker compose up --build
```

Backend дождётся готовности PostgreSQL и автоматически применит миграции. После добавления новой миграции её также можно применить вручную:

```bash
make migrate
```

Остановить стек можно командой `make down`. Данные PostgreSQL сохраняются в именованном томе `postgres_data`.

## Доступные URL

| Сервис | URL |
| --- | --- |
| Страница приглашения | <http://localhost:3000> |
| Health endpoint backend | <http://localhost:8000/api/v1/health/> |
| OpenAPI-схема | <http://localhost:8000/api/schema/> |
| Swagger UI | <http://localhost:8000/api/docs/> |

## API приглашений

Создать приглашение можно публичным запросом:

```bash
curl -X POST http://localhost:8000/api/v1/invitations/ \
  -H 'Content-Type: application/json' \
  -d '{
    "author_name": "Алиса",
    "recipient_name": "Борис",
    "message": "Давай сходим на свидание?"
  }'
```

Ответ содержит непредсказуемый UUID. Получить одно приглашение можно по адресу:

```text
GET /api/v1/invitations/<uuid>/
```

Каждое приглашение хранится отдельной записью, поэтому данные разных пар не перезаписывают друг друга. Публичного `GET /api/v1/invitations/` нет: без авторизации API не раскрывает общий список чужих приглашений. До появления аккаунтов UUID следует считать приватной ссылкой доступа.

Все API-запросы ограничены по частоте. По умолчанию анонимному клиенту разрешено `60` запросов в минуту, будущему авторизованному — `120`. При превышении сервер отвечает `429 Too Many Requests` и возвращает `Retry-After`.

В текущем Compose throttling использует общий файловый cache внутри одного backend-контейнера, поэтому лимит разделяется между Gunicorn workers. Это базовая защита от чрезмерного использования API, а не полноценная DDoS-защита. Перед горизонтальным production-развёртыванием понадобятся общий сетевой cache и rate limiting на уровне доверенного reverse proxy или API gateway.

## Команды Makefile

| Команда | Назначение |
| --- | --- |
| `make up` | Собрать образы и запустить dev-стек в текущем терминале |
| `make down` | Остановить контейнеры и удалить осиротевшие контейнеры |
| `make build` | Собрать образы всех сервисов |
| `make logs` | Следить за логами всех сервисов |
| `make migrate` | Применить миграции Django |
| `make test` | Запустить тесты backend и frontend |
| `make test-backend` | Запустить только pytest |
| `make test-frontend` | Запустить только Vitest |
| `make lint` | Запустить Ruff, ESLint и проверку TypeScript |
| `make format` | Отформатировать Python и применить безопасные исправления линтеров |
| `make typecheck` | Запустить TypeScript-проверку Nuxt |

Все команды выполняются в сервисах Docker Compose и не зависят от глобально установленных Python- или Node-пакетов.

## Тесты и проверки качества

Полный набор проверок запускается так:

```bash
make test
make lint
```

Отдельные проверки можно запустить явно:

```bash
docker compose run --rm backend pytest
docker compose run --rm backend ruff check .
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build
```

GitHub Actions выполняет те же категории проверок backend и frontend при каждом push и pull request.

## Переменные окружения

| Переменная | Используется | Назначение |
| --- | --- | --- |
| `POSTGRES_DB` | PostgreSQL, Django | Имя базы данных |
| `POSTGRES_USER` | PostgreSQL, Django | Пользователь базы данных |
| `POSTGRES_PASSWORD` | PostgreSQL, Django | Пароль; вне локальной разработки задайте уникальный секрет |
| `POSTGRES_HOST` | Django | Хост базы данных; внутри Compose-сети используется `db` |
| `POSTGRES_PORT` | Django | Порт базы данных, обычно `5432` |
| `BACKEND_PORT` | Docker Compose | Публикуемый порт backend, по умолчанию `8000` |
| `FRONTEND_PORT` | Docker Compose | Публикуемый порт frontend, по умолчанию `3000` |
| `DJANGO_SECRET_KEY` | Django | Ключ подписи; значение из примера подходит только для разработки |
| `DJANGO_DEBUG` | Django | Включает debug-режим Django при значении `True` |
| `DJANGO_ALLOWED_HOSTS` | Django | Разделённый запятыми список разрешённых HTTP-хостов |
| `CORS_ALLOWED_ORIGINS` | Django | Разделённый запятыми список доверенных origin frontend |
| `DRF_THROTTLE_ANON_RATE` | Django REST Framework | Лимит запросов анонимного клиента, по умолчанию `60/min` |
| `DRF_THROTTLE_USER_RATE` | Django REST Framework | Лимит запросов авторизованного клиента, по умолчанию `120/min` |
| `DRF_NUM_PROXIES` | Django REST Framework | Число доверенных reverse proxy; для текущего прямого Compose-подключения `0` |
| `DRF_THROTTLE_CACHE_LOCATION` | Django | Абсолютный путь к общему cache throttling внутри backend-контейнера |
| `NUXT_PUBLIC_API_BASE_URL` | Nuxt, браузер | Публичный базовый URL для API-запросов |

Файл `.env` исключён из Git. Compose содержит безопасные значения по умолчанию для локальной разработки, но копирование `.env.example` делает конфигурацию явной.

## Текущие возможности

- Адаптивная романтическая страница приглашения на локальных графических ресурсах.
- Управление ответами мышью, касанием и клавиатурой с учётом `prefers-reduced-motion`.
- Состояния принятого и отклонённого приглашения и кнопка сброса демонстрации.
- Создание и чтение отдельных приглашений по UUID через `/api/v1/`.
- Серверная валидация имён и текста приглашения без публичного списка записей.
- Ограничение частоты API-запросов с ответом `429 Too Many Requests`.
- Индикатор доступности backend, видимый только в режиме разработки.
- Health endpoint Django, OpenAPI-схема и Swagger UI.
- Локальная разработка с PostgreSQL и healthcheck сервисов.
- Автоматические линтеры, тесты, проверка типов и production-сборка frontend в CI.

## Ближайшие этапы

Следующий небольшой этап — подключить frontend к API создания приглашения и добавить публичную страницу по UUID. Затем можно реализовать сохранение ответа, совместный выбор даты, времени и места, а также итоговую страницу автора. Аккаунты и подтверждённое владение приглашениями понадобятся до появления личного кабинета; фоновые очереди и deployment-инфраструктуру стоит добавлять только по мере конкретной необходимости.
