import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

CSV_FILE = "merged_multialgo_results.csv"

def plot_analysis(df, analysis_name):
    """
    Gera um gráfico HORIZONTAL para um tipo específico de análise.
    Eixo Y: Algoritmos
    Eixo X: Tempo Médio
    """
    subset = df[df["analysis"] == analysis_name].copy()
    
    if subset.empty:
        print(f"Sem dados para a análise: {analysis_name}")
        return

    # Ordem de exibição no eixo Y
    order = ["CHA", "RTA", "VTA", "SPARK"]
    
    plt.figure(figsize=(12, 6))
    sns.set(style="whitegrid")

    # Violin Plot (Horizontal: x=mean, y=algorithm)
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

    # Strip Plot (Horizontal)
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

def plot_spark_baseline(df):
    """
    Gera um gráfico SINTÉTICO comparando todas as análises simultaneamente.
    Usa o SPARK como Baseline (Valor 1.0).
    Calcula: Ratio = Tempo_Algo / Tempo_SPARK
    """
    print("Gerando gráfico sintético com SPARK Baseline...")

    # 1. Pivotar a tabela para ter colunas: CHA, RTA, VTA, SPARK na mesma linha (por cenário)
    pivot_cols = ['analysis', 'project', 'class', 'method', 'merge_commit']
    
    # Remove duplicatas se houver e pivota
    df_pivot = df.pivot_table(
        index=pivot_cols, 
        columns='algorithm', 
        values='mean'
    ).reset_index()

    # Verifica se SPARK existe nos dados
    if 'SPARK' not in df_pivot.columns:
        print("⚠️ Dados do SPARK não encontrados para servir de baseline.")
        return

    # 2. Calcular a razão em relação ao SPARK
    # Ratio < 1.0 -> Mais rápido que SPARK
    # Ratio > 1.0 -> Mais lento que SPARK
    algos_to_compare = ['CHA', 'RTA', 'VTA']
    relative_data = []

    for _, row in df_pivot.iterrows():
        spark_time = row['SPARK']
        
        # Ignora casos onde SPARK é 0 ou nulo para evitar divisão por zero
        if pd.isna(spark_time) or spark_time == 0:
            continue

        for algo in algos_to_compare:
            if algo in row and not pd.isna(row[algo]):
                ratio = row[algo] / spark_time
                relative_data.append({
                    "Analysis": row['analysis'].upper(), # IOA, ICF, etc.
                    "Algorithm": algo,
                    "Ratio vs SPARK": ratio
                })

    df_rel = pd.DataFrame(relative_data)

    if df_rel.empty:
        print("⚠️ Não foi possível calcular comparações relativas.")
        return

    # 3. Plotar Boxplot Agrupado
    plt.figure(figsize=(14, 7))
    sns.set(style="whitegrid")

    # Boxplot: X = Ratio, Y = Analysis, Hue = Algorithm
    ax = sns.boxplot(
        data=df_rel,
        y="Analysis",
        x="Ratio vs SPARK",
        hue="Algorithm",
        palette="magma",
        showfliers=False, # Oculta outliers extremos para limpar a visualização
        orient="h",
        width=0.7
    )

    # Linha de referência no 1.0 (Performance do SPARK)
    plt.axvline(x=1.0, color='red', linestyle='--', linewidth=1.5, label='SPARK Baseline (1.0)')

    plt.title("Relative Performance vs SPARK (Baseline = 1.0)", fontsize=16)
    plt.xlabel("Execution Time Ratio (Lower is Faster)", fontsize=12)
    plt.ylabel("Analysis Type", fontsize=12)
    plt.legend(title="Algorithm", loc="upper right")

    sns.despine(left=True)
    plt.tight_layout()

    filename = "plot_synthetic_baseline_spark.png"
    plt.savefig(filename, dpi=300)
    print(f"📈 Gráfico sintético salvo: {filename}")
    plt.close()

def main():
    try:
        df = pd.read_csv(CSV_FILE, delimiter=';')
    except FileNotFoundError:
        print(f"Erro: Arquivo {CSV_FILE} não encontrado. Rode o script de merge antes.")
        return

    # Converter tempo para numérico e limpar
    df["mean"] = pd.to_numeric(df["mean"], errors='coerce')
    df = df.dropna(subset=["mean"])

    # 1. Gráficos Individuais (Horizontais)
    unique_analyses = df["analysis"].unique()
    for analysis in unique_analyses:
        plot_analysis(df, analysis)

    # 2. Gráfico Sintético (SPARK Baseline)
    plot_spark_baseline(df)

if __name__ == "__main__":
    main()