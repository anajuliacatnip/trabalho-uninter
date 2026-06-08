"""
Script de conversão: roda UMA VEZ no seu computador.
Converte todos os XLS da FEPAM para CSV prontos para o dashboard.

Uso:
  1. Coloque todos os .xls baixados da FEPAM na mesma pasta que este script
  2. Execute: python converter_xls_para_csv.py
  3. Copie os .csv gerados para a pasta dados/ do repositório
"""

import os
import pandas as pd
import glob

PASTA_ENTRADA = "."   # pasta onde estão os XLS
PASTA_SAIDA   = "dados_csv"  # pasta de saída dos CSV

os.makedirs(PASTA_SAIDA, exist_ok=True)

arquivos = sorted(glob.glob(os.path.join(PASTA_ENTRADA, "*.xls")) +
                  glob.glob(os.path.join(PASTA_ENTRADA, "*.xlsx")))

print(f"Encontrados {len(arquivos)} arquivo(s).\n")

for caminho in arquivos:
    nome = os.path.basename(caminho)
    ext  = nome.lower().split(".")[-1]
    try:
        engine = "xlrd" if ext == "xls" else "openpyxl"
        df = pd.read_excel(caminho, engine=engine)

        # Normaliza colunas
        df.columns = [c.strip().lower() for c in df.columns]

        # Mapeia colunas variantes para nomes padrão
        renomear = {}
        for col in df.columns:
            c = col.strip().lower()
            if c in ("data","date","datetime","hora","timestamp"):
                renomear[col] = "data"
            elif "pm10" in c:   renomear[col] = "pm10"
            elif "pm2"  in c:   renomear[col] = "pm25"
            elif "so2"  in c and "24" not in c: renomear[col] = "so2"
            elif "no2"  in c:   renomear[col] = "no2"
            elif c.startswith("o3") or "ozonio" in c: renomear[col] = "o3"
            elif c == "co" or c.startswith("co "):    renomear[col] = "co"
        df = df.rename(columns=renomear)

        # Filtra só colunas relevantes
        cols_manter = [c for c in ["data","pm10","pm25","so2","no2","o3","co"] if c in df.columns]
        if "data" not in cols_manter:
            print(f"  ✗ {nome}: coluna 'data' não encontrada — pulando.")
            continue
        df = df[cols_manter].copy()

        # Converte e filtra datas válidas
        df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
        df = df[df["data"].notna()]

        # Valida que o ano no arquivo bate com o ano no nome
        try:
            ano_nome = int(''.join(filter(str.isdigit, nome))[-4:])
            df = df[df["data"].dt.year == ano_nome]
        except Exception:
            pass

        if len(df) < 24:
            print(f"  ✗ {nome}: menos de 24 leituras válidas ({len(df)}) — arquivo corrompido, pulando.")
            continue

        # Salva como CSV
        nome_csv = os.path.splitext(nome)[0] + ".csv"
        saida = os.path.join(PASTA_SAIDA, nome_csv)
        df.to_csv(saida, index=False, sep=",", decimal=".")
        print(f"  ✓ {nome} → {nome_csv}  ({len(df)} linhas, colunas: {df.columns.tolist()})")

    except Exception as e:
        print(f"  ✗ {nome}: erro — {e}")

print(f"\nConcluído! CSVs salvos em: {os.path.abspath(PASTA_SAIDA)}/")
print("Copie o conteúdo dessa pasta para dados/ no repositório GitHub.")
