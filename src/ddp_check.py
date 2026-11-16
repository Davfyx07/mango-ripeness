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
