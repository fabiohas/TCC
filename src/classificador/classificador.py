import sys
import time
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_gemini_api_key
from src.db import DatabaseManager


# 1. Molde Estruturado Completo (8 Dimensões Analíticas)
class ClassificacaoReclamacao(BaseModel):
    motivo_principal: str = Field(
        description="A causa raiz da reclamação. Use categorias como: Atraso na Entrega, Cobrança Indevida, Manutenção, Sinistro, ou Cancelamento."
    )
    etapa_jornada: str = Field(
        description="Em qual fase do serviço o problema ocorreu? Responda exatamente com uma destas opções: Adesão, Uso Contínuo, Manutenção, ou Encerramento."
    )
    impacto_mobilidade: str = Field(
        description="O cliente relata estar impossibilitado de se locomover ou sem carro no momento? Responda apenas 'Sim' ou 'Não'."
    )
    resolucao_esperada: str = Field(
        description="O que o cliente está exigindo da empresa? Exemplo: Estorno, Isenção de Multa, Entrega do Veículo, Carro Reserva."
    )
    risco_juridico: str = Field(
        description="O cliente menciona Procon, advogados, justiça ou processo judicial? Responda apenas 'Sim' ou 'Não'."
    )
    canal_falho: str = Field(
        description="Onde o cliente tentou atendimento antes de reclamar? Opções: WhatsApp, Telefone, App, Loja Física, ou Não Informado."
    )
    tipo_cobranca: str = Field(
        description="Qual cobrança é contestada? Opções: Mensalidade, Multa de Trânsito, Franquia/Sinistro, Multa Rescisória, ou Nenhuma."
    )
    modelo_veiculo: str = Field(
        description="Qual o modelo do carro mencionado? (Ex: Argo, Compass, Tracker). Se não mencionado, responda 'Não Informado'."
    )


def main():
    load_dotenv(ROOT_DIR / ".env")
    db = DatabaseManager()
    db.ensure_schema()

    df = db.fetch_raw_unclassified()
    if df.empty:
        print("Nenhuma reclamação nova para classificar.")
        return

    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError("GOOGLE_API_KEY não configurada. Defina a variável no arquivo .env.")

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0.0)
    extrator = llm.with_structured_output(ClassificacaoReclamacao)

    print(f"Iniciando classificação estruturada de {len(df)} reclamações...\n")

    for index, row in df.iterrows():
        texto = str(row.get('texto_reclamacao') or row.get('Texto_Reclamacao') or '')
        raw_id = int(row['id'])
        print(f"Processando [{index+1}/{len(df)}] - ID: {raw_id}")

        try:
            prompt = f"Analise esta reclamação de um cliente de carros por assinatura (Localiza Meoo) e extraia os dados solicitados: {texto}"
            resultado = None
            for tentativa_ia in range(2):
                resultado = extrator.invoke(prompt)
                if resultado is not None:
                    break
                print(f"  -> Resposta vazia da IA na tentativa {tentativa_ia + 1}. Repetindo...")
                time.sleep(1.2)

            if resultado is None:
                raise ValueError("Resposta vazia da IA")

            payload = {
                'external_id': row.get('external_id') or row.get('ID'),
                'motivo_principal': resultado.motivo_principal,
                'etapa_jornada': resultado.etapa_jornada,
                'impacto_mobilidade': resultado.impacto_mobilidade,
                'resolucao_esperada': resultado.resolucao_esperada,
                'risco_juridico': resultado.risco_juridico,
                'canal_falho': resultado.canal_falho,
                'tipo_cobranca': resultado.tipo_cobranca,
                'modelo_veiculo': resultado.modelo_veiculo,
            }
            db.insert_classificacao(raw_reclamacao_id=raw_id, payload=payload)

        except Exception as e:
            print(f"  -> Erro na extração: {e}")
            db.insert_classificacao(
                raw_reclamacao_id=raw_id,
                payload={
                    'external_id': row.get('external_id') or row.get('ID'),
                    'motivo_principal': 'Não Informado',
                    'etapa_jornada': 'Não Informado',
                    'impacto_mobilidade': 'Não Informado',
                    'resolucao_esperada': 'Não Informado',
                    'risco_juridico': 'Não Informado',
                    'canal_falho': 'Não Informado',
                    'tipo_cobranca': 'Não Informado',
                    'modelo_veiculo': 'Não Informado',
                },
            )

        time.sleep(2.5)

    print("\nSucesso! Base classificada e persistida no banco MySQL.")


if __name__ == "__main__":
    main()