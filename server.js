
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

  // 주기적으로 데이터 전송 (예시)
  const interval = setInterval(() => {
    // 여기에 모니터링 데이터 전송 로직 추가
    const command = 'tasklist /fi "IMAGENAME eq java.exe" /fo csv /nh';
    exec(command, (err, stdout, stderr) => {
        if (err) {
            console.error(`exec error: ${err}`);
            return;
        }

        // stdout 파싱하여 의미있는 데이터로 가공
        const lines = stdout.trim().split('\n');
        const processes = lines.map(line => {
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

        ws.send(JSON.stringify({ processInfo: processes }));
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
