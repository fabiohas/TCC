#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[1/6] Subindo stack Docker..."
docker compose up --build -d

echo "[2/6] Limpando dados anteriores para demo reprodutivel..."
docker compose exec -T mysql mysql -u tcc_user -ptcc_password -D tcc_localiza -e "DELETE FROM reclamacoes_classificadas; DELETE FROM raw_reclamacoes;"

echo "[3/6] Executando scraper (modo apresentacao: 1 pagina)..."
docker compose exec -T airflow-webserver env SCRAPER_MAX_PAGINAS=5 python -c "from src.scraper.scraper import main; main()"

echo "[4/6] Executando classificador..."
docker compose exec -T airflow-webserver python -c "from src.classificador.classificador import main; main()"

echo "[5/6] Validando resultados no MySQL..."
docker compose exec -T mysql mysql -u tcc_user -ptcc_password -D tcc_localiza -e "SELECT COUNT(*) AS total_raw FROM raw_reclamacoes; SELECT COUNT(*) AS total_classificada FROM reclamacoes_classificadas; SELECT id, raw_reclamacao_id, external_id, motivo_principal, etapa_jornada FROM reclamacoes_classificadas ORDER BY id DESC LIMIT 10;"

echo "[6/6] Dashboard:"
dashboard_port=8501
for p in 8501 8502 8503 8504 8505; do
	if ! lsof -iTCP:"$p" -sTCP:LISTEN -n >/dev/null 2>&1; then
		dashboard_port="$p"
		break
	fi
done

echo "Subindo dashboard em background com MYSQL_HOST=localhost na porta ${dashboard_port}..."
MYSQL_HOST=localhost MYSQL_PORT=3306 /opt/anaconda3/bin/streamlit run src/dashboard/dashboard.py --server.headless true --server.port "${dashboard_port}" >/tmp/tcc_dashboard.log 2>&1 &

sleep 3
if curl -sI "http://localhost:${dashboard_port}" | head -n 1 | grep -q "200"; then
	echo "Dashboard online: http://localhost:${dashboard_port}"
else
	echo "Dashboard pode estar iniciando. Veja logs em /tmp/tcc_dashboard.log"
	echo "Tente abrir: http://localhost:${dashboard_port}"
fi
