#!/bin/bash
# usage: run.sh name [args...]
cd "C:/Users/HI/AppData/Local/Temp/claude/C--Users-HI-AppData-Local-Programs-Obsidian/f3cbc3a6-4b57-479b-b4ee-8119b1c67195/scratchpad"
N=$1; shift
SP="$(pwd -W 2>/dev/null || pwd)"
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P build_room.py -- out="$SP/$N.png" "$@" 2>&1 | grep -E "parquet|err|ERROR|RENDER|Traceback|Error|File " 
