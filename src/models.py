"""Topic 4: los 5 modelos (3 CNN y 2 Transformers), preentrenados en ImageNet.
Uso (tabla de tamaños):  python src/models.py
"""
import timm

from config import CLASSES

CNNS = ["resnet50", "efficientnet_b0", "convnext_tiny"]
TRANSFORMERS = ["vit_small_patch16_224", "swin_tiny_patch4_window7_224"]
MODELS = CNNS + TRANSFORMERS


def create_model(name, pretrained=True):
    """Descarga el modelo ya entrenado en ImageNet y le cambia la última capa por una de 3 salidas."""
    # shortcut: todos reciben la normalización de ImageNet aunque ViT se preentrenó con otra;
    # el fine-tuning lo absorbe. Usar la de cada modelo si ViT rinde peor de lo esperado.
    return timm.create_model(name, pretrained=pretrained, num_classes=len(CLASSES))


if __name__ == "__main__":
    import torch

    for name in MODELS:
        model = create_model(name, pretrained=False)
        out = model(torch.zeros(2, 3, 224, 224))
        assert out.shape == (2, len(CLASSES)), out.shape
        family = "CNN" if name in CNNS else "Transformer"
        millions = sum(p.numel() for p in model.parameters()) / 1e6
        print(f"{name:<32} {family:<12} {millions:5.1f} M de parámetros")
