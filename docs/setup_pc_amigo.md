# Entrenamiento distribuido con el PC de tu amigo (Windows 11)

El PC de tu amigo y el tuyo entrenan **juntos**: Hyperband, los 5 modelos y los ensembles, todo repartido entre los dos. Un solo comando en cada PC y se encarga de todo.

| PC | Quién | RANK | Qué hace |
|---|---|---|---|
| **PC A** | Tu laptop | `0` | Manda las órdenes, valida, guarda todos los resultados en `outputs_ddp\` |
| **PC B** | Tu amigo | `1` | Entrena su mitad de las fotos y obedece |

Tu amigo no escribe código. Solo hay que instalarle cosas (Parte A) y, el día del entrenamiento, pegar un comando (Parte C).

> **Qué está probado y qué no.**
> - Probado en tu laptop con **dos procesos** hablando entre sí (Hyperband, entrenamiento final, ensembles).
> - **No probado:** la conexión entre dos PCs reales. Haz la Parte B antes de empezar el entrenamiento largo.
> - **No verificado:** que PyTorch funcione en la tarjeta de tu amigo (depende del modelo, ver A1).

---

## Antes de salir de tu casa

1. **Empaqueta el proyecto** (19 MB, sin las fotos originales de 6 GB). En PowerShell, dentro de la carpeta del proyecto:

   ```powershell
   $dest = "$env:TEMP\mango_paquete"
   robocopy . $dest /E /XD "$PWD\.venv" "$PWD\Data\raw" "$PWD\outputs" "$PWD\outputs_ddp" "$PWD\results" "$PWD\.git" "$PWD\src\__pycache__" /NFL /NDL /NJH /NJS | Out-Null
   Compress-Archive -Path "$dest\*" -DestinationPath "$HOME\Desktop\mango.zip" -Force
   ```

   (`robocopy` avisa con un código de salida 1 cuando copia bien; es normal.) Queda `mango.zip` en tu escritorio. Llévalo en una USB, o pásalo por correo, Drive o WhatsApp: 19 MB caben en todos.

   El zip ya trae las fotos reducidas y los CSV de la partición: así los dos PCs usan **exactamente los mismos datos**.

2. **Lleva** el cargador de la laptop (el entrenamiento dura horas), el cable Ethernet y la USB.

3. **Tu versión 0.1 está a salvo** en `results\v0.1_un_pc\`: el entrenamiento distribuido escribe en otra carpeta (`outputs_ddp\`) y no la toca.

---

## La red: cómo conectar los dos PCs

Como van a usar **el internet de tu amigo**, la forma más simple es que **los dos PCs estén en el mismo router**. No hace falta cable de PC a PC.

| Opción | Cómo | Velocidad |
|---|---|---|
| **1. Los dos con cable al router (la mejor)** | Un cable del router al PC de tu amigo, otro del router a tu laptop. Si el router tiene un solo puerto libre, usa el tuyo y deja al otro por Wi-Fi | Hasta 1 Gbps |
| **2. Uno con cable y el otro por Wi-Fi** | El PC de tu amigo por cable (si ya está así) y tu laptop por Wi-Fi | Depende del Wi-Fi |
| **3. Los dos por Wi-Fi** | Todo conectado a la misma red | La más lenta |
| **4. Cable de PC a PC (solo si falla lo demás)** | Tu Ethernet con el de él, con IPs fijas (ver al final de esta sección) | 1 Gbps, pero sin internet por ese cable |

**Por qué importa la velocidad:** en cada paso los dos PCs se envían todos los gradientes del modelo, entre 16 MB (EfficientNet) y 111 MB (ConvNeXt). Con cable a 1 Gbps son unos 100 MB/s: del orden de un segundo por paso en los modelos grandes. Por Wi-Fi puede ser varias veces peor.

**Comprueba la velocidad del cable** en cada PC (si tiene cable):

```powershell
Get-NetAdapter | Select-Object Name, Status, LinkSpeed
```

La línea del adaptador Ethernet debe decir `1 Gbps`. Si dice `100 Mbps`, el cable o el puerto no sirven: cambia de cable o de puerto del router.

**Sobre la placa madre de tu amigo:** casi todos los PCs de escritorio tienen puerto Ethernet de fábrica y muchos no traen Wi-Fi. Eso solo importa si quieres la opción 4, porque ahí su PC se queda sin internet por ese cable. Con el router no cambia nada. En el PC de tu amigo, `Get-NetAdapter` te muestra si tiene Wi-Fi: busca una línea con `Wi-Fi` o `802.11`.

### Opción 4: cable de PC a PC (solo si falla lo demás)

1. Conecta el cable entre los dos puertos Ethernet. Los PCs modernos no necesitan un cable especial.
2. En cada PC, abre **PowerShell como administrador** y pon una IP fija. Cambia `Ethernet` por el nombre del adaptador que sale en `Get-NetAdapter`:

   ```powershell
   # En el PC A (tu laptop)
   New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.50.1 -PrefixLength 24
   # En el PC B (tu amigo)
   New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.50.2 -PrefixLength 24
   ```

3. Usa `192.168.50.1` como `MASTER_ADDR`.
4. Al terminar, quita la IP fija: `Remove-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.50.1 -Confirm:$false` (y `.2` en el otro).

---

## Parte A: instalar en el PC de tu amigo (una sola vez)

Todo en **PowerShell** (menú Inicio, escribe "PowerShell", abrir). La instalación son 30–40 minutos, casi todo descargas.

### A0. Que el PC no se duerma

Durante el entrenamiento el PC no puede suspenderse. En PowerShell **como administrador**:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 0
```

