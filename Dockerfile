FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python","paper_runner.py","--csv","data/sample_ohlcv.csv","--symbol","DEMO","--interval","5"]
