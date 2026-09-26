data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../lambda/app.py"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "portfolio_assistant" {
  function_name = "${var.project_name}-function"

  role    = aws_iam_role.lambda.arn
  handler = "app.lambda_handler"
  runtime = "python3.13"

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  timeout     = 10
  memory_size = 128

  tags = {
    Project = var.project_name
  }

  environment {
    variables = {
      PORTFOLIO_BUCKET = aws_s3_bucket.portfolio_data.bucket
    }
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.portfolio_assistant.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.portfolio_api.execution_arn}/*/*"
}