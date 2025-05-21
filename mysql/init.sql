-- Удаляем пользователя, если он уже существует
DROP USER IF EXISTS 'grafana'@'%';

-- Создаём пользователя заново
CREATE USER 'grafana'@'%' IDENTIFIED BY 'grafana';
GRANT SELECT ON tinkoff_db.* TO 'grafana'@'%';
FLUSH PRIVILEGES;