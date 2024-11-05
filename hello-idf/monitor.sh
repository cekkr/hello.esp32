CUR_DIR=$(pwd)

cd "$IDF_PATH"
# Salva la directory corrente di IDF_PATH
IDF_PWD=$(pwd)  

. ./export.sh

# Torna alla directory di IDF_PATH (potrebbe essere stata modificata da export.sh)
cd "$IDF_PWD" 
cd "$CUR_DIR"

idf.py monitor