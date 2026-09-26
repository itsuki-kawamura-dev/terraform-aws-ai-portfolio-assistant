resource "aws_s3_bucket" "portfolio_data" {
  bucket = "${var.project_name}-data"

  tags = {
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "portfolio_data" {
  bucket = aws_s3_bucket.portfolio_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "portfolio_context" {
  bucket = aws_s3_bucket.portfolio_data.id
  key    = "portfolio_context.json"
  source = "${path.module}/../data/portfolio_context.json"

  etag = filemd5("${path.module}/../data/portfolio_context.json")
}