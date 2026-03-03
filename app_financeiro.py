import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Comissão Angels (D0/D1)", layout="wide")
st.title("💸 Calculadora de Comissões - Angels (Modelo D0/D1)")

# --- FUNÇÃO DE CÁLCULO DE DIAS ÚTEIS ---
def calcular_dias_corridos_uteis(start_col, end_col):
    # Converte para data (ignora hora) para saber se é D0, D1, etc.
    # np.busday_count conta dias úteis entre duas datas (exclui Sábado e Domingo)
    # Se abrir e fechar no mesmo dia, retorna 0 (D0)
    dias = np.busday_count(
        start_col.values.astype('datetime64[D]'), 
        end_col.values.astype('datetime64[D]')
    )
    return dias

# --- APLICAÇÃO ---
uploaded_file = st.file_uploader("Carregue o Relatorio.csv para calcular", type="csv")

if uploaded_file is not None:
    try:
        # Carregar dados
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        
        # Filtro Automático: Apenas Status "BAIXADA" (conforme solicitado)
        # Normalizando texto para garantir que pegue "Baixada", "BAIXADA", etc.
        df['Status_Upper'] = df['Status'].astype(str).str.upper().str.strip()
        df_filtrado = df[df['Status_Upper'] == 'BAIXADA'].copy()
        
        if df_filtrado.empty:
            st.warning("Não foram encontradas visitas com status 'BAIXADA'. Verifique o arquivo.")
        else:
            # Converter datas
            cols_data = ['Data Abertura', 'Data Atendimento']
            for col in cols_data:
                df_filtrado[col] = pd.to_datetime(df_filtrado[col], dayfirst=True, errors='coerce')
            
            # Remover erros de data
            df_filtrado.dropna(subset=cols_data, inplace=True)
            
            # Calcular o "D" (D0, D1, D2...) considerando dias úteis
            df_filtrado['Dias_Uteis'] = calcular_dias_corridos_uteis(
                df_filtrado['Data Abertura'], 
                df_filtrado['Data Atendimento']
            )
            # Garantir que não haja negativos
            df_filtrado['Dias_Uteis'] = df_filtrado['Dias_Uteis'].clip(lower=0)

            st.success(f"Arquivo carregado! {len(df_filtrado)} visitas 'BAIXADA' processadas.")

            # --- CONFIGURAÇÃO DE VALORES (EDITÁVEL) ---
            st.divider()
            st.subheader("⚙️ Configuração dos Valores (Comissão)")
            
            col_stone, col_ton = st.columns(2)
            
            # Configuração STONE
            with col_stone:
                st.markdown("### 🟢 STONE")
                st.info("Regra: D0=Alto, D1=Médio, D2+=Baixo")
                v_stone_d0 = st.number_input("Valor D0 (Mesmo dia)", value=5.00, key="s0")
                v_stone_d1 = st.number_input("Valor D1 (1 dia útil)", value=3.00, key="s1")
                v_stone_d2_plus = st.number_input("Valor D2 em diante", value=2.00, key="s2")

            # Configuração TON
            with col_ton:
                st.markdown("### 🔵 TON")
                st.info("Regra: D0, D1 e D2 pagam igual. D3+ paga menos.")
                v_ton_d0_d2 = st.number_input("Valor D0, D1 e D2", value=5.00, key="t02")
                v_ton_d3_plus = st.number_input("Valor acima de D2 (D3+)", value=2.00, key="t3")

            # --- CÁLCULO ---
            if st.button("Calcular Comissões", type="primary"):
                resultados = []
                
                for idx, row in df_filtrado.iterrows():
                    dias = int(row['Dias_Uteis'])
                    contratante = str(row['Contratante']).upper()
                    valor = 0.0
                    regra_desc = ""

                    # Lógica STONE
                    if "STONE" in contratante:
                        if dias == 0:
                            valor = v_stone_d0
                            regra_desc = "D0"
                        elif dias == 1:
                            valor = v_stone_d1
                            regra_desc = "D1"
                        else:
                            valor = v_stone_d2_plus
                            regra_desc = f"D{dias} (D2+)"
                    
                    # Lógica TON
                    elif "TON" in contratante:
                        if dias <= 2: # 0, 1 ou 2
                            valor = v_ton_d0_d2
                            regra_desc = f"D{dias} (Faixa D0-D2)"
                        else: # 3 em diante
                            valor = v_ton_d3_plus
                            regra_desc = f"D{dias} (D3+)"
                    
                    # Outros (Caso exista)
                    else:
                        valor = 0.0
                        regra_desc = "Outro Contratante"

                    resultados.append({
                        'Chamado': row['Chamado'],
                        'Técnico': row['Técnico'],
                        'Contratante': row['Contratante'],
                        'Data Abertura': row['Data Abertura'],
                        'Data Atendimento': row['Data Atendimento'],
                        'Prazo (Dias Úteis)': dias,
                        'Classificação': regra_desc,
                        'Comissão (R$)': valor
                    })

                # --- EXIBIÇÃO DOS RESULTADOS ---
                df_resultado = pd.DataFrame(resultados)
                
                st.divider()
                st.header("📊 Resultado Final")

                # Totais
                total_pagar = df_resultado['Comissão (R$)'].sum()
                st.metric("Total de Comissões a Pagar", f"R$ {total_pagar:,.2f}")

                # Tabela Resumo por Técnico
                resumo = df_resultado.groupby('Técnico').agg(
                    Qtd_Visitas=('Chamado', 'count'),
                    Media_Dias=('Prazo (Dias Úteis)', 'mean'),
                    Total_Comissao=('Comissão (R$)', 'sum')
                ).reset_index().sort_values('Total_Comissao', ascending=False)

                col_table, col_detail = st.columns([1, 1])

                with col_table:
                    st.subheader("Por Angel")
                    st.dataframe(
                        resumo.style.format({
                            "Total_Comissao": "R$ {:.2f}",
                            "Media_Dias": "{:.1f} dias"
                        }),
                        use_container_width=True
                    )

                with col_detail:
                    st.subheader("Gráfico de Performance")
                    st.bar_chart(resumo.set_index('Técnico')['Total_Comissao'])

                # Botão Download
                csv = df_resultado.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
                st.download_button(
                    label="📥 Baixar Relatório Completo (CSV)",
                    data=csv,
                    file_name="comissoes_angels_d0_d1.csv",
                    mime="text/csv"
                )

                with st.expander("Ver dados detalhados"):
                    st.dataframe(df_resultado)

    except Exception as e:
        st.error(f"Erro ao processar: {e}")