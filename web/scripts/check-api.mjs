const targets = [
  ["Flask health", "http://127.0.0.1:8000/health"],
  ["Flask models", "http://127.0.0.1:8000/models"],
  ["Vite health", "http://localhost:5173/health"],
  ["Vite models", "http://localhost:5173/models"],
];

let failed = false;
const payloads = new Map();
for (const [name, url] of targets) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(5_000) });
    const body = await response.text();
    console.log(`${name}: HTTP ${response.status} ${body}`);
    if (!response.ok) failed = true;
    payloads.set(name, body);
  } catch (error) {
    failed = true;
    console.error(`${name}: ${error.message}`);
  }
}

for (const endpoint of ["health", "models"]) {
  if (
    payloads.get(`Flask ${endpoint}`) !== payloads.get(`Vite ${endpoint}`)
  ) {
    console.error(
      `Las respuestas directas y mediante proxy difieren para /${endpoint}.`,
    );
    failed = true;
  }
}
process.exitCode = failed ? 1 : 0;
