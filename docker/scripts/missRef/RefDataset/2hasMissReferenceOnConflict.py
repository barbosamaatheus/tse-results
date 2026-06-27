import csv
import re

def extract_from_traversed_line(line_str):
    """
    Extrai ClassName, MethodName e SourceCodeLineNumber de uma linha:
    at org.apache.commons.configuration.AbstractConfiguration.interpolate(AbstractConfiguration.java:432)
    """
    match = re.search(r'at ([^(]+)\.([^(]+)\([^\:]+:(\d+)\)', line_str)
    if match:
        class_name = match.group(1).strip()
        method_name = match.group(2).strip()
        line_number = int(match.group(3))
        return class_name, method_name, line_number
    return None, None, None

def parse_source_sink_line(line):
    """Extrai source e sink de uma linha no formato específico."""
    pattern = r"(source|sink)\(([^,]+), ([^,]+), (\d+), (.*?), \[(.*?)\]\)"
    matches = re.findall(pattern, line)
    parsed = []
    for match in matches:
        kind, class_name, method_name, line_number, unit_stmt, traversed = match
        parsed.append({
            "Kind": kind,
            "ClassName": class_name.strip(),
            "MethodName": method_name.strip(),
            "SourceCodeLineNumber": int(line_number),
            "UnitStatement": unit_stmt.strip(),
            "TraversedLines": [t.strip() for t in traversed.split(',') if t.strip()]
        })
    return parsed

def extract_method_name_from_signature(signature: str) -> str:
    """
    Extrai o nome do método da assinatura completa.
    Exemplo: "private static java.lang.String fillBasicEntries()" -> "fillBasicEntries"
    """
    # Pega a última palavra antes do '('
    method_name = signature.strip().split()[-1].split('(')[0]
    return method_name


def load_txt_data(txt_path):
    print(f"Lendo arquivo TXT: {txt_path}")
    with open(txt_path, encoding='utf-8') as f:
        lines = f.readlines()
    print(f"Linhas lidas do TXT: {len(lines)}")
    all_entries = []
    for line in lines:
        entries = parse_source_sink_line(line.strip())
        all_entries.extend(entries)
    print(f"Entradas extraídas (source/sink): {len(all_entries)}")
    return all_entries

def load_csv_data(csv_path):
    print(f"Lendo arquivo CSV: {csv_path}")
    csv.field_size_limit(2**31 - 1)  # Máximo permitido (~2GB)
    with open(csv_path, newline='', encoding='utf-8') as f:
         rows = list(csv.DictReader(f, delimiter=';'))
    print(f"Linhas lidas do CSV: {len(rows)}")
    return rows

def match_entries_by_traversed_lines(source_sink_list, csv_data):
    print("Iniciando verificação de matches com base em TraversedLines...\n")
    matches = []
    # Itera sobre cada entrada extraída do arquivo TXT (source ou sink)
    for entry_index, entry in enumerate(source_sink_list):
        print(f"[{entry_index+1}/{len(source_sink_list)}] {entry['Kind']} verificando {len(entry['TraversedLines'])} traversedLines...")
        for t_line in entry["TraversedLines"]:
            # Extrai da linha a classe, método e número da linha
            t_class, t_method, t_line_number = extract_from_traversed_line(t_line)

            # Se não for possível extrair corretamente, ignora
            if not t_class:
                print(f"  Ignorado: não foi possível extrair de '{t_line}'")
                continue
            # Itera sobre todas as linhas do CSV tentando encontrar um match
            for row in csv_data:
                # Extrai apenas o nome do método da assinatura completa do CSV
                method_name_from_csv = extract_method_name_from_signature(row["MethodName"])
                # Verifica se a classe, método e linha batem com os extraídos da TraversedLine
                if (
                    t_class == row["ClassName"].strip() and
                    t_method == method_name_from_csv and
                    str(t_line_number) == row["SourceCodeLineNumber"].strip()
                ):
                    # Se bater, registra o match
                    print(f"  ✅ Match encontrado com: {t_line}")
                    matches.append({
                        "Kind": entry["Kind"],
                        "Entry": entry,
                        "CSV_Row": row,
                        "MatchedTraversedLine": t_line
                    })
                    break  # para evitar múltiplos matches para mesma traversedLine
    return matches

def main():
    txt_path = "out.txt"
    csv_path = "PANotResolve.csv"

    txt_entries = load_txt_data(txt_path)
    csv_entries = load_csv_data(csv_path)
    matches = match_entries_by_traversed_lines(txt_entries, csv_entries)

    print(f"\nTotal de matches com base em TraversedLines: {len(matches)}\n")
    for match in matches:
        print(f"{match['Kind'].upper()} MATCH:")
        print(f"  TraversedLine: {match['MatchedTraversedLine']}")
        print(f"  CSV => Class: {match['CSV_Row']['ClassName']}, Method: {match['CSV_Row']['MethodName']}, Line: {match['CSV_Row']['SourceCodeLineNumber']}")
        print("-" * 80)

    # Salvar resultados em CSV
    output_csv_path = "matches_output.csv"
    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, delimiter=';')
        # Cabeçalho
        writer.writerow([
            "Conflict",
            "Kind",
            "MatchedTraversedLine",
            "CSV_ClassName",
            "CSV_MethodName",
            "CSV_SourceCodeLineNumber"
        ])
        # Linhas
        for match in matches:
            writer.writerow([
                match["Entry"],
                match["Kind"],
                match["MatchedTraversedLine"],
                match["CSV_Row"]["ClassName"],
                match["CSV_Row"]["MethodName"],
                match["CSV_Row"]["SourceCodeLineNumber"]
            ])

    print(f"Resultados salvos em '{output_csv_path}'")

if __name__ == "__main__":
    main()
