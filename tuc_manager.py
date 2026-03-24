#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════╗
║   TUC Server Manager CLI  v1.0.0         ║
║   SSH-compatible · Python3 · rich TUI    ║
╚══════════════════════════════════════════╝

설치: pip install rich
실행: python3 tuc_manager.py
"""

import os
import sys
import subprocess
import time
import re
import glob
import signal
import shutil
from datetime import datetime
from typing import Optional, Tuple, Dict, List

# ── rich 설치 여부 확인 ──────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.columns import Columns
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    from rich.align import Align
    from rich.rule import Rule
    from rich.syntax import Syntax
except ImportError:
    print("[ERROR] 'rich' 라이브러리가 필요합니다.")
    print("설치 명령어: pip3 install rich")
    sys.exit(1)

# ── 전역 콘솔 ─────────────────────────────────────────────────────────────────
console = Console()

# ══════════════════════════════════════════════════════════════════════════════
#  설정 (환경에 맞게 수정)
# ══════════════════════════════════════════════════════════════════════════════
TUC_HOME        = "/tuc/tuc-service/server"
TUC_MODULE_DIR  = f"{TUC_HOME}/module"
TUC_LOGS        = f"{TUC_HOME}/logs"
TUC_CONF        = f"{TUC_HOME}/conf"
TUC_HEAPDUMP    = f"{TUC_HOME}/heapdump"

TOMCAT_TUC      = "/tuc/apache-tomcat-6.0.35-tuc"
TOMCAT_TUCMAIL  = "/tuc/apache-tomcat-6.0.35-tucmail"

# 서버 정의: (이름, JAR경로, 디버그포트, Xms, Xmx)
SERVERS = [
    ("AlarmBatch",      f"{TUC_MODULE_DIR}/ab/ab.jar",                          5000, "1024m", "1024m"),
    ("Dispatcher",      f"{TUC_MODULE_DIR}/ds/ds.jar",                          5005, "1024m", "1024m"),
    ("Session",         f"{TUC_MODULE_DIR}/ss/ss.jar",                          5011, "6144m", "6144m"),
    ("Messaging",       f"{TUC_MODULE_DIR}/ms/ms.jar",                          5009, "2048m", "4096m"),
    ("Relay",           f"{TUC_MODULE_DIR}/rs/rs.jar",                          5010, "1024m", "1024m"),
    ("File",            f"{TUC_MODULE_DIR}/fs/fs.jar",                          5006, "2048m", "2048m"),
    ("Team",            f"{TUC_MODULE_DIR}/ts/ts.jar",                          5012, "1024m", "1024m"),
    ("GW_Filetransfer", f"{TUC_MODULE_DIR}/gs_filetransfer/gs_filetransfer.jar",5007, "1024m", "1024m"),
    ("BOT_BMS",         f"{TUC_MODULE_DIR}/bs_bms/bs_bms.jar",                  5002, "1024m", "1024m"),
    ("BOT_Link",        f"{TUC_MODULE_DIR}/bs_link/bs_link.jar",                5003, "512m",  "512m"),
    ("CyclicWorker",    f"{TUC_MODULE_DIR}/cw/cw.jar",                          5004, "512m",  "512m"),
]

TOMCAT_SERVERS = [
    ("Tomcat_TUC",    TOMCAT_TUC),
    ("Tomcat_TUCMAIL", TOMCAT_TUCMAIL),
]

MONITOR_TARGETS = ["ms.jar", "ss.jar"]   # JVM 모니터링 대상

# ══════════════════════════════════════════════════════════════════════════════
#  유틸리티
# ══════════════════════════════════════════════════════════════════════════════
def run(cmd: str, timeout: int = 10) -> Tuple[int, str, str]:
    """명령어 실행 → (returncode, stdout, stderr) — Python 3.6 호환"""
    try:
        r = subprocess.run(
            cmd, shell=True,
            stdout=subprocess.PIPE,   # capture_output=True 는 3.7+ 전용
            stderr=subprocess.PIPE,
            universal_newlines=True,  # text=True 는 3.7+ 전용
            timeout=timeout,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

def get_pid(jar_path: str) -> Optional[str]:
    """JAR 경로로 PID 조회 — 전체경로 우선, 파일명 폴백"""
    # 1차: 전체 경로로 탐색
    fname = os.path.basename(jar_path)
    _, out, _ = run(f"ps -ef | grep 'java' | grep '{fname}' | grep -v grep | awk '{{print $2}}'")
    pids = [p for p in out.split() if p.isdigit()]
    if pids:
        return pids[0]
    # 2차: 전체 경로로 재탐색 (경로 포함 실행 케이스)
    _, out2, _ = run(f"ps -ef | grep '{jar_path}' | grep -v grep | awk '{{print $2}}'")
    pids2 = [p for p in out2.split() if p.isdigit()]
    return pids2[0] if pids2 else None
def get_tomcat_pid(tomcat_path: str) -> Optional[str]:
    """Tomcat PID 조회 (jps 사용)"""
    _, out, _ = run(f"jps -v 2>/dev/null | grep Bootstrap | grep '{tomcat_path}/conf'")
    if out:
        parts = out.split()
        if parts and parts[0].isdigit():
            return parts[0]
    return None

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def clear():
    os.system("clear")

# ══════════════════════════════════════════════════════════════════════════════
#  헤더 배너
# ══════════════════════════════════════════════════════════════════════════════
def print_banner():
    banner = Text()
    banner.append("  ████████╗██╗   ██╗ ██████╗\n", style="bold cyan")
    banner.append("     ██╔══╝██║   ██║██╔════╝\n", style="bold cyan")
    banner.append("     ██║   ██║   ██║██║     \n", style="bold cyan")
    banner.append("     ██║   ██║   ██║██║     \n", style="bold cyan")
    banner.append("     ██║   ╚██████╔╝╚██████╗\n", style="bold cyan")
    banner.append("     ╚═╝    ╚═════╝  ╚═════╝\n", style="bold cyan")
    banner.append(f"  Server Manager CLI  ", style="dim white")
    banner.append(f"[{now_str()}]", style="dim cyan")

    console.print(Panel(
        Align.center(banner),
        border_style="cyan",
        padding=(0, 2),
    ))

# ══════════════════════════════════════════════════════════════════════════════
#  메인 메뉴
# ══════════════════════════════════════════════════════════════════════════════
def print_menu():
    menu_items = [
        ("[bold cyan]1[/]", "전체 서버 시작"),
        ("[bold cyan]2[/]", "전체 서버 중지"),
        ("[bold cyan]3[/]", "개별 서버 시작"),
        ("[bold cyan]4[/]", "개별 서버 중지"),
        ("[bold cyan]5[/]", "개별 서버 재시작"),
        ("[bold cyan]6[/]", "서버 상태 확인"),
        ("[bold yellow]7[/]", "실시간 JVM 모니터링"),
        ("[bold yellow]8[/]", "네트워크 상태 확인"),
        ("[bold magenta]9[/]", "로그 뷰어"),
        ("[bold red]0[/]",   "종료"),
    ]
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key",   style="", no_wrap=True, width=6)
    table.add_column("Action", style="white")
    for key, label in menu_items:
        table.add_row(key, label)

    console.print(Panel(table, title="[bold cyan]MENU[/]", border_style="cyan", width=50))
    console.print()

# ══════════════════════════════════════════════════════════════════════════════
#  서버 상태 테이블
# ══════════════════════════════════════════════════════════════════════════════
def build_status_table() -> Table:
    table = Table(
        title=f"[bold cyan]서버 상태[/]  [dim]{now_str()}[/]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("#",      width=3,  justify="right", style="dim")
    table.add_column("서버명",  width=18)
    table.add_column("타입",   width=7,  justify="center")
    table.add_column("상태",   width=10, justify="center")
    table.add_column("PID",    width=8,  justify="right")
    table.add_column("디버그포트", width=10, justify="center")
    table.add_column("메모리(Xms/Xmx)", width=16, justify="center")

    idx = 1
    for name, jar, port, xms, xmx in SERVERS:
        pid = get_pid(jar)
        status_text = Text("● RUNNING", style="bold green") if pid else Text("○ STOP   ", style="bold red")
        pid_text    = Text(pid or "—", style="cyan" if pid else "dim")
        mem_text    = f"{xms}/{xmx}"
        table.add_row(str(idx), f"[bold]{name}[/]", "JAR", status_text, pid_text, str(port), mem_text)
        idx += 1

    for name, path in TOMCAT_SERVERS:
        pid = get_tomcat_pid(path)
        status_text = Text("● RUNNING", style="bold green") if pid else Text("○ STOP   ", style="bold red")
        pid_text    = Text(pid or "—", style="cyan" if pid else "dim")
        table.add_row(str(idx), f"[bold]{name}[/]", "TOMCAT", status_text, pid_text, "—", "—")
        idx += 1

    return table

def show_status():
    clear()
    console.print(build_status_table())
    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  서버 시작 / 중지 함수
# ══════════════════════════════════════════════════════════════════════════════
def start_jar_server(name: str, jar: str, port: int, xms: str, xmx: str):
    pid = get_pid(jar)
    if pid:
        console.print(f"  [yellow]⚠  {name} 이미 실행 중 (PID: {pid})[/]")
        return

    log4j_key = jar.split("/")[-1].replace(".jar", "")
    opts = (
        f"-Xms{xms} -Xmx{xmx} "
        f"-server -XX:PermSize=128m -XX:MaxPermSize=256m "
        f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address={port} "
        f"-Dlog4j.configuration=file:{TUC_CONF}/log4j-{log4j_key}.properties "
        f"-Dtuc.base={TUC_HOME} -Dtuc.config.package=test"
    )
    cmd = f"nohup java {opts} -jar {jar} >/dev/null 2>&1 &"
    rc, _, err = run(cmd)
    time.sleep(0.8)
    new_pid = get_pid(jar)
    if new_pid:
        console.print(f"  [green]✔  {name} 시작 완료 — PID [{new_pid}][/]")
    else:
        console.print(f"  [red]✘  {name} 시작 실패[/]")

def stop_jar_server(name: str, jar: str):
    pid = get_pid(jar)
    if not pid:
        console.print(f"  [yellow]⚠  {name} 이미 중지 상태[/]")
        return
    run(f"kill {pid}")
    time.sleep(0.5)
    console.print(f"  [red]■  {name} 중지 완료 (PID: {pid})[/]")

def start_tomcat(name: str, path: str):
    pid = get_tomcat_pid(path)
    if pid:
        console.print(f"  [yellow]⚠  {name} 이미 실행 중 (PID: {pid})[/]")
        return
    run(f"sh {path}/bin/catalina.sh start")
    time.sleep(1.5)
    new_pid = get_tomcat_pid(path)
    if new_pid:
        console.print(f"  [green]✔  {name} 시작 완료 — PID [{new_pid}][/]")
    else:
        console.print(f"  [red]✘  {name} 시작 실패[/]")

def stop_tomcat(name: str, path: str):
    pid = get_tomcat_pid(path)
    if not pid:
        console.print(f"  [yellow]⚠  {name} 이미 중지 상태[/]")
        return
    run(f"sh {path}/bin/catalina.sh stop")
    time.sleep(0.5)
    console.print(f"  [red]■  {name} 중지 완료 (PID: {pid})[/]")

# ══════════════════════════════════════════════════════════════════════════════
#  전체 시작 / 중지
# ══════════════════════════════════════════════════════════════════════════════
def all_start():
    clear()
    console.print(Rule("[bold cyan]전체 서버 시작[/]", style="cyan"))
    console.print()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as prog:
        for name, jar, port, xms, xmx in SERVERS:
            task = prog.add_task(f"Starting {name}...", total=None)
            start_jar_server(name, jar, port, xms, xmx)
            prog.remove_task(task)
        for name, path in TOMCAT_SERVERS:
            task = prog.add_task(f"Starting {name}...", total=None)
            start_tomcat(name, path)
            prog.remove_task(task)
    console.print()
    console.print(Rule("[bold green]전체 시작 완료[/]", style="green"))
    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

def all_stop():
    clear()
    console.print(Rule("[bold red]전체 서버 중지[/]", style="red"))
    if not Confirm.ask("[red]정말 모든 서버를 중지하시겠습니까?[/]"):
        return
    console.print()
    all_svrs = list(reversed(SERVERS))
    for name, jar, *_ in all_svrs:
        stop_jar_server(name, jar)
    for name, path in reversed(TOMCAT_SERVERS):
        stop_tomcat(name, path)
    console.print()
    console.print(Rule("[bold red]전체 중지 완료[/]", style="red"))
    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  개별 서버 선택 UI
# ══════════════════════════════════════════════════════════════════════════════
ALL_SERVERS_LIST = [(n, j, p, xs, xm, "jar") for n, j, p, xs, xm in SERVERS] + \
                   [(n, pt, 0, "-", "-", "tomcat") for n, pt in TOMCAT_SERVERS]

def select_server_menu(action: str) -> Optional[tuple]:
    """서버 선택 테이블 출력 후 번호 입력"""
    label_map = {"start": "시작", "stop": "중지", "restart": "재시작"}
    clear()
    console.print(Rule(f"[bold cyan]개별 서버 {label_map[action]}[/]", style="cyan"))
    console.print()

    table = Table(box=box.SIMPLE_HEAD, header_style="bold cyan", border_style="cyan")
    table.add_column("#", width=4, justify="right", style="dim")
    table.add_column("서버명", width=20)
    table.add_column("타입",  width=8)
    table.add_column("상태",  width=12)

    for i, (name, path, port, xms, xmx, stype) in enumerate(ALL_SERVERS_LIST, 1):
        if stype == "jar":
            pid = get_pid(path)
        else:
            pid = get_tomcat_pid(path)
        st = Text("● RUNNING", style="green") if pid else Text("○ STOP", style="red")
        table.add_row(str(i), name, stype.upper(), st)

    console.print(table)
    console.print()

    total = len(ALL_SERVERS_LIST)
    raw = Prompt.ask(f"[cyan]서버 번호 입력[/] [dim](1~{total}, 0=취소)[/]")
    if not raw.isdigit():
        console.print("[red]잘못된 입력[/]")
        return None
    num = int(raw)
    if num == 0:
        return None
    if not (1 <= num <= total):
        console.print("[red]범위를 벗어났습니다.[/]")
        return None
    return ALL_SERVERS_LIST[num - 1]

def individual_action(action: str):
    srv = select_server_menu(action)
    if not srv:
        return
    name, path, port, xms, xmx, stype = srv
    console.print()
    console.print(Rule(f"[bold cyan]{name} {action}[/]", style="cyan"))
    console.print()

    if stype == "jar":
        if action == "start":
            start_jar_server(name, path, port, xms, xmx)
        elif action == "stop":
            stop_jar_server(name, path)
        elif action == "restart":
            stop_jar_server(name, path)
            console.print("  [dim]2초 대기...[/]")
            time.sleep(2)
            start_jar_server(name, path, port, xms, xmx)
    else:
        if action == "start":
            start_tomcat(name, path)
        elif action == "stop":
            stop_tomcat(name, path)
        elif action == "restart":
            stop_tomcat(name, path)
            console.print("  [dim]5초 대기...[/]")
            time.sleep(5)
            start_tomcat(name, path)

    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  JVM 모니터링
# ══════════════════════════════════════════════════════════════════════════════
def parse_jstat(pid: str) -> Optional[dict]:
    """jstat -gc 결과 파싱"""
    rc, out, _ = run(f"jstat -gc {pid}", timeout=5)
    if rc != 0 or not out:
        return None
    lines = out.strip().split("\n")
    if len(lines) < 2:
        return None
    vals = lines[-1].split()
    try:
        eu    = float(vals[5])   # Eden Used
        ec    = float(vals[4])   # Eden Capacity
        ou    = float(vals[7])   # Old Used
        oc    = float(vals[6])   # Old Capacity
        mu    = float(vals[9])   # Meta Used
        mc    = float(vals[8])   # Meta Capacity
        ygc   = int(float(vals[12]))
        fgc   = int(float(vals[14]))
        gct   = float(vals[16])
        total_cap  = ec + oc
        total_used = eu + ou
        util = round(total_used / total_cap * 100, 1) if total_cap > 0 else 0
        return {
            "eden_pct":  round(eu / ec * 100, 1) if ec > 0 else 0,
            "old_pct":   round(ou / oc * 100, 1) if oc > 0 else 0,
            "meta_pct":  round(mu / mc * 100, 1) if mc > 0 else 0,
            "heap_used": round(total_used / 1024, 1),
            "heap_cap":  round(total_cap  / 1024, 1),
            "heap_pct":  util,
            "ygc": ygc, "fgc": fgc, "gct": round(gct, 3),
        }
    except (IndexError, ValueError):
        return None

def get_thread_count(pid: str) -> str:
    _, out, _ = run(f"cat /proc/{pid}/status 2>/dev/null | grep Threads | awk '{{print $2}}'")
    return out.strip() or "—"

def pct_bar(pct: float, width: int = 20) -> Text:
    """퍼센트 막대 생성"""
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if pct < 60 else ("yellow" if pct < 85 else "red")
    t = Text()
    t.append(f"[{bar}]", style=color)
    t.append(f" {pct:5.1f}%", style=f"bold {color}")
    return t

def build_jvm_panel(name: str, jar: str) -> Panel:
    pid = get_pid(jar)
    if not pid:
        return Panel(
            Align.center(Text("● 프로세스 없음", style="bold red")),
            title=f"[bold cyan]{name}[/]",
            border_style="red",
        )

    jstat  = parse_jstat(pid)
    threads = get_thread_count(pid)

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("label", style="dim", width=14)
    table.add_column("value")

    table.add_row("PID",     Text(pid, style="bold cyan"))
    table.add_row("Threads", Text(threads, style="yellow"))

    if jstat:
        table.add_row("Heap",   pct_bar(jstat["heap_pct"]))
        table.add_row("  Used", Text(f"{jstat['heap_used']} MB / {jstat['heap_cap']} MB", style="dim"))
        table.add_row("Eden",   pct_bar(jstat["eden_pct"]))
        table.add_row("Old",    pct_bar(jstat["old_pct"]))
        table.add_row("Meta",   pct_bar(jstat["meta_pct"]))
        table.add_row("YGC",    Text(str(jstat["ygc"]), style="green"))
        table.add_row("FGC",    Text(str(jstat["fgc"]), style="red"))
        table.add_row("GCT",    Text(f"{jstat['gct']}s", style="cyan"))
    else:
        table.add_row("jstat", Text("데이터 없음", style="dim red"))

    return Panel(table, title=f"[bold cyan]{name}[/] [dim]({jar.split('/')[-1]})[/]", border_style="cyan")

def _try_cmds(cmds, timeout=5):
    """명령어 목록을 순서대로 시도, 출력 있는 첫 번째 결과 반환"""
    for cmd in cmds:
        rc, out, err = run(cmd, timeout=timeout)
        if out.strip():
            return out, cmd, ""
    # 모두 실패 시 마지막 에러 반환
    return "", cmds[-1], err

def _parse_proc_net_tcp(hex_state_filter=None):
    """
    /proc/net/tcp(6) 직접 파싱 — ss/netstat 없어도 동작
    hex_state_filter: None=모두, {'0A'}=ESTABLISHED 등
    반환: Dict[ip_str, count]
    """
    ip_counts: Dict[str, int] = {}
    state_counts: Dict[str, int] = {"estab": 0, "time_wait": 0, "close_wait": 0}

    STATE_MAP = {
        "01": "estab",
        "06": "time_wait",
        "08": "close_wait",
    }

    for fname in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(fname) as f:
                lines = f.readlines()[1:]  # 헤더 스킵
        except IOError:
            continue

        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            state_hex = parts[3].upper()
            label = STATE_MAP.get(state_hex)
            if label:
                state_counts[label] = state_counts.get(label, 0) + 1

            # ESTAB(01) 만 IP 수집
            if state_hex != "01":
                continue
            remote_field = parts[2]           # hex "ip:port"
            try:
                hex_ip, hex_port = remote_field.split(":")
                if len(hex_ip) == 8:           # IPv4
                    b = bytes.fromhex(hex_ip)
                    ip_str = f"{b[3]}.{b[2]}.{b[1]}.{b[0]}"
                elif len(hex_ip) == 32:        # IPv6
                    # 표시만 간략화
                    ip_str = ":".join(
                        hex_ip[i:i+4] for i in range(0, 32, 4)
                    )
                else:
                    continue
                if ip_str in ("0.0.0.0", "127.0.0.1", "::1"):
                    continue
                ip_counts[ip_str] = ip_counts.get(ip_str, 0) + 1
            except Exception:
                continue

    return state_counts, ip_counts

def build_network_panel() -> Panel:
    """네트워크 상태 — ss → netstat → /proc/net/tcp 순으로 폴백"""

    net    = {"estab": 0, "time_wait": 0, "close_wait": 0}
    ip_counts: Dict[str, int] = {}
    source_label = ""
    raw_lines: List[str] = []

    # ── 1단계: ss 시도 (경로 여러 개) ─────────────────────────────────────
    SS_BINS = ["ss", "/usr/sbin/ss", "/sbin/ss", "/bin/ss"]
    ss_bin = None
    for b in SS_BINS:
        rc, out, _ = run(f"{b} -s", timeout=4)
        if out.strip():
            ss_bin = b
            # 요약 파싱
            for line in out.splitlines():
                m = re.search(r"estab[\s:]+([\d]+)", line, re.I)
                if m: net["estab"] = int(m.group(1))
                m = re.search(r"time.?wait[\s:]+([\d/]+)", line, re.I)
                if m: net["time_wait"] = int(m.group(1).split("/")[0])
                m = re.search(r"close.?wait[\s:]+([\d]+)", line, re.I)
                if m: net["close_wait"] = int(m.group(1))
            source_label = f"ss ({b})"
            break

    if ss_bin:
        # IP 목록은 ss -tan
        _, tan_out, _ = run(f"{ss_bin} -tan", timeout=5)
        raw_lines = tan_out.splitlines()[1:]
        for line in raw_lines:
            parts = line.split()
            if len(parts) < 5:
                continue
            state = parts[0]
            if state not in ("ESTAB", "ESTABLISHED", "TIME-WAIT", "TIMEWAIT", "CLOSE-WAIT"):
                continue
            # ss -tan 컬럼: State Recv-Q Send-Q Local Peer
            peer = parts[4]
            peer_ip = peer.rsplit(":", 1)[0].strip("[]").replace("::ffff:", "")
            if peer_ip in ("-", "*", "", "0.0.0.0", "127.0.0.1"):
                continue
            ip_counts[peer_ip] = ip_counts.get(peer_ip, 0) + 1

    # ── 2단계: netstat 폴백 ────────────────────────────────────────────────
    if not ss_bin:
        _, ns_out, ns_err = run("netstat -tan 2>&1", timeout=8)
        if ns_out.strip() and "command not found" not in ns_out:
            source_label = "netstat"
            for line in ns_out.splitlines():
                parts = line.split()
                if len(parts) < 6:
                    continue
                # netstat -tan: Proto Recv-Q Send-Q Local Foreign State
                state = parts[5] if len(parts) >= 6 else ""
                foreign = parts[4] if len(parts) >= 5 else ""
                if state == "ESTABLISHED":
                    net["estab"] += 1
                    peer_ip = foreign.rsplit(":", 1)[0]
                    if peer_ip not in ("0.0.0.0", "127.0.0.1", "*"):
                        ip_counts[peer_ip] = ip_counts.get(peer_ip, 0) + 1
                elif state == "TIME_WAIT":
                    net["time_wait"] += 1
                elif state == "CLOSE_WAIT":
                    net["close_wait"] += 1

    # ── 3단계: /proc/net/tcp 직접 파싱 폴백 ──────────────────────────────
    if not ss_bin and not ip_counts and net["estab"] == 0:
        source_label = "/proc/net/tcp"
        proc_counts, proc_ips = _parse_proc_net_tcp()
        net.update(proc_counts)
        ip_counts = proc_ips

    # ── 연결 상태 테이블 ──────────────────────────────────────────────────
    conn_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan",
                       title="[bold]연결 상태[/]", padding=(0, 1))
    conn_table.add_column("상태",  width=14)
    conn_table.add_column("COUNT", justify="right", width=8)

    e_color = "green" if net["estab"] < 1000 else ("yellow" if net["estab"] < 5000 else "red")
    conn_table.add_row(Text("Established", style="bold"),
                       Text(str(net["estab"]),      style=f"bold {e_color}"))
    conn_table.add_row(Text("Time Wait",   style="dim"),
                       Text(str(net["time_wait"]),  style="yellow"))
    conn_table.add_row(Text("Close Wait",  style="dim"),
                       Text(str(net["close_wait"]), style="red"))

    # ── Peer IP 테이블 ────────────────────────────────────────────────────
    ip_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan",
                     title="[bold]Peer IP Top 10[/]", padding=(0, 1))
    ip_table.add_column("IP",  width=24)
    ip_table.add_column("Cnt", justify="right", width=6)

    top_ips = sorted(ip_counts.items(), key=lambda x: -x[1])[:10]
    if top_ips:
        for ip, cnt in top_ips:
            color = "red" if cnt >= 100 else ("yellow" if cnt >= 30 else "cyan")
            ip_table.add_row(ip, Text(str(cnt), style=f"bold {color}"))
    else:
        ip_table.add_row("[dim]활성 외부 연결 없음[/]", "")

    content = Columns([conn_table, ip_table], equal=False, expand=False)
    subtitle = (
        f"[dim cyan]data: {source_label}  ·  {now_str()}[/]"
        if source_label else
        f"[yellow]명령어 없음 — /proc/net/tcp 파싱 사용[/]"
    )
    return Panel(content, title="[bold cyan]Network Monitor[/]",
                 subtitle=subtitle, border_style="cyan")


def monitor_live():
    """실시간 JVM + 네트워크 모니터링 (Ctrl+C 종료)"""
    clear()
    console.print("[dim]Ctrl+C 를 눌러 모니터링 종료[/]\n")

    try:
        with Live(console=console, refresh_per_second=0.1, screen=False) as live:
            while True:
                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="jvm"),
                    Layout(name="network", size=16),
                )
                layout["header"].update(
                    Panel(
                        Text(f"  TUC JVM Monitor  ·  {now_str()}  ·  갱신주기: 10s",
                             style="bold cyan", justify="center"),
                        border_style="cyan", padding=(0, 0),
                    )
                )

                jvm_panels = []
                for name, jar, *_ in SERVERS:
                    if any(t in jar for t in MONITOR_TARGETS):
                        jvm_panels.append(build_jvm_panel(name, jar))

                # 모니터링 대상이 없으면 전체 서버 표시
                if not jvm_panels:
                    for name, jar, *_ in SERVERS:
                        jvm_panels.append(build_jvm_panel(name, jar))

                layout["jvm"].update(Columns(jvm_panels, equal=True, expand=True))
                layout["network"].update(build_network_panel())

                live.update(layout)
                time.sleep(10)
    except KeyboardInterrupt:
        pass
    console.print("\n[dim]모니터링을 종료했습니다.[/]")
    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  네트워크 상태 (단독 메뉴)
# ══════════════════════════════════════════════════════════════════════════════
def show_network():
    clear()
    console.print(build_network_panel())
    console.print()
    Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  로그 뷰어
# ══════════════════════════════════════════════════════════════════════════════
def log_viewer():
    """로그 파일 선택 및 tail 보기"""
    log_pattern = f"{TUC_LOGS}/*.log"
    log_files = sorted(glob.glob(log_pattern))

    while True:
        clear()
        console.print(Rule("[bold magenta]로그 뷰어[/]", style="magenta"))
        console.print()

        if not log_files:
            console.print(f"[red]로그 파일을 찾을 수 없습니다: {log_pattern}[/]")
            console.print()
            Prompt.ask("[dim]엔터를 눌러 메뉴로 돌아가기[/]", default="")
            return

        table = Table(box=box.SIMPLE_HEAD, header_style="bold magenta", border_style="magenta")
        table.add_column("#",    width=4, justify="right", style="dim")
        table.add_column("파일명", width=40)
        table.add_column("크기",  width=10, justify="right")
        table.add_column("수정일", width=22)

        for i, fpath in enumerate(log_files, 1):
            fname = os.path.basename(fpath)
            try:
                stat  = os.stat(fpath)
                size  = f"{stat.st_size // 1024} KB"
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except:
                size, mtime = "—", "—"
            table.add_row(str(i), fname, size, mtime)

        console.print(table)
        console.print()
        console.print("[dim]조회 방법: 번호(tail -n), 'g'(grep), 0(돌아가기)[/]")
        console.print()

        raw = Prompt.ask("[magenta]로그 번호 또는 명령[/]")

        if raw == "0":
            return

        # grep 검색
        if raw.lower() == "g":
            keyword = Prompt.ask("[magenta]검색어[/]")
            file_num = Prompt.ask("[magenta]파일 번호[/]")
            if file_num.isdigit() and 1 <= int(file_num) <= len(log_files):
                fpath = log_files[int(file_num) - 1]
                clear()
                console.print(Rule(f"[magenta]grep '{keyword}' ← {os.path.basename(fpath)}[/]", style="magenta"))
                rc, out, _ = run(f"grep -n '{keyword}' '{fpath}' | tail -100", timeout=15)
                if out:
                    for line in out.splitlines():
                        # 라인번호 하이라이트
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            console.print(f"[dim]{parts[0]:>6}[/]  {parts[1]}")
                        else:
                            console.print(line)
                else:
                    console.print("[dim]검색 결과 없음[/]")
                console.print()
                Prompt.ask("[dim]엔터 계속[/]", default="")
            continue

        if not raw.isdigit() or not (1 <= int(raw) <= len(log_files)):
            console.print("[red]잘못된 입력[/]")
            time.sleep(1)
            continue

        fpath = log_files[int(raw) - 1]
        fname = os.path.basename(fpath)

        # tail 줄 수 선택
        lines_raw = Prompt.ask("[magenta]몇 줄 출력?[/]", default="100")
        n = int(lines_raw) if lines_raw.isdigit() else 100

        # follow 여부
        follow = Confirm.ask("[magenta]실시간 follow (-f)?[/]", default=False)

        clear()
        console.print(Rule(f"[magenta]{fname}[/]  [dim]tail -{n}{'f' if follow else ''}[/]", style="magenta"))
        console.print("[dim]종료: Ctrl+C[/]\n")

        if follow:
            proc = None
            try:
                proc = subprocess.Popen(
                    ["tail", f"-n{n}", "-f", fpath],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    universal_newlines=True, bufsize=1,
                )
                for line in proc.stdout:
                    # 로그 레벨 색상
                    if "ERROR" in line or "FATAL" in line:
                        console.print(Text(line.rstrip(), style="bold red"))
                    elif "WARN" in line:
                        console.print(Text(line.rstrip(), style="yellow"))
                    elif "INFO" in line:
                        console.print(Text(line.rstrip(), style="white"))
                    else:
                        console.print(Text(line.rstrip(), style="dim"))
            except KeyboardInterrupt:
                if proc:
                    proc.terminate()
                    proc.wait()
        else:
            rc, out, _ = run(f"tail -n {n} '{fpath}'", timeout=15)
            for line in out.splitlines():
                if "ERROR" in line or "FATAL" in line:
                    console.print(Text(line, style="bold red"))
                elif "WARN" in line:
                    console.print(Text(line, style="yellow"))
                elif "INFO" in line:
                    console.print(Text(line, style="white"))
                else:
                    console.print(Text(line, style="dim"))

        console.print()
        Prompt.ask("[dim]엔터 계속[/]", default="")

# ══════════════════════════════════════════════════════════════════════════════
#  메인 루프
# ══════════════════════════════════════════════════════════════════════════════
def check_user():
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if user and user != "tuc":
        console.print(f"[red bold]이 스크립트는 'tuc' 계정에서만 실행할 수 있습니다. (현재: {user})[/]")
        sys.exit(1)

def graceful_exit():
    clear()
    console.print(Panel(
        Align.center(Text("종료합니다. Goodbye.", style="bold cyan")),
        border_style="cyan", padding=(1, 0),
    ))
    sys.exit(0)

def main():
    check_user()

    while True:
        clear()
        print_banner()
        print_menu()

        try:
            choice = Prompt.ask("[cyan]선택[/]", default="")
        except (KeyboardInterrupt, EOFError):
            graceful_exit()

        choice = choice.strip()

        try:
            if   choice == "1": all_start()
            elif choice == "2": all_stop()
            elif choice == "3": individual_action("start")
            elif choice == "4": individual_action("stop")
            elif choice == "5": individual_action("restart")
            elif choice == "6": show_status()
            elif choice == "7": monitor_live()
            elif choice == "8": show_network()
            elif choice == "9": log_viewer()
            elif choice == "0": graceful_exit()
            else:
                console.print("[red]잘못된 입력입니다.[/]")
                time.sleep(0.8)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]⚠  작업이 중단되었습니다. 메인 메뉴로 돌아갑니다.[/]")
            time.sleep(1)

if __name__ == "__main__":
    main()
