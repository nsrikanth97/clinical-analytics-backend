#!/bin/sh

echo "This is test file"
ls -al /usr/src/app
python manage.py migrate

exec "$@"