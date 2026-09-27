import json
import boto3
import os
import urllib.request
import urllib.error

s3 = boto3.client("s3")
ssm = boto3.client("ssm")

BUCKET_NAME = os.environ["PORTFOLIO_BUCKET"]
OBJECT_KEY = "portfolio_context.json"

GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_API_KEY_PARAMETER = "/portfolio-assistant/gemini-api-key"

MAX_QUESTION_LENGTH = 500


def build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def get_gemini_api_key():
    response = ssm.get_parameter(
        Name=GEMINI_API_KEY_PARAMETER,
        WithDecryption=True
    )
    return response["Parameter"]["Value"]


def lambda_handler(event, context):
    try:
        # 1. Parse request body
        body = json.loads(event.get("body", "{}"))
        question = body.get("question", "").strip()

        # 2. Validate input
        if not question:
            return build_response(
                400,
                {"error": "question is required"}
            )

        if len(question) > MAX_QUESTION_LENGTH:
            return build_response(
                400,
                {"error": "question is too long"}
            )

        # 3. Load portfolio context from private S3
        s3_response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=OBJECT_KEY
        )

        portfolio_context = (
            s3_response["Body"]
            .read()
            .decode("utf-8")
        )

        # 4. Build prompt
        prompt = f"""
You are a portfolio assistant for Itsuki Kawamura.

Answer the recruiter's question using ONLY the portfolio context below.

Rules:
- Do not invent experience or skills.
- If the information is not in the portfolio context, say that it is not available.
- Answer in the same language as the question, concisely and for a recruiter.
- Answer the question directly with concrete evidence from the context. For broad
  questions about strengths, include one or two specific work examples when available.
- Clearly distinguish employment from personal portfolio projects.
- Do not send the reader to the portfolio, GitHub, a CV, or other material as a
  generic closing line. Do not add a call to action or filler after the answer.

PORTFOLIO CONTEXT:
{portfolio_context}

RECRUITER QUESTION:
{question}
"""

        # 5. Get Gemini API key
        api_key = get_gemini_api_key()

        # 6. Call Gemini
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
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
            ],
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.2
            }
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

        try:
            with urllib.request.urlopen(
                request,
                timeout=15
            ) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

        except urllib.error.HTTPError as error:
            print(
                f"Gemini API HTTP error: "
                f"status={error.code}"
            )

            if error.code == 429:
                return build_response(
                    503,
                    {
                        "error":
                        "The AI service is temporarily busy. "
                        "Please try again later."
                    }
                )

            return build_response(
                502,
                {
                    "error":
                    "The AI service is temporarily unavailable."
                }
            )

        except urllib.error.URLError as error:
            print(
                f"Gemini API connection error: "
                f"{type(error).__name__}"
            )

            return build_response(
                502,
                {
                    "error":
                    "Unable to reach the AI service."
                }
            )

        # 7. Extract answer
        answer = (
            result["candidates"][0]
            ["content"]
            ["parts"][0]
            ["text"]
        )

        return build_response(
            200,
            {"answer": answer}
        )

    except json.JSONDecodeError:
        return build_response(
            400,
            {"error": "Invalid JSON request"}
        )

    except Exception as error:
        print(
            f"Unexpected error: "
            f"{type(error).__name__}"
        )

        return build_response(
            500,
            {"error": "Internal server error"}
        )
