### Analysis of stack usage:
idf.py --no-ccache build CFLAGS="-fstack-usage"
find build -name "*.su" | xargs cat | sort -n -k2