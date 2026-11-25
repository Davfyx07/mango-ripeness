import { spawn } from "node:child_process";
import { python, repoDir, requirePython } from "./runtime.mjs";

await requirePython();
const imports = [
  "import importlib.metadata as m",
  "packages=['flask','flask-cors','torch','torchvision','pillow','timm']",
  "mods=['flask','flask_cors','torch','torchvision','PIL','timm']",
  "import importlib",
  "[importlib.import_module(name) for name in mods]",
  "print({name:m.version(name) for name in packages})",
  "import torch",
  "print({'cuda_available':torch.cuda.is_available()})",
].join(";");

const check = spawn(python, ["-c", imports], {
  cwd: repoDir,
  stdio: "inherit",
});
check.once("exit", (code) => process.exit(code ?? 1));
