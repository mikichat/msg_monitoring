const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;

// 정적 파일 제공
app.use(express.static(path.join(__dirname, 'public')));

wss.on('connection', (ws) => {
  console.log('Client connected');

  const monitorInterval = setInterval(async () => {
    try {
      const data = await getMonitoringData();
      ws.send(JSON.stringify(data));
    } catch (error) {
      console.error('Monitoring Error:', error.message);
      ws.send(JSON.stringify({ error: error.message }));
    }
  }, 10000); // Run every 10 seconds

  ws.on('close', () => {
    console.log('Client disconnected');
    clearInterval(monitorInterval);
  });

  ws.on('error', (error) => {
    console.error('WebSocket Error:', error);
    clearInterval(monitorInterval);
  });
});

async function getMonitoringData() {
  const isWindows = process.platform === 'win32';
  const data = { timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19) };

  // 1. Find PIDs for both ms.jar and ss.jar
  const targets = ['ms.jar', 'ss.jar'];
  const foundProcesses = [];

  for (const target of targets) {
    let pid = null;
    try {
      if (isWindows) {
        const { stdout } = await execPromise(
          `wmic process where "name='java.exe' and commandline like '%${target}%'" get processid`
        );
        const pids = stdout && stdout.match(/\d+/g);
        if (pids) {
          for (const p of pids) {
            if (p !== '0') foundPids.push(p);
          }
        }
      } else {
        const { stdout } = await execPromise(`pgrep -f "java.*-jar /.*\\/${target}( |$)" | grep -v "bs_bms.jar"`);
        const pids = stdout && stdout.trim().split('\n').filter(Boolean);
        if (pids) foundPids.push(...pids);
      }
    } catch (e) {
      // ignore and continue to next target
    }

    for (const pid of foundPids) {
      if (!pid) continue;

      // 2. Get Thread Count for this PID
    const threadCountCommand = isWindows
      ? `wmic process where processid=${pid} get ThreadCount`
      : `cat /proc/${pid}/status | grep Threads | awk '{print $2}'`;
    const { stdout: threadStdout } = await execPromise(threadCountCommand);
    const threadMatch = threadStdout.match(/\d+/g);
    const threadCount = threadMatch ? (isWindows ? threadMatch[1] : threadMatch[0]) : undefined;

    // 3. Get Heap Usage for this PID
    const { stdout: heapStdout } = await execPromise(`jstat -gc ${pid}`);
    const heapLines = heapStdout.trim().split('\n');
    const heapData = heapLines[heapLines.length - 1].trim();
    const heapValues = heapData.split(/\s+/);
    const heapUsage = {
      raw: heapData,
      parsed: {
        youngGen: {
          s0c: parseFloat(heapValues[0]) || 0,
          s1c: parseFloat(heapValues[1]) || 0,
          s0u: parseFloat(heapValues[2]) || 0,
          s1u: parseFloat(heapValues[3]) || 0,
          ec: parseFloat(heapValues[4]) || 0,
          eu: parseFloat(heapValues[5]) || 0,
        },
        oldGen: {
          oc: parseFloat(heapValues[6]) || 0,
          ou: parseFloat(heapValues[7]) || 0,
        },
        metaspace: {
          mc: parseFloat(heapValues[8]) || 0,
          mu: parseFloat(heapValues[9]) || 0,
        },
        gc: {
          ygc: parseInt(heapValues[12]) || 0,
          ygct: parseFloat(heapValues[13]) || 0,
          fgc: parseInt(heapValues[14]) || 0,
          fgct: parseFloat(heapValues[15]) || 0,
          gct: parseFloat(heapValues[16]) || 0
        }
      },
      summary: {
        totalHeapCapacity: Math.round(((parseFloat(heapValues[4]) || 0) + (parseFloat(heapValues[6]) || 0)) / 1024),
        totalHeapUsed: Math.round(((parseFloat(heapValues[5]) || 0) + (parseFloat(heapValues[7]) || 0)) / 1024),
        heapUtilization: Math.round(((parseFloat(heapValues[5]) || 0) + (parseFloat(heapValues[7]) || 0)) / ((parseFloat(heapValues[4]) || 0) + (parseFloat(heapValues[6]) || 0)) * 100),
        youngGenUtilization: Math.round((parseFloat(heapValues[5]) || 0) / (parseFloat(heapValues[4]) || 1) * 100),
        oldGenUtilization: Math.round((parseFloat(heapValues[7]) || 0) / (parseFloat(heapValues[6]) || 1) * 100),
        metaspaceUtilization: Math.round((parseFloat(heapValues[9]) || 0) / (parseFloat(heapValues[8]) || 1) * 100),
        totalGcCount: (parseInt(heapValues[12]) || 0) + (parseInt(heapValues[14]) || 0),
        totalGcTime: Math.round((parseFloat(heapValues[16]) || 0) * 1000) / 1000
      }
    };

    foundProcesses.push({ target: `${target}-${pid}`, pid, threadCount, heapUsage });
    }
  }

  if (foundProcesses.length === 0) {
    throw new Error('Target Java processes not found. (ms.jar, ss.jar)');
  }
  data.processes = foundProcesses;

  // 각 프로세스의 데이터를 개별 필드로 추가
  data.msJarProcesses = [];
  data.ssJarProcesses = [];
  foundProcesses.forEach(p => {
    if (p.target.startsWith('ms.jar')) {
      data.msJarProcesses.push({ pid: p.pid, threadCount: p.threadCount, heapUsage: p.heapUsage });
    } else if (p.target.startsWith('ss.jar')) {
      data.ssJarProcesses.push({ pid: p.pid, threadCount: p.threadCount, heapUsage: p.heapUsage });
    }
  });
  // 기존 단일 필드는 제거 (클라이언트에서 data.processes 또는 새로 추가된 필드를 사용하도록 유도)

  // 4. Get Network Info
  if (isWindows) {
    const { stdout: netstatStdout } = await execPromise('netstat -an');
    const netstatLines = netstatStdout.trim().split('\n');
    const networkStatus = { 
      estab: 0, 
      time_wait: 0, 
      close_wait: 0,
      closed: 0,
      orphaned: 0
    };
    const connectionSummary = {};
    
    netstatLines.forEach(line => {
        const upperLine = line.toUpperCase();
        const parts = line.trim().split(/\s+/);
        if (upperLine.includes('ESTABLISHED')) {
            networkStatus.estab++;
            const ip = parts[2];
            if (ip) connectionSummary[ip] = (connectionSummary[ip] || 0) + 1;
        }
        if (upperLine.includes('TIME_WAIT')) networkStatus.time_wait++;
        if (upperLine.includes('CLOSE_WAIT')) networkStatus.close_wait++;
        if (upperLine.includes('CLOSED')) networkStatus.closed++;
    });
    
    data.networkStatus = networkStatus;
    // Count가 2 이상인 연결만 필터링
    data.connectionSummary = Object.entries(connectionSummary)
      .filter(([ip, count]) => count >= 2)
      .map(([ip, count]) => ({ ip, count }));
  } else { // Linux
    const { stdout: ssStatusStdout } = await execPromise('ss -s');
    
    // 네트워크 상태 초기화
    const networkStatus = { 
      estab: 0, 
      time_wait: 0, 
      close_wait: 0,
      closed: 0,
      orphaned: 0
    };
    
    // ss -s 출력 전체에서 각 상태값을 찾아서 파싱
    const statusLines = ssStatusStdout.split('\n');
    
    statusLines.forEach(line => {
      const trimmedLine = line.trim();
      
      // TCP 라인에서 established 연결 수 추출
      if (trimmedLine.startsWith('TCP:')) {
        const estabMatch = trimmedLine.match(/estab (\d+)/);
        if (estabMatch) networkStatus.estab = parseInt(estabMatch[1]);
      }
      
      // 각 상태별로 개별 매칭 (대소문자 구분 없이)
      const timeWaitMatch = trimmedLine.match(/timewait (\d+)/i) || trimmedLine.match(/time-wait (\d+)/i);
      const closeWaitMatch = trimmedLine.match(/closewait (\d+)/i) || trimmedLine.match(/close-wait (\d+)/i);
      const closedMatch = trimmedLine.match(/closed (\d+)/i);
      const orphanedMatch = trimmedLine.match(/orphaned (\d+)/i);
      
      if (timeWaitMatch) networkStatus.time_wait = parseInt(timeWaitMatch[1]);
      if (closeWaitMatch) networkStatus.close_wait = parseInt(closeWaitMatch[1]);
      if (closedMatch) networkStatus.closed = parseInt(closedMatch[1]);
      if (orphanedMatch) networkStatus.orphaned = parseInt(orphanedMatch[1]);
    });
    
    // ss -tan 결과로부터 추가 상태 정보 수집 (백업용)
    try {
      const { stdout: ssTanStdout } = await execPromise('ss -tan | grep -E "(TIME-WAIT|CLOSE-WAIT)" | wc -l');
      const additionalCounts = await execPromise('ss -tan | awk \'$1=="TIME-WAIT" {tw++} $1=="CLOSE-WAIT" {cw++} END {print tw+0, cw+0}\'');
      const [timeWaitCount, closeWaitCount] = additionalCounts.stdout.trim().split(' ').map(n => parseInt(n) || 0);
      
      // ss -s에서 값을 찾지 못한 경우 ss -tan 결과 사용
      if (networkStatus.time_wait === 0 && timeWaitCount > 0) {
        networkStatus.time_wait = timeWaitCount;
      }
      if (networkStatus.close_wait === 0 && closeWaitCount > 0) {
        networkStatus.close_wait = closeWaitCount;
      }
    } catch (error) {
      console.log('Could not get additional network stats:', error.message);
    }
    
    data.networkStatus = networkStatus;

    const { stdout: ssConnStdout } = await execPromise('ss -tan');
    const connectionLines = ssConnStdout.trim().split('\n');
    const connectionSummary = {};
    
    connectionLines.slice(1).forEach(line => {
        const parts = line.trim().split(/\s+/);
        const state = parts[0];
        if (state === 'ESTAB' || state === 'TIME-WAIT' || state === 'CLOSE-WAIT') {
            const ip = parts[4];
            if (ip) connectionSummary[ip] = (connectionSummary[ip] || 0) + 1;
        }
    });
    
    // Count가 2 이상인 연결만 필터링
    data.connectionSummary = Object.entries(connectionSummary)
      .filter(([ip, count]) => count >= 2)
      .map(([ip, count]) => ({ ip, count }));
  }

  return data;
}

server.listen(PORT, () => {
  console.log(`Server is listening on port ${PORT}`);
});
