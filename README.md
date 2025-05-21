# Проект: Анализ фондового рынка через Tinkoff API

## Описание проекта

Цель проекта — собрать и проанализировать данные об акциях с использованием Tinkoff API, сохранить их в MySQL и визуализировать ключевые показатели в Grafana.

Проект реализует следующие задачи:

1. Получение данных об акциях и исторических свечах из Tinkoff API
2. Загрузка этих данных в таблицы `shares` и `candle_year` в MySQL
3. Построение аналитических графиков на базе собранных данных по следующим гипотезам:
   - Распределение рынка акций по странам
   - Оценка диверсификации акций по странам в секторе IT
   - Сравнение волатильности IT и сырьевого секторов
   - Анализ влияния господдержки (нац. программа "Цифровая экономика") на стоимость акций IT
   - Изменение стоимости 5 самых дорогих IT-акций РФ

## Структура проекта

```
.
├── docker-compose.build.yml         # Сборка образов и сервисов
├── docker-compose.yml               # Запуск сервисов (MySQL, Grafana, App)
├── grafana/
│   └── provisioning/                # Автозагрузка dashboards/datasources
├── mysql/
│   └── init.sql                     # Скрипт инициализации пользователя grafana
└── tinkoff-app/
    ├── Dockerfile                   # Docker-образ приложения
    ├── entrypoint.sh                # Стартовый скрипт, ждёт БД и запускает код
    ├── requirements.txt             # Зависимости Python
    └── TinApyProject.py             # Основной ETL-скрипт: выгрузка, загрузка, анализ
```

## Установка и запуск

1. Установите `docker` и `docker-compose` на сервере
2. В корне проекта выполните:

```bash
docker compose -f docker-compose.build.yml up --build
```

3. Убедитесь, что:
   - Grafana доступна на `http://localhost:3000`
   - MySQL запущена и содержит таблицы `shares`, `candle_year`

## Настройка переменных окружения

Укажите следующие переменные через `.env` или вручную:

- `TINKOFF_API_TOKEN` — API-токен Tinkoff Invest
- `MYSQL_ROOT_PASSWORD` — пароль root для MySQL
- `MYSQL_DATABASE` — имя базы данных (по умолчанию: `tinkoff_db`)

## Использование

Приложение запускается автоматически через `entrypoint.sh` и:
- Загружает список акций (`shares`) из Tinkoff
- Определяет топовые акции по цене в секторах IT и Materials в РФ
- Загружает свечи по ним за последние 5 лет (`candle_year`)

## Визуализация в Grafana

Дашборд `tinkoff_dashboard.json` строит 6 графиков:

1. **Распределение акций по странам** — круговая диаграмма количества акций, сформированная SQL-запросом:
   ```sql
   SELECT CONCAT(country) AS "Country", COUNT(*) AS "TotalCount"
   FROM shares
   WHERE country IS NOT NULL AND TRIM(country) <> ''
   GROUP BY country
   ORDER BY TotalCount DESC;
   ```
   Этот запрос группирует акции по странам, исключая пустые значения, и сортирует по убыванию.

2. **Оценка диверсификации (IT-сектор)** — круговая диаграмма стран, содержащих IT-компании:
   ```sql
   SELECT CONCAT(country, ' (IT)') AS "Country", COUNT(*) AS "Count"
   FROM shares
   WHERE country IS NOT NULL AND TRIM(country) <> '' AND sector LIKE '%IT%'
   GROUP BY country
   ORDER BY Count DESC;
   ```
   График отражает, в каких странах и в каком объёме представлены IT-компании.

3. **Всего акций (IT-сектор)** — числовой виджет, отображающий общее количество IT-акций

4. **Сравнение волатильности: IT vs Сырьевой сектор** — горизонтальный барчарт. Используется запрос:
   ```sql
   SELECT s.sector AS "Sector", AVG(v.daily_volatility) AS "Volatility"
   FROM (
     SELECT c1.figi,
            STDDEV_SAMP((c1.close - c2.close) / c2.close) AS daily_volatility
     FROM candle_year c1
     JOIN candle_year c2 
       ON c1.figi = c2.figi 
       AND DATE(c1.time) = DATE_ADD(DATE(c2.time), INTERVAL 1 DAY)
     WHERE $__timeFilter(c1.time)
     GROUP BY c1.figi
   ) v
   JOIN shares s ON s.figi = v.figi
   WHERE s.sector IN ('it', 'materials')
   GROUP BY s.sector;
   ```
   Рассчитывается средняя дневная волатильность (стандартное отклонение доходности) для каждого сектора.

5. **Кумулятивная доходность IT-сектора** — линейный график, показывающий рост капитала до и после господдержки (01.07.2020):
   ```sql
   SELECT
     c1.time AS time,
     EXP(SUM(LOG(c1.close / c2.close))) AS value,
     CASE
       WHEN c1.time < '2020-07-01' THEN 'До господдержки'
       ELSE 'После господдержки'
     END AS metric
   FROM candle_year c1
   JOIN candle_year c2
     ON c1.figi = c2.figi
    AND DATE(c2.time) = DATE_SUB(DATE(c1.time), INTERVAL 1 DAY)
   JOIN shares s ON c1.figi = s.figi
   WHERE s.sector = 'it'
     AND c1.time BETWEEN '2020-01-01' AND '2021-03-01'
   GROUP BY c1.time
   ORDER BY c1.time;
   ```
   Вычисляется кумулятивная доходность акций IT-сектора и делится по периодам «до» и «после» господдержки для сравнения динамики.

6. **Изменение стоимости топ-5 IT акций РФ** — линейный график, отображающий динамику цен на выбранные акции IT-компаний из РФ.

## Импорт дашборда

1. Откройте Grafana
2. Меню → **Dashboards → Import**
3. Загрузите `tinkoff_dashboard.json`
4. Замените UID источника данных на ваш

## Зависимости Python

Установлены в `requirements.txt`:
- tinkoff-investments
- pandas
- mysql-connector-python
- sqlalchemy
- pymysql

## Лицензия

MIT
