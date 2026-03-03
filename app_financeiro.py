import streamlit as st
import pandas as pd
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Pagamento Angels", layout="wide")

st.title("🚚 Sistema de Pagamento de Agentes Logísticos")
st.markdown("Faça o upload do **Relatorio.csv** para calcular a produção.")

# 1. Upload do Arquivo
uploaded_file = st.file_uploader("Carregue o arquivo CSV aqui", type="csv")

if uploaded_file is not None:
    # Carregando os dados
    try:
        df = pd.read_csv(uploaded_file, sep=';')
        
        # Convertendo colunas de data para o formato correto do Pandas
        # O formato identificado foi DD/MM/YYYY HH:MM:SS
        df['Data Atendimento'] = pd.to_datetime(df['Data Atendimento'], dayfirst=True, errors='coerce')
        
        st.success("Arquivo carregado com sucesso!")
        
        # --- FILTROS LATERAIS ---
        st.sidebar.header("Filtros")
        
        # Filtro de Data
        min_date = df['Data Atendimento'].min().date()
        max_date = df['Data Atendimento'].max().date()
        
        data_inicio = st.sidebar.date_input("Data Inicial", min_date)
        data_fim = st.sidebar.date_input("Data Final", max_date)
        
        # Filtro de Status (Por padrão, seleciona 'BAIXADA')
        status_options = df['Status'].unique()
        default_status = ['BAIXADA'] if 'BAIXADA' in status_options else status_options
        status_selecionados = st.sidebar.multiselect("Status Considerados", status_options, default=default_status)
        
        # --- APLICAÇÃO DOS FILTROS ---
        # Filtra por data e status
        mask = (
            (df['Data Atendimento'].dt.date >= data_inicio) & 
            (df['Data Atendimento'].dt.date <= data_fim) & 
            (df['Status'].isin(status_selecionados))
        )
        df_filtrado = df.loc[mask].copy()
        
        st.info(f"Foram encontrados **{len(df_filtrado)}** atendimentos válidos no período selecionado.")

        # --- TABELA DE PREÇOS (DINÂMICA) ---
        st.subheader("💰 Tabela de Preços por Serviço")
        st.markdown("Ajuste os valores abaixo conforme a negociação:")
        
        # Identifica todos os serviços únicos no filtro atual
        servicos_encontrados = df_filtrado['Serviço'].unique()
        
        # Cria um DataFrame inicial para a tabela de preços
        tabela_precos_inicial = pd.DataFrame({
            'Serviço': servicos_encontrados,
            'Valor Unitário (R$)': 20.00 # Valor padrão sugerido
        })
        
        # Editor de dados interativo
        tabela_precos_editavel = st.data_editor(
            tabela_precos_inicial, 
            column_config={
                "Valor Unitário (R$)": st.column_config.NumberColumn(
                    "Valor (R$)",
                    help="Valor pago ao Angel por este serviço",
                    min_value=0.0,
                    step=1.0,
                    format="R$ %.2f"
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
        # --- CÁLCULO DO PAGAMENTO ---
        if not df_filtrado.empty:
            # Transforma a tabela editável em um dicionário para busca rápida
            mapa_precos = dict(zip(tabela_precos_editavel['Serviço'], tabela_precos_editavel['Valor Unitário (R$)']))
            
            # Cria a coluna de valor a receber
            df_filtrado['Valor a Receber'] = df_filtrado['Serviço'].map(mapa_precos).fillna(0)
            
            # Agrupa por Técnico
            pagamento_por_tecnico = df_filtrado.groupby('Técnico').agg(
                Qtd_Visitas=('Chamado', 'count'),
                Total_Receber=('Valor a Receber', 'sum')
            ).reset_index().sort_values(by='Total_Receber', ascending=False)
            
            # --- EXIBIÇÃO DOS RESULTADOS ---
            st.divider()
            st.subheader("📊 Relatório Final de Pagamento")
            
            # Formatação para exibição
            st.dataframe(
                pagamento_por_tecnico.style.format({"Total_Receber": "R$ {:.2f}"}),
                use_container_width=True
            )
            
            # Botão de Download
            csv = pagamento_por_tecnico.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
            st.download_button(
                label="📥 Baixar Relatório de Pagamento (CSV)",
                data=csv,
                file_name='Folha_Pagamento_Angels.csv',
                mime='text/csv',
            )
            
            # Detalhes (Opcional)
            with st.expander("Ver detalhes de todas as visitas calculadas"):
                st.dataframe(df_filtrado[['Data Atendimento', 'Chamado', 'Técnico', 'Serviço', 'Status', 'Valor a Receber']])
        else:
            st.warning("Nenhum dado encontrado com os filtros atuais.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")