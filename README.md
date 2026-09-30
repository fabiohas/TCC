# Projeto - Extração e Classificação de Reclamações Localiza Meoo

O pipeline do projeto consiste na extração de reclamações apresentadas no site Reclame Aqui sobre o serviço de carros por assinatura da Localiza Meoo para um banco MySQL, seguido pelo processamento de linguagem natural via LLM para classificação e extração de KPIs dos textos. Os resultados alimentam um dashboard analítico voltado à detecção de falhas operacionais e otimização do atendimento.

## Estrutura dos arquivos

- `src/config.py`  
  Carrega as variáveis de ambiente do projeto e centraliza as configurações de banco e chaves de API.

- `src/db.py`  
  Responsável pela conexão com MySQL, criação das tabelas e persistência dos dados brutos e classificados.

- `src/scraper/scraper.py`  
  Faz o scraping do Reclame Aqui usando Selenium. Coleta links das reclamações, entra em cada página e extrai o texto do cliente para salvar em JSON/CSV.

- `src/classificador/classificador.py`  
  Lê as reclamações ainda não classificadas, envia o texto para o modelo Gemini e salva a estrutura padronizada da reclamação no banco.

- `src/dashboard/dashboard.py`  
  Cria o dashboard em Streamlit com KPIs, filtros e gráficos sobre os principais motivos, etapas, canais falhos e distribuição geográfica.

- `dags/tcc_pipeline.py`  
  DAG do Airflow que orquestra o fluxo: scraping → classificação.

- `webserver_config.py`  
  Arquivo de configuração do Airflow Webserver.

- `src/__init__.py`  
  Marca o pacote Python e permite importação dos módulos do projeto.

## Pré-requisitos

- Docker
- Docker Compose
- Chave da API do Google Gemini configurada em um arquivo `.env` na raiz do projeto

Exemplo de `.env`:

```env
GOOGLE_API_KEY=sua_chave_aqui
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_DATABASE=tcc_localiza
MYSQL_USER=tcc_user
MYSQL_PASSWORD=tcc_password
SCRAPER_MAX_PAGINAS=5
```

## Como executar a demo

A forma mais simples é rodar o script pronto:

```bash
bash scripts/run_banca_demo.sh
```

Esse script realiza os passos abaixo:

1. sobe o ambiente Docker (MySQL + Airflow)
2. limpa os dados da demo
3. executa o scraper
4. executa o classificador com IA
5. valida os resultados no banco
6. abre o dashboard em uma porta local do Streamlit

Ao final, o terminal mostra a URL do dashboard, algo parecido com:

```bash
http://localhost:8501
```

## Execução manual (opcional)

Se quiser rodar os passos separadamente:

```bash
docker compose up --build -d

docker compose exec -T airflow-webserver env SCRAPER_MAX_PAGINAS=5 python -c "from src.scraper.scraper import main; main()"
docker compose exec -T airflow-webserver python -c "from src.classificador.classificador import main; main()"
```

Depois, para abrir o dashboard localmente:

```bash
MYSQL_HOST=localhost MYSQL_PORT=3306 streamlit run src/dashboard/dashboard.py
```

## Observações

- Os dados brutos ficam em `data/`.
- O banco principal é MySQL e as tabelas principais são `raw_reclamacoes` e `reclamacoes_classificadas`.
- O pipeline está pronto para ser executado por Airflow via `dags/tcc_pipeline.py`.
