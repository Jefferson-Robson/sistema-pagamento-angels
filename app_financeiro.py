import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Pagamento Angels v3.0", layout="wide")
st.title("🚚 Sistema de Pagamento (TMA Dias Úteis)")

# Função para calcular dias úteis com precisão decimal (ex: 0.43 dias)
def calcular_dias_uteis_preciso(start_col, end_col):
    # 1. Calcula dias úteis inteiros entre as datas (sem contar horas)
    # np.busday_count conta dias úteis entre duas datas (exclui sab/dom)
    dias_inteiros = np.busday_count(
        start_col.values.astype('datetime64[D]'), 
        end_col.values.astype('datetime64[D]')
    )
    
    # 2. Calcula a fração do dia baseada nas horas
    # (Hora Fim - Hora Inicio) em segundos / segundos em um dia
    segundos_dia = 24 * 60 * 60
    # Extrai a diferença de tempo dentro do próprio dia
    start_seconds = (start_col.dt.hour * 3600 + start_col.dt.minute * 60 + start_col.dt.second)
    end_seconds = (end_col.dt.hour * 3600 + end_col.dt.minute * 60 + end_col.dt.second)
    fracao_dia = (end_seconds - start_seconds) / segundos_dia
    
    # 3. Soma tudo
    total_dias = dias_inteiros + fracao_dia
    return total_dias

# --- UPLOAD E PROCESSAMENTO ---
uploaded_file = st.file_uploader("Carregue o Relatorio.csv", type="csv")

