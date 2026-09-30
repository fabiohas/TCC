import json
import os
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_project_path
from src.db import DatabaseManager

# Configurações de URL e XPath
URL_LISTA = "https://www.reclameaqui.com.br/empresa/localiza-meoo/lista-reclamacoes/?status=ANSWERED"
XPATH_RECLAMACOES = "//*[starts-with(@id, 'complaint-title-')]/a"
XPATH_BOTAO_PROXIMO = '//*[@id="main-content"]/div[2]/div[2]/section/div[2]/div[2]/astro-island/div/nav//ul/li[last()]/button'
XPATH_TEXTO_RECLAMACAO = '//body'


def iniciar_driver():
    """Inicializa e retorna uma instância do Chrome via Selenium."""
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    return driver


def coletar_links(driver, max_paginas=1):
    """Navega pela paginação e coleta títulos e links das reclamações."""
    print("--- INICIANDO ETAPA 1: COLETANDO LINKS ---")
    driver.get(URL_LISTA)
    time.sleep(5)

    todas_reclamacoes = []

    for pagina in range(1, max_paginas + 1):
        print(f"Lendo lista - página {pagina}...")
        try:
            elementos = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, XPATH_RECLAMACOES))
            )
            for el in elementos:
                titulo = el.text.strip()
                link = el.get_attribute("href")
                if titulo:
                    todas_reclamacoes.append({"titulo": titulo, "link": link, "texto": ""})

            if pagina == max_paginas:
                break

            botao_proximo = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, XPATH_BOTAO_PROXIMO))
            )

            if botao_proximo.get_attribute("disabled"):
                break

            driver.execute_script("arguments[0].click();", botao_proximo)
            time.sleep(4)

        except Exception as e:
            print(f"Erro na paginação: {e}")
            break

    print(f"Etapa 1 Concluída! {len(todas_reclamacoes)} links coletados.\n")
    return todas_reclamacoes


def extrair_textos(driver, reclamacoes):
    """Acessa cada link e extrai o texto completo da reclamação."""
    print("--- INICIANDO ETAPA 2: EXTRAINDO TEXTOS ---")

    for i, reclamacao in enumerate(reclamacoes):
        print(f"Acessando link {i + 1} de {len(reclamacoes)}...")
        texto_extraido = ""

        page_driver = iniciar_driver()
        try:
            for tentativa in range(3):
                try:
                    page_driver.get(reclamacao["link"])
                    time.sleep(4 + tentativa)
                    elemento_texto = WebDriverWait(page_driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, XPATH_TEXTO_RECLAMACAO))
                    )
                    texto_extraido = elemento_texto.text.strip()

                    if any(token in texto_extraido.lower() for token in [
                        "performing security verification",
                        "this website uses a security service",
                        "cloudflare",
                    ]):
                        print(f"  -> Detectado desafio anti-bot na tentativa {tentativa + 1}. Tentando novamente...")
                        texto_extraido = ""
                        continue

                    if not texto_extraido:
                        raise TimeoutException("Corpo da página vazio")

                    break

                except TimeoutException:
                    print(f"  -> Timeout na tentativa {tentativa + 1}.")

                except WebDriverException as e:
                    print(f"  -> WebDriver falhou na tentativa {tentativa + 1}: {type(e).__name__}")
        finally:
            page_driver.quit()

        if not texto_extraido:
            print(f"\nALERTA [Timeout]: Falha ao extrair a reclamação {i+1}.")
            reclamacao["texto"] = "Erro: Timeout (Tempo limite excedido)."
        else:
            reclamacao["texto"] = texto_extraido
            print(" -> Texto extraído com sucesso!")

        time.sleep(random.uniform(4.0, 7.5))

    return reclamacoes


def salvar_dados(dados, nome_arquivo):
    """Salva a lista de dicionários em um arquivo JSON."""
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
    print(f"\nSUCESSO! Arquivo JSON salvo como '{nome_arquivo}'.")


# ========================================================
# FUNÇÕES DE LIMPEZA E FORMATAÇÃO (PANDAS)
# ========================================================

def limpar_texto_reclamacao(texto):
    if not isinstance(texto, str):
        return texto

    texto = texto.replace('\r', '\n')
    texto = re.sub(r'\s*\|\s*', '\n', texto)

    partes = re.split(r'ID:\s*\d+\s*\n', texto, maxsplit=1)
    if len(partes) > 1:
        texto = partes[1]

    if 'Resposta da empresa' in texto:
        texto = texto.split('Resposta da empresa', 1)[0]

    if 'Reclamações Parecidas' in texto:
        texto = texto.split('Reclamações Parecidas', 1)[0]

    texto = texto.replace('RA Ads', '')
    texto = re.sub(r'(?im)^\s*(Publicidade|Control your privacy|Our website uses cookies to improve navigation\.?|Privacy Policy - Terms of use|Customize|Reject|Accept|Entrar|Criar conta|Previous slide|Next slide|Compartilhe)\s*$', '', texto)
    texto = texto.replace('Previous slide', '').replace('Next slide', '').replace('Compartilhe', '').strip()
    texto = re.sub(r'\n{2,}', '\n', texto)

    return texto.strip(' \n|')


