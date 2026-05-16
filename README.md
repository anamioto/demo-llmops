## 1. Introdução e Contextualização 🔍

### 1.1 Definição do Problema

Atualmente, tomadores de decisão e equipes de negócio dependem de análises de dados constantes para guiar estratégias operacionais. No entanto, o acesso a essas informações frequentemente exige o domínio de linguagens de consulta estruturadas (como **SQL**), gerando duas grandes dores:

1. **Dependência técnica:** Áreas de negócio enfrentam filas de espera para obter respostas simples.
2. **Sobrecarga dos times de dados:** Profissionais de dados gastam tempo produtivo respondendo a consultas ad-hoc repetitivas.

**Exemplos de perguntas de negócio comuns:**

* *"Qual foi a receita total por categoria de produto?"*
* *"Quais são os 5 produtos mais vendidos?"*
* *"Qual país teve maior quantidade de pedidos?"*
* *"Qual foi o ticket médio?"*

---

### 1.2 Objetivo do Sistema

Para democratizar o acesso à informação e garantir autonomia self-service, este sistema foi desenvolvido como uma interface inteligente de **Text-to-SQL**. O objetivo principal é traduzir a intenção do usuário em insights acionáveis através do seguinte fluxo:

* **Interface em Linguagem Natural:** Receber perguntas complexas de negócio formuladas nativamente em português.
* **Geração Segura de Código:** Traduzir o texto em uma consulta SQL otimizada, performática e segura (protegida contra SQL Injection) mapeada para o **Google BigQuery**.
* **Execução e Consumo:** Executar a consulta diretamente no *data warehouse*.
* **Sintetização de Resultados:** Interpolar os dados estruturados retornados e devolvê-los ao usuário final em uma resposta explicada, fluida e em linguagem simples.

---

# 2. Fonte de Dados e Preparação dos dados 🔧

## 2.1 Dataset de Referência (BigQuery Public Data)

Para acelerar o desenvolvimento, garantir a reprodutibilidade do projeto e eliminar o overhead de construção de pipelines de ingestão manuais nesta fase, o sistema consome diretamente um dataset público oficial hospedado no Google BigQuery:

* **ID do Dataset:** ``` bigquery-public-data.thelook_ecommerce ```

* **Contexto:** Dados sintéticos que simulam uma operação real de e-commerce (clientes, produtos, pedidos e fluxos de entrega).

---

## 2.2 Tabelas Escopadas

O mapeamento do assistente Text-to-SQL está concentrado nas quatro principais tabelas core do ecossistema do dataset:

```orders:``` Registro transacional dos pedidos realizados na plataforma.

```order_items:``` Detalhamento ao nível de item de cada pedido, contendo valores de venda e status de entrega.

```products:``` Catálogo completo de produtos, incluindo informações de categoria, marca e preço de custo.

```users:``` Dados demográficos e cadastrais dos usuários/clientes.

---

## 2.3 Consulta de Validação (Smoke Test)

Para validar a conectividade com o Data Warehouse, o mapeamento das chaves de JOIN e a integridade dos dados, utiliza-se a consulta padrão abaixo.Este script calcula o market share financeiro agregando a receita total por categoria de produto:

1. Para testar, entre em sua conta da Google no link: https://console.cloud.google.com/
2. Ative o faturamento - muita atenção aqui, você possui R$300 de créditos - não esqueça nada ligado quando não estiver usando.
3. Busque Vertex AI e entre no ambiente
4. No menu lateral entre em notebooks -> colab enterprise
5. <img width="544" height="341" alt="image" src="https://github.com/user-attachments/assets/e617003f-0694-4028-bd4e-57d007139290" />
6. Cole o código abaixo e veja a mágica acontecer.

```SQL
SELECT
  p.category AS categoria_produto,
  ROUND(SUM(oi.sale_price), 2) AS receita_total
FROM `bigquery-public-data.thelook_ecommerce.order_items` AS oi
INNER JOIN `bigquery-public-data.thelook_ecommerce.products` AS p
  ON oi.product_id = p.id
GROUP BY 
  p.category
ORDER BY 
  receita_total DESC
LIMIT 10;
```

**OBSERVAÇÃO:**  Este é o ambiente que você testará seus prompts e llms antes de criar o script em produção

---

# 3. Prompt Engineering e Design de Contexto 🔠

