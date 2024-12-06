#!/bin/bash
cd ../hello-idf/
source buildVerbose.sh

cd ../analyze
python3 analyze.py > analyze.txt 2>&1