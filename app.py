"""Painel do gerente - Raio-X do Prato (Bovinu's Grill & Beer, Augusta).

Rodar:  streamlit run app.py
"""
import json
import os

import pandas as pd
import streamlit as st

from analisador import analisar_prato
from custos import (
    CATEGORIAS, CUSTO_KG, LIMITE_FILA_CHURRASQUEIRA_MIN, LIMITE_MARGEM_ALERTA,
    META_FILA_CHURRASQUEIRA_MIN, PRECO_KG, aplicar_margem, calcular_margem,
)
from simulador import gerar_dia

ESTACOES = {
    "t_saladas": "Saladas",
    "t_quentes": "Pratos quentes",
    "t_churrasqueira": "Churrasqueira",
    "t_balanca": "Balança",
}
NOMES_CATEGORIA = {"carne": "Carne", "guarnicao": "Guarnição", "salada": "Salada", "outros": "Outros"}

st.set_page_config(page_title="Raio-X do Prato", layout="wide")


@st.cache_data
def carregar_dados():
    """Usa data/pratos.csv (dados reais) se existir; senão, o dia simulado."""
    if os.path.exists("data/pratos.csv"):
        return pd.read_csv("data/pratos.csv"), False
    return gerar_dia(), True


dados, simulado = carregar_dados()

# ---------------- Barra lateral: premissas ----------------
st.sidebar.header("Premissas")
preco_kg = st.sidebar.number_input("Preço do kg (R$)", value=float(PRECO_KG), step=1.0)
st.sidebar.caption("Custo estimado do alimento por kg (R$):")
custo_kg = {c: st.sidebar.number_input(NOMES_CATEGORIA[c], value=float(CUSTO_KG[c]), step=1.0) for c in CATEGORIAS}
limite = st.sidebar.slider("Alerta de custo alto: margem abaixo de", 0.40, 0.90, float(LIMITE_MARGEM_ALERTA), 0.01)
meta_fila = st.sidebar.number_input("Meta de fila na churrasqueira (min)", value=float(META_FILA_CHURRASQUEIRA_MIN), step=0.5)

st.sidebar.divider()
st.sidebar.header("IA de visão")
chave_ia = st.sidebar.text_input(
    "Chave da API do Gemini", value=os.getenv("GEMINI_API_KEY", ""), type="password",
    help="Chave gratuita do Google AI Studio. Fica só na memória desta sessão, não é salva em arquivo.",
).strip()
if chave_ia:
    st.sidebar.success("IA de visão ligada")
else:
    st.sidebar.info("Sem chave: a análise ao vivo fica simulada")

df = aplicar_margem(dados, custo_kg=custo_kg, preco_kg=preco_kg, limite=limite)

# ---------------- Cabeçalho ----------------
st.title("Raio-X do Prato")
st.caption("Bovinu's Grill & Beer - Augusta | almoço por quilo")
if simulado:
    st.warning("Dados SIMULADOS com os parâmetros informados pela diretoria (ver README). "
               "Com a câmera na balança, estes números passam a ser reais.")

aba_gerente, aba_prato, aba_galeria = st.tabs(["Visão do gerente", "Câmera na balança (ao vivo)", "Galeria de pratos analisados"])

