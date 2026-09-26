FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["python", "bitget_live_runner.py", "--symbol", "rAAPLUSDT", "--interval", "15m", "--poll", "20"]