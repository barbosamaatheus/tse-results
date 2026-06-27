import pandas as pd
import numpy as np
import os
import logging
from fpdf import FPDF
from datetime import datetime
import warnings
import matplotlib.pyplot as plt
from scipy.stats import chi2  # Importacao para o P-Value do McNemar

warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# CONFIGURAÇÕES
# ==========================================
# Cenario 1: Qualquer timeout = TRUE
# Cenario 2: Qualquer timeout = FALSE
# Cenario 3: Qualquer timeout = REMOVE
# Cenario 4: Qualquer timeout = REMOVE e ignora RTA
# Cenario 5: true-timeout = TRUE, false-timeout = FALSE
# Cenario 6: true-timeout = TRUE, false-timeout = REMOVE
# Cenario 7: true-timeout = TRUE, false-timeout = REMOVE e ignora RTA
CENARIO = 1

if CENARIO in [4, 7]:
    FERRAMENTAS = ['CHA', 'VTA', 'SPARK']
else:
    FERRAMENTAS = ['CHA', 'RTA', 'VTA', 'SPARK']
# Incluimos 'or all' nas analises para processamento unificado
ANALISES = ['icf', 'ioa', 'idfp'] 
SUBPASTA_DADOS = 'data1'
NOME_ARQUIVO_RESULTADO = 'soot-results.csv'

# Saída
NOME_RELATORIO = 'relatorio_final_index_linha.pdf'
NOME_CSV_CONSOLIDADO = 'tabela_bruta_concatenada.csv'
NOME_CSV_AUDITORIA = 'detalhes_comparacao_spark.csv'
PASTA_TEMP_IMG = 'temp_images'

DELIMITADOR_RES = ';' 

# --- CHAVE DE MERGE INCLUI 'index' ---
# Como o index será o número da linha, cada ocorrência será tratada como única.
CHAVE_MERGE = ['project', 'class', 'method', 'merge commit', 'index']

# Colunas de Valor
COL_ICF_RAW = 'Confluence Inter'
COL_IOA_RAW = 'OA Inter'
COL_LR_RAW = 'left right DFP-Inter'
COL_RL_RAW = 'right left DFP-Inter'

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

if not os.path.exists(PASTA_TEMP_IMG):
    os.makedirs(PASTA_TEMP_IMG)

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def normalizar_valor(valor, cenario):
    if pd.isna(valor): return 'not-found'
    s = str(valor).strip().lower()
    if not s or s == 'nan' or s == 'not-found': return 'not-found'
    if s in ['true', 'yes', 't', '1', 'verdadeiro', 'sim']: return 'TRUE'
    if s in ['false', 'no', 'f', '0', 'falso', 'nao', 'não']: return 'FALSE'
    if s in ['error', 'err', 'exception']: return 'error'
    if s == 'remove': return 'REMOVE'
    
    is_timeout = s in ['timeout', 'to', 'time out', 'timed out']
    is_true_timeout = s == 'true-timeout'
    is_false_timeout = s == 'false-timeout'
    
    if is_timeout or is_true_timeout or is_false_timeout:
        if cenario == 0:
            if is_true_timeout: return 'true-timeout'
            if is_false_timeout: return 'false-timeout'
            return 'timeout'
        elif cenario == 1:
            return 'TRUE'
        elif cenario == 2:
            return 'FALSE'
        elif cenario in [3, 4]:
            return 'REMOVE'
        elif cenario == 5:
            if is_true_timeout: return 'TRUE'
            if is_false_timeout: return 'FALSE'
            return 'timeout'
        elif cenario in [6, 7]:
            if is_true_timeout: return 'TRUE'
            if is_false_timeout: return 'REMOVE'
            return 'REMOVE'
            
    return 'not-found'

def combinar_or(lista_valores, cenario):
    vals = [normalizar_valor(v, cenario) for v in lista_valores]
    if 'TRUE' in vals: return 'TRUE'
    if 'REMOVE' in vals: return 'REMOVE'
    if 'true-timeout' in vals: return 'true-timeout'
    if 'false-timeout' in vals: return 'false-timeout'
    if 'timeout' in vals: return 'timeout'
    if 'error' in vals: return 'error'
    if 'FALSE' in vals: return 'FALSE'
    return 'not-found'

