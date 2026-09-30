# 1. Start from an official image that already has Python 3.12
FROM python:3.12-slim

# 2. Work inside /app in the container
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# 3. Install libraries first. Docker caches each step, so as long as
#    requirements.txt doesn't change, rebuilds skip this slow part.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the code (minus everything in .dockerignore)
COPY . .

# 5. Store the database in /data (a volume will be mounted there)
ENV WORKSHOP_DB_PATH=/data/workshop.db
RUN mkdir -p /data

# 6. Document that the app listens on port 8000
EXPOSE 8000

# 7. The command that runs when the container starts
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]