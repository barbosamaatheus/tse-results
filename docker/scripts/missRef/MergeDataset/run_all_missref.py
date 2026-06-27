"""
Orquestrador para executar os 3 scripts de MissReference para todas as 9 configurações.

Configurações:
  - ICF (CF format) x {CHA, RTA, VTA}
  - IDFP (DF format) x {CHA, RTA, VTA}
  - IOA (OA format) x {CHA, RTA, VTA}

Para cada configuração:
  1. Cria diretório de saída em missref/{OA|DF|CF}/{CG}/
  2. Copia os arquivos de entrada necessários
  3. Executa os 3 scripts na sequência correta

Uso:
  python run_all_missref.py              # Roda todas as 9 configurações
  python run_all_missref.py ICF CHA      # Roda apenas ICF/CHA
  python run_all_missref.py IDFP         # Roda IDFP com CHA, RTA, VTA
"""

import os
import sys
import shutil
import subprocess

# Forçar UTF-8 no stdout para evitar erros de encoding no Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# === Diretório base (onde este script está) ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # mergedataset/

# === Arquivo compartilhado de cenários de merge ===
SOOT_RESULTS_WITH_LINES = os.path.join(SCRIPT_DIR, 'soot-results-with-lines.csv')

# === Mapeamento de análise → formato do out.txt e script correspondente ===
ANALYSIS_MAP = {
    'ICF': {
        'format': 'CF',
        'script2': '2hasMissReferenceOnConflict_CF.py',
        'out_dir': 'icf',
        'output_label': 'CF',
    },
    'IDFP': {
        'format': 'DF',
        'script2': '2hasMissReferenceOnConflict_DF.py',
        'out_dir': 'idfp',
        'output_label': 'DF',
    },
    'IOA': {
        'format': 'OA',
        'script2': '2hasMissReferenceOnConflict.py',
        'out_dir': 'ioa',
        'output_label': 'OA',
    },
}

CG_OPTIONS = ['CHA', 'RTA', 'VTA']


def get_paths(analysis, cg):
    """Retorna os caminhos dos arquivos de entrada para uma configuração."""
    info = ANALYSIS_MAP[analysis]

    out_txt = os.path.join(PROJECT_ROOT, info['out_dir'], cg, 'data1', 'out.txt')
    pa_not_resolve = os.path.join(PROJECT_ROOT, info['out_dir'], 'SPARK', 'data1', 'PANotResolve.csv')
    output_dir = os.path.join(SCRIPT_DIR, info['output_label'], cg)

    return out_txt, pa_not_resolve, output_dir


def setup_working_dir(output_dir, out_txt, pa_not_resolve):
    """
    Cria o diretório de saída e copia os arquivos de entrada necessários.
    Os scripts esperam encontrar estes arquivos no CWD:
      - out.txt
      - PANotResolve.csv
      - soot-results-with-lines.csv
    """
    os.makedirs(output_dir, exist_ok=True)

    # Copiar out.txt
    dest_out = os.path.join(output_dir, 'out.txt')
    if not os.path.exists(dest_out) or os.path.getsize(dest_out) != os.path.getsize(out_txt):
        print(f"  Copiando out.txt ({os.path.getsize(out_txt)} bytes)...")
        shutil.copy2(out_txt, dest_out)
    else:
        print(f"  out.txt já existe e tem o mesmo tamanho, pulando cópia.")

    # Copiar PANotResolve.csv
    dest_pa = os.path.join(output_dir, 'PANotResolve.csv')
    if not os.path.exists(dest_pa) or os.path.getsize(dest_pa) != os.path.getsize(pa_not_resolve):
        print(f"  Copiando PANotResolve.csv ({os.path.getsize(pa_not_resolve)} bytes)...")
        shutil.copy2(pa_not_resolve, dest_pa)
    else:
        print(f"  PANotResolve.csv já existe e tem o mesmo tamanho, pulando cópia.")

    # Copiar soot-results-with-lines.csv
    dest_soot = os.path.join(output_dir, 'soot-results-with-lines.csv')
    if not os.path.exists(dest_soot):
        print(f"  Copiando soot-results-with-lines.csv...")
        shutil.copy2(SOOT_RESULTS_WITH_LINES, dest_soot)
    else:
        print(f"  soot-results-with-lines.csv já existe, pulando cópia.")


def run_script(script_name, working_dir):
    """Executa um script Python no diretório de trabalho especificado."""
    script_path = os.path.join(SCRIPT_DIR, script_name)

    if not os.path.exists(script_path):
        print(f"  ERRO: Script não encontrado: {script_path}")
        return False

    print(f"  Executando: {script_name}")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=working_dir,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )

    if result.returncode != 0:
        stdout_tail = (result.stdout or '')[-500:]
        stderr_tail = (result.stderr or '')[-500:]
        print(f"  ERRO ao executar {script_name}:")
        print(f"  STDOUT: {stdout_tail if stdout_tail else '(vazio)'}")
        print(f"  STDERR: {stderr_tail if stderr_tail else '(vazio)'}")
        return False

    # Mostrar últimas linhas do output
    stdout = result.stdout or ''
    if stdout.strip():
        lines = stdout.strip().split('\n')
        for line in lines[-3:]:
            print(f"    {line}")

    return True


