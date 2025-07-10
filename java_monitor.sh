#!/bin/bash

LOG_DIR="/root/tmp"
LOG_FILE="$LOG_DIR/java_monitor.log"

mkdir -p "$LOG_DIR"

while true; do
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    echo "=== $TIMESTAMP ===" | tee -a "$LOG_FILE"

    # JVM 프로세스 확인
    JAVA_PID=$(pgrep -f "java.*ss.jar")

    if [ -n "$JAVA_PID" ]; then
        echo "JVM PID: $JAVA_PID" | tee -a "$LOG_FILE"

        # 메모리 사용량
        echo "Heap Usage:" | tee -a "$LOG_FILE"
        jstat -gc $JAVA_PID | tail -1 | tee -a "$LOG_FILE"

        # 스레드 수
        THREAD_COUNT=$(ps -eLf | awk -v pid="$JAVA_PID" '$2==pid' | wc -l)
        echo "Thread Count: $THREAD_COUNT" | tee -a "$LOG_FILE"
    else
        echo "WARNING: JVM process not found!" | tee -a "$LOG_FILE"
    fi

    # TCP 연결 상태
    echo "Network Status:" | tee -a "$LOG_FILE"
    ss -s | grep TCP | tee -a "$LOG_FILE"

    # 연결 요약 (ESTAB, CLOSE_WAIT 등) count 1개 이상 ip 출력
    echo "Connection State Summary:" | tee -a "$LOG_FILE"
    ss -tan | awk '/ESTAB|CLOSE-WAIT|TIME-WAIT/ {ip=$5; count[ip]++} END {for (i in count) if (count[i]>1) print i, count[i]}' | tee -a "$LOG_FILE"

    echo "---" | tee -a "$LOG_FILE"
    sleep 10
done