if uploaded_file is not None:
    try:
        # Carregar dados
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        
        # Converter datas
        cols_data = ['Data Abertura', 'Data Atendimento']
        for col in cols_data:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
        
        # Remover linhas sem data (erros de preenchimento)
        df.dropna(subset=cols_data, inplace=True)

        # --- CÁLCULO DO TMA (DIAS ÚTEIS) ---
        # Calcula dias úteis excluindo fins de semana
        df['TMA_Dias_Uteis'] = calcular_dias_uteis_preciso(df['Data Abertura'], df['Data Atendimento'])
        # Garante que não tenha valor negativo (caso erro de data)
        df['TMA_Dias_Uteis'] = df['TMA_Dias_Uteis'].clip(lower=0)

        # Normalizar nomes dos grupos de serviço (maiúsculas)
        df['Grupo Serviço'] = df['Grupo Serviço'].str.upper().str.strip()

        # Definir quais grupos entram na regra de TMA
        GRUPOS_TMA = ['TROCA', 'INSTALAÇÃO', 'MANUTENÇÃO', 'MANUTENCAO']
        
        # Criar coluna para identificar a regra
        df['Regra'] = df['Grupo Serviço'].apply(lambda x: 'TMA' if x in GRUPOS_TMA else 'FIXO')

        st.success("Dados processados! Dias úteis calculados.")

        # --- FILTROS DE VISUALIZAÇÃO ---
        with st.expander("📅 Filtros (Data e Status)", expanded=False):
            col1, col2 = st.columns(2)
            min_date = df['Data Atendimento'].min().date()
            max_date = df['Data Atendimento'].max().date()
            data_inicio = col1.date_input("Data Inicial", min_date)
            data_fim = col1.date_input("Data Final", max_date)
            
            status_options = df['Status'].unique()
            default_status = ['BAIXADA'] if 'BAIXADA' in status_options else status_options
            status_selecionados = col2.multiselect("Status", status_options, default=default_status)

        # Aplicar filtros
        mask = (
            (df['Data Atendimento'].dt.date >= data_inicio) & 
            (df['Data Atendimento'].dt.date <= data_fim) & 
            (df['Status'].isin(status_selecionados))
        )
        df_filtrado = df.loc[mask].copy()

        # --- CONFIGURAÇÃO DE PAGAMENTO ---
        st.divider()
        st.header("💰 Configuração de Valores")
        
        tab1, tab2 = st.tabs(["Regra TMA (Troca/Instalação)", "Regra Fixa (Outros)"])

        # --- ABA 1: SERVIÇOS COM TMA ---
        config_tma = {}
        with tab1:
            st.info("Estes valores aplicam-se apenas a: TROCA, INSTALAÇÃO e MANUTENÇÃO.")
            contratantes = df_filtrado['Contratante'].unique()
            
            cols = st.columns(len(contratantes))
            for idx, contratante in enumerate(contratantes):
                with cols[idx]:
                    st.subheader(contratante)
                    # Tabela padrão de faixas
                    df_padrao = pd.DataFrame({
                        'Até (Dias Úteis)': [1.0, 2.0, 3.0, 99.0],
                        'Valor (R$)': [25.00, 20.00, 15.00, 10.00]
                    })
                    tabela = st.data_editor(
                        df_padrao, 
                        key=f"tma_{contratante}",
                        hide_index=True,
                        column_config={"Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")}
                    )
                    config_tma[contratante] = tabela

        # --- ABA 2: SERVIÇOS FIXOS ---
        config_fixo = {}
        with tab2:
            st.info("Defina o valor fixo para serviços que NÃO entram no cálculo de TMA.")
            servicos_fixos = df_filtrado[df_filtrado['Regra'] == 'FIXO']['Serviço'].unique()
            
            if len(servicos_fixos) > 0:
                df_servicos = pd.DataFrame({'Serviço': servicos_fixos, 'Valor Fixo (R$)': 15.00})
                tabela_fixa = st.data_editor(
                    df_servicos,
                    hide_index=True,
                    column_config={"Valor Fixo (R$)": st.column_config.NumberColumn(format="R$ %.2f")}
                )
                # Converter para dicionário para busca rápida
                config_fixo = dict(zip(tabela_fixa['Serviço'], tabela_fixa['Valor Fixo (R$)']))
            else:
                st.write("Nenhum serviço 'Fixo' encontrado no filtro atual.")

        # --- CÁLCULO FINAL ---
        if st.button("Calcular Folha de Pagamento", type="primary"):
            resultados = []
            
            for idx, row in df_filtrado.iterrows():
                valor_final = 0.0
                regra_aplicada = ""
                
                # LÓGICA 1: É serviço de TMA?
                if row['Regra'] == 'TMA':
                    tabela_regras = config_tma.get(row['Contratante'])
                    if tabela_regras is not None:
                        # Ordena faixas
                        tabela_regras = tabela_regras.sort_values('Até (Dias Úteis)')
                        # Busca a faixa
                        for _, faixa in tabela_regras.iterrows():
                            if row['TMA_Dias_Uteis'] <= faixa['Até (Dias Úteis)']:
                                valor_final = faixa['Valor (R$)']
                                regra_aplicada = f"TMA <= {faixa['Até (Dias Úteis)']}"
                                break
                
                # LÓGICA 2: É serviço FIXO?
                else:
                    valor_final = config_fixo.get(row['Serviço'], 0.0)
                    regra_aplicada = "Tabela Fixa"

                resultados.append({
                    'Chamado': row['Chamado'],
                    'Técnico': row['Técnico'],
                    'Contratante': row['Contratante'],
                    'Grupo Serviço': row['Grupo Serviço'],
                    'Serviço': row['Serviço'],
                    'Data Atendimento': row['Data Atendimento'],
                    'TMA (Dias Úteis)': round(row['TMA_Dias_Uteis'], 2),
                    'Regra Aplicada': regra_aplicada,
                    'Valor a Receber': valor_final
                })

            df_res = pd.DataFrame(resultados)
            
            # --- EXIBIÇÃO ---
            st.divider()
            col_total, col_download = st.columns([3, 1])
            
            total_geral = df_res['Valor a Receber'].sum()
            col_total.metric("Total da Folha", f"R$ {total_geral:,.2f}")
            
            # Tabela Resumo por Técnico
            resumo_tecnico = df_res.groupby('Técnico').agg(
                Visitas=('Chamado', 'count'),
                TMA_Medio=('TMA (Dias Úteis)', 'mean'),
                Total_Receber=('Valor a Receber', 'sum')
            ).reset_index().sort_values('Total_Receber', ascending=False)

            st.subheader("📊 Resumo por Angel")
            st.dataframe(
                resumo_tecnico.style.format({
                    "Total_Receber": "R$ {:.2f}",
                    "TMA_Medio": "{:.2f} dias"
                }),
                use_container_width=True
            )

            # Botão Download
            csv = df_res.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
            col_download.download_button(
                "📥 Baixar Detalhado (CSV)",
                csv,
                "folha_pagamento_angels.csv",
                "text/csv"
            )

    except Exception as e:
        st.error(f"Erro no processamento: {e}")