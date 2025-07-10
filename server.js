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

  // 1. Get JVM PID
  const pidCommand = isWindows
    ? 'wmic process where "commandline like \'%ss.jar%\' and name=\'java.exe\'" get processid'
    : 'pgrep -f "java.*ss.jar"';
  const { stdout: pidStdout } = await execPromise(pidCommand);
  const pidMatch = pidStdout.match(/\d+/);
  if (!pidMatch) {
    throw new Error('Target Java process (ss.jar) not found.');
  }
  const pid = pidMatch[0];
  data.pid = pid;

  // 2. Get Thread Count
  const threadCountCommand = isWindows
    ? `wmic process where processid=${pid} get ThreadCount`
    : `cat /proc/${pid}/status | grep Threads | awk '{print $2}'`;
  const { stdout: threadStdout } = await execPromise(threadCountCommand);
  const threadMatch = threadStdout.match(/\d+/g);
  if (threadMatch) {
      data.threadCount = isWindows ? threadMatch[1] : threadMatch[0];
  }

  // 3. Get Heap Usage
  const { stdout: heapStdout } = await execPromise(`jstat -gc ${pid}`);
  const heapLines = heapStdout.trim().split('\n');
  data.heapUsage = heapLines[heapLines.length - 1].trim();

  // 4. Get Network Info
  if (isWindows) {
    const { stdout: netstatStdout } = await execPromise('netstat -an');
    const lines = netstatStdout.trim().split('\n');
    const networkStatus = { 
      estab: 0, 
      time_wait: 0, 
      close_wait: 0,
      closed: 0,
      orphaned: 0
    };
    const connectionSummary = {};
    
    lines.forEach(line => {
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
    const tcpLine = ssStatusStdout.split('\n').find(l => l.trim().startsWith('TCP:'));
    
    // 네트워크 상태 초기화
    const networkStatus = { 
      estab: 0, 
      time_wait: 0, 
      close_wait: 0,
      closed: 0,
      orphaned: 0
    };
    
    if (tcpLine) {
      const estabMatch = tcpLine.match(/estab (\d+)/);
      const timeWaitMatch = tcpLine.match(/timewait (\d+)/);
      const closeWaitMatch = tcpLine.match(/closewait (\d+)/);
      const closedMatch = tcpLine.match(/closed (\d+)/);
      const orphanedMatch = tcpLine.match(/orphaned (\d+)/);
      
      networkStatus.estab = estabMatch ? parseInt(estabMatch[1]) : 0;
      networkStatus.time_wait = timeWaitMatch ? parseInt(timeWaitMatch[1]) : 0;
      networkStatus.close_wait = closeWaitMatch ? parseInt(closeWaitMatch[1]) : 0;
      networkStatus.closed = closedMatch ? parseInt(closedMatch[1]) : 0;
      networkStatus.orphaned = orphanedMatch ? parseInt(orphanedMatch[1]) : 0;
    }
    
    data.networkStatus = networkStatus;

    const { stdout: ssConnStdout } = await execPromise('ss -tan');
    const lines = ssConnStdout.trim().split('\n');
    const connectionSummary = {};
    
    lines.slice(1).forEach(line => {
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