def carregar_raw(filepath):
    """
    Carrega o CSV e usa o NÚMERO DA LINHA como índice único.
    Isso impede que qualquer dado seja descartado como duplicata.
    """
    if not os.path.exists(filepath):
        return None, 0
    try:
        df = pd.read_csv(filepath, sep=DELIMITADOR_RES, dtype=str, on_bad_lines='warn', encoding='utf-8')
        df.columns = [c.strip().replace('"', '') for c in df.columns]
        
        # --- ALTERAÇÃO PRINCIPAL ---
        # Cria a coluna 'index' usando o número da linha do DataFrame
        # Isso torna cada linha única, mesmo que o conteúdo seja idêntico.
        df['index'] = df.index.astype(str)
        
        # Limpeza de strings nas chaves
        keys_to_clean = [k for k in CHAVE_MERGE if k != 'index'] # Index já é limpo
        for c in keys_to_clean:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip()
        
        # Como o index é único, o drop_duplicates não deve remover nada,
        # a menos que exista algum erro bizarro de duplicidade de índice no pandas (raro).
        linhas_antes = len(df)
        
        # Garante que temos todas as colunas da chave antes de prosseguir
        missing_keys = [k for k in CHAVE_MERGE if k not in df.columns]
        if missing_keys:
            # Se faltar coluna chave (ex: project), não dá pra fazer merge
            # Mas se for só o 'index', acabamos de criar.
            logger.warning(f"Faltando colunas chaves no arquivo {filepath}: {missing_keys}")
            return None, 0

        df.drop_duplicates(subset=CHAVE_MERGE, inplace=True)
        
        return df, linhas_antes
    except Exception as e:
        logger.error(f"Erro lendo {filepath}: {e}")
        return None, 0

def calcular_stats_mcnemar_formatado(store_matrix):
    stats_output = {a: {} for a in store_matrix.keys()}
    for analise in store_matrix.keys():
        stats_output[analise]['SPARK'] = [1.0, 0.0, "Same"]
        for tool in [t for t in FERRAMENTAS if t != 'SPARK']:
            matrix = store_matrix[analise].get(tool, {})
            b = 0; c = 0
            for (val_tool, val_spark), count in matrix.items():
                is_tool_true = (val_tool == 'TRUE')
                is_spark_true = (val_spark == 'TRUE')
                if is_tool_true and not is_spark_true: b += count
                elif not is_tool_true and is_spark_true: c += count
            denom = b + c
            if denom > 0:
                stat_val = (abs(b - c) - 1)**2 / denom
                p_val = chi2.sf(stat_val, 1)
                sig_label = "SIM" if p_val < 0.05 else "NAO"
                stats_output[analise][tool] = [p_val, stat_val, sig_label]
            else:
                stats_output[analise][tool] = [1.0, 0.0, "Same"]
    return stats_output

# --- GRAFICOS ---
def gerar_grafico_divergencias_empilhadas(matrix_data):
    labels = []
    
    active_categories = set()
    analises_ordem = ['idfp', 'ioa', 'icf']
    tools_ordem = [t for t in FERRAMENTAS if t != 'SPARK']
    
    for analise in analises_ordem:
        for tool in tools_ordem:
            for (vt, vs), count in matrix_data[analise][tool].items():
                if vt != vs and count > 0:
                    active_categories.add((vt, vs))
                    
    active_categories = sorted(list(active_categories))
    cat_labels = [f"{vt} -> {vs}" for vt, vs in active_categories]
    plot_data = {cl: [] for cl in cat_labels}
    
    for analise in analises_ordem:
        for tool in tools_ordem:
            label_x = f"{analise}-{tool}"
            labels.append(label_x)
            tool_matrix = matrix_data[analise][tool]
            for i, (vt, vs) in enumerate(active_categories):
                plot_data[cat_labels[i]].append(tool_matrix.get((vt, vs), 0))

    cmap = plt.get_cmap('tab20')
    colors = [cmap(i % 20) for i in range(max(1, len(cat_labels)))]
    
    fig, ax = plt.subplots(figsize=(14, 7))
    bottom = np.zeros(len(labels))
    for i, (cat_label, values) in enumerate(plot_data.items()):
        if len(colors) > i: color = colors[i]
        else: color = 'gray'
        ax.bar(labels, values, bottom=bottom, label=cat_label, color=color, edgecolor='black', linewidth=0.5)
        bottom += np.array(values)

    ax.set_title('Tipos de Divergencia por Analise e Ferramenta (vs SPARK)', fontsize=16, fontweight='bold')
    ax.set_ylabel('Numero de Divergencias', fontsize=12)
    ax.set_xlabel('Analise - Ferramenta', fontsize=12)
    ax.legend(title="Divergencia (Tool -> Spark)", bbox_to_anchor=(1.01, 1), loc='upper left')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    plt.tight_layout()
    filename = os.path.join(PASTA_TEMP_IMG, "grafico_divergencias_empilhadas.png")
    plt.savefig(filename, dpi=120)
    plt.close()
    return filename

