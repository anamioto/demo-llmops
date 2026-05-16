import os
import json
import re
from flask import Flask, request, jsonify
from google.cloud import bigquery
from google import genai
from google.genai.types import HttpOptions

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us-central1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

ALLOWED_DATASET = "bigquery-public-data.thelook_ecommerce"
MAX_BYTES_BILLED = 100_000_000  # 100 MB

app = Flask(__name__)

bq_client = bigquery.Client(project=PROJECT_ID)

gemini_client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
    http_options=HttpOptions(api_version="v1")
)


SCHEMA_CONTEXT = """
Você pode consultar apenas as tabelas abaixo do BigQuery:

1. `bigquery-public-data.thelook_ecommerce.orders`
   - order_id
   - user_id
   - status
   - created_at
   - returned_at
   - shipped_at
   - delivered_at
   - num_of_item

2. `bigquery-public-data.thelook_ecommerce.order_items`
   - id
   - order_id
   - user_id
   - product_id
   - inventory_item_id
   - status
   - created_at
   - shipped_at
   - delivered_at
   - sale_price

3. `bigquery-public-data.thelook_ecommerce.products`
   - id
   - cost
   - category
   - name
   - brand
   - retail_price
   - department

4. `bigquery-public-data.thelook_ecommerce.users`
   - id
   - first_name
   - last_name
   - email
   - age
   - gender
   - state
   - street_address
   - postal_code
   - city
   - country
   - latitude
   - longitude
   - traffic_source
   - created_at
"""


def extract_sql(text: str) -> str:
    """
    Extrai SQL da resposta do modelo.
    Aceita resposta pura ou dentro de bloco ```sql.
    """
    match = re.search(r"```sql(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"```(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return text.strip()


def validate_sql(sql: str) -> None:
    """
    Validação simples para reduzir risco.
    Em produção, evoluir para parser SQL ou camada semântica.
    """
    sql_lower = sql.lower()

    blocked_keywords = [
        "insert", "update", "delete", "drop", "alter", "create",
        "merge", "truncate", "grant", "revoke"
    ]

    if not sql_lower.startswith("select"):
        raise ValueError("A consulta precisa começar com SELECT.")

    for keyword in blocked_keywords:
        if re.search(rf"\b{keyword}\b", sql_lower):
            raise ValueError(f"Comando não permitido detectado: {keyword}")

    if ALLOWED_DATASET not in sql:
        raise ValueError("A consulta usa dataset não permitido.")

    if "limit" not in sql_lower:
        raise ValueError("A consulta precisa conter LIMIT para controlar custo.")


def generate_sql(question: str) -> str:
    prompt = f"""
Você é um especialista em BigQuery e analytics engineering.

Sua tarefa é converter a pergunta do usuário em uma consulta SQL GoogleSQL válida.

Regras obrigatórias:
- Use apenas as tabelas listadas no contexto.
- Use sempre nomes totalmente qualificados com crase.
- Gere apenas SELECT.
- Sempre inclua LIMIT.
- Não use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER ou MERGE.
- Não invente colunas.
- Responda somente com o SQL, sem explicações.

Contexto das tabelas:
{SCHEMA_CONTEXT}

Pergunta do usuário:
{question}
"""

    response = gemini_client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    sql = extract_sql(response.text)
    validate_sql(sql)

    return sql


def run_bigquery(sql: str):
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        use_query_cache=True
    )

    query_job = bq_client.query(sql, job_config=job_config)
    rows = query_job.result()

    results = [dict(row) for row in rows]
    return results


def summarize_answer(question: str, sql: str, results: list) -> str:
    prompt = f"""
Você é um cientista de dados explicando resultados para uma pessoa de negócio.

Pergunta original:
{question}

SQL executado:
{sql}

Resultado da consulta em JSON:
{json.dumps(results, ensure_ascii=False, default=str)}

Instruções:
- Responda em português.
- Seja claro e objetivo.
- Use apenas os dados fornecidos no JSON.
- Se o resultado estiver vazio, diga que a consulta não retornou dados.
- Não invente valores.
- Traga uma interpretação de negócio curta.
"""

    response = gemini_client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text


@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "ok",
        "service": "llmops-gemini-data-assistant"
    })


@app.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question")

    if not question:
        return jsonify({"error": "Campo obrigatório: question"}), 400

    try:
        sql = generate_sql(question)
        results = run_bigquery(sql)
        answer = summarize_answer(question, sql, results)

        app.logger.info(json.dumps({
            "event": "question_answered",
            "question": question,
            "sql": sql,
            "rows_returned": len(results)
        }, ensure_ascii=False))

        return jsonify({
            "question": question,
            "sql": sql,
            "results": results,
            "answer": answer
        })

    except ValueError as e:
        # Erros de validação (regras de negócio do nosso próprio código, como falta de LIMIT)
        # Esses erros são seguros de mostrar, pois foram gerados pelo nosso 'validate_sql'
        app.logger.warning(json.dumps({
            "event": "validation_failed",
            "question": question,
            "error": str(e)
        }, ensure_ascii=False))

        return jsonify({
            "error": f"Erro de validação: {str(e)}"
        }), 400

    except Exception as e:
        # Erros sistêmicos (Ex: falha de conexão com BigQuery, erro de sintaxe SQL do banco, crash do Gemini)
        # O erro real (detalhado) vai APENAS para o log interno
        app.logger.error(json.dumps({
            "event": "internal_error",
            "question": question,
            "error": str(e)  # O log do GCP/Cloud Run captura o erro completo para debug
        }, ensure_ascii=False))

        # O usuário recebe apenas uma mensagem genérica e polida
        return jsonify({
            "error": "Não foi possível processar sua pergunta devido a um erro interno. Por favor, tente reformular a pergunta ou tente novamente mais tarde."
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))