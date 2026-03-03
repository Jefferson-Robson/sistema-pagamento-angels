import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Comissão Angels", layout="wide")
st.title("💸 Calculadora de Comissões (Angels)")

# --- FUNÇÕES DE CÁLCULO (CORRIGIDAS) ---
def calcular_dias_uteis(start_col, end_col):
    """
    Conta dias úteis ignorando finais de semana.
    Ex: Sexta para Segunda = 1 dia útil (D1).
    """
    # Converte para data pura (sem hora) para garantir precisão do calendario
    dias = np.busday_count(
        start_col.values.astype('datetime64[D]'), 
        end_col.values.astype('datetime64[D]')
    )
    return dias

def calcular_dias_corridos(start_col, end_col):
    """
    Conta dias de calendário (virada de data).
    Ex: Sexta para Segunda = 3 dias (D3).
    Ex: Dia 30 às 23h para Dia 31 às 01h = 1 dia (D1).
    """
    # Normaliza para meia-noite (remove horas) para calcular a distância entre DIAS
    start_norm = pd.to_datetime(start_col).dt.normalize()
    end_norm = pd.to_datetime(end_col).dt.normalize()
    
    # Calcula a diferença em dias
    diferenca = (end_norm - start_norm).dt.days
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

            # --- BARRA LATERAL (CONFIGURAÇÕES) ---
            st.sidebar.header("⚙️ Configurações")
            
            # Opção Decisiva
            tipo_contagem = st.sidebar.radio(
                "Regra de Contagem de Dias:",
                ("Dias Úteis (Sem Sab/Dom)", "Dias Corridos (Calendário)"),
                index=0
            )

            # --- APLICAÇÃO DA LÓGICA DE DIAS ---
            # O cálculo é feito aqui para garantir que a mudança no rádio afete os dados
            if "Úteis" in tipo_contagem:
                df_filtrado['Dias_Calculados'] = calcular_dias_uteis(
                    df_filtrado['Data Abertura'], df_filtrado['Data Atendimento']
                )
                label_prazo = "Prazo (Úteis)"
                msg_tipo = "Ignorando Finais de Semana"
            else:
                df_filtrado['Dias_Calculados'] = calcular_dias_corridos(
                    df_filtrado['Data Abertura'], df_filtrado['Data Atendimento']
                )
                label_prazo = "Prazo (Corridos)"
                msg_tipo = "Contando Sábados e Domingos"
                
            # Garante que não haja negativos
            df_filtrado['Dias_Calculados'] = df_filtrado['Dias_Calculados'].clip(lower=0)

            st.info(f"Modo Ativo: **{tipo_contagem}** ({msg_tipo})")

            # --- CONFIGURAÇÃO DE VALORES ---
            st.divider()
            st.subheader("💰 Tabela de Valores")
            
            col_stone, col_ton = st.columns(2)
            
            # Valores STONE
            with col_stone:
                st.markdown("### 🟢 STONE")
                s_d0 = st.number_input("STONE - D0", value=5.00)
                s_d1 = st.number_input("STONE - D1", value=3.00)
                s_d2 = st.number_input("STONE - D2+", value=2.00)

            # Valores TON
            with col_ton:
                st.markdown("### 🔵 TON")
                t_d0 = st.number_input("TON - D0", value=5.00)
                t_d1 = st.number_input("TON - D1", value=5.00)
                t_d2 = st.number_input("TON - D2+", value=2.00)

            # --- PROCESSAMENTO DO PAGAMENTO ---
            # Removemos o botão para o cálculo ser reativo (instantâneo)
            resultados = []
            
            for idx, row in df_filtrado.iterrows():
                dias = int(row['Dias_Calculados'])
                contratante = str(row['Contratante']).upper().strip()
                valor = 0.0
                classificacao = ""

                # Seleção de Tabela
                if "STONE" in contratante:
                    precos = [s_d0, s_d1, s_d2]
                elif "TON" in contratante:
                    precos = [t_d0, t_d1, t_d2]
                else:
                    precos = [0.0, 0.0, 0.0]

                # Classificação D0, D1, D2
                if dias == 0:
                    valor = precos[0]
                    classificacao = "D0"
                elif dias == 1:
                    valor = precos[1]
                    classificacao = "D1"
                else:
                    valor = precos[2]
                    classificacao = f"D{dias} (D2+)"

                resultados.append({
                    'Chamado': row['Chamado'],
                    'Técnico': row['Técnico'],
                    'Contratante': row['Contratante'],
                    'Data Abertura': row['Data Abertura'],
                    'Data Atendimento': row['Data Atendimento'],
                    label_prazo: dias, # Nome da coluna muda dinamicamente
                    'Classificação': classificacao,
                    'Comissão (R$)': valor
                })

            df_res = pd.DataFrame(resultados)

            # --- EXIBIÇÃO ---
            st.divider()
            
            # Métricas
            total = df_res['Comissão (R$)'].sum()
            col_met1, col_met2 = st.columns(2)
            col_met1.metric("Total a Pagar", f"R$ {total:,.2f}")
            col_met2.metric("Quantidade Visitas", len(df_res))

            # Resumo
            resumo = df_res.groupby('Técnico').agg(
                Visitas=('Chamado', 'count'),
                Total=('Comissão (R$)', 'sum')
            ).reset_index().sort_values('Total', ascending=False)

            st.subheader("📊 Resumo por Angel")
            st.dataframe(resumo.style.format({"Total": "R$ {:.2f}"}), use_container_width=True)

            # Download
            csv = df_res.to_csv(index=False, sep=';', decimal=',').encode('utf-8')
            st.download_button(
                "📥 Baixar Relatório (CSV)",
                csv,
                "pagamento_final.csv",
                "text/csv"
            )
            
            with st.expander("Ver Tabela Detalhada"):
                st.dataframe(df_res)

    except Exception as e:
        st.error(f"Erro no processamento: {e}")