Para garantir robustez, segurança e alta acurácia, a interação com o modelo de linguagem (Gemini) foi desenhada de forma desacoplada em um pipeline de duas etapas distintas. Essa separação de responsabilidades isola a lógica de compilação de código estruturado da lógica de síntese e comunicação fluida.

[Pergunta] ──> [Etapa 1: Text-to-SQL] ──> [Query SQL] ──> [BigQuery]
                                                               │
[Resposta Final] <── [Etapa 2: Explicador] <─── [Dados Brutos] ┘

--- 

## 3.1 Etapa 1: Agente Text-to-SQL (Geração de Código)

Esta etapa atua como um compilador determinístico. O modelo assume uma persona estritamente técnica (Engenheiro de Dados AI) cuja única função é traduzir a intenção de negócio em uma sintaxe SQL válida para o BigQuery.

**Payload de Entrada (Contexto do Prompt):**

```Prompt do Usuário:``` A pergunta original formulada em linguagem natural/português.

```Dicionário de Dados (Data Catalog):``` Esquema detalhado das tabelas escopadas (orders, order_items, products, users), incluindo nomes de colunas, tipos de dados e chaves de relacionamento (JOINs).

```Políticas de Segurança (Guardrails):``` Regras explícitas para mitigar vulnerabilidades, como o bloqueio total a comandos de mutação de dados (DELETE, DROP, UPDATE) e instruções anti-SQL Injection.

```Contrato de Saída (Output Formatting):``` Instrução mandatória para que o modelo retorne apenas o bloco de código SQL puro, sem explicações textuais adjacentes ou formatações adicionais.

---

## 3.2 Etapa 2: Agente Analista (Síntese e Explicabilidade)

Após a execução bem-sucedida do SQL no BigQuery, este segundo agente entra em ação assumindo a persona de um Analista de Business Intelligence (BI). O foco aqui é a interpretabilidade e a entrega de valor para o negócio.

**Payload de Entrada (Contexto do Prompt):**

```Contexto de Negócio:``` A pergunta original do usuário para garantir o alinhamento da resposta.

```Transparência Técnica:``` A query SQL que foi efetivamente executada (fornecendo rastreabilidade ao modelo).

```Resultado Estruturado:``` O dataframe ou JSON com as linhas e colunas brutas retornadas diretamente pelo BigQuery.

```Diretriz da Resposta Final:```
O modelo deve consolidar os dados brutos em uma resposta fluida, didática e de fácil leitura, destacando os principais insights gerados, tendências observadas ou anomalias nos dados, eliminando completamente a necessidade de o usuário interpretar tabelas cruas.

---

## 4. Seleção de Modelos e Critérios de Escolha 📊

Para a implementação prática deste assistente, a escolha da família de modelos é guiada pelo binômio **Custo vs. Latência**, garantindo eficiência financeira e respostas rápidas para o usuário final. Utilizaremos o ecossistema do **Vertex AI** na Google Cloud Platform (GCP).

### 4.1 Matriz de Estratégia de Modelos

A arquitetura do projeto permite alternar dinamicamente entre diferentes capacidades de computação cognitiva dependendo da complexidade da pergunta de negócio recebida:

| Família de Modelo | Casos de Uso Recomendados | Vantagens Core | Perfil Financeiro |
| :--- | :--- | :--- | :--- |
| **Gemini Flash**<br>*(ex: Gemini 2.5 Flash / Gemini 3 Flash)* | Perguntas analíticas diretas, consultas baseadas em esquemas simples e síntese ágil de tabelas. | Altíssima velocidade (baixa latência) e excelente eficiência de tokens. | **Extremamente Econômico** (Ideal para alta escala e prototipagem). |
| **Gemini Pro**<br>*(ex: Gemini 2.5 Pro)* | Consultas que envolvem raciocínio lógico pesado, múltiplos `JOINs` complexos ou ambiguidade severa no prompt. | Janela de contexto massiva e capacidade superior de codificação complexa. | **Custo Moderado** (Reservado para fluxos críticos ou analíticos avançados). |

**Confira a documentação para mais detalhes:** 
1. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/2-5-flash?hl=pt
2. https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/2-5-pro?hl=pt

---

### 4.2 Diretriz Prática para a Demo

