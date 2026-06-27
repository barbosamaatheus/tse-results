# -*- coding: utf-8 -*-
"""
Script para extrair e comparar os resultados dos 7 cenarios,
focando em FP reduction do SPARK vs CHA/RTA/VTA.
Salva output em arquivo para evitar problemas de encoding no console.
"""
import pandas as pd
import numpy as np
import os
import sys

sys.path.insert(0, '.')
from mds_results import *

def main():
    # 1. Carregar GT
    df_gt = pd.read_csv(ARQUIVO_GT, sep=DELIMITADOR_GT, dtype=str, on_bad_lines='skip')
    df_gt.dropna(how='all', axis=1, inplace=True)
    df_gt.columns = [c.strip() for c in df_gt.columns]
    df_gt = filtrar_blacklist(df_gt)
    df_gt['GT_BOOL'] = df_gt[COLUNA_GT_ALVO].apply(lambda x: True if normalizar_valor(x) == 'TRUE' else False)

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
            except: pass

    for tool in TOOLS_DIRS:
        col_icf, col_ioa, col_idfp = f"{tool}_icf", f"{tool}_ioa", f"{tool}_idfp"
        s_or = master_df.apply(lambda r: combinar_or([
            r[col_icf] if col_icf in master_df.columns else 'not-found',
            r[col_ioa] if col_ioa in master_df.columns else 'not-found',
            r[col_idfp] if col_idfp in master_df.columns else 'not-found'
        ]), axis=1)
        master_df[f"{tool}_or all"] = s_or

    # 3. Salvar em arquivo
    out = open('analise_output.txt', 'w', encoding='utf-8')
    
    analises = ['icf', 'ioa', 'idfp', 'or all']
    
    # CSV consolidado para facil verificacao
    csv_rows = []
    
    for atype in analises:
        out.write(f"\n{'='*120}\n")
        out.write(f"  ANALISE: {atype.upper()}\n")
        out.write(f"{'='*120}\n")
        
        for cen in CENARIOS:
            cen_key = cen['key']
            tools_cen = [t for t in TOOLS_DIRS if not (cen['exclude_rta'] and t == 'RTA')]
            
            # Pre-computar mascara de linha para cenarios de remocao
            row_mask = None
            if cen_key in ('c3', 'c4', 'c6', 'c7'):
                row_mask = pd.Series(True, index=master_df.index)
                for t in tools_cen:
                    col = f"{t}_{atype}"
                    if col not in master_df.columns: continue
                    s = master_df[col].fillna('not-found')
                    t_transformed = s.apply(lambda v, ck=cen_key: transformar_cenario(v, ck))
                    row_mask = row_mask & t_transformed.notna()
            
            out.write(f"\n  --- {cen['title']} ---\n")
            out.write(f"  {cen['desc']}\n")
            out.write(f"  {'Tool':<8} {'TP':>5} {'FP':>5} {'TN':>5} {'FN':>5} {'N':>5} | {'Prec':>7} {'Rec':>7} {'Acc':>7} {'F1':>7} | {'FPR':>7}\n")
            out.write(f"  {'-'*90}\n")
            
            for tool in tools_cen:
                col_name = f"{tool}_{atype}"
                if col_name not in master_df.columns: continue
                
                series = master_df[col_name].fillna('not-found')
                transformed = series.apply(lambda v, ck=cen_key: transformar_cenario(v, ck))
                
                if row_mask is not None:
                    valid_mask = row_mask & ~series.isin(['not-found', 'error'])
                else:
                    valid_mask = transformed.notna() & ~transformed.isin(['not-found', 'error'])
                
                df_cen = master_df[valid_mask]
                pred = transformed[valid_mask]
                
                if len(df_cen) == 0: continue
                
                tp, fp, tn, fn, p, r, a, f1 = calc_stats(df_cen['GT_BOOL'], pred == 'TRUE')
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                
                out.write(f"  {tool:<8} {tp:>5} {fp:>5} {tn:>5} {fn:>5} {len(df_cen):>5} | {p:>7.4f} {r:>7.4f} {a:>7.4f} {f1:>7.4f} | {fpr:>7.4f}\n")
                
                csv_rows.append({
                    'Cenario': cen['title'],
                    'CenKey': cen_key,
                    'Analise': atype,
                    'Tool': tool,
                    'TP': int(tp), 'FP': int(fp), 'TN': int(tn), 'FN': int(fn),
                    'N': len(df_cen),
                    'Precision': round(p, 4),
                    'Recall': round(r, 4),
                    'Accuracy': round(a, 4),
                    'F1': round(f1, 4),
                    'FPR': round(fpr, 4)
                })
    
    # Resumo SPARK vs CHA
    out.write(f"\n\n{'='*120}\n")
    out.write(f"RESUMO SPARK vs CHA (Reducao de FP)\n")
    out.write(f"{'='*120}\n\n")
    out.write(f"{'Cenario':<45} | {'Analise':<8} | {'N':>5} | {'FP_CHA':>7} {'FP_SPK':>7} {'Red':>5} {'%Red':>7} | {'Prec_CHA':>9} {'Prec_SPK':>9} {'dPrec':>7}\n")
    out.write(f"{'-'*120}\n")
    
    df_csv = pd.DataFrame(csv_rows)
    
    for cen in CENARIOS:
        for atype in analises:
            cha_row = df_csv[(df_csv['CenKey'] == cen['key']) & (df_csv['Analise'] == atype) & (df_csv['Tool'] == 'CHA')]
            spk_row = df_csv[(df_csv['CenKey'] == cen['key']) & (df_csv['Analise'] == atype) & (df_csv['Tool'] == 'SPARK')]
            
            if len(cha_row) == 0 or len(spk_row) == 0: continue
            
            fp_cha = int(cha_row.iloc[0]['FP'])
            fp_spk = int(spk_row.iloc[0]['FP'])
            red = fp_cha - fp_spk
            pct = (red / fp_cha * 100) if fp_cha > 0 else 0
            p_cha = float(cha_row.iloc[0]['Precision'])
            p_spk = float(spk_row.iloc[0]['Precision'])
            n = int(spk_row.iloc[0]['N'])
            
            out.write(f"{cen['title']:<45} | {atype:<8} | {n:>5} | {fp_cha:>7} {fp_spk:>7} {red:>5} {pct:>6.1f}% | {p_cha:>9.4f} {p_spk:>9.4f} {p_spk-p_cha:>+7.4f}\n")
        out.write(f"{'-'*120}\n")
    
    out.close()
    
    # Salvar CSV para verificacao
    df_csv.to_csv('analise_cenarios_dados.csv', index=False, sep=';', encoding='utf-8')
    
    print("Dados salvos em: analise_output.txt e analise_cenarios_dados.csv")

if __name__ == "__main__":
    main()
