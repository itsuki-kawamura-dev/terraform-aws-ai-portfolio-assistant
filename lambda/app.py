import json
import boto3
import os
import urllib.request

s3 = boto3.client("s3")
ssm = boto3.client("ssm")

BUCKET_NAME = os.environ["PORTFOLIO_BUCKET"]
OBJECT_KEY = "portfolio_context.json"

GEMINI_MODEL = "gemini-2.5-flash-lite"


def get_gemini_api_key():
    response = ssm.get_parameter(
        Name="/portfolio-assistant/gemini-api-key",
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def lambda_handler(event, context):
    # 1. Get recruiter question
    body = json.loads(event.get("body", "{}"))
    question = body.get("question", "").strip()

    if not question:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "question is required"
            })
        }

    # 2. Load portfolio context from S3
    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=OBJECT_KEY
    )

    portfolio_context = response["Body"].read().decode("utf-8")

    # 3. Build prompt
    prompt = f"""
You are a portfolio assistant for Itsuki Kawamura.

Answer the recruiter's question using ONLY the portfolio context below.

Rules:
- Do not invent experience or skills.
- If the information is not in the portfolio context, say that it is not available.
- Keep the answer concise and recruiter-friendly.
- Mention relevant projects when useful.

PORTFOLIO CONTEXT:
{portfolio_context}

RECRUITER QUESTION:
{question}
"""

    # 4. Get Gemini API key
    api_key = get_gemini_api_key()

    # 5. Call Gemini API
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))

    answer = result["candidates"][0]["content"]["parts"][0]["text"]

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "answer": answer
        })
    }