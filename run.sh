#!/bin/bash

OLD_PATH=$PATH
source /home/pimania/dev/guiFromCron/crongui.sh
PATH=$PATH:$OLD_PATH
cd /home/pimania/dev/convertLinks
uv run convertLinks.py "$@"
