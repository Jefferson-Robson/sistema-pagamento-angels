import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Comissão Angels (Flexível)", layout="wide")
st.title("💸 Calculadora de Comissões Flexível")

# --- FUNÇÕES DE CÁLCULO ---
def calcular_dias_uteis(start_col, end_col):
    """Conta apenas dias úteis (Seg a Sex)."""
    dias = np.busday_count(
        start_col.values.astype('datetime64[D]'), 
        end_col.values.astype('datetime64[D]')
    )
    return dias

def calcular_dias_corridos(start_col, end_col):
    """Conta dias corridos (Inclui Sab/Dom)."""
    # Diferença em dias
    diferenca = (end_col - start_col).dt.days
    return diferenca

# --- APLICAÇÃO ---
uploaded_file = st.file_uploader("Carregue o Relatorio.csv", type="csv")

if uploaded_file is not None:
    try:
        # Carregar dados
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        
        # Filtro Automático: Apenas Status "BAIXADA"
        df['Status_Upper'] = df['Status'].astype(str).str.upper().str.strip()
        df_filtrado = df[df['Status_Upper'] == 'BAIXADA'].copy()
        
        if df_filtrado.empty:
            st.warning("Nenhum atendimento 'BAIXADA' encontrado.")
        else:
            # Tratamento de Datas
            cols_data = ['Data Abertura', 'Data Atendimento']
            for col in cols_data:
                df_filtrado[col] = pd.to_datetime(df_filtrado[col], dayfirst=True, errors='coerce')
            df_filtrado.dropna(subset=cols_data, inplace=True)

            # --- CONFIGURAÇÕES LATERAIS ---
            st.sidebar.header("⚙️ Configurações Gerais")
            
            # Opção Decisiva: Dias Úteis vs Corridos
            tipo_contagem = st.sidebar.radio(
                "Como contar os dias?",
                ("Dias Úteis (Sem Sab/Dom)", "Dias Corridos (Inclui Fim de Semana)"),
                index=0,
                help="Dias Úteis pagam mais (ignoram atraso no fim de semana). Dias Corridos são mais rígidos."
            )
            
            # Aplica a lógica escolhida
            if "Úteis" in tipo_contagem:
                df_filtrado['Dias_Calculados'] = calcular_dias_uteis(
                    df_filtrado['Data Abertura'], df_filtrado['Data Atendimento']
                )
                nome_coluna_prazo = "Prazo (Dias Úteis)"
            else:
                df_filtrado['Dias_Calculados'] = calcular_dias_corridos(
                    df_filtrado['Data Abertura'], df_filtrado['Data Atendimento']
                )
                nome_coluna_prazo = "Prazo (Dias Corridos)"
                
            # Garante que não haja negativos (se atendeu antes de abrir, vira 0)
            df_filtrado['Dias_Calculados'] = df_filtrado['Dias_Calculados'].clip(lower=0)

            st.success(f"Arquivo processado! Usando regra de: **{tipo_contagem}**")

            # --- CONFIGURAÇÃO DE VALORES (Padronizada) ---
            st.divider()
            st.subheader("💰 Tabela de Valores (Por Performance)")
            st.markdown("Ajuste os valores para cada faixa de atendimento (D0, D1, D2+).")
            
            col_stone, col_ton = st.columns(2)
            
            # Configuração STONE
            with col_stone:
                st.markdown("### 🟢 STONE")
                s_d0 = st.number_input("STONE - D0 (Mesmo dia)", value=5.00)
                s_d1 = st.number_input("STONE - D1 (Dia seguinte)", value=3.00)
                s_d2 = st.number_input("STONE - D2 em diante", value=2.00)

            # Configuração TON (Agora idêntica à Stone)
            with col_ton:
                st.markdown("### 🔵 TON")
                t_d0 = st.number_input("TON - D0 (Mesmo dia)", value=5.00)
                t_d1 = st.number_input("TON - D1 (Dia seguinte)", value=5.00) # Padrão TON é pagar bem no D1 também
                t_d2 = st.number_input("TON - D2 em diante", value=2.00)

            # --- CÁLCULO FINAL ---
            if st.button("Calcular Pagamento", type="primary"):
                resultados = []
                
                for idx, row in df_filtrado.iterrows():
                    dias = int(row['Dias_Calculados'])
                    contratante = str(row['Contratante']).upper().strip()
                    valor = 0.0
                    classificacao = ""

                    # Define qual tabela de preços usar
                    if "STONE" in contratante:
                        precos = [s_d0, s_d1, s_d2] # Lista [D0, D1, D2+]
                        nome_empresa = "STONE"
                    elif "TON" in contratante:
                        precos = [t_d0, t_d1, t_d2] # Lista [D0, D1, D2+]
                        nome_empresa = "TON"
                    else:
                        precos = [0.0, 0.0, 0.0]
                        nome_empresa = "OUTROS"

                    # Aplica a regra D0, D1, D2+
                    if dias == 0:
                        valor = precos[0]
                        classificacao = "D0"
                    elif dias == 1:
                        valor = precos[1]
                        classificacao = "D1"
                    else:
                        valor = precos[2] # Qualquer coisa acima de D1 cai aqui
                        classificacao = f"D{dias} (D2+)"

                    resultados.append({
                        'Chamado': row['Chamado'],
                        'Técnico': row['Técnico'],
                        'Contratante': row['Contratante'],
                        'Data Atendimento': row['Data Atendimento'],
                        nome_coluna_prazo: dias,
                        'Classificação': classificacao,
                        'Comissão (R$)': valor
                    })

                df_res = pd.DataFrame(resultados)

                # --- EXIBIÇÃO ---
                st.divider()
                col_kpi1, col_kpi2 = st.columns(2)
                col_kpi1.metric("Total a Pagar", f"R$ {df_res['Comissão (R$)'].sum():,.2f}")
                col_kpi2.metric("Visitas Pagas", len(df_res))

                # Tabela Resumida
                resumo = df_res.groupby('Técnico').agg(
                    Visitas=('Chamado', 'count'),
                    Total=('Comissão (R$)', 'sum')
                ).reset_index().sort_values('Total', ascending=False)

                st.subheader("Resumo por Angel")
                st.dataframe(resumo.style.format({"Total": "R$ {:.2f}"}), use_container_width=True)

                # Download
                csv = df_res.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
                st.download_button(
                    "📥 Baixar Relatório (CSV)",
                    csv,
                    "folha_pagamento_final.csv",
                    "text/csv"
                )
                
                with st.expander("Ver detalhes completos"):
                    st.dataframe(df_res)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")