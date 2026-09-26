import json
import boto3
import os

s3 = boto3.client("s3")

BUCKET_NAME = os.environ["PORTFOLIO_BUCKET"]
OBJECT_KEY = "portfolio_context.json"


def lambda_handler(event, context):
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=OBJECT_KEY
    )

    portfolio_context = json.loads(
        response["Body"].read().decode("utf-8")
    )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(portfolio_context)
    }