#!/usr/bin/bash

ps aux | grep '[p]ython bot.py' | awk '{print $2}' | xargs kill 2>/dev/null
