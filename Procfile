web: python -m app.check_db --max-attempts 10 --wait-time 10 && python -c 'from app.models import create_tables; create_tables()' && uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: python -m app.check_db --max-attempts 10 --wait-time 10 && python -m celery -A app.tasks worker --loglevel=info
beat: python -m app.check_db --max-attempts 10 --wait-time 10 && python -m celery -A app.tasks beat --loglevel=info
flower: python -m app.check_db --max-attempts 10 --wait-time 10 --skip-db && python -m celery -A app.tasks flower --port=$PORT 