import express from "express";
import http from "http";
import { exec, spawn } from "child_process";
import fs from "fs";
import https from "https";
import path from "path";
import dotenv from "dotenv";

// Pass local development secrets (such as GEMINI_API_KEY) to the Flask child
// process. Environment variables supplied by the host still take precedence.
dotenv.config();

const app = express();
const PORT = 3000;

let isFlaskReady = false;
let flaskProcess: any = null;

function logToFile(message: string) {
  try {
    fs.appendFileSync("flask_log.txt", `[${new Date().toISOString()}] ${message}\n`);
  } catch (err) {
    console.error("Error writing to log file:", err);
  }
}

// Clear log file at startup
try {
  fs.writeFileSync("flask_log.txt", "=== Server Started ===\n");
} catch (err) {}

let pythonCmd = "python3";

// Detect correct Python command (python3 on Linux/Mac, python on Windows)
function detectPythonCommand(callback: (cmd: string) => void) {
  exec("python3 --version", (err: any) => {
    if (!err) {
      logToFile("Detected python3 command.");
      pythonCmd = "python3";
      callback("python3");
    } else {
      exec("python --version", (err2: any) => {
        if (!err2) {
          logToFile("python3 not found. Using python command instead.");
          pythonCmd = "python";
          callback("python");
        } else {
          logToFile("WARNING: Neither python3 nor python found! Flask will not start.");
          callback("python3"); // best effort
        }
      });
    }
  });
}

function startFlask() {
  logToFile(`Launching Python Flask Server on Port 5000 using '${pythonCmd}'...`);
  flaskProcess = spawn(pythonCmd, ["app.py"], {
    env: { ...process.env, PYTHONUNBUFFERED: "1" }
  });

  flaskProcess.stdout.on("data", (data: any) => {
    const output = data.toString();
    logToFile(`[Flask STDOUT] ${output.trim()}`);
    if (output.includes("Running on") || output.includes("Debugger PIN") || output.includes("5000")) {
      isFlaskReady = true;
      logToFile(">>> Flask Server is fully ready and listening on port 5000 <<<");
    }
  });

  flaskProcess.stderr.on("data", (data: any) => {
    const output = data.toString();
    logToFile(`[Flask STDERR] ${output.trim()}`);
    if (output.includes("Running on") || output.includes("Debugger PIN") || output.includes("5000")) {
      isFlaskReady = true;
    }
  });

  flaskProcess.on("close", (code: any) => {
    logToFile(`Flask process terminated with code ${code}. Restarting in 5 seconds...`);
    isFlaskReady = false;
    setTimeout(startFlask, 5000);
  });
}

function runCommandWithLogging(cmd: string, args: string[], onDone: (code: number | null, err: Error | null) => void) {
  logToFile(`Running: ${cmd} ${args.join(" ")}`);
  const proc = spawn(cmd, args);
  let errorOccurred = false;

  proc.stdout.on("data", (data: any) => {
    logToFile(`[${cmd} STDOUT] ${data.toString().trim()}`);
  });

  proc.stderr.on("data", (data: any) => {
    logToFile(`[${cmd} STDERR] ${data.toString().trim()}`);
  });

  proc.on("error", (err: any) => {
    logToFile(`[${cmd} ERROR EVENT] ${err.message}`);
    errorOccurred = true;
    onDone(null, err);
  });

  proc.on("close", (code: any) => {
    if (!errorOccurred) {
      logToFile(`[${cmd} CLOSED] code: ${code}`);
      onDone(code, null);
    }
  });
}

function installDepsAndStart() {
  detectPythonCommand((cmd) => {
    logToFile(`Checking if Python dependencies are already installed using '${cmd}'...`);
    runCommandWithLogging(cmd, ["-c", "import flask"], (code) => {
      if (code === 0) {
        logToFile(">>> Flask is already present. Bypassing installation! <<<");
        startFlask();
      } else {
        logToFile("Flask is missing. Checking if 'pip' module is available...");
        runCommandWithLogging(cmd, ["-m", "pip", "--version"], (pipCheckCode) => {
          if (pipCheckCode === 0) {
            logToFile("Pip is available! Installing Flask...");
            runCommandWithLogging(cmd, ["-m", "pip", "install", "flask", "werkzeug", "--no-input", "--disable-pip-version-check"], (pipInstallCode) => {
              if (pipInstallCode === 0) {
                logToFile("Flask installed successfully using pip!");
                startFlask();
              } else {
                logToFile("Failed to install Flask using pip. Trying with --user flag...");
                runCommandWithLogging(cmd, ["-m", "pip", "install", "flask", "werkzeug", "--user", "--no-input", "--disable-pip-version-check"], (pipUserCode) => {
                  if (pipUserCode === 0) {
                    logToFile("Flask installed successfully using pip --user!");
                    startFlask();
                  } else {
                    logToFile("Failed to install Flask with pip --user.");
                    tryBootstrapPip(cmd);
                  }
                });
              }
            });
          } else {
            logToFile("Pip module is NOT available. Attempting to bootstrap pip...");
            tryBootstrapPip(cmd);
          }
        });
      }
    });
  });
}

