"""
Dashboard de Qualidade do Ar – Porto Alegre (2002–2024)
Fonte: FEPAM – Rede Ar do Sul (dados oficiais)
Resolução CONAMA Nº 506/2024
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import os
from datetime import datetime, timezone, timedelta

# ── Configuração ─────────────────────────────────
st.set_page_config(
    page_title="Qualidade do Ar – Porto Alegre",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRT = timezone(timedelta(hours=-3))

POLUENTES = {
    "PM10 (µg/m³)":  "pm10",
    "SO2 (µg/m³)":   "so2",
    "NO2 (µg/m³)":   "no2",
    "O3 (µg/m³)":    "o3",
    "CO (ppm)":       "co",
}

LIMITES_CONAMA = {
    "PM10 (µg/m³)":  50,
    "SO2 (µg/m³)":   50,
    "NO2 (µg/m³)":   200,
    "O3 (µg/m³)":    100,
    "CO (ppm)":       9,
}

CORES = {
    "PM10 (µg/m³)":  "#bc8cff",
    "SO2 (µg/m³)":   "#ff7b72",
    "NO2 (µg/m³)":   "#ffa657",
    "O3 (µg/m³)":    "#56d364",
    "CO (ppm)":       "#e3b341",
}

CAT_CORES = {
    "Boa":                        "#00e400",
    "Moderada":                   "#ffff00",
    "Ruim para Grupos Sensíveis": "#ff7e00",
    "Ruim":                       "#ff0000",
    "Muito Ruim / Péssima":       "#8f3f97",
}

MESES_PT = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
            7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

# ── Utilitários ──────────────────────────────────

def hex_to_rgba(hex_color, alpha=0.15):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"


def calcular_iqar_pm10(pm10):
    """IQAr baseado em PM10 (principal poluente disponível FEPAM 2002-2024)."""
    cb = [0, 50, 100, 250, 420, 1200]
    ci = [0, 40,  80, 120, 200,  500]
    for i in range(len(cb)-1):
        if cb[i] <= pm10 <= cb[i+1]:
            return round((ci[i+1]-ci[i])/(cb[i+1]-cb[i])*(pm10-cb[i])+ci[i])
    return 500 if pm10 > cb[-1] else 0


def categoria_iqar(iq):
    if iq <= 40:  return "Boa"
    if iq <= 80:  return "Moderada"
    if iq <= 120: return "Ruim para Grupos Sensíveis"
    if iq <= 200: return "Ruim"
    return "Muito Ruim / Péssima"


# ── Carregamento de dados ────────────────────────

@st.cache_data(ttl=86400, show_spinner="Carregando dados da FEPAM...")
def carregar_todos_anos():
    """
    Lê todos os arquivos XLS/CSV da pasta dados/.
    Estrutura esperada dos arquivos FEPAM:
      data | pm10 | so2 | no2 | o3 | co   (dados horários)
    Retorna DataFrame diário agregado por média.
    """
    pasta = os.path.join(os.path.dirname(__file__), "dados")
    if not os.path.exists(pasta):
        return None, "pasta_ausente"

    arquivos = sorted([
        f for f in os.listdir(pasta)
        if f.lower().endswith((".csv", ".xls", ".xlsx", ".txt"))
    ])
    if not arquivos:
        return None, "sem_arquivos"

    dfs = []
    for nome in arquivos:
        caminho = os.path.join(pasta, nome)
        try:
            ext = nome.lower().split(".")[-1]
            if ext in ("xls", "xlsx"):
                df = pd.read_excel(caminho, engine="xlrd" if ext == "xls" else "openpyxl")
            else:
                # Tenta vírgula, depois ponto-e-vírgula
                try:
                    df = pd.read_csv(caminho, sep=",", decimal=".", encoding="latin-1")
                except Exception:
                    df = pd.read_csv(caminho, sep=";", decimal=",", encoding="latin-1")

            # Normaliza nomes das colunas
            df.columns = [c.strip().lower() for c in df.columns]

            # Mapeia variações de nome
            renomear = {}
            for col in df.columns:
                if col in ("data", "date", "datetime", "hora", "timestamp"):
                    renomear[col] = "data"
                elif "pm10" in col or "pm 10" in col:
                    renomear[col] = "pm10"
                elif "pm2" in col:
                    renomear[col] = "pm25"
                elif "so2" in col or "so₂" in col:
                    renomear[col] = "so2"
                elif "no2" in col or "no₂" in col:
                    renomear[col] = "no2"
                elif col.startswith("o3") or "ozonio" in col or "ozônio" in col:
                    renomear[col] = "o3"
                elif col == "co" or col.startswith("co "):
                    renomear[col] = "co"
            df = df.rename(columns=renomear)

            if "data" not in df.columns:
                continue

            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["data"])

            for p in ["pm10","so2","no2","o3","co","pm25"]:
                if p in df.columns:
                    df[p] = pd.to_numeric(df[p], errors="coerce")

            dfs.append(df)
        except Exception as e:
            st.warning(f"Erro ao ler {nome}: {e}")
            continue

    if not dfs:
        return None, "erro_leitura"

    df_all = pd.concat(dfs, ignore_index=True)

    # Agrega por dia (média das leituras horárias)
    cols_pols = [c for c in ["pm10","so2","no2","o3","co","pm25"] if c in df_all.columns]
    df_all["dia"] = df_all["data"].dt.date
    df_dia = df_all.groupby("dia")[cols_pols].mean().reset_index()
    df_dia["dia"] = pd.to_datetime(df_dia["dia"])
    df_dia = df_dia.sort_values("dia").reset_index(drop=True)
    df_dia["ano"]  = df_dia["dia"].dt.year
    df_dia["mes"]  = df_dia["dia"].dt.month
    df_dia["iqar"] = df_dia["pm10"].apply(lambda x: calcular_iqar_pm10(x) if pd.notna(x) else np.nan)
    df_dia["categoria"] = df_dia["iqar"].apply(lambda x: categoria_iqar(int(x)) if pd.notna(x) else "")

    return df_dia, "ok"


# ── Carrega ──────────────────────────────────────
df_dia, status = carregar_todos_anos()

# ── Sidebar ──────────────────────────────────────
with st.sidebar:
    st.title("🌿 Qualidade do Ar")
    st.caption("Porto Alegre · 2002–2024")
    st.divider()

    if status == "ok" and df_dia is not None:
        anos_disp = sorted(df_dia["ano"].unique().tolist())
        ano_min, ano_max = int(anos_disp[0]), int(anos_disp[-1])
        intervalo = st.slider("Intervalo de anos", ano_min, ano_max,
                              (ano_min, ano_max), step=1)
        st.divider()

    poluente_label = st.selectbox("Poluente — análise", list(POLUENTES.keys()))
    poluente_col   = POLUENTES[poluente_label]

    st.divider()
    st.caption("**Fontes oficiais**")
    st.markdown("[FEPAM – Dados do Monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento)")
    st.markdown("[Boletim Diário FEPAM](https://ww3.fepam.rs.gov.br/qualidade/boletim_qualidade_ar.asp)")
    st.markdown("[Relatórios FEPAM](https://www.fepam.rs.gov.br/relatorios-de-qualidade-do-ar)")
    st.divider()
    st.caption("Base legal: Resolução CONAMA Nº 506/2024")
    st.caption(f"Atualizado: {datetime.now(BRT).strftime('%d/%m/%Y %H:%M')} (BRT)")

    if st.button("🔄 Recarregar dados"):
        st.cache_data.clear()
        st.rerun()

# ── Sem dados: instruções ─────────────────────────
if status != "ok" or df_dia is None:
    st.markdown("## 🌿 Qualidade do Ar — Porto Alegre (2002–2024)")
    st.error("Nenhum dado encontrado na pasta `dados/`.", icon="❌")
    st.info("""
