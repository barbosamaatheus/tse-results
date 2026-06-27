import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np

CSV_FILE = "merged_multialgo_results.csv"

def plot_analysis(df, analysis_name):
    """
    Gera um gráfico HORIZONTAL para um tipo específico de análise.
    Mantido conforme solicitado.
    """
    subset = df[df["analysis"] == analysis_name].copy()
    
    if subset.empty:
        print(f"Sem dados para a análise: {analysis_name}")
        return

    order = ["CHA", "RTA", "VTA", "SPARK"]
    
    plt.figure(figsize=(12, 6))
    sns.set(style="whitegrid")

    # Violin Plot
    ax = sns.violinplot(
        data=subset, 
        y="algorithm", 
        x="mean", 
        order=order,
        inner=None, 
        color=".9", 
        linewidth=1.2,
        orient="h"
    )

    # Strip Plot
    sns.stripplot(
        data=subset, 
        y="algorithm", 
        x="mean", 
        order=order,
        hue="algorithm", 
        palette="viridis", 
        jitter=0.2, 
        size=4, 
        alpha=0.7,
        legend=False,
        orient="h"
    )

    plt.title(f"Performance Distribution: {analysis_name.upper()}", fontsize=14)
    plt.xlabel("Mean Execution Time (s)", fontsize=12)
    plt.ylabel("Call Graph Algorithm", fontsize=12)
    
    sns.despine()
    plt.tight_layout()
    
    filename = f"plot_{analysis_name}_horizontal.png"
    plt.savefig(filename, dpi=300)
    print(f"📊 Gráfico individual salvo: {filename}")
    plt.close()

def plot_spark_baseline_inclusive(df):
    """
    Gera um gráfico SINTÉTICO comparando todas as análises simultaneamente.
    INCLUI O SPARK NA VISUALIZAÇÃO.
    Ratio = Tempo_Algo / Tempo_SPARK
    """
    print("Gerando gráfico sintético relativo (incluindo SPARK)...")

    # 1. Pivotar
    pivot_cols = ['analysis', 'project', 'class', 'method', 'merge_commit']
    df_pivot = df.pivot_table(index=pivot_cols, columns='algorithm', values='mean').reset_index()

    if 'SPARK' not in df_pivot.columns:
        print("⚠️ SPARK não encontrado para baseline.")
        return

    # 2. Calcular Razão (Incluindo o próprio SPARK)
    # Adicionamos 'SPARK' na lista de algoritmos a comparar
    algos_to_compare = ['CHA', 'RTA', 'VTA', 'SPARK'] 
    relative_data = []

    for _, row in df_pivot.iterrows():
        spark_time = row['SPARK']
        
        if pd.isna(spark_time) or spark_time == 0:
            continue

        for algo in algos_to_compare:
            if algo in row and not pd.isna(row[algo]):
                ratio = row[algo] / spark_time
                relative_data.append({
                    "Analysis": row['analysis'].upper(),
                    "Algorithm": algo,
                    "Ratio vs SPARK": ratio
                })

    df_rel = pd.DataFrame(relative_data)

    if df_rel.empty: return

    # 3. Plotar Boxplot Agrupado
    plt.figure(figsize=(14, 8))
    sns.set(style="whitegrid")

    # Ordem customizada para garantir que SPARK fique no final ou no começo
    hue_order = ["CHA", "RTA", "VTA", "SPARK"]

    ax = sns.boxplot(
        data=df_rel,
        y="Analysis",
        x="Ratio vs SPARK",
        hue="Algorithm",
        hue_order=hue_order,
        palette="magma",
        showfliers=False, 
        orient="h",
        width=0.8,
        linewidth=1.2
    )

    # Linha de referência no 1.0
    plt.axvline(x=1.0, color='black', linestyle=':', alpha=0.5, label='Baseline (1.0)')

    plt.title("Relative Performance (Normalized to SPARK)", fontsize=16)
    plt.xlabel("Normalized Time (1.0 = SPARK Time)\nValues < 1.0 are faster", fontsize=12)
    plt.ylabel("Analysis Type", fontsize=12)
    plt.legend(title="Algorithm", loc="upper right")

    sns.despine(left=True)
    plt.tight_layout()

    filename = "plot_synthetic_baseline_inclusive.png"
    plt.savefig(filename, dpi=300)
    print(f"📈 Gráfico relativo (com SPARK) salvo: {filename}")
    plt.close()