Tu amigo debe dejar el PC **enchufado**.

### A1. Revisar la tarjeta de video

```powershell
nvidia-smi
```

- Si sale una tabla con el nombre de una tarjeta NVIDIA, sigue. Anota el nombre y la memoria.
- Si dice que el comando no existe, no hay tarjeta NVIDIA o falta el driver. **Sin tarjeta NVIDIA esto no sirve** (en CPU sería lentísimo): avísame.

Actualiza el driver a la última versión desde la app de NVIDIA o desde nvidia.com. La versión de PyTorch de abajo usa CUDA 13 y necesita un driver reciente.

**Ojo con tarjetas viejas.** Si el nombre empieza por `GTX 10` (serie 1050, 1060, 1070, 1080) es posible que CUDA 13 no las soporte. En ese caso, en el paso A4 usa `cu126` en lugar de `cu130` (el resto igual). No lo he verificado en esa tarjeta: si algo falla en A5, es lo primero que hay que probar.

### A2. Instalar Python 3.13

```powershell
winget install -e --id Python.Python.3.13
```

**Cierra PowerShell y ábrelo otra vez.** Luego:

```powershell
py -3.13 --version
```

Debe decir `Python 3.13.x`. Si `winget` no existe, descarga Python 3.13 de python.org, instálalo y **marca la casilla "Add python.exe to PATH"** en la primera pantalla.

### A3. Poner el proyecto

Pasa `mango.zip` al PC (por la USB, por ejemplo a `Descargas`) y:

```powershell
Expand-Archive "$HOME\Downloads\mango.zip" "$HOME\Documents\mango" -Force
cd "$HOME\Documents\mango"
dir
```

Debe haber `Data`, `docs`, `src`, `README.md` y `requirements.txt`.

