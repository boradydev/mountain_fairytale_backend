-- ПРОВЕРКА ТЕКУЩЕЙ ЛОКАЛИ БАЗЫ ДАННЫХ PostgreSQL 16+
SELECT datname, datcollate, datctype
FROM pg_database
WHERE datname = 'mountain_fairytale_test';


-- ПЕРЕСОЗДАНИЕ БАЗЫ ДАННЫХ С ИСПРАВЛЕННОЙ ЛОКАЛЬЮ (WINDOWS ОПТИМИЗАЦИЯ)
CREATE DATABASE mountain_fairytale
    WITH
    TEMPLATE = template0
    ENCODING = 'UTF8'
    LC_COLLATE = 'Russian_Russia.utf8'
    LC_CTYPE = 'Russian_Russia.utf8';
