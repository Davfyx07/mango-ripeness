# Preparar el segundo PC (Windows 11) para el entrenamiento distribuido

Esta guía deja el PC de tu amigo listo para entrenar junto con el tuyo. Parte de cero: sin Python ni Git.

- **Parte A**: instalar todo (una sola vez, 30–40 minutos, casi todo es descarga).
- **Parte B**: conectar los dos PCs y hacer una prueba de conexión.
- **Parte C**: qué hacer el día del entrenamiento.

Todos los comandos van en **PowerShell**. Los dos PCs deben quedar con las **mismas versiones** de Python y de las librerías; por eso los comandos traen el número de versión.

> **Estado de las pruebas.** La instalación y la prueba de conexión se probaron en un solo PC con Windows 11 (dos procesos hablando entre sí). La conexión entre dos PCs distintos **no se ha probado todavía**: hagan la Parte B antes del día de la entrega. Si falla, hay un plan B al final.

---

## Parte A — Instalación

### A1. Revisar la tarjeta de video

```powershell
nvidia-smi
```

- Si muestra una tabla con el nombre de la tarjeta, sirve. Anota el nombre y la memoria.
- Si dice que el comando no existe, el PC no tiene tarjeta NVIDIA o le falta el driver. **Sin tarjeta NVIDIA esta guía no funciona**: avísame y cambiamos de plan.

Después **actualiza el driver** a la última versión desde la app de NVIDIA o desde nvidia.com. La versión de PyTorch que vamos a instalar usa CUDA 13 y necesita un driver reciente.

### A2. Instalar Python 3.13 y Git

```powershell
winget install -e --id Python.Python.3.13
winget install -e --id Git.Git
```

**Cierra PowerShell y ábrelo de nuevo.** Luego comprueba:

```powershell
py -3.13 --version
git --version
```

Debe salir `Python 3.13.x` (el otro PC tiene 3.13.14; que coincida el `3.13` es suficiente) y una versión de Git.

### A3. Traer el proyecto

Con el repo ya subido a GitHub:

```powershell
cd $HOME\Documents
git clone <URL-del-repo> mango
cd mango
```

Si el repo es privado, GitHub pedirá iniciar sesión, y la cuenta de tu amigo debe estar invitada como colaborador.

El clon ya trae las fotos reducidas (`data/processed`, unos 19 MB) y los CSV de la partición (`data/splits`). **No hace falta copiar los 6 GB de fotos originales.**

### A4. Crear el entorno e instalar las librerías

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

Si `Activate.ps1` da un error de "ejecución de scripts deshabilitada", corre esto una vez y repite la activación:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Con el entorno activo (se ve `(.venv)` al inicio de la línea):

```powershell
pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
```

La primera línea descarga unos 2.5 GB.

### A5. Comprobar que PyTorch ve la tarjeta

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Debe imprimir `2.14.1+cu130 True` y el nombre de la tarjeta. Si sale `False`, el driver está viejo: vuelve al paso A1.

---

## Parte B — Conectar los dos PCs

### B1. Misma red

- Los dos PCs en el **mismo router**. Lo ideal es **cable Ethernet**; por Wi-Fi funciona, pero el entrenamiento va más lento.
- En los dos, la red debe estar como **Privada**: Configuración → Red e Internet → (Wi-Fi o Ethernet) → Tipo de perfil de red → **Red privada**.
- **Apaga VPNs** (y Tailscale, Hamachi o similares) en los dos PCs mientras entrenan.

### B2. Anotar las direcciones IP

En cada PC:

```powershell
ipconfig
```

Busca "Dirección IPv4" del adaptador Wi-Fi o Ethernet. Se ve como `192.168.1.23`.

- **PC A** (el principal, por ejemplo el tuyo): IP = `__________`
- **PC B** (el de tu amigo): IP = `__________`

### B3. El script de prueba

Crea el archivo `src/ddp_check.py` con esto (una sola vez, en un PC; el otro lo recibe con `git pull`):

