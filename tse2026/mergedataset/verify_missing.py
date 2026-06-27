import pandas as pd
spark = pd.read_csv('casos_perdidos_pelo_spark.csv', sep=';')
res = pd.read_csv('missref/OA/CHA/scenario_conflict_match_result.csv', sep=';')
spark['method_norm'] = spark['method'].apply(lambda x: x.split('(')[0].strip() if pd.notna(x) else '')
res['method_norm'] = res['method'].apply(lambda x: x.split('(')[0].strip() if pd.notna(x) else '')
merged = pd.merge(spark, res, left_on=['merge commit', 'method_norm'], right_on=['merge commit', 'method_norm'], how='left')
missing = merged[merged['ConflictPathHasMissReference'] != True]
for _, row in missing.iterrows():
    print(f"Faltando: {row['merge commit']} - {row['method_norm']}")
