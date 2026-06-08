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


def _iqar_escalar(v, cb, ci):
    for i in range(len(cb)-1):
        if cb[i] <= v <= cb[i+1]:
            return round((ci[i+1]-ci[i])/(cb[i+1]-cb[i])*(v-cb[i])+ci[i])
    return 500 if v > cb[-1] else 0

def calcular_iqar_row(row):
    """
    IQAr usando o melhor poluente disponível na linha.
    Prioridade: PM10 > NO2 > O3 > SO2 > CO
    """
    ci = [0, 40, 80, 120, 200, 500]
    indices = []
    if pd.notna(row.get("pm10")): indices.append(_iqar_escalar(row["pm10"],[0,50,100,250,420,1200],ci))
    if pd.notna(row.get("no2")):  indices.append(_iqar_escalar(row["no2"], [0,200,240,320,1130,2260],ci))
    if pd.notna(row.get("o3")):   indices.append(_iqar_escalar(row["o3"],  [0,100,130,160,200,800],ci))
    if pd.notna(row.get("so2")):  indices.append(_iqar_escalar(row["so2"], [0,50,100,150,800,1600],ci))
    if pd.notna(row.get("co")):   indices.append(_iqar_escalar(row["co"],  [0,9,15,30,40,200],ci))
    return max(indices) if indices else np.nan

def calcular_iqar_pm10(pm10):
    """Mantido para compatibilidade — usa só PM10."""
    if pd.isna(pm10): return np.nan
    return _iqar_escalar(pm10, [0,50,100,250,420,1200], [0,40,80,120,200,500])


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
    arquivos_com_erro = []
    for nome in arquivos:
        caminho = os.path.join(pasta, nome)
        try:
            ext = nome.lower().split(".")[-1]

            # Lê o arquivo — apenas CSV/TXT são suportados diretamente
            # Para XLS, use o script converter_xls_para_csv.py antes do deploy
            if ext in ("xls", "xlsx"):
                st.warning(f"⚠️ {nome}: formato XLS não suportado no servidor. "
                           f"Execute `converter_xls_para_csv.py` e suba os CSVs gerados.")
                continue

            # Tenta detectar separador automaticamente
            for sep, dec in [(",", "."), (";", ","), ("\t", ".")]:
                try:
                    df_test = pd.read_csv(caminho, sep=sep, decimal=dec,
                                          encoding="utf-8", nrows=3)
                    if len(df_test.columns) >= 3:
                        df = pd.read_csv(caminho, sep=sep, decimal=dec,
                                         encoding="utf-8")
                        break
                except Exception:
                    try:
                        df_test = pd.read_csv(caminho, sep=sep, decimal=dec,
                                              encoding="latin-1", nrows=3)
                        if len(df_test.columns) >= 3:
                            df = pd.read_csv(caminho, sep=sep, decimal=dec,
                                             encoding="latin-1")
                            break
                    except Exception:
                        continue
            else:
                st.warning(f"⚠️ {nome}: não foi possível detectar o formato.")
                continue

            # Normaliza colunas
            df.columns = [str(c).strip().lower() for c in df.columns]

            # Mapeia variações de nome para padrão
            renomear = {}
            for col in df.columns:
                c = col.strip().lower()
                if c in ("data","date","datetime","hora","timestamp"):
                    renomear[col] = "data"
                elif "pm10" in c and "24" not in c: renomear[col] = "pm10"
                elif "pm2"  in c:                   renomear[col] = "pm25"
                elif "so2"  in c and "24" not in c: renomear[col] = "so2"
                elif "no2"  in c:                   renomear[col] = "no2"
                elif c.startswith("o3") or "ozonio" in c or "ozônio" in c:
                                                    renomear[col] = "o3"
                elif c == "co" or (c.startswith("co") and "8h" not in c and "24" not in c):
                                                    renomear[col] = "co"
            df = df.rename(columns=renomear)

            if "data" not in df.columns:
                continue

            # Converte e valida datas
            df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
            df = df[df["data"].notna()].copy()

            # Valida mínimo de leituras
            if len(df) < 24:
                arquivos_com_erro.append(f"{nome} (sem leituras válidas)")
                continue

            # Valida que o ano bate com o nome do arquivo
            try:
                ano_nome = int(''.join(filter(str.isdigit, nome))[-4:])
                df = df[df["data"].dt.year == ano_nome]
                if len(df) < 24:
                    arquivos_com_erro.append(f"{nome} (ano {ano_nome} sem dados)")
                    continue
            except Exception:
                pass

            # Converte poluentes para numérico
            for p in ["pm10","pm25","so2","no2","o3","co"]:
                if p in df.columns:
                    df[p] = pd.to_numeric(df[p], errors="coerce")

            dfs.append(df)

        except Exception as e:
            arquivos_com_erro.append(f"{nome} ({e})")
            continue

    if arquivos_com_erro:
        st.warning("⚠️ Arquivos ignorados: " + " · ".join(arquivos_com_erro))

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
    df_dia["iqar"] = df_dia.apply(calcular_iqar_row, axis=1)
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