def gerar_painel_detalhado(dados_dict):
    labels = [t for t in FERRAMENTAS if t != 'SPARK']
    colors = ['#FF9999', '#66B3FF', '#99FF99'][:len(labels)]
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), constrained_layout=True)
    if not isinstance(axes, np.ndarray): axes = [axes]
    analises_nomes = ['icf', 'ioa', 'idfp']
    for i, analise in enumerate(analises_nomes):
        ax = axes[i]
        dataset = [dados_dict[analise].get(t, []) for t in labels]
        if any(len(d) > 0 for d in dataset):
            ax.hist(dataset, bins='auto', color=colors, label=labels,
                    alpha=0.85, edgecolor='black', rwidth=0.8)
            ax.set_title(f"Analise: {analise.upper()}", fontsize=14, fontweight='bold')
            ax.set_xlabel("Qtd. Divergencias", fontsize=11)
            if i == 0: ax.set_ylabel("Numero de Projetos", fontsize=11)
            ax.legend(title="Ferramenta")
            ax.grid(axis='y', alpha=0.3, linestyle='--')
        else:
            ax.text(0.5, 0.5, 'Sem dados', ha='center', va='center')
            ax.set_title(analise.upper())
    filename = os.path.join(PASTA_TEMP_IMG, "grafico_1_painel.png")
    plt.savefig(filename, dpi=120)
    plt.close()
    return filename

def gerar_histograma_total_unificado(dados_dict):
    plt.figure(figsize=(12, 7))
    tools_no_spark = [t for t in FERRAMENTAS if t != 'SPARK']
    lista_icf = sum([dados_dict['icf'][t] for t in tools_no_spark], [])
    lista_ioa = sum([dados_dict['ioa'][t] for t in tools_no_spark], [])
    lista_idfp = sum([dados_dict['idfp'][t] for t in tools_no_spark], [])
    dataset = [lista_icf, lista_ioa, lista_idfp]
    labels = ['ICF (Total)', 'IOA (Total)', 'IDFP (Total)']
    colors = ['#FF9999', '#F0E68C', '#90EE90'] 
    if any(len(d) > 0 for d in dataset):
        plt.hist(dataset, bins='auto', color=colors, label=labels,
                 alpha=0.9, edgecolor='black', rwidth=0.85)
        plt.title("Comparacao Global Unificada: ICF vs IOA vs IDFP", fontsize=16, fontweight='bold')
        plt.xlabel("Quantidade de Divergencias (vs SPARK)", fontsize=12)
        plt.ylabel("Numero de Projetos", fontsize=12)
        plt.legend()
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        filename = os.path.join(PASTA_TEMP_IMG, "grafico_2_unificado.png")
        plt.tight_layout()
        plt.savefig(filename, dpi=120)
        plt.close()
        return filename
    return None

