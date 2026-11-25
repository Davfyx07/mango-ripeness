output "url_api" {
  description = "URL pública (HTTPS) del backend"
  value       = aws_lambda_function_url.api.function_url
}

output "repositorio_ecr" {
  description = "Dirección del repositorio donde se sube la imagen"
  value       = aws_ecr_repository.api.repository_url
}
