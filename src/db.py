import pandas as pd
import mysql.connector
from mysql.connector import Error

from src.config import get_db_config


class DatabaseManager:
    def __init__(self, config=None):
        self.config = config or get_db_config()

    def get_connection(self):
        return mysql.connector.connect(**self.config)

    def ensure_schema(self):
        query_raw = """
            CREATE TABLE IF NOT EXISTS raw_reclamacoes (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                external_id VARCHAR(50),
                titulo VARCHAR(255),
                link TEXT,
                texto TEXT,
                data DATE,
                cidade VARCHAR(255),
                estado VARCHAR(10),
                texto_reclamacao LONGTEXT,
                resposta_empresa LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_raw_external_id (external_id)
            )
        """

        query_classificada = """
            CREATE TABLE IF NOT EXISTS reclamacoes_classificadas (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                raw_reclamacao_id BIGINT NOT NULL,
                external_id VARCHAR(50),
                motivo_principal VARCHAR(255),
                etapa_jornada VARCHAR(255),
                impacto_mobilidade VARCHAR(50),
                resolucao_esperada TEXT,
                risco_juridico VARCHAR(50),
                canal_falho VARCHAR(255),
                tipo_cobranca VARCHAR(255),
                modelo_veiculo VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_class_raw_id (raw_reclamacao_id),
                CONSTRAINT fk_raw_reclamacao
                    FOREIGN KEY (raw_reclamacao_id)
                    REFERENCES raw_reclamacoes(id)
                    ON DELETE CASCADE
            )
        """

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query_raw)
            cursor.execute(query_classificada)
            conn.commit()
        finally:
            conn.close()

    def insert_raw_reclamacao(self, row: dict):
        row = row or {}

        def normalize(value):
            if pd.isna(value):
                return None
            return value

        external_id = normalize(row.get("ID") or row.get("external_id"))
        titulo = normalize(row.get("Titulo") or row.get("titulo"))
        link = normalize(row.get("link") or row.get("Link"))
        texto = normalize(row.get("texto") or row.get("Texto"))
        data = normalize(row.get("Data"))
        cidade = normalize(row.get("Cidade") or row.get("cidade"))
        estado = normalize(row.get("Estado") or row.get("estado"))
        texto_reclamacao = normalize(row.get("Texto_Reclamacao") or row.get("texto_reclamacao"))
        resposta_empresa = normalize(row.get("Resposta_Empresa") or row.get("resposta_empresa"))

        query = """
            INSERT INTO raw_reclamacoes (
                external_id, titulo, link, texto, data, cidade, estado,
                texto_reclamacao, resposta_empresa
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                titulo = VALUES(titulo),
                link = VALUES(link),
                texto = VALUES(texto),
                data = VALUES(data),
                cidade = VALUES(cidade),
                estado = VALUES(estado),
                texto_reclamacao = VALUES(texto_reclamacao),
                resposta_empresa = VALUES(resposta_empresa),
                updated_at = CURRENT_TIMESTAMP
        """

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    external_id,
                    titulo,
                    link,
                    texto,
                    data,
                    cidade,
                    estado,
                    texto_reclamacao,
                    resposta_empresa,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def fetch_raw_unclassified(self):
        query = """
            SELECT r.*
            FROM raw_reclamacoes r
            LEFT JOIN reclamacoes_classificadas c
                ON c.raw_reclamacao_id = r.id
            WHERE c.raw_reclamacao_id IS NULL
            ORDER BY r.id ASC
        """
        conn = self.get_connection()
        try:
            return pd.read_sql(query, conn)
        finally:
            conn.close()

    def insert_classificacao(self, raw_reclamacao_id: int, payload: dict):
        query = """
            INSERT INTO reclamacoes_classificadas (
                raw_reclamacao_id,
                external_id,
                motivo_principal,
                etapa_jornada,
                impacto_mobilidade,
                resolucao_esperada,
                risco_juridico,
                canal_falho,
                tipo_cobranca,
                modelo_veiculo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                motivo_principal = VALUES(motivo_principal),
                etapa_jornada = VALUES(etapa_jornada),
                impacto_mobilidade = VALUES(impacto_mobilidade),
                resolucao_esperada = VALUES(resolucao_esperada),
                risco_juridico = VALUES(risco_juridico),
                canal_falho = VALUES(canal_falho),
                tipo_cobranca = VALUES(tipo_cobranca),
                modelo_veiculo = VALUES(modelo_veiculo),
                created_at = CURRENT_TIMESTAMP
        """

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    raw_reclamacao_id,
                    payload.get("external_id"),
                    payload.get("motivo_principal"),
                    payload.get("etapa_jornada"),
                    payload.get("impacto_mobilidade"),
                    payload.get("resolucao_esperada"),
                    payload.get("risco_juridico"),
                    payload.get("canal_falho"),
                    payload.get("tipo_cobranca"),
                    payload.get("modelo_veiculo"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def fetch_classified_dataframe(self):
        query = """
            SELECT
                c.id,
                c.raw_reclamacao_id,
                c.external_id,
                c.motivo_principal AS Motivo_IA,
                c.etapa_jornada AS Etapa_Jornada_IA,
                c.impacto_mobilidade AS Impacto_Mobilidade_IA,
                c.resolucao_esperada AS Resolucao_Esperada_IA,
                c.risco_juridico AS Risco_Juridico_IA,
                c.canal_falho AS Canal_Falho_IA,
                c.tipo_cobranca AS Tipo_Cobranca_IA,
                c.modelo_veiculo AS Modelo_Veiculo_IA,
                r.data AS Data,
                r.estado AS Estado,
                r.cidade AS Cidade,
                r.texto_reclamacao AS Texto_Reclamacao
            FROM reclamacoes_classificadas c
            LEFT JOIN raw_reclamacoes r
                ON r.id = c.raw_reclamacao_id
            ORDER BY c.id ASC
        """
        conn = self.get_connection()
        try:
            return pd.read_sql(query, conn)
        finally:
            conn.close()

    def get_row_by_id(self, reclamacao_id: int):
        query = "SELECT * FROM raw_reclamacoes WHERE id = %s"
        conn = self.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (reclamacao_id,))
            return cursor.fetchone()
        finally:
            conn.close()
