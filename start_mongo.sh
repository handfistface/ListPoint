#!/bin/bash

mkdir -p data/db

mongod --dbpath=data/db --bind_ip=127.0.0.1 --port=27017 --fork --logpath=data/mongodb.log

sleep 2

python app.py
