resource "aws_ecr_repository" "api" {
  name                 = "mango-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # permite `terraform destroy` aunque tenga imágenes dentro

  image_scanning_configuration {
    scan_on_push = true # AWS revisa cada imagen en busca de vulnerabilidades conocidas
  }
}

# La imagen pesa ~2,5 GB y ECR cobra por almacenamiento: se conservan solo las 3 últimas
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las 3 últimas imágenes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 3
      }
      action = { type = "expire" }
    }]
  })
}

# ---------- 2. Permisos de la función ----------

data "aws_iam_policy_document" "lambda_confia" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "mango-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_confia.json
}

# Único permiso que se le da: escribir sus propios registros en CloudWatch
resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------- 3. Registros ----------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/mango-api"
  retention_in_days = 7 # sin esto los registros se guardan para siempre y se cobran
}

# ---------- 4. La función ----------

resource "aws_lambda_function" "api" {
  function_name = "mango-api"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 3008
  timeout       = 60

  environment {
    variables = {
      MANGO_PRELOAD       = "0"
      MANGO_MAX_UPLOAD_MB = "5"
      MANGO_CORS_ORIGINS  = var.cors_origins
    }
  }

  depends_on = [aws_cloudwatch_log_group.api, aws_iam_role_policy_attachment.logs]
}

# ---------- 5. La URL pública con HTTPS ----------

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # pública: el navegador no firma las peticiones
}

# Para que una URL pública funcione hacen falta estos dos permisos
resource "aws_lambda_permission" "url_invocar_url" {
  statement_id           = "PermitirURLPublica"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "url_invocar_funcion" {
  statement_id             = "PermitirInvocacionPorURL"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.api.function_name
  principal                = "*"
  invoked_via_function_url = true
}
# ---------- 6. Alerta de gasto ----------

resource "aws_budgets_budget" "mensual" {
  name         = "mango-mensual"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
