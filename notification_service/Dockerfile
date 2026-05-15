FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# WORKER_MODE=1 starts the consumer; default starts the API.
CMD ["sh", "-c", "if [ \"$WORKER_MODE\" = \"1\" ]; then python -m worker.main; else uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1; fi"]
