import { portAvailable, requirePython, startBackend } from "./runtime.mjs";

await requirePython();
if (!(await portAvailable(8000))) {
  console.error(
    "El puerto 8000 ya está ocupado. Comprueba el servicio existente antes de continuar.",
  );
  process.exit(1);
}

const backend = startBackend();
backend.once("exit", (code) => process.exit(code ?? 1));
