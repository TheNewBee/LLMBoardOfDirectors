#!/bin/sh
for tid in 1 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 28 29 30 31 33 58; do
    d=/proc/1/task/$tid
    if [ -e $d/comm ]; then
        state=$(awk '/^State:/{print $2}' $d/status)
        wchan=$(cat $d/wchan 2>/dev/null)
        printf 'tid=%s state=%s wchan=%s\n' "$tid" "$state" "$wchan"
    fi
done
