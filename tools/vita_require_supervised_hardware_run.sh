#!/usr/bin/env bash
set -euo pipefail

if [[ "${VITAKART_SUPERVISED_HARDWARE_RUN:-0}" == "1" ]]; then
    exit 0
fi

if [[ ! -t 0 || ! -t 1 ]]; then
    cat >&2 <<'MSG'
Refusing to continue: this command can build, install, or prepare a hardware run.

Re-run only when a tester is present, either from an interactive terminal or with:

    VITAKART_SUPERVISED_HARDWARE_RUN=1

Do not set that variable for unattended hardware deployment.
MSG
    exit 2
fi

cat <<'MSG'
This command may build, deploy, or prepare Vita Kart 64 for a hardware run.
A tester should be present before continuing.
MSG
printf 'Type SUPERVISED to continue: '
read -r answer

if [[ "$answer" != "SUPERVISED" ]]; then
    echo "Aborted: supervised hardware confirmation was not provided." >&2
    exit 2
fi
