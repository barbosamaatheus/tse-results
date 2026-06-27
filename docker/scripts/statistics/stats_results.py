import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.stats import shapiro, kruskal, mannwhitneyu
import sys
import io

CSV_FILE = "merged_multialgo_results.csv"
PDF_FILE = "statistical_report.pdf"

class DualLogger:
    """Classe auxiliar para imprimir no terminal e guardar num buffer para o PDF."""
    def __init__(self):
        self.buffer = []
        self.terminal = sys.stdout

    def write(self, message):
        self.terminal.write(message)
        self.buffer.append(message)

    def flush(self):
        self.terminal.flush()

    def get_content(self):
        return "".join(self.buffer)

def interpret_p(p_value, alpha=0.05):
    return "Sig. (Diferente)" if p_value < alpha else "Não Sig. (Igual)"

def run_stats():
    # Redirecionar stdout para capturar o output
    logger = DualLogger()
    sys.stdout = logger

    try:
        df = pd.read_csv(CSV_FILE, delimiter=';')
    except FileNotFoundError:
        print(f"Erro: Arquivo {CSV_FILE} não encontrado.")
        return

    # Limpeza e Conversão
    df["mean"] = pd.to_numeric(df["mean"], errors='coerce')
    df = df.dropna(subset=["mean"])

    analyses = df["analysis"].unique()
    algorithms = ["CHA", "RTA", "VTA", "SPARK"]

    print("="*60)
    print(f"RELATÓRIO ESTATÍSTICO AUTOMATIZADO")
    print("="*60)
    print(f"Total de cenários processados: {len(df)}")
    print(f"Algoritmos: {', '.join(algorithms)}")
    print(f"Análises:   {', '.join(analyses)}")
    print("="*60 + "\n")

    # ---------------------------------------------------------
    # PARTE 1: ANÁLISE DENTRO DE CADA GRUPO (IOA, ICF, IDFP)
    # ---------------------------------------------------------
    for analysis in analyses:
        print(f"\n{'#'*20} ANÁLISE: {analysis.upper()} {'#'*20}")
        
        subset = df[df["analysis"] == analysis]
        
        # 1. Estatística Descritiva
        print("\n--- 1. Estatísticas Descritivas (Tempo Médio em Segundos) ---")
        desc = subset.groupby("algorithm")["mean"].describe()
        print(desc[["count", "mean", "std", "min", "max"]].round(4))

        # 2. Teste de Normalidade (Shapiro-Wilk)
        print("\n--- 2. Teste de Normalidade (Shapiro-Wilk) ---")
        print("H0: Os dados seguem uma distribuição normal.")
        groups = {}
        for algo in algorithms:
            data_algo = subset[subset["algorithm"] == algo]["mean"]
            if len(data_algo) >= 3:
                stat, p = shapiro(data_algo)
                normal = "Sim" if p >= 0.05 else "Não"
                print(f"{algo:5}: W={stat:.4f}, p={p:.6f} -> Normal? {normal}")
                groups[algo] = data_algo
            else:
                print(f"{algo:5}: Dados insuficientes para Shapiro.")

        # 3. Comparação Global (Kruskal-Wallis)
        print("\n--- 3. Comparação Global entre Algoritmos (Kruskal-Wallis) ---")
        print("Ideal para comparar > 2 grupos não paramétricos.")
        print("H0: As medianas de todos os grupos são iguais.")
        
        if len(groups) > 1:
            args = [groups[algo] for algo in groups.keys() if algo in groups]
            stat, p = kruskal(*args)
            print(f"H-statistic: {stat:.4f}")
            print(f"p-value:     {p:.6f}")
            
            if p < 0.05:
                print("→ RESULTADO: Há diferença estatística entre os algoritmos.")
                
                # 4. Post-hoc (Mann-Whitney U com Correção de Bonferroni)
                print("\n--- 4. Post-hoc: Comparação Par a Par (Mann-Whitney U) ---")
                print("Comparando SPARK (Com Pointer Analysis) vs Outros.")
                print(f"Correção de Bonferroni aplicada (alpha = 0.05 / n_comparisons)")
                
                # Definir pares de interesse
                # Adicionado CHA vs VTA conforme solicitado
                pairs = [
                    ("CHA", "SPARK"),   # No PA vs PA Completo
                    ("RTA", "SPARK"),   # Intermediate vs PA Completo
                    ("VTA", "SPARK"),   # Intermediate vs PA Completo
                    ("CHA", "RTA"),     # No PA vs Intermediate 1
                    ("CHA", "VTA"),     # No PA vs Intermediate 2 (ADICIONADO)
                    ("RTA", "VTA")      # Intermediate 1 vs Intermediate 2
                ]
                
                # Número de comparações para correção
                n_comparisons = len(pairs)
                alpha_corrected = 0.05 / n_comparisons
                
                print(f"{'Par de Algoritmos':<20} | {'p-value':<10} | {'Resultado (Alpha='f'{alpha_corrected:.4f})'}")
                print("-" * 65)
                
                for algo1, algo2 in pairs:
                    if algo1 in groups and algo2 in groups:
                        u_stat, p_mw = mannwhitneyu(groups[algo1], groups[algo2], alternative='two-sided')
                        res = interpret_p(p_mw, alpha_corrected)
                        print(f"{algo1} vs {algo2:<12} | {p_mw:.6f}   | {res}")
            else:
                print("→ RESULTADO: Não há evidência suficiente para dizer que os algoritmos diferem.")
        else:
            print("Grupos insuficientes para comparação.")

    # ---------------------------------------------------------
    # PARTE 2: COMPARAÇÃO ENTRE AS TÉCNICAS (IOA vs ICF vs IDFP)
    # ---------------------------------------------------------
    print("\n" + "="*60)
    print(f"COMPARAÇÃO CRUZADA ENTRE ANÁLISES (CONSISTÊNCIA)")
    print("="*60)
    
    # 1. Descritiva por Análise
    print("\n--- 1. Média Global por Tipo de Análise ---")
    print(df.groupby("analysis")["mean"].describe()[["count", "mean", "std"]].round(4))

    # 2. Kruskal-Wallis entre Análises
    print("\n--- 2. Teste de Diferença entre Análises (Kruskal-Wallis) ---")
    print("Verificando se IOA, ICF e IDFP têm custos de tempo significativamente diferentes.")
    
    analysis_groups = []
    analysis_names = []
    for an in analyses:
        g = df[df["analysis"] == an]["mean"]
        analysis_groups.append(g)
        analysis_names.append(an)
    
    if len(analysis_groups) > 1:
        stat_an, p_an = kruskal(*analysis_groups)
        print(f"H-statistic: {stat_an:.4f}")
        print(f"p-value:     {p_an:.6f}")
        
        if p_an < 0.05:
            print("→ RESULTADO: As análises têm tempos de execução estatisticamente diferentes.")
            
            # Post-hoc simples entre análises
            print("\n--- 3. Post-hoc Análises (Mann-Whitney U) ---")
            import itertools
            combos = list(itertools.combinations(analysis_names, 2))
            alpha_corr_an = 0.05 / len(combos)
            
            print(f"{'Comparação':<20} | {'p-value':<10} | {'Resultado'}")
            print("-" * 55)
            for a1, a2 in combos:
                g1 = df[df["analysis"] == a1]["mean"]
                g2 = df[df["analysis"] == a2]["mean"]
                u_stat, p_mw = mannwhitneyu(g1, g2, alternative='two-sided')
                res = interpret_p(p_mw, alpha_corr_an)
                print(f"{a1.upper()} vs {a2.upper():<10} | {p_mw:.6f}   | {res}")

        else:
            print("→ RESULTADO: As análises têm tempos de execução estatisticamente similares.")

    # Restaurar stdout
    sys.stdout = logger.terminal
    
    # ---------------------------------------------------------
    # PARTE 3: GERAÇÃO DO PDF
    # ---------------------------------------------------------
    generate_pdf(logger.get_content())

def generate_pdf(text_content):
    print(f"\nGerando PDF: {PDF_FILE} ...")
    
    # Configurações de layout
    lines = text_content.split('\n')
    lines_per_page = 55  # Ajuste conforme tamanho da fonte
    
    with PdfPages(PDF_FILE) as pdf:
        # Divide o texto em blocos (páginas)
        for i in range(0, len(lines), lines_per_page):
            chunk = lines[i:i + lines_per_page]
            page_text = "\n".join(chunk)
            
            plt.figure(figsize=(8.5, 11)) # Tamanho Carta/A4
            plt.axis('off') # Remove eixos
            
            # Plota o texto usando fonte monoespaçada para manter alinhamento de tabelas
            plt.text(0.05, 0.95, page_text, 
                     transform=plt.gca().transAxes, 
                     fontsize=9, 
                     verticalalignment='top', 
                     family='monospace')
            
            pdf.savefig()
            plt.close()
            
    print(f"✅ PDF gerado com sucesso!")

if __name__ == "__main__":
    run_stats()