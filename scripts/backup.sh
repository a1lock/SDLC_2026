#!/bin/sh
# Ежедневная резервная копия БД: формат pg_dump -Fc, хранится 14 последних копий.
# Запуск из каталога проекта, например из cron в 03:00:
#   0 3 * * * cd /opt/sklad && BACKUP_DIR=/mnt/backup/sklad ./scripts/backup.sh
# Восстановление: docker compose exec -T db pg_restore -U sklad -d sklad --clean < файл.dump
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-14}"

mkdir -p "$BACKUP_DIR"
target="$BACKUP_DIR/sklad_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T db pg_dump -U sklad -Fc sklad > "$target"
echo "Копия сохранена: $target"

# Оставляем только KEEP последних копий.
ls -1t "$BACKUP_DIR"/sklad_*.dump | tail -n +"$((KEEP + 1))" | xargs -r rm --