def plot_absolute_comparison(df):
    """
    NOVO GRÁFICO: Comparação Absoluta.
    Mostra o tempo real (não relativo) de tudo junto.
    Útil para comparar se IOA é mais rápida que IDFP no geral.
    """
    print("Gerando gráfico de comparação absoluta global...")
    
    plt.figure(figsize=(14, 8))
    sns.set(style="whitegrid")

    # Ordem dos algoritmos
    hue_order = ["CHA", "RTA", "VTA", "SPARK"]

    # Usamos Boxplot para ver a distribuição global dos tempos
    # Log scale é útil se houver outliers muito grandes, mas vamos tentar linear primeiro
    ax = sns.boxplot(
        data=df,
        y="analysis",
        x="mean",
        hue="algorithm",
        hue_order=hue_order,
        palette="Spectral", # Paleta diferente para distinguir
        showfliers=False, # Oculta outliers extremos para focar na mediana
        orient="h",
        width=0.8
    )

    plt.title("Global Absolute Execution Time Comparison", fontsize=16)
    plt.xlabel("Mean Execution Time (seconds)", fontsize=12)
    plt.ylabel("Analysis Type", fontsize=12)
    plt.legend(title="Algorithm", loc="lower right")

    sns.despine(left=True)
    plt.tight_layout()

    filename = "plot_global_absolute_times.png"
    plt.savefig(filename, dpi=300)
    print(f"⏱️  Gráfico absoluto salvo: {filename}")
    plt.close()

def plot_median_heatmap(df):
    """
    NOVO GRÁFICO: Heatmap de Performance Mediana.
    Cria uma matriz: Linhas=Analises, Colunas=Algoritmos.
    Célula = Mediana(Tempo Algo / Tempo SPARK).
    """
    print("Gerando Heatmap de performance...")

    # Pivotar para calcular ratios
    pivot_cols = ['analysis', 'project', 'class', 'method', 'merge_commit']
    df_pivot = df.pivot_table(index=pivot_cols, columns='algorithm', values='mean').reset_index()
    
    if 'SPARK' not in df_pivot.columns: return

    # Calcular ratios normalizados
    records = []
    algos = ["CHA", "RTA", "VTA", "SPARK"]
    
    for _, row in df_pivot.iterrows():
        if pd.isna(row['SPARK']) or row['SPARK'] == 0: continue
        for algo in algos:
            if algo in row and not pd.isna(row[algo]):
                records.append({
                    "Analysis": row['analysis'].upper(),
                    "Algorithm": algo,
                    "Normalized": row[algo] / row['SPARK']
                })
    
    df_ratios = pd.DataFrame(records)
    
    # Agrupar pela mediana (mais robusto que média)
    heatmap_data = df_ratios.groupby(["Analysis", "Algorithm"])["Normalized"].median().unstack()
    
    # Reordenar colunas
    heatmap_data = heatmap_data[algos]

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        heatmap_data, 
        annot=True, 
        fmt=".2f", 
        cmap="RdYlGn_r", # Vermelho (alto/1.0) -> Verde (baixo/rápido)
        linewidths=.5,
        cbar_kws={'label': 'Median Normalized Time (vs SPARK)'}
    )
    
    plt.title("Median Performance Ratio Matrix\n(Values < 1.0 mean faster than SPARK)", fontsize=14)
    plt.tight_layout()
    
    filename = "plot_performance_heatmap.png"
    plt.savefig(filename, dpi=300)
    print(f"🔥 Heatmap salvo: {filename}")
    plt.close()

def main():
    try:
        df = pd.read_csv(CSV_FILE, delimiter=';')
    except FileNotFoundError:
        print(f"Erro: Arquivo {CSV_FILE} não encontrado.")
        return

    # Limpeza básica
    df["mean"] = pd.to_numeric(df["mean"], errors='coerce')
    df = df.dropna(subset=["mean"])

    # 1. Gráficos Individuais
    unique_analyses = df["analysis"].unique()
    for analysis in unique_analyses:
        plot_analysis(df, analysis)

    # 2. Gráfico Sintético Relativo (Com SPARK)
    plot_spark_baseline_inclusive(df)
    
    # 3. Gráfico Comparativo Absoluto (NOVO)
    plot_absolute_comparison(df)

    # 4. Heatmap de Resumo (NOVO)
    plot_median_heatmap(df)

if __name__ == "__main__":
    main()