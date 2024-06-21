terraform {
  backend "s3" {
    bucket = "computehorde-facilitator-12345"
    key    = "prod/main.tfstate"
    region = "us-east-1"
  }
}