# ---------------- Aba 1: gerente ----------------
with aba_gerente:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Clientes no dia", f"{len(df)}")
    c2.metric("Peso médio do prato", f"{df['peso_g'].mean():.0f} g")
    c3.metric("Margem média", f"{df['margem_pct'].mean() * 100:.1f}%")
    c4.metric("Pratos de custo alto", f"{df['custo_alto'].mean() * 100:.1f}%")
    c5.metric("Tempo médio no buffet", f"{df['tempo_total_min'].mean():.1f} min")

    st.subheader("Onde o cliente demora")
    medias = pd.Series({nome: df[col].mean() for col, nome in ESTACOES.items()})
    esq, dir_ = st.columns([1, 2])
    esq.bar_chart(medias.rename("minutos (média do dia)"))

    por_hora = df.groupby("hora_cheia")[list(ESTACOES.keys())].mean().rename(columns=ESTACOES)
    por_hora.index = [f"{h}h" for h in por_hora.index]
    dir_.line_chart(por_hora)

    pico = df[(df["hora"] >= "12:10") & (df["hora"] <= "13:20")]
    fila_pico = pico["t_churrasqueira"].mean() if len(pico) else float("nan")
    if fila_pico > LIMITE_FILA_CHURRASQUEIRA_MIN * 0.9:
        st.error(f"Gargalo: no pico (12:10-13:20) o cliente leva em média {fila_pico:.1f} min na churrasqueira "
                 f"(meta: {meta_fila:.1f} min). Sugestão: reforçar um churrasqueiro nesse intervalo.")
    elif fila_pico > meta_fila:
        st.warning(f"Atenção: churrasqueira com {fila_pico:.1f} min no pico (meta: {meta_fila:.1f} min).")
    else:
        st.success(f"Churrasqueira dentro da meta no pico ({fila_pico:.1f} min).")

    st.subheader("O que o cliente pega e quanto isso rende")
    esq, dir_ = st.columns(2)
    mix_medio = pd.Series({NOMES_CATEGORIA[c]: df[f"frac_{c}"].mean() * 100 for c in CATEGORIAS})
    esq.caption("Mix médio do prato (%)")
    esq.bar_chart(mix_medio)

    margem_hora = df.groupby("hora_cheia")["margem_pct"].mean() * 100
    margem_hora.index = [f"{h}h" for h in margem_hora.index]
    dir_.caption("Margem média por hora (%)")
    dir_.line_chart(margem_hora)

    caros = df[df["custo_alto"]]
    normais = df[~df["custo_alto"]]
    if len(caros) and len(normais):
        ganho = (caros["receita"] * normais["margem_pct"].mean() - caros["margem_rs"]).sum()
        st.info(f"{len(caros)} pratos ({len(caros) / len(df) * 100:.0f}%) ficaram abaixo de {limite * 100:.0f}% de margem. "
                f"Se tivessem a margem dos demais, o dia renderia cerca de R$ {ganho:,.0f} a mais "
                f"(estimativa ilustrativa, depende das premissas de custo).")

    with st.expander("Ver dados brutos"):
        st.dataframe(df, width="stretch")

# ---------------- Aba 2: galeria de pratos analisados ----------------
with aba_galeria:
    st.write("Pratos de exemplo cuja foto foi analisada por um modelo de visão de IA durante o desenvolvimento. "
             "O painel cruza o mix estimado com o peso e com as premissas de custo da barra lateral.")
    st.caption("Os pesos são estimativas visuais (não foram pesados) e as fotos são de exemplo, não do restaurante.")

    caminho = "data/analises_fotos.json"
    if not os.path.exists(caminho):
        st.info("Nenhuma análise encontrada em data/analises_fotos.json.")
    else:
        with open(caminho, encoding="utf-8") as f:
            pratos = json.load(f)

        for p in pratos:
            p["margem"] = calcular_margem(p["peso_g"], p["mix"], custo_kg=custo_kg, preco_kg=preco_kg)

        media = sum(p["margem"]["margem_pct"] for p in pratos) / len(pratos)
        pior = min(pratos, key=lambda p: p["margem"]["margem_pct"])
        melhor = max(pratos, key=lambda p: p["margem"]["margem_pct"])
        g1, g2, g3 = st.columns(3)
        g1.metric("Margem média da galeria", f"{media * 100:.1f}%")
        g2.metric(f"Menor margem ({pior['titulo'].split(' - ')[0]})", f"{pior['margem']['margem_pct'] * 100:.1f}%")
        g3.metric(f"Maior margem ({melhor['titulo'].split(' - ')[0]})", f"{melhor['margem']['margem_pct'] * 100:.1f}%")

        colunas = st.columns(3)
        for i, p in enumerate(pratos):
            with colunas[i % 3]:
                with st.container(border=True):
                    st.image(os.path.join("data", p["arquivo"]), width="stretch")
                    st.markdown(f"**{p['titulo']}**")
                    st.caption(f"Peso estimado: {p['peso_g']} g")
                    st.bar_chart(pd.Series({NOMES_CATEGORIA[c]: p["mix"][c] * 100 for c in CATEGORIAS}), height=140)
                    m = p["margem"]
                    st.metric("Margem", f"{m['margem_pct'] * 100:.1f}%", f"R$ {m['margem_rs']:.2f} por prato")
                    if m["margem_pct"] < limite:
                        st.error("Custo alto")
                    if p.get("itens"):
                        st.caption("Itens: " + ", ".join(p["itens"]))
                    st.caption(p["observacao"])

