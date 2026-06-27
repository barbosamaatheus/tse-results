import pandas as pd
import re

# === Caminhos dos arquivos CSV ===
csv1_path = 'soot-results-with-lines.csv'   # <-- CSV com as modificações (left/right modifications)
csv2_path = 'PANotResolve.csv' # <-- CSV com a análise de código (source lines)

print("Iniciando leitura dos arquivos CSV...")

# === Leitura dos CSVs com separador ';' ===
df_mods = pd.read_csv(csv1_path, sep=';')
df_source = pd.read_csv(csv2_path, sep=';')

print(f"CSV de modificações carregado: {df_mods.shape[0]} linhas")
print(f"CSV de análise de código carregado: {df_source.shape[0]} linhas")

# === Função para extrair só o nome simples do método (ignorando assinatura e tipo) ===
def extract_method_name(method_full: str) -> str:
    # 1. Pega tudo antes do primeiro '('
    before_paren = method_full.split('(')[0]
    # 2. Pega a última palavra (que é o nome do método)
    return before_paren.strip().split()[-1]

print("Processando os nomes de métodos da análise de código...")

# === Preprocessamento do CSV de análise de código ===
df_source['CleanMethod'] = df_source['MethodName'].apply(extract_method_name)

# Convertendo coluna de linhas de código para número (caso tenha NaN ou erro)
df_source['SourceCodeLineNumber'] = pd.to_numeric(df_source['SourceCodeLineNumber'], errors='coerce')

print("Conversão de nomes de método e linhas de código concluída.")

# === Função para transformar string de linhas modificadas em lista de inteiros ===
def parse_line_list(text):
    if pd.isna(text) or text in ['timeout', 'FALSE', 'TRUE']:
        return []
    text = text.strip('[]')
    if not text:
        return []
    return [int(x.strip()) for x in text.split(',') if x.strip().isdigit()]

# === Função principal de verificação ===
def has_reference(row):
    class_name = row['class']
    method = row['method']
    method_clean = extract_method_name(method)

    left_lines = parse_line_list(row['left modifications'])
    right_lines = parse_line_list(row['right modifications'])
    all_lines = set(left_lines + right_lines)

    print(f"\nVerificando: Projeto={row['project']}, Classe={class_name}, Método={method_clean}")
    print(f"  - Linhas modificadas (left + right): {sorted(all_lines)}")

    # Filtrar por classe e método simples
    filtered = df_source[
        (df_source['ClassName'] == class_name) &
        (df_source['CleanMethod'] == method_clean)
    ]

    source_lines = set(filtered['SourceCodeLineNumber'].dropna().astype(int).tolist())
    print(f"  - Linhas de código encontradas na análise: {sorted(source_lines)}")

    # Verificar interseção
    has_match = len(all_lines.intersection(source_lines)) > 0
    print(f"  - Tem referência? {'SIM' if has_match else 'NÃO'}")

    return has_match

print("\nIniciando verificação linha a linha...")

# === Aplicando a verificação para cada linha do CSV de modificações ===
df_mods['HasMissReference'] = df_mods.apply(has_reference, axis=1)

print("\nVerificação concluída. Exportando resultado...")

# === Exportar o resultado para novo CSV ===
output_path = 'output_with_miss_reference.csv'
df_mods.to_csv(output_path, index=False, sep=';')

print(f"Exportação finalizada! Arquivo salvo em: {output_path}")
