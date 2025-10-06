#!/bin/bash

mkdir -p data/db

mongod --dbpath=data/db --bind_ip=127.0.0.1 --port=27017 --fork --logpath=data/mongodb.log

sleep 2

gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
