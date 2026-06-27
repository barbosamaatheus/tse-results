import pandas as pd

spark = pd.read_csv('casos_perdidos_pelo_spark.csv', sep=';')
res = pd.read_csv('missref/OA/CHA/scenario_conflict_match_result.csv', sep=';')

# Normalizar métodos
spark['method_norm'] = spark['method'].apply(lambda x: x.split('(')[0].strip() if pd.notna(x) else '')
res['method_norm'] = res['method'].apply(lambda x: x.split('(')[0].strip() if pd.notna(x) else '')

# Filtrar res para ConflictPathHasMissReference == True
res_true = res[res['ConflictPathHasMissReference'] == True]

# Checar quantos dos 40 estao no SPARK
merged = pd.merge(res_true, spark, left_on=['merge commit', 'method_norm'], right_on=['merge commit', 'method_norm'], how='left')
print('Total True no Result:', len(res_true))
print('Desses, quantos estao no SPARK perdidos:', merged['GT'].notna().sum())
print('\nExtra matches (nao estao no SPARK):')
extra = merged[merged['GT'].isna()]
for _, row in extra.iterrows():
    print(f"{row['project']} - {row['merge_commit']} - {row['method_x']}")