> 💡 **Recomendação de Arquitetura:** Para o escopo desta demonstração, o modelo padrão configurado em todo o pipeline (tanto no Agente Text-to-SQL quanto no Agente Analista) será o **Gemini Flash**.

**Por que iniciar pelo Gemini Flash?**

* **Mitigação de Custos:** Como um ambiente de aprendizado envolve múltiplas iterações, testes de código manuais e execuções repetidas por diversos alunos, o modelo *Flash* evita surpresas na fatura da nuvem (*billing*).
* **Velocidade no Loop de Desenvolvimento:** A baixa latência do modelo acelera o ciclo de *feedback* durante o desenvolvimento das funções de backend e da interface do usuário.
* **Acurácia Suficiente:** O poder cognitivo da família *Flash* é perfeitamente qualificado para interpretar o dicionário de dados fornecido (`thelook_ecommerce`) e gerar consultas SQL robustas sem a necessidade de um modelo de maior porte.

> À medida que as regras de negócio escalarem ou novos datasets mais complexos forem acoplados, a substituição pelo modelo *Pro* pode ser feita modificando apenas uma variável de ambiente na inicialização do SDK do Vertex AI.

---

## 5. Avaliação, Segurança e Testes de Qualidade 🔐

Antes de disponibilizar o assistente *Text-to-SQL* em ambiente produtivo, é indispensável estabelecer uma esteira de validação para garantir a deterministicidade do código gerado, a segurança dos dados e a confiabilidade das respostas entregues à área de negócio.

### 5.1 Dataset de Referência (*Golden Dataset*)

Para avaliar regressões no modelo durante o ajuste de prompts ou troca de versões do Gemini, utilizamos um conjunto baseline de perguntas de teste (*Golden Dataset*). Este arquivo serve como balizador para testes manuais e automatizados:

```python
# baseline_eval_questions.py

EVAL_QUESTIONS = [
    "Qual foi a receita total por categoria?",
    "Quais são os 5 produtos mais vendidos?",
    "Qual país teve mais pedidos?",
    "Qual é o ticket médio dos pedidos?"
]

```

---

### 5.2 Pilares de Avaliação (*Quality Gates*)

Cada execução do pipeline deve ser submetida a cinco critérios estritos de aceitação:

1. **Sintaxe e Validade do SQL:** A query gerada pelo Agente Text-to-SQL possui sintaxe ANSI válida e executa no BigQuery sem retornar erros de compilação?
2. **Escopo e Governança de Dados:** O modelo limitou-se estritamente às quatro tabelas permitidas (`orders`, `order_items`, `products`, `users`)? Houve alguma tentativa de violação de acesso ou execução de comandos DDL/DML (`DROP`, `DELETE`)?
3. **Fidelidade ao Contexto (*Groundedness*):** A resposta em linguagem natural gerada pelo Agente Analista foi estritamente baseada nos dados retornados pelo BigQuery?
4. **Mitigação de Alucinações:** O modelo evitou inferir, arredondar de forma errônea ou "inventar" métricas e números que não estavam presentes no resultado bruto da query?
5. **Performance e Latência (SLA):** O tempo total de ida e volta (*Round-Trip Time*), somando a geração do SQL, execução no BigQuery e síntese da resposta, mantém-se dentro de um limite aceitável para a experiência do usuário (ex: < 3 segundos)?

---

### 5.3 Avaliação em Escala

À medida que o projeto escala além do ambiente de demonstração, as validações manuais tornam-se inviáveis. Para automação desse processo, a infraestrutura integra-se ao **Cloud Run e Vertex AI**, serviço gerenciado da Google Cloud focado na avaliação de aplicações generativas.

> 🛠️ **Funcionalidades Utilizadas do Vertex AI e Cloud Run:**
> * **Métricas Baseadas em Computação:** Avaliação de latência, consumo de tokens e exatidão exata do SQL.
> * **Métricas Baseadas em LLM (*LLM-as-a-Judge*):** Uso de modelos avaliadores autorizados para pontuar automaticamente critérios subjetivos como *Fluência*, *Coerência* e, fundamentalmente, *Groundedness* (se a resposta está ancorada nos fatos extraídos do banco de dados).
> * **Análise de Regressão:** Comparação histórica de desempenho entre diferentes iterações de engenharia de prompt.

---