**Como adicionar os dados:**

1. Baixe os arquivos XLS de cada ano em:
   👉 [fepam.rs.gov.br/dados-do-monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento)

2. Crie uma pasta chamada **`dados`** dentro do repositório

3. Coloque todos os arquivos lá (o nome não importa):
```
seu-repositorio/
├── app.py
├── requirements.txt
└── dados/
    ├── Qualidade_do_Ar_-_Dados_gerais_2002.xls
    ├── Qualidade_do_Ar_-_Dados_gerais_2003.xls
    ├── ...
    └── Qualidade_do_Ar_-_Dados_gerais_2024.xls
```

4. Faça push no GitHub → o dashboard carrega tudo automaticamente ✅
    """)
    st.stop()

# ── Filtra por intervalo de anos ─────────────────
df = df_dia[(df_dia["ano"] >= intervalo[0]) & (df_dia["ano"] <= intervalo[1])].copy()
anos_sel = sorted(df["ano"].unique().tolist())

# ── Cabeçalho ────────────────────────────────────
st.markdown("## 🌿 Qualidade do Ar — Porto Alegre")
st.caption(
    f"Monitoramento Público de Transparência Ambiental · "
    f"Fonte: FEPAM – Rede Ar do Sul · "
    f"{intervalo[0]}–{intervalo[1]} · {len(df):,} dias de medição"
)
st.divider()

# ── KPIs ─────────────────────────────────────────
col_k = st.columns(5)
iqar_medio = df["iqar"].mean()
iqar_max   = df["iqar"].max()
pm10_medio = df["pm10"].mean() if "pm10" in df.columns else np.nan
dias_acima  = int((df["pm10"] > LIMITES_CONAMA["PM10 (µg/m³)"]).sum()) if "pm10" in df.columns else 0
cat_freq    = df["categoria"].value_counts().idxmax() if df["categoria"].notna().any() else "—"

_, iqar_cor = iqar_medio, CAT_CORES.get(categoria_iqar(int(iqar_medio)) if pd.notna(iqar_medio) else "Boa", "#888")

col_k[0].metric("📅 Período", f"{intervalo[0]}–{intervalo[1]}", f"{len(anos_sel)} anos")
col_k[1].metric("🌡 IQAr Médio", f"{iqar_medio:.0f}" if pd.notna(iqar_medio) else "—",
                categoria_iqar(int(iqar_medio)) if pd.notna(iqar_medio) else "")
col_k[2].metric("🏭 PM10 Médio", f"{pm10_medio:.1f} µg/m³" if pd.notna(pm10_medio) else "—",
                f"Limite: {LIMITES_CONAMA['PM10 (µg/m³)']} µg/m³")
col_k[3].metric("⚠️ Dias acima do limite PM10", f"{dias_acima}",
                f"{100*dias_acima/len(df):.1f}% dos dias")
col_k[4].metric("🏆 Categoria mais frequente", cat_freq)

st.divider()

# ── Tendência anual ───────────────────────────────
st.subheader(f"📈 Tendência Anual — {poluente_label}")

if poluente_col in df.columns:
    df_anual = df.groupby("ano")[poluente_col].agg(["mean","max","min"]).reset_index()
    cor_p = CORES[poluente_label]

    fig_tend = go.Figure()
    fig_tend.add_trace(go.Scatter(
        x=df_anual["ano"], y=df_anual["max"],
        mode="lines", name="Máxima anual",
        line=dict(color=cor_p, width=1, dash="dot"), opacity=0.5,
    ))
    fig_tend.add_trace(go.Scatter(
        x=df_anual["ano"], y=df_anual["mean"],
        mode="lines+markers", name="Média anual",
        line=dict(color=cor_p, width=3),
        marker=dict(size=8),
        fill="tonexty", fillcolor=hex_to_rgba(cor_p, 0.08),
    ))
    if poluente_label in LIMITES_CONAMA:
        fig_tend.add_hline(
            y=LIMITES_CONAMA[poluente_label],
            line_dash="dash", line_color="#f78166",
            annotation_text=f"Limite CONAMA: {LIMITES_CONAMA[poluente_label]}",
            annotation_font_color="#f78166",
        )
    fig_tend.update_layout(
        height=340, margin=dict(l=0,r=0,t=10,b=0),
        xaxis=dict(tickmode="linear", dtick=1),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig_tend, use_container_width=True)
else:
    st.info(f"Coluna `{poluente_col}` não encontrada nos dados.")

# ── Heatmap anual × mês ───────────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader(f"🗓 Sazonalidade — {poluente_label} (médias mensais por ano)")
    if poluente_col in df.columns:
        pivot = df.groupby(["ano","mes"])[poluente_col].mean().unstack(level=1)
        pivot.columns = [MESES_PT.get(c, c) for c in pivot.columns]
        fig_heat = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[[0,"#00e400"],[0.4,"#ffff00"],[0.7,"#ff7e00"],[0.85,"#ff0000"],[1,"#8f3f97"]],
            colorbar=dict(title=poluente_label.split("(")[1].replace(")","").strip()),
            hovertemplate="Ano: %{y}<br>Mês: %{x}<br>Valor: %{z:.1f}<extra></extra>",
        ))
        fig_heat.update_layout(
            height=380, margin=dict(l=0,r=0,t=10,b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(dtick=1),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

with col_b:
    st.subheader("📊 Distribuição de Categorias IQAr por Ano")
    df_cat = df.groupby(["ano","categoria"]).size().reset_index(name="dias")
    total_ano = df_cat.groupby("ano")["dias"].transform("sum")
    df_cat["pct"] = 100 * df_cat["dias"] / total_ano

    fig_cat = go.Figure()
    for cat, cor in CAT_CORES.items():
        sub = df_cat[df_cat["categoria"] == cat]
        if not sub.empty:
            fig_cat.add_trace(go.Bar(
                name=cat, x=sub["ano"], y=sub["pct"],
                marker_color=cor, opacity=0.85,
                hovertemplate=f"{cat}: %{{y:.1f}}%<extra></extra>",
            ))
    fig_cat.update_layout(
        barmode="stack", height=380,
        margin=dict(l=0,r=0,t=10,b=0),
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis=dict(title="% dos dias"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                    yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_cat, use_container_width=True)

# ── Comparativo de poluentes por ano ─────────────
st.subheader("📉 Média Anual de Todos os Poluentes")
cols_disp = {k: v for k, v in POLUENTES.items() if v in df.columns}
df_anual_todos = df.groupby("ano")[[v for v in cols_disp.values()]].mean().reset_index()

fig_multi = go.Figure()
for label, col in cols_disp.items():
    fig_multi.add_trace(go.Scatter(
        x=df_anual_todos["ano"], y=df_anual_todos[col],
        mode="lines+markers", name=label,
        line=dict(color=CORES[label], width=2),
        marker=dict(size=6),
    ))
fig_multi.update_layout(
    height=320, margin=dict(l=0,r=0,t=10,b=0),
    xaxis=dict(tickmode="linear", dtick=1),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                yanchor="bottom", y=1.02),
)
st.plotly_chart(fig_multi, use_container_width=True)

# ── Tabela resumo anual ───────────────────────────
st.subheader("📋 Resumo Anual")
resumo = df.groupby("ano").agg(
    Dias=("pm10","count"),
    **{f"PM10 médio (µg/m³)": ("pm10","mean")},
    **{f"PM10 máx (µg/m³)":   ("pm10","max")},
    **{f"NO2 médio (µg/m³)":  ("no2","mean")} if "no2" in df.columns else {},
    **{f"SO2 médio (µg/m³)":  ("so2","mean")} if "so2" in df.columns else {},
    **{f"O3 médio (µg/m³)":   ("o3","mean")}  if "o3"  in df.columns else {},
    **{f"CO médio (ppm)":     ("co","mean")}  if "co"  in df.columns else {},
    IQAr_medio=("iqar","mean"),
).reset_index()
resumo = resumo.rename(columns={"ano":"Ano","IQAr_medio":"IQAr médio"})
resumo["Categoria"] = resumo["IQAr médio"].apply(
    lambda x: categoria_iqar(int(x)) if pd.notna(x) else "")

for col in resumo.columns:
    if resumo[col].dtype == float:
        resumo[col] = resumo[col].round(1)

st.dataframe(resumo, use_container_width=True, hide_index=True, height=400)

# ── Rodapé ───────────────────────────────────────
st.divider()
st.caption(
    "📚 **Fonte:** FEPAM – Rede Ar do Sul · "
    "[fepam.rs.gov.br/dados-do-monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento) · "
    "[Boletim Diário](https://ww3.fepam.rs.gov.br/qualidade/boletim_qualidade_ar.asp) · "
    "[Relatórios anuais](https://www.fepam.rs.gov.br/relatorios-de-qualidade-do-ar) · "
    "Base legal: **Resolução CONAMA Nº 506/2024**"
)