function tryBootstrapPip(cmd: string) {
  logToFile("Attempting to bootstrap pip using 'ensurepip'...");
  runCommandWithLogging(cmd, ["-m", "ensurepip", "--default-pip"], (ensureCode) => {
    if (ensureCode === 0) {
      logToFile("ensurepip succeeded! Retrying Flask installation...");
      runCommandWithLogging(cmd, ["-m", "pip", "install", "flask", "--no-input", "--disable-pip-version-check"], (retryInstallCode) => {
        if (retryInstallCode === 0) {
          startFlask();
        } else {
          downloadAndRunGetPip(cmd);
        }
      });
    } else {
      logToFile("ensurepip failed or is not available. Downloading get-pip.py...");
      downloadAndRunGetPip(cmd);
    }
  });
}

function downloadAndRunGetPip(cmd: string) {
  logToFile("Downloading get-pip.py from bootstrap.pypa.io...");
  const file = fs.createWriteStream("get-pip.py");
  https.get("https://bootstrap.pypa.io/get-pip.py", (response) => {
    if (response.statusCode !== 200) {
      logToFile(`Failed to download get-pip.py: HTTP ${response.statusCode}`);
      startFlask(); // Try starting anyway as last resort
      return;
    }
    response.pipe(file);
    file.on("finish", () => {
      file.close();
      logToFile("get-pip.py downloaded successfully. Executing get-pip.py...");
      runCommandWithLogging(cmd, ["get-pip.py", "--user", "--no-warn-script-location"], (getPipCode) => {
        // Delete get-pip.py
        fs.unlink("get-pip.py", () => {});
        if (getPipCode === 0) {
          logToFile("get-pip.py execution succeeded! Installing Flask...");
          runCommandWithLogging(cmd, ["-m", "pip", "install", "flask", "--user", "--no-input", "--disable-pip-version-check"], (finalInstallCode) => {
            if (finalInstallCode === 0) {
              startFlask();
            } else {
              logToFile("Failed to install Flask after bootstrapping pip.");
              startFlask();
            }
          });
        } else {
          logToFile("Failed to execute get-pip.py. Attempting to run Flask anyway as a last resort...");
          startFlask();
        }
      });
    });
  }).on("error", (err) => {
    fs.unlink("get-pip.py", () => {});
    logToFile(`Error downloading get-pip.py: ${err.message}`);
    startFlask();
  });
}

// Start installation and boot sequence
installDepsAndStart();

// Keep a simple route to show loading state if Flask isn't ready
app.use((req, res, next) => {
  if (!isFlaskReady) {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Booting InternLens AI...</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
        <style>
          body { background-color: #090b0f; color: #f1f2f6; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
          h2 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; color: #f27d26; letter-spacing: 0.1em; }
          .spinner-border { color: #f27d26 !important; }
        </style>
      </head>
      <body>
        <div class="text-center p-4">
          <div class="spinner-border mb-4 text-warning" role="status" style="width: 3.5rem; height: 3.5rem;"></div>
          <h2 class="text-uppercase tracking-widest">BOOTING INTERNLENS AI</h2>
          <p class="text-muted text-xs uppercase tracking-widest mt-2" style="font-size: 0.8rem; letter-spacing: 0.05em;">Provisioning Python environment, compiling Random Forest model & training historical cohorts...</p>
        </div>
      </body>
      </html>
    `);
  } else {
    next();
  }
});

// Serve compiled assets only.  Application routes are rendered by Flask so
// every dashboard is session-authenticated and backed by SQLite rather than
// the old demo React state.
const reactBuild = path.resolve(process.cwd(), "dist");
app.use(express.static(reactBuild, { index: false }));

// Proxy application and API routes to Flask on the same origin.
app.all("*", (req, res) => {
  const options = {
    hostname: "127.0.0.1",
    port: 5000,
    path: req.url,
    method: req.method,
    headers: req.headers,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });

  req.pipe(proxyReq, { end: true });

  proxyReq.on("error", (err) => {
    console.error("Proxy connection error:", err);
    res.writeHead(502, { "Content-Type": "text/html" });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Gateway Error</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
      </head>
      <body class="bg-dark text-white p-5">
        <div class="container text-center py-5">
          <h1 class="text-danger fw-bold">502 BAD GATEWAY</h1>
          <p class="text-muted">The Python Flask application server is still initializing. Please refresh in 10 seconds.</p>
        </div>
      </body>
      </html>
    `);
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`\nInternLens AI is running: http://localhost:${PORT}`);
  console.log(`Network address: http://127.0.0.1:${PORT}\n`);
});
