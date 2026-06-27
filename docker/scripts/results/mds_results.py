import pandas as pd
import numpy as np
import os
import logging
from fpdf import FPDF
from datetime import datetime
import warnings

# Tenta importar scipy
try:
    from scipy.stats import chi2
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# CONFIGURAÇÕES
# ==========================================
ANALISES_FOLDERS = ['icf', 'ioa', 'idfp']
TOOLS_DIRS = ['CHA', 'RTA', 'VTA', 'SPARK']
SUBPASTA_DADOS = 'data1'
NOME_ARQUIVO_RESULTADO = 'soot-results.csv' 

ARQUIVO_GT = 'loi.csv'
NOME_RELATORIO = 'relatorio_final.pdf'
NOME_ARQUIVO_DEBUG = 'detalhe_divergencias.csv'
NOME_ARQUIVO_LOSS = 'casos_perdidos_pelo_spark.csv'

DELIMITADOR_GT = ','       
DELIMITADOR_RES = ';'      

# Nomes das colunas
COL_ICF_RAW = 'Confluence Inter'
COL_IOA_RAW = 'OA Inter'
COL_LR_RAW = 'left right DFP-Inter'
COL_RL_RAW = 'right left DFP-Inter'

CHAVE_MERGE = ['project', 'class', 'method', 'merge commit']
COLUNA_GT_ALVO = 'Locally Observable Interference'

VALORES_TRUE = ['true', 'yes', 't', '1', 'verdadeiro', 'sim']
VALORES_FALSE = ['false', 'no', 'f', '0', 'falso', 'nao', 'não']
VALORES_TRUE_TIMEOUT = ['true-timeout', 'true timeout', 'true_timeout']
VALORES_FALSE_TIMEOUT = ['false-timeout', 'false timeout', 'false_timeout']
VALORES_TIMEOUT = ['timeout', 'to', 'time out', 'timed out']
VALORES_ERROR = ['error', 'err', 'exception']

COMBINACOES_CROSS = [
    ('TRUE', 'TRUE'), ('TRUE', 'FALSE'), ('TRUE', 'timeout'), ('TRUE', 'error'), ('TRUE', 'not-found'),
    ('FALSE', 'TRUE'), ('FALSE', 'FALSE'), ('FALSE', 'timeout'), ('FALSE', 'error'), ('FALSE', 'not-found'),
    ('timeout', 'TRUE'), ('timeout', 'FALSE'), ('timeout', 'timeout'), ('timeout', 'error'), ('timeout', 'not-found'),
    ('error', 'TRUE'), ('error', 'FALSE'), ('error', 'timeout'), ('error', 'error'), ('error', 'not-found'),
    ('not-found', 'TRUE'), ('not-found', 'FALSE'), ('not-found', 'timeout'), ('not-found', 'error'), ('not-found', 'not-found')
]

BLACKLIST_RAW = [
    ("antlr4", "org.antlr.v4.codegen.target.Python2Target", "python2Keywords", "69ff2669eec265e25721dbc27cb00f6c381d0b41"),
    ("antlr4", "org.antlr.v4.codegen.target.Python3Target", "python3Keywords", "69ff2669eec265e25721dbc27cb00f6c381d0b41"),
    ("swagger-maven-plugin", "com.github.kongchen.swagger.docgen.reader.AbstractReader", "hasValidAnnotations(List<Annotation>)", "e825a7fdc6ef688f1253b93d2cb236e710acfc56"),
    ("elasticsearch", "org.elasticsearch.common.settings.IndexScopedSettings", "BUILT_IN_INDEX_SETTINGS", "d896886973660785aac45275ddb110c1a6babc57"),
    ("elasticsearch", "org.elasticsearch.common.settings.ClusterSettings", "BUILT_IN_CLUSTER_SETTINGS", "0404db65e3497452886173957729c8e82cfd4a03"),
    ("cloud-slang", "io.cloudslang.lang.api.SlangImplTest", "ALL_EVENTS_SIZE", "20bac30d9bd76569aa6a4fa1e8261c1a9b5e6f76"),
    ("crawler4j", "edu.uci.ics.crawler4j.parser.Parser", "parse(Page, String)", "6fdb8f27b53c5d69b552341a459d0e1fa610f68d")
]

# ==========================================
# DEFINIÇÃO DOS 7 CENÁRIOS DE TIMEOUT
# ==========================================
# Cada cenário define como tratar valores de timeout nas métricas.
# 'transform': mapeia valor normalizado -> novo valor (None = remover da amostra)
# 'exclude_rta': se True, ignora a coluna RTA
# 'title' e 'desc': textos para o PDF

