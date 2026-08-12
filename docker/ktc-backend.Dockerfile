FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel
RUN python -m pip install --no-cache-dir --retries 10 --timeout 60 -r requirements.txt

COPY app/ /app/app/

CMD ["uvicorn", "app.main:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8000"]
