#!/bin/bash
cd ../hello-idf/
source build.sh

cd ../analyze
python3 analyze.py > analyze.txt 2>&1