### A4. Crear el entorno e instalar las librerías

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
```

Si `Activate.ps1` da error de "ejecución de scripts deshabilitada", corre esto y repite la activación:

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

Debe imprimir `2.14.1+cu130 True` y el nombre de la tarjeta. Si sale `False`, el driver está viejo (A1) o es una tarjeta que pide `cu126`.

### A6. Firewall y tipo de red

- La red debe ser **Privada**: Configuración → Red e Internet → (Wi-Fi o Ethernet) → Propiedades → Tipo de perfil de red → **Red privada**.
- Apaga cualquier VPN en los dos PCs.
- La primera vez que Python hable por la red, Windows mostrará una ventana del Firewall. **Marca "Redes privadas" y Permitir.** Pasa en los dos PCs.
- Si la ventana no aparece o la conexión falla, crea la regla a mano. PowerShell **como administrador**, en la carpeta del proyecto:

  ```powershell
  $py = & .venv\Scripts\python.exe -c "import sys; print(sys._base_executable)"
  New-NetFirewallRule -DisplayName "Mango DDP" -Direction Inbound -Program $py -Action Allow -Profile Private
  ```

  Se borra al final con `Remove-NetFirewallRule -DisplayName "Mango DDP"`.

### A7. Anotar las IPs

En los dos PCs:

```powershell
ipconfig
```

Busca "Dirección IPv4" del adaptador que están usando (Wi-Fi o Ethernet). Se ve como `192.168.1.23`.

- **IP del PC A (tu laptop):** `__________` ← esta es la que se usa como `MASTER_ADDR`
- **IP del PC B (tu amigo):** `__________`

**Solo en tu laptop:** el adaptador virtual de VirtualBox (`192.168.56.1`) puede confundir a PyTorch sobre por dónde hablar. Antes de entrenar, desactívalo (PowerShell **como administrador**) y vuélvelo a activar al terminar:

```powershell
Disable-NetAdapter -Name "Ethernet 2" -Confirm:$false
# ...al terminar:
Enable-NetAdapter -Name "Ethernet 2" -Confirm:$false
```

(`Ethernet 2` es el nombre en tu laptop; comprueba que `Get-NetAdapter` diga que ese es el de VirtualBox.)

---

## Parte B: prueba de conexión (2 minutos)

Antes del entrenamiento largo. No entrena nada: cada PC aporta un número y se suman.

En los dos PCs: abre PowerShell, `cd` a la carpeta del proyecto y activa el entorno (`.venv\Scripts\Activate.ps1`).

**Primero en el PC A** (pon la IP del PC A):

```powershell
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="0"
python src\ddp_check.py
```

Se queda esperando. **Luego, en el PC B** (la misma IP del PC A; solo cambia `RANK`):

```powershell
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="1"
python src\ddp_check.py
```

Resultado correcto, una línea en cada PC:

```
[NOMBRE-PC] rank 0 de 2 | suma = 3.0 (debe dar 3.0) | NVIDIA GeForce RTX ...
```

Un aviso `The client socket has failed to connect to [NOMBRE]:29500 (system error: 10049...)` se puede ignorar: sale también cuando todo funciona.

| Síntoma | Qué revisar |
|---|---|
| El PC B se queda esperando y da *timeout* | Firewall de alguno de los dos PCs (A6). Revisa que sea red Privada |
| La IP no responde | Revisa la IP del PC A con `ipconfig`, que estén en el mismo router y sin VPN |
| Sigue sin conectar | En tu laptop, prueba apagando el adaptador de VirtualBox (A7). Como último recurso, la opción 4 de cable directo |
| Error que menciona `gloo` o el nombre del PC | Cópiame el error completo |

---

## Parte C: el día del entrenamiento

### 1. Una prueba rápida (2–3 minutos)

Antes de lanzar las horas de entrenamiento, comprueba que todo el flujo funciona. En **los dos PCs**, con el entorno activo y en la carpeta del proyecto:

```powershell
# PC A (tu laptop):
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="0"
python src\train_ddp.py --models efficientnet_b0 --trials 2 --max-epochs 3 --epochs 2
```

```powershell
# PC B (tu amigo), unos segundos después:
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="1"
python src\train_ddp.py
```

En el PC A deben salir épocas con su loss y accuracy, y al final `tiempo con 2 PC: ... s`. El PC B no imprime épocas: solo la primera línea y luego se queda trabajando.

Antes del entrenamiento real, **borra** la carpeta de la prueba para que no se mezcle: en el PC A, `Remove-Item -Recurse -Force outputs_ddp`.

### 2. El entrenamiento completo

**Primero en el PC A** (el tuyo). Pon tu IP:

```powershell
cd $HOME\Documents\proeycts\mango
.venv\Scripts\Activate.ps1
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="0"
python src\train_ddp.py
```

**Después, en el PC B** (tu amigo), en menos de un par de minutos. La misma IP del PC A, y `RANK` en 1:

```powershell
cd $HOME\Documents\mango
.venv\Scripts\Activate.ps1
$env:MASTER_ADDR="192.168.1.23"; $env:MASTER_PORT="29500"; $env:WORLD_SIZE="2"; $env:RANK="1"
python src\train_ddp.py
```

(Tu ruta puede ser `$HOME\Documents\proeycts\mango`; la de tu amigo, `$HOME\Documents\mango`, según dónde lo hayan puesto.)

**Qué hace, en orden, sin que nadie toque nada:**

1. Hyperband para cada uno de los 5 modelos (10 pruebas por modelo).
2. Entrenamiento final de los 5 con los mejores hiperparámetros.
3. Los ensembles, medidos en test.

**Cuánto tarda:** mi estimación es de **3 a 4 horas con cable a 1 Gbps**, y más con Wi-Fi. Sale de calcular cuántos megabytes viajan por paso; no está medido en dos PCs. En tu laptop sola, Hyperband y el entrenamiento tardaron 42 minutos. Que tarde más con dos PCs es lo esperado: los gradientes viajan por la red en cada paso.

**Opciones para acortar** (solo en el PC A):

| Opción | Efecto |
|---|---|
| `--trials 5` | La mitad de pruebas de Hyperband. Aproximadamente la mitad del tiempo en esa fase |
| `--skip-tune` | Sin Hyperband: usa los valores de `outputs_ddp\tuning\best_params.json` o los por defecto |
| `--models resnet50 convnext_tiny` | Solo esos modelos (y no se calculan los ensembles) |

**Si se interrumpe** (se cae el Wi-Fi, se apaga un PC): cierra el programa en los dos PCs con Ctrl+C y vuelve a lanzar **los mismos dos comandos**. Hyperband continúa donde quedó. El entrenamiento final de cada modelo sí vuelve a empezar.

### 3. Dónde quedan los resultados

Todo en tu laptop (PC A), en `outputs_ddp\`:

| Archivo | Qué es |
|---|---|
| `ddp_summary_2pc.json` | Tiempos de Hyperband y de entrenamiento por modelo |
| `models\*.pt` y `*.json` | Los 5 modelos y su historial de épocas |
| `tuning\trials.csv`, `best_params.json` | Resultados de Hyperband |
| `ensemble_results.csv` | Resultados de los ensembles |

Para la comparación del Topic 6, la referencia de 1 PC está en `results\v0.1_un_pc\` (Hyperband 2140 s + entrenamiento 362 s, que son 2502 s en total). Para una comparación con el mismo código, puedes correr el script en tu laptop sola, sin variables de entorno y en otra carpeta:

```powershell
$env:MANGO_OUTPUTS="outputs_ddp_1pc"; python src\train_ddp.py
```

### 4. Al terminar

- En tu laptop: `Enable-NetAdapter -Name "Ethernet 2" -Confirm:$false` (como administrador) y, si creaste la regla de firewall, `Remove-NetFirewallRule -DisplayName "Mango DDP"` en los dos PCs.
- En el PC de tu amigo, si cambiaste la suspensión: `powercfg /change standby-timeout-ac 30`.

---

## Cosas que cambian respecto a la versión 0.1 (para el informe)

- **El lote efectivo se duplica.** Con 2 PCs, cada uno procesa su lote en cada paso y se promedian los gradientes: con `batch_size=16` el ajuste se hace con 32 fotos. Por eso los resultados no serán idénticos a los de la versión 0.1, y es lo normal en entrenamiento distribuido.
- **Precisión mixta distinta.** La versión 0.1 usó float16 con GradScaler. El distribuido usa bfloat16 si la tarjeta lo soporta (serie RTX 30 en adelante) y float32 si no, y se imprime al arrancar cada PC.
- **El PC B no descarga los pesos preentrenados:** los recibe del PC A por la red en cada entrenamiento. Por eso no necesita internet al entrenar (solo para instalar).
- **El promedio de gradientes está hecho a mano** (`average_gradients` en `train_ddp.py`), porque la clase `DistributedDataParallel` de PyTorch se cae en Windows con la GPU. El algoritmo es el mismo.
- **Qué no se reparte:** la validación cruzada, la GAN y el entrenamiento con fotos sintéticas siguen en un solo PC.

## Plan B

Si la conexión entre los dos PCs no funciona a tiempo, el entrenamiento distribuido se puede hacer en **Kaggle Notebooks**, que da gratis 2 GPUs en una misma máquina. El código de entrenamiento es casi el mismo, y hay que adaptar cómo se lanza.
