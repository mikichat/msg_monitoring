
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

  // 주기적으로 데이터 전송
  const interval = setInterval(() => {
    // 1. Process Monitoring
    const processCommand = 'tasklist /fi "IMAGENAME eq java.exe" /fo csv /nh';
    exec(processCommand, (procErr, procStdout) => {
        if (procErr) {
            console.error(`exec error (tasklist): ${procErr}`);
        }

        const processLines = procStdout.trim().split('\n').filter(line => line);
        const processes = processLines.map(line => {
            const columns = line.replace(/"/g, '').split(',');
            if (columns.length >= 5) {
                return {
                    name: columns[0],
                    pid: columns[1],
                    sessionName: columns[2],
                    sessionNum: columns[3],
                    memUsage: columns[4]
                };
            }
            return null;
        }).filter(p => p);

        // 2. Socket Monitoring
        const socketCommand = 'netstat -an';
        exec(socketCommand, (sockErr, sockStdout) => {
            const dataToSend = {
                processInfo: processes,
                socketInfo: { established: 0, listen: 0, time_wait: 0, close_wait: 0, total: 0 }
            };

            if (sockErr) {
                console.error(`exec error (netstat): ${sockErr}`);
                ws.send(JSON.stringify(dataToSend));
                return;
            }

            const socketLines = sockStdout.trim().split('\n');
            const socketStats = dataToSend.socketInfo;

            socketLines.forEach(line => {
                const upperLine = line.toUpperCase();
                if (upperLine.includes('ESTABLISHED')) socketStats.established++;
                if (upperLine.includes('LISTENING')) socketStats.listen++;
                if (upperLine.includes('TIME_WAIT')) socketStats.time_wait++;
                if (upperLine.includes('CLOSE_WAIT')) socketStats.close_wait++;
            });
            socketStats.total = socketStats.established + socketStats.listen + socketStats.time_wait + socketStats.close_wait;

            ws.send(JSON.stringify(dataToSend));
        });
    });
  }, 1000);

  ws.on('close', () => {
    console.log('Client disconnected');
    clearInterval(interval);
  });

  ws.on('error', (error) => {
    console.error('WebSocket Error:', error);
    clearInterval(interval);
  });
});

server.listen(PORT, () => {
  console.log(`Server is listening on port ${PORT}`);
});
