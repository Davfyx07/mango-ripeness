import type { ModelInfo, RipenessClass } from "../types/api";
export const labels: Record<RipenessClass, string> = {
  unripe: "Verde",
  partially_ripe: "En maduración",
  ripe: "Maduro",
};
export const percent = (n: number) =>
  new Intl.NumberFormat("es-CO", {
    style: "percent",
    maximumFractionDigits: 2,
  }).format(n);
export const evaluated: ModelInfo[] = [
  { id: "resnet50", nombre: "ResNet50", familia: "CNN", accuracy_test: 0.965 },
  {
    id: "efficientnet_b0",
    nombre: "EfficientNet-B0",
    familia: "CNN",
    accuracy_test: 0.895,
  },
  {
    id: "convnext_tiny",
    nombre: "ConvNeXt-Tiny",
    familia: "CNN",
    accuracy_test: 0.93,
  },
  {
    id: "vit_small",
    nombre: "ViT-Small",
    familia: "Transformer",
    accuracy_test: 0.974,
  },
  {
    id: "swin_tiny",
    nombre: "Swin-Tiny",
    familia: "Transformer",
    accuracy_test: 0.974,
  },
  { id: "ensamble_cnn", nombre: "Ensamble de 3 CNN", familia: "Ensamble", accuracy_test: 0.956 },
  { id: "ensamble_transformers", nombre: "Ensamble de 2 Transformers", familia: "Ensamble", accuracy_test: 0.974 },
  { id: "ensamble_heterogeneo", nombre: "Ensamble heterogéneo", familia: "Ensamble", accuracy_test: 0.965 },
  { id: "ensamble_hibrido", nombre: "Ensamble híbrido", familia: "Ensamble", accuracy_test: 0.974 },
];