def run_pipeline(analysis, cg):
    """Executa o pipeline completo de 3 scripts para uma configuração."""
    info = ANALYSIS_MAP[analysis]
    out_txt, pa_not_resolve, output_dir = get_paths(analysis, cg)

    print(f"\n{'='*70}")
    print(f"  {analysis} / {cg} (formato {info['format']})")
    print(f"  out.txt:        {out_txt}")
    print(f"  PANotResolve:   {pa_not_resolve}")
    print(f"  Saída:          {output_dir}")
    print(f"{'='*70}")

    # Validar que os arquivos de entrada existem
    if not os.path.exists(out_txt):
        print(f"  ERRO: out.txt não encontrado: {out_txt}")
        return False
    if not os.path.exists(pa_not_resolve):
        print(f"  ERRO: PANotResolve.csv não encontrado: {pa_not_resolve}")
        return False
    if not os.path.exists(SOOT_RESULTS_WITH_LINES):
        print(f"  ERRO: soot-results-with-lines.csv não encontrado: {SOOT_RESULTS_WITH_LINES}")
        return False

    # 1. Preparar diretório de trabalho
    print("\n  [SETUP] Preparando diretório de trabalho...")
    setup_working_dir(output_dir, out_txt, pa_not_resolve)

    # 2. Executar Script 1: outputWithMissReference
    print("\n  [STEP 1/3] 1outputWithMissReference.py")
    if not run_script('1outputWithMissReference.py', output_dir):
        print("  FALHA no Step 1. Continuando para o próximo...")

    # 3. Executar Script 2: hasMissReferenceOnConflict (versão correta do formato)
    print(f"\n  [STEP 2/3] {info['script2']}")
    if not run_script(info['script2'], output_dir):
        print("  FALHA no Step 2. Abortando pipeline para esta configuração.")
        return False

    # 4. Executar Script 3: linkConflictPathHasMissReferenceWithResults
    print("\n  [STEP 3/4] 3linkConflictPathHasMissReferenceWithResults.py")
    if not run_script('3linkConflictPathHasMissReferenceWithResults.py', output_dir):
        print("  FALHA no Step 3.")
        return False

    # 5. Executar Script 3 CountAll: linkConflictPathHasMissReferenceWithResults_CountAll
    print("\n  [STEP 4/4] 3linkConflictPathHasMissReferenceWithResults_CountAll.py")
    if not run_script('3linkConflictPathHasMissReferenceWithResults_CountAll.py', output_dir):
        print("  FALHA no Step 4.")
        return False

    print(f"\n  ✓ Pipeline concluído para {analysis}/{cg}!")
    return True


def main():
    print("="*70)
    print("  MissReference Pipeline Runner")
    print("="*70)

    # Determinar quais configurações rodar
    if len(sys.argv) >= 3:
        # Análise e CG específicos: python run_all_missref.py ICF CHA
        analysis = sys.argv[1].upper()
        cg = sys.argv[2].upper()
        if analysis not in ANALYSIS_MAP:
            print(f"Análise inválida: {analysis}. Opções: {list(ANALYSIS_MAP.keys())}")
            sys.exit(1)
        if cg not in CG_OPTIONS:
            print(f"Call graph inválido: {cg}. Opções: {CG_OPTIONS}")
            sys.exit(1)
        configs = [(analysis, cg)]
    elif len(sys.argv) >= 2:
        # Apenas análise: python run_all_missref.py ICF
        analysis = sys.argv[1].upper()
        if analysis not in ANALYSIS_MAP:
            print(f"Análise inválida: {analysis}. Opções: {list(ANALYSIS_MAP.keys())}")
            sys.exit(1)
        configs = [(analysis, cg) for cg in CG_OPTIONS]
    else:
        # Todas as configurações
        configs = [(a, cg) for a in ANALYSIS_MAP for cg in CG_OPTIONS]

    print(f"\nConfigurações a executar: {len(configs)}")
    for a, cg in configs:
        print(f"  - {a}/{cg} ({ANALYSIS_MAP[a]['format']})")

    # Executar pipelines
    results = {}
    for analysis, cg in configs:
        success = run_pipeline(analysis, cg)
        results[(analysis, cg)] = success

    # Resumo final
    print(f"\n{'='*70}")
    print("  RESUMO")
    print(f"{'='*70}")
    for (analysis, cg), success in results.items():
        status = "✓ OK" if success else "✗ FALHA"
        print(f"  {analysis}/{cg}: {status}")

    failed = sum(1 for v in results.values() if not v)
    if failed:
        print(f"\n  {failed} configuração(ões) falharam.")
        sys.exit(1)
    else:
        print(f"\n  Todas as {len(results)} configurações concluídas com sucesso!")


if __name__ == "__main__":
    main()
