
const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const { exec } = require('child_process');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;

// 정적 파일 제공
app.use(express.static(path.join(__dirname, 'public')));

wss.on('connection', (ws) => {
  console.log('Client connected');

  const monitorInterval = setInterval(() => {
    const data = {};

    // 1. Get JVM PID
    const pidCommand = 'wmic process where "commandline like '%ss.jar%' and name='java.exe'" get processid';
    exec(pidCommand, (err, stdout) => {
      if (err) {
        console.error('PID Error:', err);
        return;
      }
      const pidMatch = stdout.match(/\d+/);
      if (!pidMatch) {
        ws.send(JSON.stringify({ error: "Target Java process (ss.jar) not found."}));
        return;
      }
      const pid = pidMatch[0];
      data.pid = pid;
      data.timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

      // Chain commands: 2. Get Thread Count
      const threadCountCommand = `wmic process where processid=${pid} get ThreadCount`;
      exec(threadCountCommand, (err, stdout) => {
        if (!err) {
            const threadMatch = stdout.match(/\d+/g);
            if (threadMatch && threadMatch.length > 1) data.threadCount = threadMatch[1];
        }

        // Chain commands: 3. Get Heap Usage
        const heapCommand = `jstat -gc ${pid}`;
        exec(heapCommand, (err, stdout) => {
            if (!err) {
                const lines = stdout.trim().split('\n');
                data.heapUsage = lines[lines.length - 1].trim();
            }

            // Chain commands: 4. Get Network Info
            const netstatCommand = 'netstat -an';
            exec(netstatCommand, (err, stdout) => {
                if (!err) {
                    const lines = stdout.trim().split('\n');
                    const networkStatus = { estab: 0, time_wait: 0, close_wait: 0 };
                    const connectionSummary = {};

                    lines.forEach(line => {
                        const upperLine = line.toUpperCase();
                        const parts = line.trim().split(/\s+/);
                        if (upperLine.includes('ESTABLISHED')) {
                            networkStatus.estab++;
                            const ip = parts[2]; // Foreign Address
                            if (ip) connectionSummary[ip] = (connectionSummary[ip] || 0) + 1;
                        }
                        if (upperLine.includes('TIME_WAIT')) networkStatus.time_wait++;
                        if (upperLine.includes('CLOSE_WAIT')) networkStatus.close_wait++;
                    });
                    data.networkStatus = networkStatus;
                    data.connectionSummary = Object.entries(connectionSummary).map(([ip, count]) => ({ ip, count }));
                }
                ws.send(JSON.stringify(data));
            });
        });
      });
    });
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



server.listen(PORT, () => {
  console.log(`Server is listening on port ${PORT}`);
});
