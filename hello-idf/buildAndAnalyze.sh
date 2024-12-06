#!/bin/bash
./build.sh
exit
python3 analyzeBuildOutput.py > analyze.txt 2>&1