import csv
import re
from collections import defaultdict

# --- Compilação de Regex ---
RE_TRAVERSED = re.compile(r'at ([^(]+)\.([^(]+)\([^\:]+:(\d+)\)')
RE_SOURCE_SINK = re.compile(r"(source|sink)\(([^,]+), ([^,]+), (\d+), (.*?), \[(.*?)\]\)")

def extract_from_traversed_line(line_str):
    """
    Extrai ClassName, MethodName e SourceCodeLineNumber de uma string.
    """
    match = RE_TRAVERSED.search(line_str)
    if match:
        class_name = match.group(1).strip()
        method_name = match.group(2).strip()
        line_number = match.group(3) # String para comparação rápida
        return class_name, method_name, line_number
    return None, None, None

def extract_method_name_from_signature(signature: str) -> str:
    """Extrai apenas o nome do método da assinatura."""
    before_paren = signature.split('(')[0]
    return before_paren.strip().split()[-1]

def build_csv_index(csv_path):
    """
    Lê o CSV e cria um índice em memória.
    Chave: (ClassName, MethodName, LineNumber)
    Valor: Lista de linhas do CSV
    """
    print(f"Indexando CSV: {csv_path}...")
    csv.field_size_limit(2**31 - 1)
    
    csv_index = defaultdict(list)
    count = 0
    
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            clean_method = extract_method_name_from_signature(row["MethodName"])
            c_name = row["ClassName"].strip()
            line_num = row["SourceCodeLineNumber"].strip()
            
            key = (c_name, clean_method, line_num)
            csv_index[key].append(row)
            count += 1
            
    print(f"CSV Indexado! Total de linhas no índice: {count}")
    return csv_index

def parse_and_match_stream(txt_path, csv_index, output_csv_path):
    print(f"Processando TXT e buscando matches: {txt_path}")
    
    match_count = 0
    
    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, delimiter=';')
        
        # Cabeçalho IDÊNTICO ao original
        writer.writerow([
            "Conflict",
            "Kind",
            "MatchedTraversedLine",
            "CSV_ClassName",
            "CSV_MethodName",
            "CSV_SourceCodeLineNumber"
        ])

        with open(txt_path, encoding='utf-8') as f_in:
            for line_idx, line in enumerate(f_in):
                if line_idx % 5000 == 0 and line_idx > 0:
                    print(f"Processando linha {line_idx}... (Matches: {match_count})")

                # Parse da linha (procura source/sink)
                matches_in_line = RE_SOURCE_SINK.findall(line)
                
                for match in matches_in_line:
                    kind, class_name, method_name, line_number, unit_stmt, traversed_raw = match
                    
                    # Converte traversed lines em lista
                    traversed_list = [t.strip() for t in traversed_raw.split(',') if t.strip()]

                    # --- RECONSTRUÇÃO DO DICIONÁRIO ORIGINAL ---
                    # Isso garante que a coluna "Conflict" seja igual ao seu script antigo
                    entry_dict = {
                        "Kind": kind,
                        "ClassName": class_name.strip(),
                        "MethodName": method_name.strip(),
                        "SourceCodeLineNumber": int(line_number),
                        "UnitStatement": unit_stmt.strip(),
                        "TraversedLines": traversed_list
                    }
                    
                    # Verifica os matches
                    for t_line in traversed_list:
                        t_class, t_method, t_line_num = extract_from_traversed_line(t_line)
                        
                        if not t_class:
                            continue
                        
                        # Busca O(1) no índice
                        search_key = (t_class, t_method, t_line_num)
                        
                        if search_key in csv_index:
                            csv_rows = csv_index[search_key]
                            
                            for csv_row in csv_rows:
                                match_count += 1
                                # Escreve mantendo o formato original
                                writer.writerow([
                                    entry_dict,  # O dicionário Python será convertido para string aqui
                                    kind,
                                    t_line,
                                    csv_row["ClassName"],
                                    csv_row["MethodName"],
                                    csv_row["SourceCodeLineNumber"]
                                ])
                                break # O código original tinha um break para evitar duplicatas da mesma traversedLine

    print(f"\nConcluído! Total de matches encontrados: {match_count}")
    print(f"Resultados salvos em '{output_csv_path}'")

def main():
    txt_path = "out.txt"
    csv_path = "PANotResolve.csv"
    output_path = "matches_output.csv" # Nome do arquivo original

    # 1. Carregar CSV indexado
    csv_index = build_csv_index(csv_path)

    # 2. Processar TXT gerando saída idêntica
    parse_and_match_stream(txt_path, csv_index, output_path)

if __name__ == "__main__":
    main()