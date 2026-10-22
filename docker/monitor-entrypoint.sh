#!/bin/sh
set -eu

set -- --pcap "${PCAP_PATH:-/captures/demo.pcap}" --database-url "$DATABASE_URL"
if [ -n "${MODEL_PATH:-}" ]; then
    set -- "$@" --model "$MODEL_PATH"
fi

exec python -m nids_engine.monitor "$@"
