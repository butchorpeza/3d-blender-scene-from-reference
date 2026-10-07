#!/bin/bash
cd "C:/Users/HI/AppData/Local/Temp/claude/C--Users-HI-AppData-Local-Programs-Obsidian/f3cbc3a6-4b57-479b-b4ee-8119b1c67195/scratchpad"
SP="$(pwd -W)"
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P probe.py -- "$SP/ref.webp" "$SP/$1.png" 2>&1 | grep "^PROBE" | sed 's/ \([a-z_0-9]*=\)/\n   \1/g'
