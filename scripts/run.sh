APP_NAME="NFE Manager"
PORT=8000

if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "=== Iniciando $APP_NAME ==="
echo "Acesse: http://localhost:$PORT"
echo "Pressione Ctrl+C para parar"
echo ""

uvicorn backend.main:app --host 0.0.0.0 --port $PORT --reload
