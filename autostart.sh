#!/usr/bin/bash

if [ -z "${TMUX+x}" ]; then
    echo "Starting tmux session for manager"
    tmux new-session -d -s manager "$0"
else
    cd "$(dirname "$0")"
    . ./secrets.sh
    ./manager.py
fi
