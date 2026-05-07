# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Java 애플리케이션(메신저 서버) 모니터링 대시보드 + 서버 관리 CLI 도구

- **server.js**: Node.js 모니터링 서버 (실시간 대시보드)
- **tuc_manager.py**: Python CLI 서버 관리 도구 (TUI)

## 개발 명령어

```bash
# 의존성 설치
npm install

# 모니터링 서버 실행 (기본 포트 3000)
node server.js

# 포트 변경
PORT=8080 node server.js

# TUC 서버 관리 CLI 실행 (Python 3.6 호환)
python3 tuc_manager.py
```

## 아키텍처

### server.js - 모니터링 서버

```
server.js
├── Express.js 정적 파일 서버 (public/)
├── WebSocket 서버 (클라이언트에 10초마다 데이터 푸시)
└── getMonitoringData() - 플랫폼별 데이터 수집
    ├── Java 프로세스 탐색: ms.jar, ss.jar (Windows: wmic, Linux: pgrep)
    ├── JVM 메트릭 수집: jstat -gc (힙 메모리, GC 통계)
    ├── 스레드 수: /proc/{pid}/status 또는 wmic
    └── 네트워크 상태: ss (Linux) 또는 netstat (Windows)
```

**주요 모니터링 대상**: `ms.jar` (Messaging), `ss.jar` (Session)

### tuc_manager.py - 서버 관리 CLI

```
tuc_manager.py
├── SERVERS[] - JAR 서버 정의 (이름, 경로, 디버그포트, Xms, Xmx)
├── TOMCAT_SERVERS[] - Tomcat 서버 정의
├── MONITOR_TARGETS - 실시간 JVM 모니터링 대상
└── 메뉴: 전체/개별 시작·중지·재시작, JVM 모니터링, 네트워크 확인, 로그 뷰어
```

**주요 기능**:

- Rich TUI 기반 인터랙티브 메뉴
- JVM 모니터링: `jstat -gc` 파싱, 힙/GC 메트릭
- 네트워크 모니터링: `ss` → `netstat` → `/proc/net/tcp` 폴백 chain
- 로그 뷰어: tail -f, grep 지원

## 플랫폼 호환성

- **server.js**: Windows (`wmic`) / Linux (`pgrep`, `/proc`)
- **tuc_manager.py**: Linux전용 (경로: `/tuc/tuc-service/server`)

## Git 워크플로우

1. 파일 수정 전: `git pull` 실행
2. 파일 수정 후: `git push` 실행
3. 커밋 메시지: **반드시 한국어**로 작성

## 사용 언어

**반드시 한국어로 응답**
