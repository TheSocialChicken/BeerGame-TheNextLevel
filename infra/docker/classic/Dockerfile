FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY variants/classic/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY core/ /app/core/
COPY variants/classic/ /app/variants/classic/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "variants.classic.main:app", "--host", "0.0.0.0", "--port", "8000"]