## 6. Implantação e Disponibilização no Google Cloud Run ✅

Esta seção descreve o processo de empacotamento, deploy e disponibilização (*serving*) da aplicação utilizando o **Google Cloud Run**. Adotaremos a estratégia de *Source-to-Service*, onde o Google Cloud Build gerencia a criação do container automaticamente a partir do código-fonte, eliminando a necessidade de gerenciar um `Dockerfile` manualmente nesta etapa.

### 6.1 Estrutura de Diretórios do Projeto

Para que o deploy automatizado identifique os pontos de entrada corretamente, o repositório deve seguir a estrutura minimalista abaixo:

```text
llmops-gemini-data-assistant/
├── main.py              # Aplicação principal
├── requirements.txt     # Dependências do projeto
├── teste_api.py         # Teste com um prompt
└── README.md            # Documentação técnica

```

---

### 6.2 Fluxo de Implantação via Google Cloud Shell Resumido

Execute os blocos de comandos abaixo diretamente no terminal do **Google Cloud Shell** para configurar o ambiente e realizar o deploy.

#### Passo 1: Definição e Configuração das Variáveis de Ambiente

Configure o escopo do projeto e as variáveis que serão reaproveitadas nos comandos subsequentes:

```bash
# Substitua pelo ID do seu projeto GCP 
export PROJECT_ID="seu-projeto-gcp"
export REGION="us-central1"
export SERVICE_NAME="llmops-gemini-data-assistant"

# Garante que o Cloud Shell está apontando para o projeto correto
gcloud config set project $PROJECT_ID

```

#### Passo 2: Habilitação das APIs Gerenciadas

Ative os serviços necessários na Google Cloud Platform para suportar a execução da aplicação, computação servless, banco de dados e inteligência artificial:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  logging.googleapis.com

```

#### Passo 3: Execução do Deploy Serverless

Inicie o processo de build e implantação. O parâmetro `--source .` instrui o Cloud Run a empacotar o diretório atual, enviar para o Cloud Build e implantar o container resultante de forma automática:

```bash
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars PROJECT_ID=$PROJECT_ID,LOCATION=$REGION,MODEL_NAME=gemini-2.5-flash

```

> **Nota de Arquitetura:** As variáveis de ambiente injetadas via `--set-env-vars` garantem que o código interno da aplicação (em `main.py`) consiga instanciar o cliente do Vertex AI e o BigQuery apontando dinamicamente para os recursos corretos, utilizando o modelo de menor latência definido no setup (`Gemini Flash`).

---

### 6.3 Testes de Integração e Validação do Endpoint

Ao final do deploy, o terminal exibirá a URL pública gerada para o serviço (Service URL). Mapeie essa URL em seu terminal local ou Cloud Shell para realizar os testes de fumaça (*smoke tests*).

```bash
export SERVICE_URL="https://sua-url-gerada-pelo-cloud-run.run.app"

```

#### Abordagem A: Teste Automatizado via Script Python

Para executar baterias de testes estruturadas a partir do arquivo baseline ou SDKs internos:

```bash
python teste_api.py

```

#### Abordagem B: Validação Direta via Chamada HTTP (cURL)

Envie uma requisição de negócio em formato JSON diretamente para o endpoint `/ask` para validar o fluxo de ponta a ponta (Text $\rightarrow$ SQL $\rightarrow$ BigQuery $\rightarrow$ Resposta Explicada):

```bash
curl -X POST "$SERVICE_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Qual país teve mais pedidos?"
  }'

```

**Exemplo de Resposta Esperada (JSON):**

```json
{
  "question": "Qual país teve mais pedidos?",
  "sql_generated": "SELECT country, COUNT(order_id) AS total_pedidos FROM `bigquery-public-data.thelook_ecommerce.users` GROUP BY country ORDER BY total_pedidos DESC LIMIT 1;",
  "response": "Com base nos dados analisados no BigQuery, o país com a maior quantidade de pedidos registrados foi a China, totalizando X pedidos. Esse volume destaca a região como o principal mercado de volumetria na operação do e-commerce."
}

```

**LEMBRETE:** Após experimentação exclua o projeto ou desligue tudo que esteja sendo usado para não gerar custos!

# Muito obrigada por participar da palestra e não deixe de me acompanhar nas redes sociais! 💜
## https://linktr.ee/anamioto
