import pandas as pd
import json
import re
import ast

# Caminhos dos arquivos CSV
conflicts_csv = 'matches_output.csv'  # CSV com os conflitos (o que tem JSON na coluna Conflict)
scenarios_csv = 'soot-results-with-lines.csv'  # CSV com os cenários (o segundo CSV)

print("==> Lendo arquivos CSV...")

# Lendo os CSVs com separador ;
conflicts_df = pd.read_csv(conflicts_csv, sep=';', encoding='utf-8')
scenarios_df = pd.read_csv(scenarios_csv, sep=';', encoding='utf-8')

print(f"==> Total de conflitos carregados: {len(conflicts_df)}")
print(f"==> Total de cenários carregados: {len(scenarios_df)}")

# Função para limpar nome de método (remover parâmetros)
def normalize_method_name(method):
    return re.sub(r'\(.*\)', '', method).strip()

def safe_eval_dict(s):
    try:
        return ast.literal_eval(s)
    except Exception as e:
        print(f"\n[ERRO EVAL] Não foi possível interpretar como dict Python:\n{s}\nErro: {e}\n")
        return None

print("\n==> Pre-processando conflitos para otimização de busca...")
parsed_conflicts = []
for idx, conflict_row in conflicts_df.iterrows():
    c_json = safe_eval_dict(conflict_row['Conflict'])
    if c_json is None:
        continue
    
    # Pre-parse das traces
    parsed_traces = []
    for trace in c_json.get('TraversedLines', []):
        m = re.match(r'at\s+(.*)\.(.*)\((.*):(\d+)\)', trace)
        if m:
            parsed_traces.append({
                'class': m.group(1),
                'method': m.group(2),
                'line': int(m.group(4))
            })

    parsed_conflicts.append({
        'json': c_json,
        'class': c_json.get('ClassName', ''),
        'method_normalized': normalize_method_name(c_json.get('MethodName', '')),
        'line': c_json.get('SourceCodeLineNumber', -1),
        'traces': parsed_traces
    })

# Função principal de verificação de compatibilidade
def has_conflict_match(row, parsed_conflicts):
    class_name = str(row['class'])
    method_name = normalize_method_name(str(row['method']))
    
    try:
        left_lines = eval(row['left modifications']) if pd.notna(row['left modifications']) else []
        right_lines = eval(row['right modifications']) if pd.notna(row['right modifications']) else []
    except Exception as e:
        print(f"Erro ao processar linhas modificadas na row:\n{row}\nErro: {e}")
        left_lines, right_lines = [], []

    modified_lines = set(left_lines + right_lines)
    matched_flows = []
    
    for conflict in parsed_conflicts:
        class_match = conflict['class'] in class_name
        method_match = conflict['method_normalized'] in method_name
        line_match = conflict['line'] in modified_lines

        traversed_line_match = False
        for trace in conflict['traces']:
            if (trace['class'] in class_name or trace['class'].endswith(class_name)) and trace['line'] in modified_lines:
                traversed_line_match = True
                break
        
        if (class_match and method_match and line_match) or traversed_line_match:
            matched_flows.append(conflict['json'])

    if len(matched_flows) > 0:
        unique_flows = set()
        for m in matched_flows:
            flow_id = (m.get('ClassName'), m.get('MethodName'), m.get('SourceCodeLineNumber'), tuple(m.get('TraversedLines', [])))
            unique_flows.add(flow_id)
        
        # print(f"\n--> Encontrados {len(unique_flows)} fluxos unicos impactados para:")
        # print(f"Scenario: Class={class_name}, Method={method_name}, ModifiedLines={modified_lines}")
        return True, len(unique_flows), json.dumps(matched_flows)

    return False, 0, ""

print("\n==> Iniciando verificação de conflitos...")

result_conflict_flag = []
result_conflict_count = []
result_conflict_detail = []

total = len(scenarios_df)
for idx, scenario_row in scenarios_df.iterrows():
    if idx % 100 == 0 or idx == total - 1:
        print(f"Processando cenário {idx+1}/{total}...")

    match, count, detail = has_conflict_match(scenario_row, parsed_conflicts)
    result_conflict_flag.append(match)
    result_conflict_count.append(count)
    result_conflict_detail.append(detail)

print("\n==> Processamento finalizado. Adicionando colunas ao DataFrame...")

# Adiciona colunas ao resultado
scenarios_df['ConflictPathHasMissReference'] = result_conflict_flag
scenarios_df['MissReferenceImpactedFlowsCount'] = result_conflict_count
scenarios_df['ConflictMatchDetail'] = result_conflict_detail

output_file = 'scenario_conflict_match_result_counted.csv'
print(f"==> Salvando resultado em: {output_file}")

# Exporta resultado
scenarios_df.to_csv(output_file, sep=';', index=False, encoding='utf-8')

print("\n==> Script finalizado com sucesso!")
