
const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

const PORT = process.env.PORT || 3000;

// 정적 파일 제공
app.use(express.static(path.join(__dirname, 'public')));

const LOG_FILE_PATH = path.join(__dirname, 'java_monitor.log');

wss.on('connection', (ws) => {
  console.log('Client connected');

  const sendLogData = () => {
    fs.readFile(LOG_FILE_PATH, 'utf8', (err, data) => {
      if (err) {
        console.error(`Error reading log file: ${err}`);
        ws.send(JSON.stringify({ error: 'Log file not found or unreadable.' }));
        return;
      }

      const latestEntry = parseLogData(data);
      ws.send(JSON.stringify(latestEntry));
    });
  };

  // Initial send
  sendLogData();

  // Watch for file changes
  const watcher = fs.watch(LOG_FILE_PATH, (eventType) => {
      if (eventType === 'change') {
          sendLogData();
      }
  });

  ws.on('close', () => {
    console.log('Client disconnected');
    watcher.close();
  });

  ws.on('error', (error) => {
    console.error('WebSocket Error:', error);
    watcher.close();
  });
});

function parseLogData(logContent) {
    const entries = logContent.trim().split('---');
    const lastBlock = entries[entries.length - 2]; // Get the last complete block
    if (!lastBlock) return {};

    const lines = lastBlock.trim().split('\n');
    const data = {
        timestamp: 'N/A',
        pid: 'N/A',
        heapUsage: 'N/A',
        threadCount: 'N/A',
        networkStatus: {},
        connectionSummary: []
    };

    let readingConnectionSummary = false;

    lines.forEach(line => {
        if (line.startsWith('===')) {
            data.timestamp = line.replace('===', '').trim();
        } else if (line.startsWith('JVM PID:')) {
            data.pid = line.split(':')[1].trim();
        } else if (line.startsWith('Heap Usage:')) {
            // The next line is the actual heap data
        } else if (!isNaN(line.trim().split(' ')[0]) && line.includes('.')) {
            data.heapUsage = line.trim();
        } else if (line.startsWith('Thread Count:')) {
            data.threadCount = line.split(':')[1].trim();
        } else if (line.startsWith('Network Status:')) {
            const tcpLine = lines[lines.indexOf(line) + 1];
            if (tcpLine && tcpLine.startsWith('TCP:')) {
                const matches = tcpLine.match(/estab (\d+), closed (\d+), orphaned (\d+), timewait (\d+)/);
                if (matches) {
                    data.networkStatus = {
                        estab: matches[1],
                        closed: matches[2],
                        orphaned: matches[3],
                        timewait: matches[4]
                    };
                }
            }
        } else if (line.startsWith('Connection State Summary:')) {
            readingConnectionSummary = true;
        } else if (readingConnectionSummary && line.trim()) {
            const parts = line.split(/\s+/);
            if (parts.length === 2) {
                data.connectionSummary.push({ ip: parts[0], count: parts[1] });
            }
        }
    });

    return data;
}

server.listen(PORT, () => {
  console.log(`Server is listening on port ${PORT}`);
});
