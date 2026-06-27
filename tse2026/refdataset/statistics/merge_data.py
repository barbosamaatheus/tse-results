import csv
from pathlib import Path
from statistics import mean, median, stdev
from collections import defaultdict

BASE_DIR = Path(".")
OUTPUT_FILENAME = "merged_multialgo_results.csv"
DISCARDED_FILENAME = "discarded_scenarios.csv"
NUM_EXECUTIONS = 10

# Configuração das colunas de validação por análise
ANALYSIS_CONFIG = {
    "ioa": ["OA Inter"],
    "icf": ["Confluence Inter"],
    "idfp": ["left right DFP-Inter", "right left DFP-Inter"]
}

ALGORITHMS = ["CHA", "RTA", "VTA", "SPARK"]

BLACKLIST = {
    # Exemplo: ("project_name", "class_name", "method_name", "commit_hash")
}

def get_validation_columns(analysis_type):
    return ANALYSIS_CONFIG.get(analysis_type, [])

def read_results():
    """
    Lê os resultados considerando a ordem e duplicatas.
    A chave única agora é: (project, class, method, commit, ID_OCORRENCIA)
    Isso garante que se o mesmo método aparecer 2x, ele será tratado como 2 cenários distintos.
    """
    
    # Estrutura: data[analysis][algo][(proj, class, method, commit, occurrence_id)] = [t1, t2, ..., t10]
    # Usamos defaultdict para facilitar a inserção, mas em Python 3.7+ a ordem de inserção é preservada.
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    discarded = []

    # Varre de results1 a results10
    for i in range(1, NUM_EXECUTIONS + 1):
        run_folder = f"results{i}"
        run_dir = BASE_DIR / run_folder
        if not run_dir.exists():
            print(f"⚠️  Diretório {run_dir} não encontrado. Pulando...")
            continue
        
        print(f"Processando {run_dir}...")

        for analysis in ANALYSIS_CONFIG.keys():
            for algo in ALGORITHMS:
                csv_path = run_dir / analysis / algo / "data1" / "soot-results.csv"
                
                if not csv_path.exists():
                    continue

                valid_cols = get_validation_columns(analysis)
                
                # Rastreador de ocorrências PARA ESTE ARQUIVO ESPECÍFICO
                # Reinicia a cada arquivo lido para garantir o alinhamento correto
                key_occurrence_counter = defaultdict(int)

                with open(csv_path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=';')
                    
                    for row in reader:
                        base_key = (row['project'], row['class'], row['method'], row['merge commit'])
                        
                        # --- LÓGICA DE DUPLICATAS ---
                        # Obtém o índice atual para esta chave (0 para a 1ª vez, 1 para a 2ª, etc.)
                        occ_idx = key_occurrence_counter[base_key]
                        key_occurrence_counter[base_key] += 1
                        
                        # Criamos uma 'unique_key' composta que inclui o ID da ocorrência
                        # Isso diferencia linhas duplicadas no CSV original
                        unique_key = base_key + (occ_idx,)

                        # --- VERIFICAÇÃO 1: BLACKLIST ---
                        if base_key in BLACKLIST:
                            discarded.append({
                                "run": run_folder, "analysis": analysis, "algorithm": algo,
                                "unique_key": unique_key, # Guarda a chave única para rastreio
                                "reason": "BLACKLISTED", "raw_value": "N/A"
                            })
                            continue

                        # --- VERIFICAÇÃO 2: COLUNAS DE VALIDAÇÃO (ex: not-found) ---
                        is_valid = True
                        rejection_reason = ""
                        bad_value = ""

                        for col in valid_cols:
                            val = row.get(col, "").strip().lower()
                            if not val or val == "not-found":
                                is_valid = False
                                rejection_reason = f"INVALID_VALUE_IN_{col}"
                                bad_value = val if val else "(empty)"
                                break
                        
                        if not is_valid:
                            discarded.append({
                                "run": run_folder, "analysis": analysis, "algorithm": algo,
                                "unique_key": unique_key,
                                "project": row['project'], "class": row['class'], 
                                "method": row['method'], "commit": row['merge commit'],
                                "occurrence": occ_idx,
                                "reason": rejection_reason, "raw_value": bad_value
                            })
                            continue

                        # --- VERIFICAÇÃO 3: FORMATO DO TEMPO ---
                        try:
                            time_val = float(row['Time'])
                        except ValueError:
                            discarded.append({
                                "run": run_folder, "analysis": analysis, "algorithm": algo,
                                "unique_key": unique_key,
                                "project": row['project'], "class": row['class'], 
                                "method": row['method'], "commit": row['merge commit'],
                                "occurrence": occ_idx,
                                "reason": "INVALID_TIME_FORMAT", "raw_value": row.get('Time', '')
                            })
                            continue

                        # Se passou por tudo, armazena nos dados válidos usando a chave única
                        data[analysis][algo][unique_key].append(time_val)

    return data, discarded

