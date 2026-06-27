import csv
import re
from collections import defaultdict

# =============================================================================
# Parser para formato CF (ICF) - Control Flow
# Formato do out.txt:
#   SOURCE=>BASE: Node(<ClassName: RetType method(params)>,stmt,line,NodeType, path: (...))
#     => Node(<...>,stmt,line,NodeType, path: (...))
#   SINK=>BASE: Node(<...>,stmt,line,NodeType, path: (...))
#     => Node(<...>,stmt,line,NodeType, path: (...))
# =============================================================================

RE_NODE_LINE_TYPE = re.compile(r',(\d+),(SourceNode|SinkNode|SimpleNode),')
RE_CF_PREFIX = re.compile(r'^(SOURCE|SINK)=>BASE:\s*')


def find_nodes(text):
    """
    Encontra todos os Node(...) no texto, tratando parênteses aninhados.
    Retorna uma lista com o conteúdo interno de cada Node.
    """
    nodes = []
    i = 0
    while i < len(text):
        pos = text.find('Node(', i)
        if pos == -1:
            break
        start = pos + 5  # Após 'Node('
        depth = 1
        j = start
        while j < len(text) and depth > 0:
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
            j += 1
        node_content = text[start:j-1]
        nodes.append(node_content)
        i = j
    return nodes


def parse_node(node_content):
    """
    Extrai ClassName, MethodName, LineNumber, Kind e Statement do conteúdo de um Node.
    
    O conteúdo tem o formato:
      <ClassName: RetType methodName(params)>,stmt,lineNumber,NodeType, path: (...)
    
    Retorna (class_name, method_name, line_number, kind, stmt) ou None se falhar.
    """
    if not node_content.startswith('<'):
        return None

    # Encontrar o > que fecha a assinatura do método (rastreando profundidade de <>)
    depth = 0
    sig_end = -1
    for i, c in enumerate(node_content):
        if c == '<':
            depth += 1
        elif c == '>':
            depth -= 1
            if depth == 0:
                sig_end = i
                break

    if sig_end == -1:
        return None

    method_sig = node_content[1:sig_end]  # Sem < e >

    # Extrair ClassName e MethodName da assinatura
    # Formato: "ClassName: ReturnType methodName(params)"
    colon_pos = method_sig.find(':')
    if colon_pos == -1:
        return None

    class_name = method_sig[:colon_pos].strip()
    method_part = method_sig[colon_pos + 1:].strip()

    if '(' in method_part:
        method_name = method_part.split('(')[0].strip().split()[-1]
    else:
        method_name = method_part.strip().split()[-1] if method_part.strip() else ''

    # Encontrar lineNumber e NodeType usando regex
    match = RE_NODE_LINE_TYPE.search(node_content)
    if not match:
        return None

    line_number = match.group(1)
    node_type = match.group(2)

    # Extrair o statement (entre o fim da assinatura e o lineNumber)
    stmt_start = sig_end + 2  # Após '>' e ','
    stmt_end = match.start()
    stmt = node_content[stmt_start:stmt_end].strip() if stmt_end > stmt_start else ""

    kind_map = {'SourceNode': 'source', 'SinkNode': 'sink', 'SimpleNode': 'simple'}
    kind = kind_map.get(node_type, 'unknown')

    return class_name, method_name, line_number, kind, stmt


def make_traversed_line_str(class_name, method_name, line_number):
    """
    Constrói uma string de traversed line no formato compatível com o script 3:
      at ClassName.methodName(SimpleClassName.java:lineNumber)
    """
    simple_class = class_name.rsplit('.', 1)[-1].split('$')[0]
    return f"at {class_name}.{method_name}({simple_class}.java:{line_number})"


def extract_method_name_from_signature(signature):
    """Extrai apenas o nome do método da assinatura completa (mesma lógica do script OA)."""
    before_paren = signature.split('(')[0]
    return before_paren.strip().split()[-1]


def build_csv_index(csv_path):
    """
    Lê o PANotResolve.csv e cria um índice em memória.
    Chave: (ClassName, MethodName, LineNumber) — todos como string.
    Valor: Lista de linhas do CSV.
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
    """
    Processa o out.txt no formato CF, extrai Nodes e busca matches no índice CSV.
    Trata as linhas SOURCE=>BASE: e SINK=>BASE: do formato CF.
    """
    print(f"Processando TXT (formato CF): {txt_path}")

    match_count = 0

    with open(output_csv_path, mode='w', newline='', encoding='utf-8') as f_out:
        writer = csv.writer(f_out, delimiter=';')

        # Cabeçalho idêntico ao script OA
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
                line = line.strip()
                if not line:
                    continue

                if line_idx % 5000 == 0 and line_idx > 0:
                    print(f"Processando linha {line_idx}... (Matches: {match_count})")

                # Extrair o prefixo CF (SOURCE=>BASE: ou SINK=>BASE:)
                prefix_match = RE_CF_PREFIX.match(line)
                if prefix_match:
                    cf_kind = prefix_match.group(1).lower()  # 'source' ou 'sink'
                    line_content = line[prefix_match.end():]
                else:
                    # Linha sem prefixo CF — pular
                    continue

                # Parsear todos os Nodes da linha
                node_contents = find_nodes(line_content)
                if not node_contents:
                    continue

                parsed_nodes = []
                for nc in node_contents:
                    result = parse_node(nc)
                    if result:
                        parsed_nodes.append(result)

                if not parsed_nodes:
                    continue

                # Usar o primeiro node como base para o entry_dict
                # O Kind vem do prefixo CF (SOURCE/SINK)
                first_node = parsed_nodes[0]

                # Construir lista de traversed lines (compatível com script 3)
                traversed_list = []
                for pn in parsed_nodes:
                    cn, mn, ln, kn, st = pn
                    t_str = make_traversed_line_str(cn, mn, ln)
                    traversed_list.append(t_str)

                entry_dict = {
                    "Kind": cf_kind,
                    "ClassName": first_node[0],
                    "MethodName": first_node[1],
                    "SourceCodeLineNumber": int(first_node[2]),
                    "UnitStatement": first_node[4],
                    "TraversedLines": traversed_list
                }

                # Verificar cada Node contra o índice do PANotResolve
                for pn in parsed_nodes:
                    cn, mn, ln, kn, st = pn
                    search_key = (cn, mn, ln)

                    if search_key in csv_index:
                        csv_rows = csv_index[search_key]
                        for csv_row in csv_rows:
                            match_count += 1
                            matched_line = make_traversed_line_str(cn, mn, ln)
                            writer.writerow([
                                entry_dict,
                                cf_kind,
                                matched_line,
                                csv_row["ClassName"],
                                csv_row["MethodName"],
                                csv_row["SourceCodeLineNumber"]
                            ])
                            break  # Mesmo comportamento do script OA: 1 match por traversed line

    print(f"\nConcluído! Total de matches encontrados: {match_count}")
    print(f"Resultados salvos em '{output_csv_path}'")


def main():
    txt_path = "out.txt"
    csv_path = "PANotResolve.csv"
    output_path = "matches_output.csv"

    # 1. Carregar CSV indexado
    csv_index = build_csv_index(csv_path)

    # 2. Processar TXT gerando saída idêntica ao formato OA
    parse_and_match_stream(txt_path, csv_index, output_path)


if __name__ == "__main__":
    main()
