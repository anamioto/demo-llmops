import requests

SERVICE_URL = "https://llmops-gemini-data-assistant-mbig6kdzhq-uc.a.run.app"

payload = {
    #"question": "Quais são as 5 categorias com maior receita?"
    #'question': "Qual é o ticket médio dos pedidos?"
    'question' : "Qual o ID e first name do cliente com maior ticket médio?"
}

response = requests.post(
    f"{SERVICE_URL}/ask",
    json=payload,
    timeout=120
)

print("Status code:", response.status_code)
print(response.json())