def write_valid_results(data):
    header = [
        "analysis", "algorithm", 
        "project", "class", "method", "merge_commit", "occurrence_id", # Adicionei ID para debug se necessário
        "mean", "median", "stdev", "executions_count"
    ]
    header.extend([f"exec_{i}" for i in range(1, NUM_EXECUTIONS + 1)])

    count = 0
    with open(OUTPUT_FILENAME, "w", newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, delimiter=';')
        writer.writerow(header)

        # Como os dicionários em Python 3.7+ mantêm a ordem de inserção,
        # e lemos results1 primeiro, a ordem das linhas será preservada.
        for analysis in sorted(data.keys()):
            for algo in sorted(data[analysis].keys()):
                for unique_key, times in data[analysis][algo].items():
                    # unique_key é (proj, class, method, commit, occ_idx)
                    
                    # Trunca para 10 execuções
                    times = times[:NUM_EXECUTIONS]
                    
                    if not times:
                        continue

                    val_mean = mean(times)
                    val_median = median(times)
                    val_stdev = stdev(times) if len(times) > 1 else 0.0
                    
                    # Desempacota a chave para escrita (incluindo o ID da ocorrência)
                    proj, cl, meth, comm, occ_id = unique_key

                    row = [analysis, algo, proj, cl, meth, comm, occ_id,
                           f"{val_mean:.3f}",
                           f"{val_median:.3f}",
                           f"{val_stdev:.3f}",
                           len(times)]
                    
                    row.extend([f"{t:.3f}" for t in times])
                    row.extend([""] * (NUM_EXECUTIONS - len(times)))

                    writer.writerow(row)
                    count += 1
    return count

def write_discarded_results(discarded_list):
    header = [
        "run_folder", "analysis", "algorithm", 
        "project", "class", "method", "merge_commit", "occurrence_id",
        "reason", "raw_value_found"
    ]

    with open(DISCARDED_FILENAME, "w", newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, delimiter=';')
        writer.writerow(header)
        
        for item in discarded_list:
            # Recupera dados. Algumas entradas podem ter estrutura ligeiramente diferente dependendo de onde falharam
            # Mas padronizei no dicionário 'discarded.append'
            
            # Se for Blacklist, pegamos da chave unique_key se disponível
            if "project" not in item and "unique_key" in item:
                 p, c, m, cm, oid = item["unique_key"]
                 item["project"] = p
                 item["class"] = c
                 item["method"] = m
                 item["commit"] = cm
                 item["occurrence"] = oid

            writer.writerow([
                item["run"], item["analysis"], item["algorithm"],
                item.get("project", ""), item.get("class", ""), 
                item.get("method", ""), item.get("commit", ""),
                item.get("occurrence", 0),
                item["reason"], item["raw_value"]
            ])
    
    return len(discarded_list)

def main():
    print("🚀 Iniciando processamento (Preservando Duplicatas via ID)...")
    valid_data, discarded_list = read_results()
    
    valid_count = write_valid_results(valid_data)
    discarded_count = write_discarded_results(discarded_list)

    print("-" * 40)
    print(f"✅ Arquivo MERGED gerado:     {OUTPUT_FILENAME}")
    print(f"   -> Cenários Únicos:        {valid_count}")
    print(f"✅ Arquivo DISCARDED gerado:  {DISCARDED_FILENAME}")
    print(f"   -> Ocorrências descartadas:{discarded_count}")
    print("-" * 40)

if __name__ == "__main__":
    main()