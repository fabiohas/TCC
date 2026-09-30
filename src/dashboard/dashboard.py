import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import get_project_path
from src.db import DatabaseManager

# 1. Configuração da Página
st.set_page_config(
    page_title="Dashboard Analítico - Localiza Meoo",
    page_icon="🚗",
    layout="wide",
)


# 2. Carregamento de Dados com Cache
@st.cache_data
def carregar_dados():
    caminho_csv = get_project_path('data', 'reclamacoes_classificadas.csv')

    try:
        db = DatabaseManager()
        df = db.fetch_classified_dataframe()
        if df.empty and Path(caminho_csv).exists():
            df = pd.read_csv(caminho_csv)
    except Exception:
        if Path(caminho_csv).exists():
            df = pd.read_csv(caminho_csv)
        else:
            df = pd.DataFrame()

    if df.empty:
        return df

    colunas_ia = [
        'Motivo_IA', 'Etapa_Jornada_IA', 'Impacto_Mobilidade_IA',
        'Resolucao_Esperada_IA', 'Risco_Juridico_IA', 'Canal_Falho_IA',
        'Tipo_Cobranca_IA', 'Modelo_Veiculo_IA'
    ]
    for col in colunas_ia:
        if col in df.columns:
            df[col] = df[col].fillna('Não Informado')

    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

    return df


df = carregar_dados()

# 3. Barra Lateral (Filtros Interativos)
st.sidebar.image("https://logodownload.org/wp-content/uploads/2017/04/localiza-logo-1.png", width=150)
st.sidebar.title("Filtros Analíticos")

if not df.empty:
    estados_selecionados = st.sidebar.multiselect(
        "Filtrar por Estado (UF):",
        options=sorted(df['Estado'].dropna().unique()),
        default=[],
    )

    etapas_selecionadas = st.sidebar.multiselect(
        "Filtrar por Etapa da Jornada:",
        options=sorted(df['Etapa_Jornada_IA'].unique()),
        default=[],
    )

    # Aplicação dos filtros no DataFrame
    df_filtrado = df.copy()
    if estados_selecionados:
        df_filtrado = df_filtrado[df_filtrado['Estado'].isin(estados_selecionados)]
    if etapas_selecionadas:
        df_filtrado = df_filtrado[df_filtrado['Etapa_Jornada_IA'].isin(etapas_selecionadas)]
else:
    st.warning("Ainda não há dados classificados no banco ou no arquivo CSV.")
    st.stop()

# 4. Cabeçalho Principal e KPIs
st.title("🚗 Painel de Inteligência: Voz do Cliente (Localiza Meoo)")
st.markdown("Análise quantitativa de reclamações estruturadas via IA Generativa.")
st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de Reclamações", len(df_filtrado))

with col2:
    perc_mobilidade = (len(df_filtrado[df_filtrado['Impacto_Mobilidade_IA'] == 'Sim']) / len(df_filtrado)) * 100 if len(df_filtrado) > 0 else 0
    st.metric("Clientes Sem Carro (Impacto na Mobilidade)", f"{perc_mobilidade:.1f}%")

with col3:
    perc_risco = (len(df_filtrado[df_filtrado['Risco_Juridico_IA'] == 'Sim']) / len(df_filtrado)) * 100 if len(df_filtrado) > 0 else 0
    st.metric("Ameaça de Processo (Risco Jurídico)", f"{perc_risco:.1f}%")

with col4:
    top_motivo = df_filtrado['Motivo_IA'].mode()[0] if not df_filtrado.empty else "N/A"
    st.metric("Principal Motivo de Atrito", top_motivo)

st.divider()

# 5. Evolução Temporal (Novo Gráfico de Série Temporal)
st.subheader("Evolução Diária de Reclamações")
if 'Data' in df_filtrado.columns:
    df_temporal = df_filtrado.groupby(df_filtrado['Data'].dt.date).size().reset_index(name='Volume')
    df_temporal.columns = ['Data', 'Volume']

    fig_temporal = px.line(
        df_temporal,
        x='Data',
        y='Volume',
        markers=True,
        labels={'Data': 'Data da Reclamação', 'Volume': 'Quantidade de Reclamações'},
        color_discrete_sequence=['#2ca02c'],
    )
    fig_temporal.update_layout(xaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig_temporal, use_container_width=True)
else:
    st.warning("Coluna de data não encontrada para gerar a série temporal.")

st.divider()

# 6. Primeira Linha de Gráficos (Visão Geral da Dor)
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.subheader("Volume por Motivo Principal")
    fig_motivo = px.bar(
        df_filtrado['Motivo_IA'].value_counts().reset_index(),
        x='Motivo_IA', y='count',
        labels={'Motivo_IA': 'Motivo', 'count': 'Volume'},
        color='count', color_continuous_scale='Reds',
    )
    st.plotly_chart(fig_motivo, use_container_width=True)

with row1_col2:
    st.subheader("Distribuição pela Etapa da Jornada")
    fig_etapa = px.pie(
        df_filtrado['Etapa_Jornada_IA'].value_counts().reset_index(),
        names='Etapa_Jornada_IA', values='count',
        hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    st.plotly_chart(fig_etapa, use_container_width=True)

# 7. Segunda Linha de Gráficos (Operação e Financeiro)
row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("Gargalos no Atendimento (Canais Falhos)")
    fig_canal = px.bar(
        df_filtrado['Canal_Falho_IA'].value_counts().reset_index(),
        y='Canal_Falho_IA', x='count', orientation='h',
        labels={'Canal_Falho_IA': 'Canal', 'count': 'Volume'},
        color_discrete_sequence=['#1f77b4'],
    )
    fig_canal.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_canal, use_container_width=True)

with row2_col2:
    st.subheader("Natureza das Cobranças Contestadas")
    fig_cobranca = px.bar(
        df_filtrado['Tipo_Cobranca_IA'].value_counts().reset_index(),
        x='Tipo_Cobranca_IA', y='count',
        labels={'Tipo_Cobranca_IA': 'Tipo de Cobrança', 'count': 'Volume'},
        color_discrete_sequence=['#ff7f0e'],
    )
    st.plotly_chart(fig_cobranca, use_container_width=True)

# 8. Terceira Linha (Geografia e Tabela de Dados)
st.divider()
st.subheader("Distribuição Geográfica (Top 10 Estados)")
fig_estados = px.bar(
    df_filtrado['Estado'].value_counts().head(10).reset_index(),
    x='Estado', y='count',
    labels={'Estado': 'UF', 'count': 'Reclamações'},
    text_auto=True,
)
st.plotly_chart(fig_estados, use_container_width=True)

st.divider()
st.subheader("Base de Dados Enriquecida")
with st.expander("Clique para visualizar ou baixar os dados brutos classificados"):
    st.dataframe(
        df_filtrado[['Data', 'Estado', 'Motivo_IA', 'Etapa_Jornada_IA', 'Risco_Juridico_IA', 'Resolucao_Esperada_IA']],
        use_container_width=True,
    )