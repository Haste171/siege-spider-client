#!/bin/bash

# Clean previous builds
rm -rf build dist *.spec

# Convert client to exe
pyinstaller \
  --onefile \
  --icon=assets/spider.ico \
  --hidden-import=queue \
  --clean \
  --log-level=DEBUG \
  match_client.py