# ---------------- Aba 2: câmera na balança (ao vivo) ----------------
if "historico" not in st.session_state:
    st.session_state["historico"] = []

with aba_prato:
    st.write("Simula a câmera instalada sobre a balança: tire a foto do prato (ou envie uma), informe o peso "
             "e a IA identifica o que foi servido. O painel calcula na hora a margem daquele prato.")
    if not chave_ia:
        st.info("Sem chave da IA na barra lateral: a estimativa será SIMULADA (não corresponde à foto).")

    origem = st.radio("Origem da imagem", ["Usar a câmera", "Enviar foto"], horizontal=True)
    if origem == "Usar a câmera":
        arquivo = st.camera_input("Aponte a câmera para o prato (vista de cima)")
    else:
        arquivo = st.file_uploader("Foto do prato", type=["jpg", "jpeg", "png"])
    peso = st.number_input("Peso na balança (g)", min_value=100, max_value=1500, value=550, step=10)

    if st.button("Analisar prato", type="primary", disabled=arquivo is None):
        with st.spinner("Analisando o prato..."):
            resultado = analisar_prato(peso, arquivo.getvalue(), arquivo.type or "image/jpeg",
                                       custo_kg=custo_kg, preco_kg=preco_kg, chave=chave_ia)

        if resultado["nao_e_prato"]:
            st.warning(resultado["erro_ia"])
        else:
            if resultado["erro_ia"]:
                st.error(resultado["erro_ia"])
            col_img, col_res = st.columns(2)
            col_img.image(arquivo, caption=f"Prato na balança - {peso} g", width="stretch")
            with col_res:
                if resultado["ia_real"]:
                    st.success(f"Analisado por {resultado['fonte']}")
                else:
                    st.warning("Resultado SIMULADO")
                st.bar_chart(pd.Series({NOMES_CATEGORIA[c]: resultado["mix"][c] * 100 for c in CATEGORIAS}),
                             height=220, y_label="% do prato")
                if resultado["itens"]:
                    st.caption("Itens identificados: " + ", ".join(resultado["itens"]))
                if resultado["observacao"]:
                    st.caption(resultado["observacao"])

            m = resultado["margem"]
            a, b, c = st.columns(3)
            a.metric("Valor cobrado", f"R$ {m['receita']:.2f}")
            b.metric("Custo estimado do alimento", f"R$ {m['custo']:.2f}")
            c.metric("Margem", f"{m['margem_pct'] * 100:.1f}%", f"R$ {m['margem_rs']:.2f}")
            if m["margem_pct"] < limite:
                st.error("Prato de custo alto: proporção grande de itens caros para o peso cobrado.")
            else:
                st.success("Prato dentro da margem esperada.")

            st.session_state["historico"].append({
                "hora": pd.Timestamp.now().strftime("%H:%M:%S"),
                "peso_g": peso,
                **{NOMES_CATEGORIA[c]: round(resultado["mix"][c] * 100) for c in CATEGORIAS},
                "margem_%": round(m["margem_pct"] * 100, 1),
                "custo_alto": m["margem_pct"] < limite,
                "fonte": "IA" if resultado["ia_real"] else "simulado",
            })

    historico = st.session_state["historico"]
    if historico:
        st.subheader(f"Pratos registrados nesta sessão ({len(historico)})")
        tabela = pd.DataFrame(historico)
        h1, h2, h3 = st.columns(3)
        h1.metric("Margem média", f"{tabela['margem_%'].mean():.1f}%")
        h2.metric("Peso médio", f"{tabela['peso_g'].mean():.0f} g")
        h3.metric("Pratos de custo alto", f"{int(tabela['custo_alto'].sum())}")
        st.dataframe(tabela.iloc[::-1], width="stretch", hide_index=True)
        if st.button("Limpar registros"):
            st.session_state["historico"] = []
            st.rerun()
