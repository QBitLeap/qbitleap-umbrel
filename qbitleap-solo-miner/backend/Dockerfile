FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/main.py backend/qbit.py backend/config.py backend/permissionless_telemetry.py ./
COPY scripts/init-qbit-config.sh /usr/local/bin/init-qbit-config.sh

RUN chmod +x /usr/local/bin/init-qbit-config.sh

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
