resource "aws_apigatewayv2_api" "portfolio_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = [
      "https://${aws_cloudfront_distribution.frontend.domain_name}"
    ]

    allow_methods = [
      "POST"
    ]

    allow_headers = [
      "content-type"
    ]
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id = aws_apigatewayv2_api.portfolio_api.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.portfolio_assistant.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ask" {
  api_id = aws_apigatewayv2_api.portfolio_api.id

  route_key = "POST /ask"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.portfolio_api.id

  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 2
    throttling_burst_limit = 5
  }
}