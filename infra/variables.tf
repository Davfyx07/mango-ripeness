variable "region" {
  description = "Región de AWS"
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = "Etiqueta de la imagen en ECR que ejecuta la Lambda"
  type        = string
}

variable "cors_origins" {
  description = "Orígenes del front que pueden llamar a la API, separados por coma"
  type        = string
  default     = "http://localhost:5173,http://localhost:3000"
}
variable "budget_usd" {
  description = "Presupuesto mensual en dólares; avisa por correo al llegar al 80 %"
  type        = number
  default     = 5
}

variable "budget_email" {
  description = "Correo donde llega la alerta del presupuesto"
  type        = string
}
