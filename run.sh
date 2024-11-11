#!/bin/bash

OLD_PATH=$PATH
source /home/pimania/dev/guiFromCron/crongui.sh
PATH=$PATH:$OLD_PATH
uv run /home/pimania/dev/convertLinks/convertLinks.py