def extrair_resposta_empresa(texto):
    if not isinstance(texto, str):
        return None

    if 'Resposta da empresa\n' in texto:
        resposta = texto.split('Resposta da empresa\n')[-1]
        return resposta.replace('RA Ads', '').strip()
    return None


def formatar_data_reclamacao(df, coluna_origem='Data_Hora', coluna_destino='Data'):
    data_datetime = pd.to_datetime(df[coluna_origem], format='%d/%m/%Y às %H:%M', errors='coerce')
    df[coluna_destino] = data_datetime.dt.normalize()
    return df


def extrair_cidade_estado(df, coluna_origem='Cidade_Estado'):
    padrao_regex = r'(?P<Cidade>[^\n]+)\s*-\s*(?P<Estado>[A-Z]{2})\s*$'
    extraido = df[coluna_origem].str.extract(padrao_regex)
    df['Cidade'] = extraido['Cidade'].str.strip()
    df['Estado'] = extraido['Estado']
    return df


def processar_e_limpar_dados(caminho_json, caminho_csv):
    """Lê o JSON gerado, aplica regex para estruturar colunas e salva em CSV."""
    print("\n--- INICIANDO ETAPA 3: PROCESSAMENTO E LIMPEZA DE DADOS ---")
    df = pd.read_json(caminho_json, encoding='utf-8')
    df = df.dropna(subset=['texto']).copy()
    df['texto'] = df['texto'].astype(str).str.strip()
    df = df[df['texto'] != '']
    df = df[~df['texto'].str.lower().str.contains('performing security verification|this website uses a security service|cloudflare', na=False)]

    df['ID'] = df['texto'].str.extract(r'ID:\s*(\d+)')
    df['Data_Hora'] = df['texto'].str.extract(r'(\d{2}/\d{2}/\d{4}\s*às\s*\d{2}:\d{2})')
    df = df.dropna(subset=['ID', 'Data_Hora']).copy()
    df['Cidade_Estado'] = df['texto'].str.extract(r'([A-Za-zÀ-ÿ\-\s]+ - [A-Z]{2})\n\d{2}/\d{2}/\d{4}')

    df = formatar_data_reclamacao(df, coluna_origem='Data_Hora', coluna_destino='Data')
    df = extrair_cidade_estado(df, coluna_origem='Cidade_Estado')

    df['Texto_Reclamacao'] = df['texto'].apply(limpar_texto_reclamacao)
    df['Resposta_Empresa'] = df['texto'].apply(extrair_resposta_empresa)
    df['Texto_Reclamacao'] = df['Texto_Reclamacao'].replace({None: ''})
    df['Resposta_Empresa'] = df['Resposta_Empresa'].replace({None: ''})

    # Remove colunas desnecessárias
    df = df.drop(columns=['texto', 'link', 'Data_Hora', 'Cidade_Estado', 'Resposta_Empresa'])

    # Salva o DataFrame limpo em CSV
    df.to_csv(caminho_csv, index=False, encoding='utf-8')
    print(f"SUCESSO! Arquivo CSV final estruturado salvo em '{caminho_csv}'.")
    return df


# ========================================================
# ORQUESTRAÇÃO PRINCIPAL
# ========================================================

def main():
    """Função principal que orquestra o scraper e o processamento."""
    caminho_json = get_project_path('data', 'reclamacoes_completas_localiza_meoo_updated.json')
    caminho_csv = get_project_path('data', 'reclamacoes_completas_localiza_meoo_updated.csv')
    max_paginas = int(os.getenv("SCRAPER_MAX_PAGINAS", "20"))
    db = DatabaseManager()
    db.ensure_schema()

    driver = iniciar_driver()
    try:
        print(f"Executando scraper com max_paginas={max_paginas}")
        reclamacoes = coletar_links(driver, max_paginas=max_paginas)
        if reclamacoes:
            reclamacoes_completas = extrair_textos(driver, reclamacoes)
            salvar_dados(reclamacoes_completas, caminho_json)

            df_limpo = processar_e_limpar_dados(caminho_json, caminho_csv)
            for row in df_limpo.to_dict(orient='records'):
                db.insert_raw_reclamacao(row)
        else:
            print("Nenhuma reclamação foi coletada na Etapa 1.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()