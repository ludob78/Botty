FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Use PORT env at runtime (default 8000)
ENV PORT=8000
EXPOSE 8000

# Run with 0.0.0.0 so the server is reachable from outside the container
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
