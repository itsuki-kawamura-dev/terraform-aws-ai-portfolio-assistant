output "api_endpoint" {
  value = aws_apigatewayv2_api.portfolio_api.api_endpoint
}

output "portfolio_url" {
  value = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}