import sys
from datetime import datetime
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.classificador.classificador import main as run_classificador
from src.scraper.scraper import main as run_scraper


with DAG(
    dag_id="tcc_reclamacoes_pipeline",
    description="Pipeline de scraping, classificação e análise de reclamações da Localiza Meoo",
    start_date=datetime(2026, 9, 29),
    schedule_interval="@daily",
    catchup=False,
    tags=["tcc", "localiza", "ia", "mysql"],
) as dag:

    task_scraper = PythonOperator(
        task_id="scrape_reclamacoes",
        python_callable=run_scraper,
    )

    task_classificador = PythonOperator(
        task_id="classificar_reclamacoes",
        python_callable=run_classificador,
    )

    task_scraper >> task_classificador