CENARIOS = [
    {
        'key': 'c1',
        'title': 'Cenario 1: Timeout = TRUE',
        'desc': 'Qualquer timeout (TRUE_TIMEOUT, FALSE_TIMEOUT, timeout) eh considerado TRUE.',
        'exclude_rta': False,
    },
    {
        'key': 'c2',
        'title': 'Cenario 2: Timeout = FALSE',
        'desc': 'Qualquer timeout (TRUE_TIMEOUT, FALSE_TIMEOUT, timeout) eh considerado FALSE.',
        'exclude_rta': False,
    },
    {
        'key': 'c3',
        'title': 'Cenario 3: Timeout Removido',
        'desc': 'Linhas com qualquer timeout sao removidas da amostra.',
        'exclude_rta': False,
    },
    {
        'key': 'c4',
        'title': 'Cenario 4: Timeout Removido (sem RTA)',
        'desc': 'Linhas com qualquer timeout sao removidas da amostra. Coluna RTA ignorada (muitos timeouts).',
        'exclude_rta': True,
    },
    {
        'key': 'c5',
        'title': 'Cenario 5: Resultados Parciais',
        'desc': 'TRUE_TIMEOUT = TRUE, FALSE_TIMEOUT = FALSE. Timeout puro removido da amostra.',
        'exclude_rta': False,
    },
    {
        'key': 'c6',
        'title': 'Cenario 6: Parcial TRUE',
        'desc': 'TRUE_TIMEOUT = TRUE. FALSE_TIMEOUT e timeout puro removidos da amostra.',
        'exclude_rta': False,
    },
    {
        'key': 'c7',
        'title': 'Cenario 7: Parcial TRUE (sem RTA)',
        'desc': 'TRUE_TIMEOUT = TRUE. FALSE_TIMEOUT e timeout puro removidos da amostra. RTA ignorada.',
        'exclude_rta': True,
    },
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def normalizar_valor(valor):
    if pd.isna(valor): return 'not-found'
    s = str(valor).strip().lower()
    if not s: return 'not-found'
    if s in VALORES_TRUE_TIMEOUT: return 'TRUE_TIMEOUT'
    if s in VALORES_FALSE_TIMEOUT: return 'FALSE_TIMEOUT'
    if s in VALORES_TRUE: return 'TRUE'
    if s in VALORES_FALSE: return 'FALSE'
    if s in VALORES_TIMEOUT: return 'timeout'
    if s in VALORES_ERROR: return 'error'
    return 'not-found'

def para_resultado(v):
    if v == 'TRUE_TIMEOUT': return 'TRUE'
    if v == 'FALSE_TIMEOUT': return 'FALSE'
    return v

def para_timeout(v):
    if v in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT'): return 'timeout'
    return v

def tem_timeout(v):
    return v in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout')

def eh_timeout_parcial(v):
    return v in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT')

def combinar_or(lista_valores):
    vals = [normalizar_valor(v) for v in lista_valores]
    if 'TRUE' in vals: return 'TRUE'
    if 'TRUE_TIMEOUT' in vals: return 'TRUE_TIMEOUT'
    if 'timeout' in vals: return 'timeout'
    if 'FALSE_TIMEOUT' in vals: return 'FALSE_TIMEOUT'
    if 'error' in vals: return 'error'
    if 'FALSE' in vals: return 'FALSE'
    return 'not-found'

def filtrar_blacklist(df):
    if df.empty: return df
    for c in CHAVE_MERGE:
        if c in df.columns: df[c] = df[c].astype(str).str.strip()
    df['key'] = df.apply(lambda r: (r['project'], r['class'], r['method'], r['merge commit']), axis=1)
    bl_set = set([(str(p), str(c), str(m), str(mc)) for p, c, m, mc in BLACKLIST_RAW])
    return df[~df['key'].isin(bl_set)].drop(columns=['key'])

def calc_stats(y_true, y_pred):
    TP = ((y_pred == True) & (y_true == True)).sum()
    FP = ((y_pred == True) & (y_true == False)).sum()
    TN = ((y_pred == False) & (y_true == False)).sum()
    FN = ((y_pred == False) & (y_true == True)).sum()
    
    prec = TP/(TP+FP) if (TP+FP)>0 else 0
    rec = TP/(TP+FN) if (TP+FN)>0 else 0
    acc = (TP+TN)/(TP+TN+FP+FN) if (TP+TN+FP+FN)>0 else 0
    f1 = 2*(prec*rec)/(prec+rec) if (prec+rec)>0 else 0
    return TP, FP, TN, FN, prec, rec, acc, f1

def transformar_cenario(valor, cenario_key):
    """
    Transforma valor normalizado conforme o cenário.
    Retorna None para indicar que a linha deve ser removida da amostra.
    """
    if cenario_key == 'c1':
        # Qualquer timeout → TRUE
        if valor in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout'):
            return 'TRUE'
    elif cenario_key == 'c2':
        # Qualquer timeout → FALSE
        if valor in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout'):
            return 'FALSE'
    elif cenario_key in ('c3', 'c4'):
        # Qualquer timeout → remover
        if valor in ('TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout'):
            return None
    elif cenario_key == 'c5':
        # Resultados parciais: TRUE_TIMEOUT→TRUE, FALSE_TIMEOUT→FALSE, timeout puro→remover
        if valor == 'TRUE_TIMEOUT': return 'TRUE'
        if valor == 'FALSE_TIMEOUT': return 'FALSE'
        if valor == 'timeout': return None
    elif cenario_key in ('c6', 'c7'):
        # Parcial TRUE: TRUE_TIMEOUT→TRUE, FALSE_TIMEOUT→remover, timeout→remover
        if valor == 'TRUE_TIMEOUT': return 'TRUE'
        if valor in ('FALSE_TIMEOUT', 'timeout'): return None
    return valor

# Nova função genérica para McNemar
def calcular_mcnemar(series_a, series_b):
    """
    Retorna [p_value, statistic, label_significancia]
    series_a e series_b devem ser booleanos ou categóricos alinhados.
    Para teste de performance: A = (Tool == GT), B = (SPARK == GT).
    Para teste de output: A = (Tool == TRUE), B = (SPARK == TRUE).
    """
    if not HAS_SCIPY:
        return ["No Lib", "-", "-"]
    
    # Define "Sucesso" vs "Falha" para a tabela de contingência
    # Se forem booleanos (Performance), True é sucesso.
    # Se forem strings (Output), 'TRUE' é o alvo de comparação.
    
    # Normaliza para booleano de comparação
    # Se entrada já é booleana (comparação com GT), mantém.
    # Se é string (comparação de saídas), converte.
    if series_a.dtype == bool or series_a.dtype == object: 
        # Tenta converter strings para comparação direta
        pass 

    # Casos divergentes
    # b: A é True/Sucesso, B é False/Falha
    # c: A é False/Falha, B é True/Sucesso
    
    # Nota: Se forem arrays booleanos de "Acertou?", True=Acertou.
    # Se forem arrays de strings "TRUE"/"FALSE", queremos saber se divergem.
    
    mask_diff = (series_a != series_b)
    
    # Se não há diferença nenhuma
    if not mask_diff.any():
        return [1.0, 0.0, "Same"]
        
    # Filtrar apenas as linhas divergentes
    # Para McNemar, precisamos definir um lado como "Positivo" para montar a tabela
    # Vamos assumir que "TRUE" (ou True) é o positivo.
    
    # Convertendo para booleano padronizado para contagem
    def is_pos(val):
        return val is True or str(val).upper() == 'TRUE'

    vec_a = series_a[mask_diff].apply(is_pos)
    vec_b = series_b[mask_diff].apply(is_pos)
    
    # b: A=Pos, B=Neg
    b = ((vec_a == True) & (vec_b == False)).sum()
    # c: A=Neg, B=Pos
    c = ((vec_a == False) & (vec_b == True)).sum()
    
    denom = b + c
    if denom > 0:
        stat_val = (abs(b - c) - 1)**2 / denom
        p_val = chi2.sf(stat_val, 1)
        sig_label = "SIM" if p_val < 0.05 else "NAO"
        return [p_val, stat_val, sig_label]
    else:
        return [1.0, 0.0, "Same"]

# ==========================================
# PDF CLASS
# ==========================================
class AdvancedPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Relatório Comparativo de Análise Estática', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.ln(8)

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 14)
        self.set_fill_color(220, 230, 240) 
        self.cell(0, 10, f"  {label}", 0, 1, 'L', 1)
        self.ln(4)

    def draw_legend(self, text):
        self.set_font('Arial', 'I', 7)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 4, text, 0, 'L')
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def draw_grouped_table(self, title, data_dict, row_labels, groups, tools=None):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, title, 0, 1, 'L')
        
        TOOLS = tools or TOOLS_DIRS
        total_cols = len(groups) * len(TOOLS)
        page_w = 277 
        lbl_w = 35
        col_w = (page_w - lbl_w) / total_cols
        
        self.set_font('Arial', 'B', 8)
        self.cell(lbl_w, 6, "", 1, 0)
        for group_name, color in groups:
            self.set_fill_color(*color)
            self.cell(col_w * len(TOOLS), 6, group_name.upper(), 1, 0, 'C', 1)
        self.ln()
        
        self.set_font('Arial', 'B', 7)
        self.cell(lbl_w, 6, "", 1, 0)
        for group_name, _ in groups:
            for tool in TOOLS:
                self.cell(col_w, 6, tool, 1, 0, 'C')
        self.ln()
        
        self.set_font('Arial', '', 7)
        for i, row_lbl in enumerate(row_labels):
            if row_lbl.endswith('%') or row_lbl == 'TOTAL':
                self.set_font('Arial', 'B', 7)
            else:
                self.set_font('Arial', '', 7)
                
            self.cell(lbl_w, 6, row_lbl, 1, 0, 'L')
            for group_name, _ in groups:
                for tool in TOOLS:
                    try:
                        val = data_dict[group_name][tool][i]
                        txt = f"{val:.2f}".replace('.', ',') if isinstance(val, float) else str(val)
                        if isinstance(val, str) and '%' in val: 
                             txt = val.replace('.', ',')
                        if 'P-Value' in row_lbl and isinstance(val, float):
                             txt = f"{val:.4f}"
                    except:
                        txt = "-"
                    self.cell(col_w, 6, txt, 1, 0, 'C')
            self.ln()
        self.ln(5)

    def draw_impact_table(self, title, data_dict, row_labels, groups):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, title, 0, 1, 'L')
        TOOLS_CMP = [t for t in TOOLS_DIRS if t != 'SPARK']
        n_subcols = 2 
        total_data_cols = len(groups) * len(TOOLS_CMP) * n_subcols
        page_w = 277 
        lbl_w = 35
        col_w = (page_w - lbl_w) / total_data_cols
        
        self.set_font('Arial', 'B', 8)
        self.cell(lbl_w, 6, "", 1, 0)
        for group_name, color in groups:
            self.set_fill_color(*color)
            width_group = col_w * len(TOOLS_CMP) * n_subcols
            self.cell(width_group, 6, group_name.upper(), 1, 0, 'C', 1)
        self.ln()
        
        self.set_font('Arial', 'B', 7)
        self.cell(lbl_w, 6, "", 1, 0)
        for group_name, _ in groups:
            for tool in TOOLS_CMP:
                self.cell(col_w * n_subcols, 6, tool, 1, 0, 'C')
        self.ln()

        self.set_font('Arial', 'B', 6)
        self.cell(lbl_w, 5, "", 1, 0) 
        for group_name, _ in groups:
            for tool in TOOLS_CMP:
                self.cell(col_w, 5, "Dif", 1, 0, 'C')
                self.cell(col_w, 5, "%", 1, 0, 'C')
        self.ln()
        
        self.set_font('Arial', '', 6) 
        for i, row_lbl in enumerate(row_labels):
            if row_lbl == 'TOTAL': self.set_font('Arial', 'B', 6)
            else: self.set_font('Arial', '', 6)
            self.cell(lbl_w, 5, row_lbl, 1, 0, 'L')
            for group_name, _ in groups:
                for tool in TOOLS_CMP:
                    diff_val = "-"
                    pct_val = "-"
                    try:
                        raw_data = data_dict[group_name][tool][i]
                        diff_val = f"{raw_data[0]:+d}" 
                        pct_val = f"{raw_data[1]:.0f}%"
                    except: pass
                    self.cell(col_w, 5, diff_val, 1, 0, 'C')
                    self.cell(col_w, 5, pct_val, 1, 0, 'C')
            self.ln()
        self.ln(5)

    def draw_cross_matrix_table(self, analise_name, data_dict_analise):
        self.set_font('Arial', 'B', 12)
        if 'icf' in analise_name.lower(): self.set_fill_color(240, 160, 160)
        elif 'ioa' in analise_name.lower(): self.set_fill_color(255, 245, 180)
        elif 'idfp' in analise_name.lower(): self.set_fill_color(180, 230, 180)
        else: self.set_fill_color(200, 220, 255)

        self.cell(0, 10, f"Detalhes de Comparacao vs SPARK: {analise_name.upper()}", 0, 1, 'L', 1)
        self.ln(2)

        TOOLS_CMP = [t for t in TOOLS_DIRS if t != 'SPARK']
        lbl_w = 40
        page_w = 277
        col_w = (page_w - lbl_w) / len(TOOLS_CMP)

        self.set_font('Arial', 'B', 9)
        self.cell(lbl_w, 8, "TOOL / SPARK", 1, 0, 'C', 1) 
        for tool in TOOLS_CMP:
            self.cell(col_w, 8, tool, 1, 0, 'C', 1)
        self.ln()
        self.set_font('Arial', '', 9)
        for (t_val, s_val) in COMBINACOES_CROSS:
            label = f"{t_val} / {s_val}"
            self.cell(lbl_w, 8, label, 1, 0, 'L')
            for tool in TOOLS_CMP:
                try:
                    idx = COMBINACOES_CROSS.index((t_val, s_val))
                    val = data_dict_analise[tool][idx]
                except: val = "-"
                self.cell(col_w, 8, str(val), 1, 0, 'C')
            self.ln()
        self.ln(8)

