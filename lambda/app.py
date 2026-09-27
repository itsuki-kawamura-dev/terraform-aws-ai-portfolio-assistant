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

PROJECTS = {
    "windows-maintenance": {
        "key": "projects/terraform-aws-windows-maintenance-automation.md",
        "keywords": [
            "windows", "maintenance", "patch", "patching",
            "step functions", "snapshot", "powershell",
            "保守", "メンテナンス", "パッチ", "自動化"
        ]
    },

    "azure-private-vm": {
        "key": "projects/terraform-azure-private-vm.md",
        "keywords": [
            "azure", "private endpoint", "managed identity",
            "entra", "rbac", "storage",
            "プライベートエンドポイント", "マネージドid",
            "マネージドアイデンティティ"
        ]
    },

    "ansible-docker-alb": {
        "key": "projects/terraform-aws-ansible-docker-alb.md",
        "keywords": [
            "ansible", "docker", "alb", "nginx",
            "container", "configuration",
            "コンテナ", "ansible", "docker"
        ]
    },

    "github-oidc": {
        "key": "projects/terraform-aws-github-actions-oidc-ci.md",
        "keywords": [
            "oidc", "github actions", "ci/cd", "pipeline",
            "workflow", "github", "デプロイ", "パイプライン"
        ]
    },

    "private-ec2-ssm": {
        "key": "projects/terraform-aws-private-ec2-ssm.md",
        "keywords": [
            "session manager", "private ec2", "vpc endpoint",
            "imdsv2", "nat", "ssm",
            "プライベートec2", "vpcエンドポイント"
        ]
    },

    "cloudwatch-alarm": {
        "key": "projects/terraform-aws-cloudwatch-alarm-sns.md",
        "keywords": [
            "cloudwatch", "alarm", "sns", "monitoring",
            "notification", "監視", "アラーム", "通知"
        ]
    },

    "ai-portfolio": {
        "key": "projects/terraform-aws-ai-portfolio-assistant.md",
        "keywords": [
            "ai", "llm", "gemini", "portfolio",
            "cloudfront", "api gateway", "cors",
            "throttling", "budget",
            "ポートフォリオ", "生成ai", "gemini"
        ]
    }
}

MAX_PROJECTS = 2
MAX_PROJECT_CONTEXT_CHARS = 12000


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

def select_projects(question):
    question_lower = question.lower()

    scored_projects = []

    for project_name, project in PROJECTS.items():
        score = 0

        for keyword in project["keywords"]:
            if keyword.lower() in question_lower:
                score += 1

        if score > 0:
            scored_projects.append(
                (score, project_name, project)
            )

    scored_projects.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return scored_projects[:MAX_PROJECTS]


def load_project_context(question):
    selected_projects = select_projects(question)

    contexts = []

    for _, project_name, project in selected_projects:
        response = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=project["key"]
        )

        content = (
            response["Body"]
            .read()
            .decode("utf-8")
        )

        content = content[:MAX_PROJECT_CONTEXT_CHARS]

        contexts.append(
            f"""
PROJECT: {project_name}

{content}
"""
        )

    return "\n\n".join(contexts)

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
        project_context = load_project_context(question)

        # 4. Build prompt
        prompt = f"""
You are a portfolio assistant for Itsuki Kawamura.

Answer the recruiter's question using ONLY the context provided below.

Rules:
- Do not invent experience, skills, responsibilities, or project details.
- If the information is not available in the context, say that it is not available.
- Keep the answer concise and recruiter-friendly.
- Answer in the same language as the recruiter's question.
- Prefer project README information for project-specific technical details.
- If a relevant project is mentioned, include its GitHub repository as a Markdown link.
- Use ONLY repository URLs explicitly provided in the context.
- Never invent a GitHub URL.

GENERAL PORTFOLIO CONTEXT:
{portfolio_context}

RELEVANT PROJECT README CONTEXT:
{project_context if project_context else "No specific project README selected."}

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