```python
"""Prueba de conexion entre los 2 PCs. No entrena nada: cada PC aporta un numero y se suman."""
import socket

import torch
import torch.distributed as dist

dist.init_process_group("gloo")  # lee MASTER_ADDR, MASTER_PORT, RANK y WORLD_SIZE del entorno
rank = dist.get_rank()
value = torch.tensor([float(rank + 1)])   # PC 0 aporta 1, PC 1 aporta 2
dist.all_reduce(value)                    # suma lo de todos y deja el total en cada PC
gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "SIN GPU"
print(f"[{socket.gethostname()}] rank {rank} de {dist.get_world_size()} | suma = {value.item()} (debe dar 3.0) | {gpu}")
dist.destroy_process_group()
```

Qué significa cada variable que usa:

| Variable | Qué es |
|---|---|
| `MASTER_ADDR` | La IP del PC A. Los dos PCs se encuentran ahí. Va **igual en los dos**. |
| `MASTER_PORT` | El puerto de encuentro. Usamos `29500` en los dos. |
| `WORLD_SIZE` | Cuántos PCs participan: `2`. |
| `RANK` | El número de cada PC: `0` para el PC A, `1` para el PC B. |

### B4. Correr la prueba

En los dos PCs, dentro de la carpeta del proyecto y con el entorno activo.

**Primero en el PC A** (cambia la IP por la del PC A):

```powershell
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="0"
python src\ddp_check.py
```

Se queda esperando. **Luego, antes de un par de minutos, en el PC B** (la misma IP del PC A, solo cambia `RANK`):

```powershell
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="1"
python src\ddp_check.py
```

**La primera vez, Windows muestra una ventana del Firewall preguntando por Python. Marca "Redes privadas" y dale Permitir**, en los dos PCs.

Resultado correcto, una línea en cada PC:

```
[NOMBRE-PC] rank 0 de 2 | suma = 3.0 (debe dar 3.0) | NVIDIA GeForce RTX ...
```

Si antes de esa línea aparece un aviso `The client socket has failed to connect to [NOMBRE]:29500 (system error: 10049...)`, se puede ignorar: sale también cuando todo funciona.

### B5. Si no conecta

| Síntoma | Qué revisar |
|---|---|
| El PC B se queda esperando y al final da *timeout* | El firewall del PC A bloquea a Python. Crea la regla de abajo en los dos PCs. |
| No apareció la ventana del Firewall | Igual: crea la regla de abajo. |
| Sigue sin conectar | Revisa que la IP sea la del PC A, que los dos estén en el mismo router, que la red sea Privada y que no haya VPN. |
| Error que menciona `gloo` o `hostname` | Desactiva adaptadores de red virtuales (VirtualBox, Hyper-V, WSL) y repite. Si sigue, cópiame el error completo. |

Regla de firewall manual. Abre **PowerShell como administrador**, ve a la carpeta del proyecto y corre:

```powershell
$py = & .venv\Scripts\python.exe -c "import sys; print(sys._base_executable)"
New-NetFirewallRule -DisplayName "Mango DDP" -Direction Inbound -Program $py -Action Allow -Profile Private
```

Permite que Python reciba conexiones solo en redes privadas. Cuando terminen el proyecto, se borra así:

```powershell
Remove-NetFirewallRule -DisplayName "Mango DDP"
```

---

## Parte C — El día del entrenamiento

En los dos PCs:

```powershell
cd $HOME\Documents\mango
git pull
.venv\Scripts\Activate.ps1
```

Luego se usan las mismas cuatro variables de la prueba (B4), pero corriendo el script de entrenamiento distribuido (`src\train_ddp.py`, que se escribe en el Topic 6). Primero el PC A, después el PC B.

Dos cosas a tener en cuenta:

- **El entrenamiento va al ritmo del PC más lento.** En cada paso los dos PCs se esperan.
- **Puede ir más lento que un solo PC**, porque en cada paso se envían los gradientes por la red. No es un error: se reporta en una tabla (1 PC contra 2 PCs) y se explica que la red es el cuello de botella.

## Plan B

Si la conexión entre los dos PCs no funciona a tiempo, el entrenamiento distribuido se puede hacer en **Kaggle Notebooks**, que da gratis 2 GPUs en una misma máquina. El código de entrenamiento es casi el mismo.