# ==========================================
# MAIN
# ==========================================
def main():
    logger.info("Iniciando processamento...")

    # 1. Carregar GT
    try:
        df_gt = pd.read_csv(ARQUIVO_GT, sep=DELIMITADOR_GT, dtype=str, on_bad_lines='skip')
        df_gt.dropna(how='all', axis=1, inplace=True)
        df_gt.columns = [c.strip() for c in df_gt.columns]
        df_gt = filtrar_blacklist(df_gt)
        df_gt['GT_BOOL'] = df_gt[COLUNA_GT_ALVO].apply(lambda x: True if normalizar_valor(x) == 'TRUE' else False)
        logger.info(f"GT carregado: {len(df_gt)} registros.")
    except Exception as e:
        logger.error(f"Erro ao carregar GT ({ARQUIVO_GT}): {e}")
        return

    # 2. Montar Tabela Mestra
    master_df = df_gt.copy()

    for analise_tipo in ANALISES_FOLDERS:
        for tool in TOOLS_DIRS:
            path = os.path.join(analise_tipo, tool, SUBPASTA_DADOS, NOME_ARQUIVO_RESULTADO)
            if not os.path.exists(path): continue
            try:
                df_tool = pd.read_csv(path, sep=DELIMITADOR_RES, dtype=str, on_bad_lines='skip')
                df_tool.dropna(how='all', axis=1, inplace=True)
                df_tool.columns = [c.strip() for c in df_tool.columns]
                for c in CHAVE_MERGE: 
                    if c in df_tool.columns: df_tool[c] = df_tool[c].astype(str).str.strip()
                
                col_result = pd.Series(['not-found']*len(df_tool))
                if analise_tipo == 'icf' and COL_ICF_RAW in df_tool.columns:
                    col_result = df_tool[COL_ICF_RAW].apply(normalizar_valor)
                elif analise_tipo == 'ioa' and COL_IOA_RAW in df_tool.columns:
                    col_result = df_tool[COL_IOA_RAW].apply(normalizar_valor)
                elif analise_tipo == 'idfp':
                    has_lr, has_rl = COL_LR_RAW in df_tool.columns, COL_RL_RAW in df_tool.columns
                    s_lr = df_tool[COL_LR_RAW] if has_lr else pd.Series([np.nan]*len(df_tool))
                    s_rl = df_tool[COL_RL_RAW] if has_rl else pd.Series([np.nan]*len(df_tool))
                    col_result = df_tool.apply(lambda r: combinar_or([s_lr[r.name], s_rl[r.name]]), axis=1)

                tool_extract = df_tool[CHAVE_MERGE].copy()
                tool_extract[f"{tool}_{analise_tipo}"] = col_result
                master_df = pd.merge(master_df, tool_extract, on=CHAVE_MERGE, how='left')
            except Exception as e:
                logger.error(f"Erro processando {path}: {e}")

    # 3. Calcular "OR ALL"
    for tool in TOOLS_DIRS:
        col_icf, col_ioa, col_idfp = f"{tool}_icf", f"{tool}_ioa", f"{tool}_idfp"
        s_or = master_df.apply(lambda r: combinar_or([
            r[col_icf] if col_icf in master_df.columns else 'not-found',
            r[col_ioa] if col_ioa in master_df.columns else 'not-found',
            r[col_idfp] if col_idfp in master_df.columns else 'not-found'
        ]), axis=1)
        master_df[f"{tool}_or all"] = s_or

    # 4. Processamento
    store = {
        'counts': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
        'impact': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}}, 
        'diff_spark': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}}, 
        'spark_loss': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
        'cross_matrix': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
        'stats_divergence': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
    }
    
    # Store para os 7 cenários de timeout
    store_cenarios = {}
    for cen in CENARIOS:
        k = cen['key']
        store_cenarios[k] = {
            'mat': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
            'met': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
            'stats': {'icf':{}, 'ioa':{}, 'idfp':{}, 'or all':{}},
        }
    
    analises_tipos = ['icf', 'ioa', 'idfp', 'or all']
    audit_list = []
    loss_list = []

    for atype in analises_tipos:
        spark_col_name = f"SPARK_{atype}"

        # Init
        for t in TOOLS_DIRS:
            store['spark_loss'][atype][t] = [0] 
            store['cross_matrix'][atype][t] = [0] * len(COMBINACOES_CROSS)
            store['stats_divergence'][atype][t] = ["-", "-", "-"]
            for cen in CENARIOS:
                store_cenarios[cen['key']]['mat'][atype][t] = None
                store_cenarios[cen['key']]['met'][atype][t] = None
                store_cenarios[cen['key']]['stats'][atype][t] = ["-", "-", "-"]

        # Pré-computar máscaras de remoção por linha para cenários com remoção (c3, c4, c6, c7)
        # Se QUALQUER tool participante tem timeout que seria removido, a linha inteira é excluída
        row_masks_cenario = {}
        for cen in CENARIOS:
            cen_key = cen['key']
            if cen_key not in ('c3', 'c4', 'c6', 'c7'):
                row_masks_cenario[cen_key] = None  # sem remoção por linha
                continue
            
            tools_cen = [t for t in TOOLS_DIRS if not (cen['exclude_rta'] and t == 'RTA')]
            mask_all_valid = pd.Series(True, index=master_df.index)
            
            for t in tools_cen:
                col = f"{t}_{atype}"
                if col not in master_df.columns:
                    continue
                s = master_df[col].fillna('not-found')
                # Aplicar transformação: None indica remoção
                t_transformed = s.apply(lambda v, ck=cen_key: transformar_cenario(v, ck))
                # Linha válida se transformação NÃO retornou None
                mask_all_valid = mask_all_valid & t_transformed.notna()
            
            row_masks_cenario[cen_key] = mask_all_valid

        for tool in TOOLS_DIRS:
            col_name = f"{tool}_{atype}"
            if col_name not in master_df.columns: 
                store['counts'][atype][tool] = [0]*8
                store['diff_spark'][atype][tool] = [0, "-"]
                continue
            
            series = master_df[col_name].fillna('not-found')
            
            # --- 1. Contagem ---
            vc = series.value_counts()
            v_cnt = [vc.get(k, 0) for k in ['TRUE', 'FALSE', 'TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout', 'error', 'not-found']]
            store['counts'][atype][tool] = v_cnt + [sum(v_cnt[:6])]
            
            # --- 2. Divergência vs SPARK (Output) ---
            diff_count = 0
            pct_str = "-"
            
            if spark_col_name in master_df.columns:
                if col_name == spark_col_name:
                    pct_str = "0,00%"
                    store['stats_divergence'][atype][tool] = ["1.0", "0.0", "Same"]
                else:
                    df_cmp = master_df[[col_name, spark_col_name]].copy()
                    mask_valid_cmp = (df_cmp[col_name] != 'not-found') & (df_cmp[spark_col_name] != 'not-found')
                    df_cmp = df_cmp[mask_valid_cmp]
                    
                    if len(df_cmp) > 0:
                        mask_diff = df_cmp[col_name].apply(para_resultado) != df_cmp[spark_col_name].apply(para_resultado)
                        diff_count = mask_diff.sum()
                        pct_str = f"{(diff_count / len(df_cmp)) * 100:.2f}%"
                        if diff_count > 0:
                            divs = master_df.loc[mask_diff.index, CHAVE_MERGE].copy()
                            divs['ANALISE'] = atype; divs['TOOL'] = tool
                            divs['VALOR_TOOL'] = master_df.loc[mask_diff.index, col_name]
                            divs['VALOR_SPARK'] = master_df.loc[mask_diff.index, spark_col_name]
                            audit_list.append(divs)
                    
                    # Estatística: Divergencia de Output (usando resultado, ignorando timeout)
                    store['stats_divergence'][atype][tool] = calcular_mcnemar(df_cmp[col_name].apply(para_resultado), df_cmp[spark_col_name].apply(para_resultado))

            store['diff_spark'][atype][tool] = [diff_count, pct_str]

            # --- 3. SPARK Loss ---
            if tool != 'SPARK' and spark_col_name in master_df.columns:
                mask_loss = ((master_df[col_name].apply(para_resultado) == 'TRUE') & (master_df[spark_col_name].apply(para_resultado) != 'TRUE') & (master_df['GT_BOOL'] == True))
                count_loss = mask_loss.sum()
                store['spark_loss'][atype][tool] = [count_loss]
                if count_loss > 0:
                    rows_loss = master_df.loc[mask_loss, CHAVE_MERGE].copy()
                    rows_loss['ANALISE'] = atype; rows_loss['TOOL_ORIGINAL'] = tool
                    rows_loss['VALOR_TOOL'] = master_df.loc[mask_loss, col_name]
                    rows_loss['VALOR_SPARK'] = master_df.loc[mask_loss, spark_col_name]
                    rows_loss['GT'] = 'TRUE'
                    loss_list.append(rows_loss)
            
            # --- 4. Cross Matrix ---
            if tool != 'SPARK' and spark_col_name in master_df.columns:
                df_cross = master_df[[col_name, spark_col_name]].fillna('not-found')
                df_cross[col_name] = df_cross[col_name].apply(para_resultado)
                df_cross[spark_col_name] = df_cross[spark_col_name].apply(para_resultado)
                store['cross_matrix'][atype][tool] = [((df_cross[col_name] == t) & (df_cross[spark_col_name] == s)).sum() for t, s in COMBINACOES_CROSS]

            # --- 5. Métricas por Cenário ---
            for cen in CENARIOS:
                cen_key = cen['key']
                
                # Pular se este cenário exclui RTA e a tool é RTA
                if cen['exclude_rta'] and tool == 'RTA':
                    continue  # mantém None (inicializado acima)
                
                # Aplicar transformação do cenário
                transformed = series.apply(lambda v, ck=cen_key: transformar_cenario(v, ck))
                
                # Determinar máscara de validade
                if row_masks_cenario.get(cen_key) is not None:
                    # Cenários com remoção (c3, c4, c6, c7): usar máscara por LINHA
                    # A linha é removida se QUALQUER tool da análise tem timeout removível
                    row_mask = row_masks_cenario[cen_key]
                    valid_mask = row_mask & ~series.isin(['not-found', 'error'])
                else:
                    # Cenários sem remoção (c1, c2, c5): filtrar por célula
                    valid_mask = transformed.notna() & ~transformed.isin(['not-found', 'error'])
                
                df_cen = master_df[valid_mask].copy()
                pred = transformed[valid_mask]
                
                if len(df_cen) == 0:
                    store_cenarios[cen_key]['mat'][atype][tool] = [0, 0, 0, 0, 0]
                    store_cenarios[cen_key]['met'][atype][tool] = [0, 0, 0, 0]
                    store_cenarios[cen_key]['stats'][atype][tool] = ["-", "-", "-"]
                    continue
                
                tp, fp, tn, fn, p, r, a, f1 = calc_stats(df_cen['GT_BOOL'], pred == 'TRUE')
                store_cenarios[cen_key]['mat'][atype][tool] = [tp, fp, tn, fn, len(df_cen)]
                store_cenarios[cen_key]['met'][atype][tool] = [p, r, a, f1]
                
                # McNemar vs SPARK
                if spark_col_name in master_df.columns:
                    if col_name == spark_col_name:
                        store_cenarios[cen_key]['stats'][atype][tool] = ["1.0", "0.0", "Same"]
                    else:
                        # Transformar SPARK com a mesma lógica do cenário
                        spark_series = master_df[spark_col_name].fillna('not-found')
                        spark_transformed = spark_series.apply(lambda v, ck=cen_key: transformar_cenario(v, ck))
                        
                        # Usar mesma lógica de máscara para SPARK
                        if row_masks_cenario.get(cen_key) is not None:
                            spark_valid = row_masks_cenario[cen_key] & ~spark_series.isin(['not-found', 'error'])
                        else:
                            spark_valid = spark_transformed.notna() & ~spark_transformed.isin(['not-found', 'error'])
                        
                        common_mask = valid_mask & spark_valid
                        if common_mask.sum() > 0:
                            df_common = master_df[common_mask]
                            pred_tool = transformed[common_mask] == 'TRUE'
                            pred_spark = spark_transformed[common_mask] == 'TRUE'
                            
                            correct_tool = (pred_tool == df_common['GT_BOOL'])
                            correct_spark = (pred_spark == df_common['GT_BOOL'])
                            
                            store_cenarios[cen_key]['stats'][atype][tool] = calcular_mcnemar(correct_tool, correct_spark)
                        else:
                            store_cenarios[cen_key]['stats'][atype][tool] = ["-", "-", "-"]
                else:
                    store_cenarios[cen_key]['stats'][atype][tool] = ["-", "-", "-"]

        # --- IMPACTO ---
        spark_vals = store['counts'][atype].get('SPARK')
        if spark_vals:
            for tool in TOOLS_DIRS:
                if tool == 'SPARK': continue
                tool_vals = store['counts'][atype].get(tool)
                if not tool_vals: continue
                diff_list = []
                for i in range(len(spark_vals)):
                    diff = spark_vals[i] - tool_vals[i]
                    pct = (diff / tool_vals[i] * 100) if tool_vals[i] != 0 else 0.0
                    diff_list.append((diff, pct))
                store['impact'][atype][tool] = diff_list

    # Exportar
    if audit_list: pd.concat(audit_list, ignore_index=True).to_csv(NOME_ARQUIVO_DEBUG, index=False, sep=';')
    if loss_list: pd.concat(loss_list, ignore_index=True).to_csv(NOME_ARQUIVO_LOSS, index=False, sep=';')

    # Gerar PDF
    try:
        if not any(store['counts']['icf']): return

        pdf = AdvancedPDF(orientation='L', unit='mm', format='A4')
        groups = [('icf', (240, 160, 160)), ('ioa', (255, 245, 180)), ('idfp', (180, 230, 180)), ('or all', (200, 220, 255))]
        
        # ===== Pagina 1: Visão Geral =====
        pdf.add_page()
        pdf.chapter_title("Visao Geral e Divergencias")
        pdf.draw_grouped_table("1a. Contagem de Resultados (Detalhada)", store['counts'],
                               ['TRUE', 'FALSE', 'TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout', 'error', 'not-found', 'TOTAL'], groups)
        pdf.ln(2)
        pdf.draw_impact_table("1b. Efeito do SPARK (SPARK - TOOL)", store['impact'],
                              ['TRUE', 'FALSE', 'TRUE_TIMEOUT', 'FALSE_TIMEOUT', 'timeout'], groups)
        pdf.ln(2)
        pdf.draw_grouped_table("2. Casos Perdidos (Tool=True, GT=True, SPARK!=True)", store['spark_loss'], ['Qtd. Casos'], groups)
        pdf.ln(2)
        pdf.draw_grouped_table("3. Divergencia em relacao ao SPARK", store['diff_spark'], ['Total Divergencias', '% Divergencia'], groups)
        
        pdf.ln(2)
        pdf.draw_grouped_table("4. Significancia Estatistica (Divergencia de Saida)", store['stats_divergence'],
                               ['P-Value', 'Statistic (Chi2)', 'Significativo (p<0.05)?'], groups)
        pdf.draw_legend("Nota: O Teste de McNemar acima avalia se as DISCORDANCIAS nas saidas (Tabela 3) sao sistematicas, independente se estao corretas ou nao. TRUE_TIMEOUT/FALSE_TIMEOUT sao tratados como TRUE/FALSE (resultado).")
        
        # ===== Paginas 2-8: Um cenário por página =====
        for cen in CENARIOS:
            cen_key = cen['key']
            cen_title = cen['title']
            cen_desc = cen['desc']
            tools_cen = [t for t in TOOLS_DIRS if not (cen['exclude_rta'] and t == 'RTA')]
            
            pdf.add_page()
            pdf.chapter_title(cen_title)
            pdf.draw_legend(f"Regra: {cen_desc}")
            
            # Preparar dados filtrados para as tools deste cenário
            mat_data = store_cenarios[cen_key]['mat']
            met_data = store_cenarios[cen_key]['met']
            stats_data = store_cenarios[cen_key]['stats']
            
            pdf.draw_grouped_table("Matriz Confusao", mat_data,
                                   ['TRUE POSITIVE', 'FALSE POSITIVE', 'TRUE NEGATIVE', 'FALSE NEGATIVE', 'Total Amostra'],
                                   groups, tools=tools_cen)
            pdf.draw_grouped_table("Metricas de Desempenho", met_data,
                                   ['Precision', 'Recall', 'Accuracy', 'F1 Score'],
                                   groups, tools=tools_cen)
            
            pdf.ln(2)
            pdf.draw_grouped_table("Significancia Estatistica vs SPARK (Corretude/Acuracia)", stats_data,
                                   ['P-Value', 'Statistic (Chi2)', 'Significativo (p<0.05)?'],
                                   groups, tools=tools_cen)
            pdf.draw_legend("Nota: Avalia se a diferenca na ACURACIA (Corretude) em relacao ao SPARK e estatisticamente significativa (McNemar). Se SIM, as metricas acima diferem estatisticamente.")

        # ===== Última Página: Cross Matrix =====
        pdf.add_page()
        pdf.chapter_title("Detalhamento Cruzado (TOOL vs SPARK)")
        pdf.draw_legend("Valores normalizados pelo resultado: TRUE_TIMEOUT = TRUE, FALSE_TIMEOUT = FALSE")
        pdf.draw_cross_matrix_table('icf', store['cross_matrix']['icf'])
        pdf.draw_cross_matrix_table('ioa', store['cross_matrix']['ioa'])
        pdf.draw_cross_matrix_table('idfp', store['cross_matrix']['idfp'])

        pdf.output(NOME_RELATORIO)
        logger.info(f"Relatorio salvo: {NOME_RELATORIO}")

    except Exception as e:
        logger.error(f"Erro salvando PDF: {e}")

if __name__ == "__main__":
    main()