# ── Glossário ────────────────────────────────────
st.subheader("📖 O que significa cada índice?")
with st.expander("Clique para ver a descrição de cada poluente e das categorias IQAr", expanded=False):
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("""
**🏭 PM10 — Partículas Inaláveis**
Partículas sólidas ou líquidas com diâmetro ≤ 10 µm. Originam-se de poeira de ruas,
obras, queima de biomassa e emissões industriais. Penetram no nariz e garganta.
Limite CONAMA: **50 µg/m³** (média 24h)

---
**🚗 NO₂ — Dióxido de Nitrogênio**
Gás emitido principalmente por veículos e usinas. Causa irritação pulmonar e contribui
para a formação de ozônio e chuva ácida.
Limite CONAMA: **200 µg/m³** (média 1h)

---
**☀️ O₃ — Ozônio**
Formado pela reação de NOx e compostos orgânicos sob luz solar. Poluente típico
de dias quentes e ensolarados. Irrita olhos, nariz e pulmões.
Limite CONAMA: **100 µg/m³** (média 8h)
""")
    with col_g2:
        st.markdown("""
**🔥 SO₂ — Dióxido de Enxofre**
Emitido pela queima de combustíveis com enxofre (petróleo, carvão) e indústrias.
Causa broncoespasmo e chuva ácida.
Limite CONAMA: **50 µg/m³** (média 24h)

---
**🛣 CO — Monóxido de Carbono**
Gás inodoro resultante da combustão incompleta de motores. Reduz a capacidade
do sangue de transportar oxigênio.
Limite CONAMA: **9 ppm** (média 8h)

---
**💨 PM2.5 — Partículas Finas** *(quando disponível)*
Partículas ≤ 2,5 µm — as mais perigosas. Chegam aos alvéolos pulmonares e
podem entrar na corrente sanguínea.
Limite CONAMA: **25 µg/m³** (média 24h)
""")

    st.divider()
    st.markdown("**🌡 Categorias do IQAr — Resolução CONAMA Nº 506/2024**")
    dados_cat = [
        ("🟢", "Boa",                        "0 – 40",    "#00e400", "Qualidade satisfatória. Risco à saúde nulo ou muito baixo."),
        ("🟡", "Moderada",                   "41 – 80",   "#cccc00", "Grupos muito sensíveis podem sentir leve desconforto."),
        ("🟠", "Ruim para Grupos Sensíveis", "81 – 120",  "#ff7e00", "Crianças, idosos e pessoas com doenças respiratórias devem reduzir atividades ao ar livre."),
        ("🔴", "Ruim",                       "121 – 200", "#ff0000", "Toda a população pode sentir efeitos. Grupos sensíveis devem evitar exposição."),
        ("🟣", "Muito Ruim / Péssima",       "> 200",     "#8f3f97", "Alerta de saúde. Toda a população deve evitar atividades ao ar livre."),
    ]
    for emoji, cat, faixa, cor, desc in dados_cat:
        st.markdown(
            f"<div style='border-left:4px solid {cor}; padding:6px 12px; margin:4px 0;'>"
            f"<strong>{emoji} {cat}</strong> &nbsp;·&nbsp; IQAr {faixa}<br>"
            f"<span style='color:#aaa; font-size:0.88rem'>{desc}</span></div>",
            unsafe_allow_html=True
        )

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
