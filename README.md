# 🎭 Theater Booking System

Система бронирования мест с QR-кодами для театрального зала (506 мест).

---

## Структура проекта

```
theater_booking/
├── main.py              ← FastAPI бэкенд (все API + раздача HTML)
├── requirements.txt     ← зависимости Python
├── theater.db           ← SQLite база (создаётся автоматически)
└── templates/
    ├── index.html       ← страница выбора мест (для зрителей)
    └── scan.html        ← страница сканирования (для администраторов)
```
 
---

## Быстрый старт

### 1. Установка Python-зависимостей

```bash
pip install -r requirements.txt
```

### 2. Запуск сервера

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

> `--reload` — автоперезагрузка при изменении кода (уберите в продакшене).

### 3. Открыть в браузере

- **Зрители:** http://localhost:8000/
- **Администратор (сканер):** http://localhost:8000/scan
- **Список всех билетов:** http://localhost:8000/api/admin/tickets

---

## Сценарий использования

### Зритель
1. Открывает **http://ваш-сервер/** на любом устройстве
2. Видит схему зала — серые места свободны, красные — заняты
3. Нажимает на свободное место
4. В нижней панели появляется кнопка **«Забронировать»**
5. В модальном окне вводит своё имя
6. Получает **QR-код** — можно сделать скриншот или показать с экрана

### Администратор в зале
1. Открывает **http://ваш-сервер/scan** на телефоне
2. Нажимает **«Включить камеру»** → разрешает доступ
3. Подносит телефон к QR-коду гостя
4. Система мгновенно показывает:
   - ✅ **Зелёный** — билет действителен, гость и место отображаются
   - ⚠️ **Жёлтый** — билет уже был использован ранее
   - ❌ **Красный** — билет не найден
5. После успешного сканирования QR-код **аннулируется** (повторный вход невозможен)

---

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Страница выбора мест |
| GET | `/scan` | Страница сканера |
| GET | `/api/seats` | Список всех занятых мест |
| POST | `/api/book` | Забронировать место |
| POST | `/api/scan` | Проверить и погасить QR |
| GET | `/api/ticket/{id}` | Информация о билете |
| GET | `/api/admin/tickets` | Все билеты (для мониторинга) |

### POST /api/book — тело запроса
```json
{
  "seat_id":    "Партер_r5_s12",
  "row_num":    5,
  "seat_num":   12,
  "section":    "Партер",
  "guest_name": "Иванов Иван"
}
```

### POST /api/scan — тело запроса
```json
{
  "ticket_id": "uuid-билета"
}
```

---

## Деплой на сервер (Linux, VPS)

```bash
# Установить зависимости системы
sudo apt update && sudo apt install python3-pip python3-venv -y

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запустить через systemd (создать /etc/systemd/system/theater.service):
[Unit]
Description=Theater Booking
After=network.target

[Service]
WorkingDirectory=/home/user/theater_booking
ExecStart=/home/user/theater_booking/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

# Активировать
sudo systemctl enable theater
sudo systemctl start theater
```

### Nginx (проксирование на порт 80/443)
```nginx
server {
    listen 80;
    server_name ваш-домен.ru;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Безопасность (для продакшена)

1. **Защита /scan и /api/scan** — добавьте простую HTTP Basic Auth или токен:
   ```python
   from fastapi.security import HTTPBasic, HTTPBasicCredentials
   # добавьте зависимость к эндпоинту /scan и /api/scan
   ```

2. **HTTPS** — обязательно для работы камеры на мобильных устройствах (`getUserMedia` требует HTTPS или localhost).

3. **Резервное копирование БД** — регулярно копируйте `theater.db`.

---

## Технологии

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, SQLite
- **QR генерация:** библиотека `qrcode` + `Pillow`
- **Frontend:** чистый HTML/CSS/JS, без фреймворков
- **QR сканирование:** библиотека `jsQR` (JavaScript, работает через камеру браузера)
