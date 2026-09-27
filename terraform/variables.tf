variable "aws_region" {
  type    = string
  default = "eu-west-2"
}

variable "project_name" {
  type    = string
  default = "portfolio-assistant"
}

variable "budget_notification_email" {
  type      = string
  sensitive = true
}