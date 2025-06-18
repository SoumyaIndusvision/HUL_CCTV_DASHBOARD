import sqlite3
import pandas as pd

# Path to your SQLite database file
db_path = '/home/HUL_CCTV_DASHBOARD/db.sqlite3'

# Table you want to export
table_name = 'Cameras'  # Use actual table name in your DB

# Output Excel file name
output_excel = '/mnt/c/Users/Soumya/Downloads/camera_info.xlsx'

# Connect to SQLite and fetch table
conn = sqlite3.connect(db_path)
df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
conn.close()

# Save to Excel
df.to_excel(output_excel, index=False)

print(f"Exported {len(df)} rows from '{table_name}' to {output_excel}")