# ==========================================
# CLASSE PDF
# ==========================================
class RelatorioPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Relatorio Final (Analise Estatica)', 0, 1, 'C')
        self.set_font('Arial', '', 8)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(5)

    def draw_grouped_table(self, title, data_dict, row_labels, groups):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, title, 0, 1, 'L')
        TOOLS = FERRAMENTAS
        page_w = 277 
        lbl_w = 30
        col_w = (page_w - lbl_w) / (len(groups) * len(TOOLS))
        self.set_font('Arial', 'B', 8)
        self.cell(lbl_w, 6, "", 1, 0)
        for group_name, color in groups:
            self.set_fill_color(*color)
            self.cell(col_w * len(TOOLS), 6, group_name.upper(), 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', 'B', 7)
        self.cell(lbl_w, 6, "", 1, 0)
        for _, _ in groups:
            for tool in TOOLS:
                self.cell(col_w, 6, tool, 1, 0, 'C')
        self.ln()
        self.set_font('Arial', '', 7)
        for i, row_lbl in enumerate(row_labels):
            is_bold = (row_lbl == 'TOTAL' or '%' in row_lbl)
            self.set_font('Arial', 'B' if is_bold else '', 7)
            self.cell(lbl_w, 6, row_lbl, 1, 0, 'L')
            for group_name, _ in groups:
                for tool in TOOLS:
                    try:
                        val = data_dict[group_name][tool][i]
                        self.cell(col_w, 6, str(val), 1, 0, 'C')
                    except:
                        self.cell(col_w, 6, "-", 1, 0, 'C')
            self.ln()
        self.ln(5)

    def draw_spark_effect_table(self, counts_data, groups):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, "1.1 Efeito do SPARK (Calculo: SPARK - TOOL)", 0, 1, 'L')
        page_w = 277; lbl_w = 25; data_w = (page_w - lbl_w) / 18 
        self.set_font('Arial', 'B', 8); self.cell(lbl_w, 6, "", 1, 0)
        for g, c in groups: self.set_fill_color(*c); self.cell(data_w * 6, 6, g.upper(), 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', 'B', 7); self.cell(lbl_w, 6, "", 1, 0)
        tools_no_spark = [t for t in FERRAMENTAS if t != 'SPARK']
        for group_name, _ in groups:
            for tool in tools_no_spark:
                self.cell(data_w * 2, 6, tool, 1, 0, 'C')
        self.ln()
        self.set_font('Arial', 'B', 6); self.cell(lbl_w, 4, "", 1, 0)
        for _ in range(len(groups) * len(tools_no_spark)): self.cell(data_w, 4, "Diff", 1, 0, 'C'); self.cell(data_w, 4, "%", 1, 0, 'C')
        self.ln()
        row_labels = ['TRUE', 'FALSE', 'timeout', 'true-timeout', 'false-timeout']
        idx_map = {'TRUE': 0, 'FALSE': 1, 'timeout': 2, 'true-timeout': 3, 'false-timeout': 4}
        self.set_font('Arial', '', 7)
        for row_lbl in row_labels:
            self.cell(lbl_w, 6, row_lbl, 1, 0, 'L')
            idx = idx_map[row_lbl]
            for group_name, _ in groups:
                try: spark_val = counts_data[group_name]['SPARK'][idx]
                except: spark_val = 0
                for tool in tools_no_spark:
                    try: tool_val = counts_data[group_name][tool][idx]
                    except: tool_val = 0
                    diff = spark_val - tool_val
                    if tool_val > 0: pct_str = f"{(diff / tool_val) * 100:.0f}%"
                    elif diff != 0: pct_str = "Inf"
                    else: pct_str = "0%"
                    diff_str = f"{diff:+d}" if diff != 0 else "0"
                    
                    if diff != 0: self.set_font('Arial', 'B', 7)
                    else: self.set_font('Arial', '', 7)
                    self.cell(data_w, 6, diff_str, 1, 0, 'C')
                    self.set_font('Arial', '', 6)
                    self.cell(data_w, 6, pct_str, 1, 0, 'C')
            self.ln()
        self.ln(5)

    def draw_stat_significance_table(self, stats_data, groups):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, "5. Significancia Estatistica (Divergencia de Saida - McNemar)", 0, 1, 'L')
        TOOLS = FERRAMENTAS; page_w = 277; lbl_w = 35; col_w = (page_w - lbl_w) / (len(groups) * len(TOOLS))
        self.set_font('Arial', 'B', 8); self.cell(lbl_w, 6, "", 1, 0)
        for g, c in groups: self.set_fill_color(*c); self.cell(col_w * len(TOOLS), 6, g.upper(), 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', 'B', 7); self.cell(lbl_w, 6, "", 1, 0)
        for _ in groups:
            for t in TOOLS: self.cell(col_w, 6, t, 1, 0, 'C')
        self.ln()
        rows_config = [("P-Value", 0), ("Statistic (Chi2)", 1), ("Significativo (p<0.05)?", 2)]
        self.set_font('Arial', '', 7)
        for label, idx in rows_config:
            self.set_font('Arial', 'B', 7); self.cell(lbl_w, 6, label, 1, 0, 'L'); self.set_font('Arial', '', 7)
            for g, _ in groups:
                for t in TOOLS:
                    try:
                        val = stats_data[g][t][idx]
                        if isinstance(val, float): txt = f"{val:.4f}" if idx == 0 else f"{val:.2f}"
                        else: txt = str(val)
                        self.set_font('Arial', 'B' if txt == "SIM" else '', 7)
                    except: txt = "-"
                    self.cell(col_w, 6, txt, 1, 0, 'C')
            self.ln()
        self.set_font('Arial', 'I', 6)
        self.cell(0, 5, "Nota: O Teste de McNemar acima avalia se as DISCORDANCIAS nas saidas (TRUE vs nao-TRUE) sao sistematicas.", 0, 1, 'L')
        self.ln(3)

    def draw_matrix_table(self, analise, matrix_data):
        self.add_page(); self.set_font('Arial', 'B', 14); self.set_fill_color(230, 230, 230)
        self.cell(0, 10, f"Detalhes de Comparacao vs SPARK: {analise.upper()}", 0, 1, 'L', 1); self.ln(2)
        labels = ['TRUE', 'FALSE', 'timeout', 'true-timeout', 'false-timeout']
        cmbs = [(vt, vs) for vt in labels for vs in labels]
        tc = [t for t in FERRAMENTAS if t != 'SPARK']
        w_lbl, w_col = 60, 40
        self.set_font('Arial', 'B', 9); self.cell(w_lbl, 6, "TOOL / SPARK", 1, 0, 'C', 1)
        for t in tc: self.cell(w_col, 6, t, 1, 0, 'C', 1)
        self.ln(); self.set_font('Arial', '', 8)
        for vt, vs in cmbs:
            self.cell(w_lbl, 5, f"{vt}  /  {vs}", 1, 0, 'L')
            for t in tc:
                try: count = matrix_data[analise][t].get((vt, vs), 0)
                except: count = 0
                self.set_font('Arial', 'B' if vt!=vs and count>0 else '', 8)
                self.cell(w_col, 5, str(count), 1, 0, 'C')
            self.ln()

    def draw_divergence_stacked_chart_page(self, img_path):
        if not img_path or not os.path.exists(img_path): return
        self.add_page(); self.set_font('Arial', 'B', 14); self.set_fill_color(240, 240, 255)
        self.cell(0, 10, "Resumo Grafico: Tipos de Divergencia (Empilhado)", 0, 1, 'C', 1); self.ln(5)
        self.image(img_path, x=10, y=30, w=275)

    def draw_panel_page(self, img_path):
        if not img_path or not os.path.exists(img_path): return
        self.add_page(); self.set_font('Arial', 'B', 14); self.set_fill_color(240, 240, 255)
        self.cell(0, 10, "Distribuicao de Divergencias (Detalhe por Ferramenta)", 0, 1, 'C', 1); self.ln(5)
        self.image(img_path, x=13, y=30, w=270)

    def draw_unified_histogram_page(self, img_path):
        if not img_path or not os.path.exists(img_path): return
        self.add_page(); self.set_font('Arial', 'B', 14); self.set_fill_color(255, 240, 240)
        self.cell(0, 10, "Distribuicao Unificada (Todas as Analises)", 0, 1, 'C', 1); self.ln(5)
        self.image(img_path, x=(297-220)/2, y=35, w=220)

# ==========================================
# MAIN
# ==========================================
def main():
    logger.info(">>> INICIANDO PROCESSO COMPLETO (COM CORRECAO DE DUPLICATAS) <<<")
    ALL_ANALYSES = ANALISES + ['or all']
    store = { 'counts': {a: {} for a in ALL_ANALYSES}, 'diff': {a: {} for a in ALL_ANALYSES}, 'matrix': {a: {t: {} for t in FERRAMENTAS} for a in ALL_ANALYSES}, 'matrix_original': {a: {t: {} for t in FERRAMENTAS} for a in ALL_ANALYSES} }
    dados_globais_hist = {a: {t: [] for t in FERRAMENTAS if t != 'SPARK'} for a in ANALISES}
    debug_frames = []
    audit_list = []
    cache_dfs = {t: {} for t in FERRAMENTAS}

    # 1. CARREGAR E PROCESSAR
    print(f"{'ANALISE':<8} | {'TOOL':<8} | {'LINHAS':<12}"); print("-" * 35)
    for analise in ANALISES:
        for tool in FERRAMENTAS:
            path = os.path.join(analise, tool, SUBPASTA_DADOS, NOME_ARQUIVO_RESULTADO)
            df, count = carregar_raw(path)
            print(f"{analise:<8} | {tool:<8} | {count:<12}")
            vals = [0,0,0,0,0]
            if df is not None:
                col_final = 'VAL_FINAL'
                if analise == 'icf': df['VAL_ORIGINAL'] = df[COL_ICF_RAW].apply(lambda x: normalizar_valor(x, 0)) if COL_ICF_RAW in df.columns else 'not-found'
                elif analise == 'ioa': df['VAL_ORIGINAL'] = df[COL_IOA_RAW].apply(lambda x: normalizar_valor(x, 0)) if COL_IOA_RAW in df.columns else 'not-found'
                elif analise == 'idfp': df['VAL_ORIGINAL'] = df.apply(lambda r: combinar_or([r[COL_LR_RAW] if COL_LR_RAW in df.columns else 'not-found', r[COL_RL_RAW] if COL_RL_RAW in df.columns else 'not-found'], 0), axis=1)

                if analise == 'icf': df[col_final] = df[COL_ICF_RAW].apply(lambda x: normalizar_valor(x, CENARIO)) if COL_ICF_RAW in df.columns else 'not-found'
                elif analise == 'ioa': df[col_final] = df[COL_IOA_RAW].apply(lambda x: normalizar_valor(x, CENARIO)) if COL_IOA_RAW in df.columns else 'not-found'
                elif analise == 'idfp': df[col_final] = df.apply(lambda r: combinar_or([r[COL_LR_RAW] if COL_LR_RAW in df.columns else 'not-found', r[COL_RL_RAW] if COL_RL_RAW in df.columns else 'not-found'], CENARIO), axis=1)
                
                cache_dfs[tool][analise] = df[CHAVE_MERGE+[col_final, 'VAL_ORIGINAL']].copy()
                
                vals = [df['VAL_ORIGINAL'].value_counts().get(k, 0) for k in ['TRUE','FALSE','timeout','true-timeout','false-timeout','error','not-found']]
                
                # Debug geral
                df_dbg = df[CHAVE_MERGE + [col_final, 'VAL_ORIGINAL']].copy(); df_dbg['ANALISE'] = analise; df_dbg['TOOL'] = tool
                debug_frames.append(df_dbg)
            
            store['counts'][analise][tool] = vals + [sum(vals)]

    # 2. OR ALL
    logger.info("Calculando 'OR ALL'...")
    from functools import reduce
    for tool in FERRAMENTAS:
        dfs = []
        for a in ANALISES:
            if cache_dfs[tool].get(a) is not None:
                d = cache_dfs[tool].get(a).rename(columns={'VAL_FINAL': f'VAL_FINAL_{a}', 'VAL_ORIGINAL': f'VAL_ORIGINAL_{a}'})
                dfs.append(d)
        if dfs:
            dm = reduce(lambda l,r: pd.merge(l,r,on=CHAVE_MERGE,how='outer'), dfs)
            dm.fillna('not-found', inplace=True)
            dm['VAL_FINAL'] = dm[[c for c in dm.columns if 'VAL_FINAL_' in c]].apply(lambda x: combinar_or(x.values, CENARIO), axis=1)
            dm['VAL_ORIGINAL'] = dm[[c for c in dm.columns if 'VAL_ORIGINAL_' in c]].apply(lambda x: combinar_or(x.values, 0), axis=1)
            cache_dfs[tool]['or all'] = dm[CHAVE_MERGE+['VAL_FINAL', 'VAL_ORIGINAL']].copy()
            vals = [dm['VAL_ORIGINAL'].value_counts().get(k, 0) for k in ['TRUE','FALSE','timeout','true-timeout','false-timeout','error','not-found']]
            store['counts']['or all'][tool] = vals + [sum(vals)]
        else: store['counts']['or all'][tool] = [0,0,0,0,0,0,0,0]

    # 3. MATRIZES, DIVERGENCIAS E AUDITORIA
    logger.info("Gerando Matrizes e Arquivo de Auditoria...")
    for analise in ALL_ANALYSES:
        spark = cache_dfs['SPARK'].get(analise)
        for tool in FERRAMENTAS:
            if tool == 'SPARK': 
                store['diff'][analise][tool] = [0, "0.00%"]
                continue
            t_df = cache_dfs[tool].get(analise)
            if t_df is not None and spark is not None:
                # Filtrar REMOVE apenas no momento do merge (amostra de divergência)
                t_df_filtered = t_df[t_df['VAL_FINAL'] != 'REMOVE']
                spark_filtered = spark[spark['VAL_FINAL'] != 'REMOVE']
                
                # Merge Inner (Intersecção)
                m = pd.merge(t_df_filtered, spark_filtered, on=CHAVE_MERGE, how='inner', suffixes=('_TOOL', '_SPARK'))
                mask = (m['VAL_FINAL_TOOL']!='not-found') & (m['VAL_FINAL_SPARK']!='not-found')
                m = m[mask].copy()
                
                diffs = (m['VAL_FINAL_TOOL']!=m['VAL_FINAL_SPARK']).sum()
                pct = (diffs/len(m))*100 if len(m)>0 else 0
                store['diff'][analise][tool] = [diffs, f"{pct:.2f}%"]
                store['matrix'][analise][tool] = m.groupby(['VAL_FINAL_TOOL','VAL_FINAL_SPARK']).size().to_dict()
                store['matrix_original'][analise][tool] = m.groupby(['VAL_ORIGINAL_TOOL','VAL_ORIGINAL_SPARK']).size().to_dict()
                
                # --- AUDITORIA CSV ---
                export_df = m.copy()
                export_df['ANALYSIS'] = analise
                export_df['TOOL'] = tool
                export_df['DIVERGENT'] = export_df['VAL_FINAL_TOOL'] != export_df['VAL_FINAL_SPARK']
                audit_list.append(export_df[CHAVE_MERGE + ['ANALYSIS', 'TOOL', 'VAL_ORIGINAL_TOOL', 'VAL_ORIGINAL_SPARK', 'VAL_FINAL_TOOL', 'VAL_FINAL_SPARK', 'DIVERGENT']])

                if analise in ANALISES:
                    divs = m[m['VAL_ORIGINAL_TOOL']!=m['VAL_ORIGINAL_SPARK']]
                    if not divs.empty:
                        dados_globais_hist[analise][tool].extend(divs['project'].value_counts().tolist())
            else: store['diff'][analise][tool] = [0, "-"]

    # 4. ESTATISTICA E EXPORTAÇÃO
    logger.info("Calculando Estatisticas (McNemar)...")
    stats_formatted = calcular_stats_mcnemar_formatado(store['matrix'])
    
    logger.info("Salvando CSVs...")
    if debug_frames: 
        pd.concat(debug_frames, ignore_index=True).to_csv(NOME_CSV_CONSOLIDADO, index=False, sep=';')
        
    if audit_list:
        pd.concat(audit_list, ignore_index=True).to_csv(NOME_CSV_AUDITORIA, index=False, sep=';')
        logger.info(f"Auditoria salva em: {NOME_CSV_AUDITORIA}")

    # 5. GRAFICOS E PDF
    logger.info("Gerando Graficos...")
    img_painel = gerar_painel_detalhado(dados_globais_hist)
    img_unificado = gerar_histograma_total_unificado(dados_globais_hist)
    img_divergencias_empilhado = gerar_grafico_divergencias_empilhadas(store['matrix_original'])

    logger.info("Montando PDF...")
    pdf = RelatorioPDF(orientation='L', unit='mm', format='A4')
    grps = [('icf', (240, 160, 160)), ('ioa', (255, 245, 180)), ('idfp', (180, 230, 180)), ('or all', (200, 220, 255))]
    
    pdf.add_page()
    pdf.draw_grouped_table("1. Contagem RAW", store['counts'], ['TRUE', 'FALSE', 'timeout', 'true-timeout', 'false-timeout', 'error', 'not-found', 'TOTAL'], grps)
    pdf.ln(5)
    pdf.draw_spark_effect_table(store['counts'], grps)
    pdf.ln(5)
    pdf.draw_grouped_table("4. Divergencia em relacao ao SPARK", store['diff'], ['Total Divergencias', '% Divergencia'], grps)
    pdf.ln(5)
    pdf.draw_stat_significance_table(stats_formatted, grps)

    for analise in ANALISES:
        pdf.draw_matrix_table(analise, store['matrix_original'])

    if img_divergencias_empilhado:
        pdf.draw_divergence_stacked_chart_page(img_divergencias_empilhado)

    if img_painel: pdf.draw_panel_page(img_painel)
    if img_unificado: pdf.draw_unified_histogram_page(img_unificado)

    try:
        pdf.output(NOME_RELATORIO)
        logger.info(f"Relatório salvo: {NOME_RELATORIO}")
    except Exception as e:
        logger.error(f"Erro ao salvar PDF: {e}")

if __name__ == "__main__":
    main()