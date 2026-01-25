#!/bin/bash

set -euo pipefail

trap func_exit SIGINT

function func_exit()
{
    sleep 1
    if [ "${ONOFF}" == "true" ]; then
        python dl24-logger.py --onoff
    fi
    sudo rfcomm unbind 0 ${BD_ADDR} 1
    deactivate
    exit 1
}

ONOFF="false"
BD_ADDR="${1:--h}"
BD_ADDR_REGEX="^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$"

if [ $# -gt 0 ]; then
    shift
fi

ARGS="$@"
if [ $# -eq 0 ]; then
    ARGS="-h"
fi

if [ "${BD_ADDR}" == "-h" ] || [ "${BD_ADDR}" == "--help" ]; then
    echo "usage: dl24-logger.sh [-h] [BD_ADDR] [dl24-logger.py parameters]"
    exit 0
fi

if [[ ! "${BD_ADDR}" =~ ${BD_ADDR_REGEX} ]]; then
    echo "Wrong BD_ADDR"
    exit 1
fi

for arg in ${ARGS}
do
    if [ "${arg}" == "--onoff" ]; then
        ONOFF="true"
        break
    fi
done

source .venv/bin/activate
sudo rfcomm bind 0 ${BD_ADDR} 1
python dl24-logger.py ${ARGS}
sudo rfcomm unbind 0 ${BD_ADDR} 1
deactivate

