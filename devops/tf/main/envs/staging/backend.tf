terraform {
  backend "s3" {
    bucket = "computehorde-facilitator-12345"
    key    = "staging/main.tfstate"
    region = "us-east-1"
  }
}
