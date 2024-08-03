#!/usr/bin/bash
pid=$(ps aux | grep '[p]ython bot.py' | awk '{print $2}')
if [ "$pid" == "" ]; then
	echo "Bot is not running."
else
	echo "Bot is running - pid: ${pid}"
fi
