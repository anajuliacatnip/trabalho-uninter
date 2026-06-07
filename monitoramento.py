"""
Dashboard de Qualidade do Ar – Porto Alegre
Fonte: FEPAM – Rede Ar do Sul (dados oficiais)
Resolução CONAMA Nº 506/2024
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# ── Configuração da página ──────────────────────
st.set_page_config(
    page_title="Qualidade do Ar – Porto Alegre",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constantes ──────────────────────────────────
POLUENTES = ["PM2.5 (µg/m³)", "PM10 (µg/m³)", "NO2 (µg/m³)", "SO2 (µg/m³)", "O3 (µg/m³)", "CO (ppm)"]

LIMITES_CONAMA = {
    "PM2.5 (µg/m³)": 25,
    "PM10 (µg/m³)":  50,
    "NO2 (µg/m³)":   200,
    "SO2 (µg/m³)":   50,
    "O3 (µg/m³)":    100,
    "CO (ppm)":       9,
}

CORES = {
    "PM2.5 (µg/m³)": "#58a6ff",
    "PM10 (µg/m³)":  "#bc8cff",
    "NO2 (µg/m³)":   "#ffa657",
    "SO2 (µg/m³)":   "#ff7b72",
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

BRT = timezone(timedelta(hours=-3))

# ── Funções utilitárias ──────────────────────────

def hex_to_rgba(hex_color, alpha=0.13):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"


def calcular_iqar(pm25, pm10, no2, so2, o3):
    def idx(v, cb, ci):
        for i in range(len(cb)-1):
            if cb[i] <= v <= cb[i+1]:
                return round((ci[i+1]-ci[i])/(cb[i+1]-cb[i])*(v-cb[i])+ci[i])
        return 500 if v > cb[-1] else 0
    ci = [0, 40, 80, 120, 200, 500]
    iq = max([
        idx(pm25, [0,25,60,125,210,600],    ci),
        idx(pm10, [0,50,100,250,420,1200],  ci),
        idx(no2,  [0,200,240,320,1130,2260],ci),
        idx(so2,  [0,50,100,150,800,1600],  ci),
        idx(o3,   [0,100,130,160,200,800],  ci),
    ])
    if iq <= 40:  return iq, "Boa",                        "#00e400"
    if iq <= 80:  return iq, "Moderada",                   "#ffff00"
    if iq <= 120: return iq, "Ruim para Grupos Sensíveis", "#ff7e00"
    if iq <= 200: return iq, "Ruim",                       "#ff0000"
    return iq,            "Muito Ruim / Péssima",          "#8f3f97"


def cat_label(iq):
    if iq <= 40:  return "Boa"
    if iq <= 80:  return "Moderada"
    if iq <= 120: return "Ruim para Grupos Sensíveis"
    if iq <= 200: return "Ruim"
    return "Muito Ruim / Péssima"


# ── Carregamento de dados ────────────────────────

@st.cache_data(ttl=3600)
def carregar_dados_fepam(arquivo_csv=None):
    """
    Prioridade:
      1. CSV real da FEPAM carregado pelo usuário (upload)
      2. Dados históricos simulados com padrões reais da Rede Ar do Sul

    Estrutura esperada do CSV da FEPAM:
      Data | PM2.5 | PM10 | NO2 | SO2 | O3 | CO
    """
    if arquivo_csv is not None:
        try:
            df = pd.read_csv(arquivo_csv, sep=";", decimal=",", encoding="latin-1")
            # Tenta mapear colunas comuns do formato FEPAM
            mapa = {}
            for col in df.columns:
                c = col.strip().upper()
                if "DATA" in c or "DATE" in c:         mapa[col] = "data"
                elif "PM2" in c or "PM 2" in c:        mapa[col] = "PM2.5 (µg/m³)"
                elif "PM10" in c or "PM 10" in c:      mapa[col] = "PM10 (µg/m³)"
                elif "NO2" in c or "NO₂" in c:         mapa[col] = "NO2 (µg/m³)"
                elif "SO2" in c or "SO₂" in c:         mapa[col] = "SO2 (µg/m³)"
                elif "O3" in c or "OZO" in c:          mapa[col] = "O3 (µg/m³)"
                elif "CO" in c:                        mapa[col] = "CO (ppm)"
            df = df.rename(columns=mapa)
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["data"]).sort_values("data").reset_index(drop=True)
            for p in POLUENTES:
                if p not in df.columns:
                    df[p] = np.nan
                else:
                    df[p] = pd.to_numeric(df[p], errors="coerce")
            return df, True   # True = dados reais
        except Exception as e:
            st.warning(f"Não foi possível ler o CSV: {e}. Usando dados simulados.")

    # ── Dados simulados baseados nos padrões FEPAM/Rede Ar do Sul ──
    np.random.seed(42)
    n = 90
    hoje = datetime.now(BRT).replace(tzinfo=None)
    datas = [hoje - timedelta(days=i) for i in range(n, 0, -1)]

    pm25 = 15 + 8*np.sin(np.linspace(0, 2*np.pi, n)) + np.random.normal(0, 4, n)
    pm10 = pm25 * 1.8 + np.random.normal(0, 5, n)
    no2  = 30 + 15*np.sin(np.linspace(np.pi/4, 2.25*np.pi, n)) + np.random.normal(0, 8, n)
    so2  = 8  + 4*np.random.random(n) + np.random.normal(0, 2, n)
    o3   = 50 + 20*np.sin(np.linspace(np.pi, 3*np.pi, n)) + np.random.normal(0, 10, n)
    co   = 0.5 + 0.3*np.random.random(n) + np.random.normal(0, 0.1, n)

    for i in [15, 32, 58, 71]:
        pm25[i] += np.random.uniform(25, 60)
        pm10[i] += np.random.uniform(40, 80)

    df = pd.DataFrame({
        "data":           datas,
        "PM2.5 (µg/m³)": np.clip(pm25, 2, 200).round(1),
        "PM10 (µg/m³)":  np.clip(pm10, 5, 300).round(1),
        "NO2 (µg/m³)":   np.clip(no2,  1, 200).round(1),
        "SO2 (µg/m³)":   np.clip(so2,  0, 100).round(1),
        "O3 (µg/m³)":    np.clip(o3,   5, 180).round(1),
        "CO (ppm)":       np.clip(co,   0.1, 5).round(2),
    })
    return df, False   # False = dados simulados


# ── Sidebar ─────────────────────────────────────
with st.sidebar:
    st.title("🌿 Qualidade do Ar")
    st.caption("Porto Alegre — Monitoramento Público")
    st.divider()

    st.markdown("#### 📂 Carregar dados reais da FEPAM")
    st.caption(
        "Baixe o CSV em: [fepam.rs.gov.br/dados-do-monitoramento]"
        "(https://www.fepam.rs.gov.br/dados-do-monitoramento) "
        "e faça o upload abaixo."
    )
    arquivo = st.file_uploader("Upload do CSV da FEPAM", type=["csv", "txt"],
                               help="Arquivo exportado da Rede Ar do Sul")
    st.divider()

    dias = st.slider("Período (dias)", 7, 90, 30, step=7)
    poluente = st.selectbox("Poluente — série histórica", POLUENTES)

    st.divider()
    st.caption("**Fontes oficiais**")
    st.markdown("[FEPAM – Dados do Monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento)")
    st.markdown("[Boletim Diário FEPAM](https://ww3.fepam.rs.gov.br/qualidade/boletim_qualidade_ar.asp)")
    st.markdown("[Relatórios FEPAM](https://www.fepam.rs.gov.br/relatorios-de-qualidade-do-ar)")
    st.markdown("[SEMA/RS](https://sema.rs.gov.br)")
    st.divider()
    st.caption("Base legal: Resolução CONAMA Nº 506/2024")
    st.caption(f"Atualizado: {datetime.now(BRT).strftime('%d/%m/%Y %H:%M')} (BRT)")

    if st.button("🔄 Atualizar"):
        st.cache_data.clear()
        st.rerun()

# ── Carregar dados ───────────────────────────────
df_full, dados_reais = carregar_dados_fepam(arquivo)
df = df_full.tail(dias).copy()

ul = df.iloc[-1]
pm25_v = float(ul["PM2.5 (µg/m³)"])
pm10_v = float(ul["PM10 (µg/m³)"])
no2_v  = float(ul["NO2 (µg/m³)"])
so2_v  = float(ul["SO2 (µg/m³)"])
o3_v   = float(ul["O3 (µg/m³)"])
co_v   = float(ul["CO (ppm)"])

iqar_val, iqar_cat, iqar_cor = calcular_iqar(pm25_v, pm10_v, no2_v, so2_v, o3_v)
fonte_label = (
    "✅ Dados reais da FEPAM – Rede Ar do Sul"
    if dados_reais else
    "⚠️ Dados simulados com padrões FEPAM (faça upload do CSV para dados reais)"
)

# ── Cabeçalho ───────────────────────────────────
st.markdown("## 🌿 Qualidade do Ar — Porto Alegre")
st.caption(f"Monitoramento Público de Transparência Ambiental · {fonte_label}")
st.divider()

# ── Banner de aviso se simulado ─────────────────
if not dados_reais:
    st.info(
        "📥 **Para exibir dados reais:** baixe o CSV da FEPAM em "
        "[fepam.rs.gov.br/dados-do-monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento) "
        "e faça o upload pelo menu lateral.",
        icon="ℹ️"
    )

# ── KPIs ────────────────────────────────────────
cols = st.columns(7)
kpis = [
    ("🌡 IQAr",  iqar_val,       "",       iqar_cor,                "Índice geral de qualidade do ar"),
    ("💨 PM2.5", f"{pm25_v:.1f}", "µg/m³", CORES["PM2.5 (µg/m³)"], "Partículas finas — atingem o pulmão"),
    ("🏭 PM10",  f"{pm10_v:.1f}", "µg/m³", CORES["PM10 (µg/m³)"],  "Partículas inaláveis — irritam vias aéreas"),
    ("🚗 NO₂",   f"{no2_v:.1f}",  "µg/m³", CORES["NO2 (µg/m³)"],   "Dióxido de nitrogênio — veículos"),
    ("🔥 SO₂",   f"{so2_v:.1f}",  "µg/m³", CORES["SO2 (µg/m³)"],   "Dióxido de enxofre — indústria"),
    ("☀️ O₃",    f"{o3_v:.1f}",   "µg/m³", CORES["O3 (µg/m³)"],    "Ozônio — reação solar + poluentes"),
    ("🛣 CO",    f"{co_v:.2f}",   "ppm",   CORES["CO (ppm)"],       "Monóxido de carbono — combustão"),
]
for col, (label, val, unit, cor, desc) in zip(cols, kpis):
    col.metric(label=label, value=f"{val} {unit}".strip())
    col.caption(desc)

st.markdown(
    f"<div style='text-align:center; font-size:1.1rem; font-weight:700; "
    f"color:{iqar_cor}; margin: 6px 0 16px'>IQAr: {iqar_cat} — conforme CONAMA 506/2024</div>",
    unsafe_allow_html=True,
)

# ── Série histórica + Gauge ──────────────────────
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"📈 Série Histórica — {poluente}")
    cor_p = CORES[poluente]
    fig_serie = go.Figure()
    fig_serie.add_trace(go.Scatter(
        x=df["data"], y=df[poluente],
        mode="lines", name=poluente,
        line=dict(color=cor_p, width=2.5),
        fill="tozeroy", fillcolor=hex_to_rgba(cor_p),
    ))
    if poluente in LIMITES_CONAMA:
        fig_serie.add_hline(
            y=LIMITES_CONAMA[poluente],
            line_dash="dash", line_color="#f78166",
            annotation_text=f"Limite CONAMA: {LIMITES_CONAMA[poluente]}",
            annotation_font_color="#f78166",
        )
    fig_serie.update_layout(
        height=320, margin=dict(l=0,r=0,t=10,b=0),
        xaxis_tickformat="%d/%m", showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_serie, use_container_width=True)

with col2:
    st.subheader("🎯 IQAr Atual")
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=iqar_val,
        gauge={
            "axis": {"range": [0, 500]},
            "bar": {"color": iqar_cor, "thickness": 0.25},
            "steps": [
                {"range": [0,40],   "color": "rgba(0,228,0,0.1)"},
                {"range": [40,80],  "color": "rgba(255,255,0,0.1)"},
                {"range": [80,120], "color": "rgba(255,126,0,0.1)"},
                {"range": [120,200],"color": "rgba(255,0,0,0.1)"},
                {"range": [200,500],"color": "rgba(143,63,151,0.1)"},
            ],
        },
        number={"font": {"color": iqar_cor, "size": 44}},
    ))
    fig_gauge.update_layout(
        height=280, margin=dict(l=10,r=10,t=10,b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown(
        f"<p style='text-align:center; color:{iqar_cor}; font-weight:700'>{iqar_cat}</p>",
        unsafe_allow_html=True,
    )

# ── Barras comparativas + Heatmap ────────────────
col3, col4 = st.columns(2)

with col3:
    st.subheader("📊 Média do Período vs. Limite CONAMA")
    pols = ["PM2.5 (µg/m³)", "PM10 (µg/m³)", "NO2 (µg/m³)", "SO2 (µg/m³)", "O3 (µg/m³)"]
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        name="Média medida",
        x=[p.split(" ")[0] for p in pols],
        y=[df[p].mean() for p in pols],
        marker_color=[CORES[p] for p in pols],
        opacity=0.85,
    ))
    fig_bar.add_trace(go.Scatter(
        name="Limite CONAMA",
        x=[p.split(" ")[0] for p in pols],
        y=[LIMITES_CONAMA[p] for p in pols],
        mode="markers",
        marker=dict(symbol="line-ew", size=22, color="#f78166",
                    line=dict(color="#f78166", width=3)),
    ))
    fig_bar.update_layout(
        height=320, margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col4:
    st.subheader("🗓 Heatmap — PM2.5 (últimos 30 dias)")
    df30 = df_full.tail(30).copy()
    df30["semana"]     = df30["data"].dt.isocalendar().week.astype(str)
    df30["dia_semana"] = df30["data"].dt.day_name()
    ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    nomes = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"]
    pivot = df30.pivot_table(index="semana", columns="dia_semana",
                             values="PM2.5 (µg/m³)", aggfunc="mean").reindex(columns=ordem)
    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values, x=nomes,
        colorscale=[[0,"#00e400"],[0.3,"#ffff00"],[0.6,"#ff7e00"],[0.8,"#ff0000"],[1,"#8f3f97"]],
        zmin=0, zmax=60,
        colorbar=dict(title="µg/m³"),
        hovertemplate="PM2.5: %{z:.1f} µg/m³<extra></extra>",
    ))
    fig_heat.update_layout(
        height=320, margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_heat, use_container_width=True)

# ── Pizza + Tabela ───────────────────────────────
col5, col6 = st.columns([1, 2])

with col5:
    st.subheader("🥧 Distribuição IQAr")
    def cat_dia(row):
        iq,_,_ = calcular_iqar(row["PM2.5 (µg/m³)"],row["PM10 (µg/m³)"],
                                row["NO2 (µg/m³)"],  row["SO2 (µg/m³)"], row["O3 (µg/m³)"])
        return cat_label(iq)

    df["categoria"] = df.apply(cat_dia, axis=1)
    contagem = df["categoria"].value_counts()
    fig_pizza = go.Figure(go.Pie(
        labels=contagem.index.tolist(),
        values=contagem.values.tolist(),
        marker_colors=[CAT_CORES.get(c,"#888") for c in contagem.index],
        hole=0.42,
    ))
    fig_pizza.update_layout(
        height=300, margin=dict(l=0,r=0,t=10,b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(bgcolor="rgba(0,0,0,0)", font_size=11),
    )
    st.plotly_chart(fig_pizza, use_container_width=True)

with col6:
    st.subheader("📋 Últimas Medições")
    df_tab = df.tail(10)[["data","PM2.5 (µg/m³)","PM10 (µg/m³)","NO2 (µg/m³)",
                           "SO2 (µg/m³)","O3 (µg/m³)","CO (ppm)","categoria"]].copy()
    df_tab["data"] = df_tab["data"].dt.strftime("%d/%m/%Y")
    df_tab = df_tab.rename(columns={"data": "Data"})
    st.dataframe(
        df_tab,
        use_container_width=True,
        hide_index=True,
        height=300,
        column_config={
            "categoria": st.column_config.TextColumn("Categoria IQAr"),
            "PM2.5 (µg/m³)": st.column_config.NumberColumn(format="%.1f µg/m³"),
            "PM10 (µg/m³)":  st.column_config.NumberColumn(format="%.1f µg/m³"),
            "NO2 (µg/m³)":   st.column_config.NumberColumn(format="%.1f µg/m³"),
            "SO2 (µg/m³)":   st.column_config.NumberColumn(format="%.1f µg/m³"),
            "O3 (µg/m³)":    st.column_config.NumberColumn(format="%.1f µg/m³"),
            "CO (ppm)":       st.column_config.NumberColumn(format="%.2f ppm"),
        }
    )

# ── Rodapé ───────────────────────────────────────
st.divider()
st.caption(
    "📚 **Fontes:** "
    "[FEPAM – Dados do Monitoramento](https://www.fepam.rs.gov.br/dados-do-monitoramento) · "
    "[Boletim Diário FEPAM](https://ww3.fepam.rs.gov.br/qualidade/boletim_qualidade_ar.asp) · "
    "[Relatórios Anuais FEPAM](https://www.fepam.rs.gov.br/relatorios-de-qualidade-do-ar) · "
    "[SEMA/RS](https://sema.rs.gov.br) · "
    "Base legal: Resolução CONAMA Nº 506/2024"
)
