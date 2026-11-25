import {
  portAvailable,
  requirePython,
  startBackend,
  startFrontend,
  terminate,
} from "./runtime.mjs";

await requirePython();
for (const port of [8000, 5173]) {
  if (!(await portAvailable(port))) {
    console.error(
      `El puerto ${port} ya está ocupado. No se cerrará ningún proceso existente.`,
    );
    process.exit(1);
  }
}

const children = [startBackend(), startFrontend()];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  children.forEach(terminate);
  setTimeout(() => process.exit(code), 300);
}
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => stop());
}
children.forEach((child) =>
  child.once("exit", (code) => stop(code === 0 ? 0 : 1)),
);
