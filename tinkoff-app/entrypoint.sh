#!/bin/bash

# Ждём, пока MySQL будет доступен
while ! mysqladmin ping -h"mysql_db" -u"root" -p"${MYSQL_ROOT_PASSWORD}" --silent; do
    echo "⏳ Waiting for MySQL..."
    sleep 1
done

# Запускаем основной скрипт
python TinApyProject.py
