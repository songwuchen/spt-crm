# Stage 1: builder — install build deps + pip packages
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime — only runtime deps
FROM python:3.12-slim

# libpq5: psycopg runtime. fonts-wqy-microhei: CJK font so exported PDFs embed
# Chinese glyphs instead of rendering 乱码 on this fontless slim image (issue #88).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 fonts-wqy-microhei && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

RUN mkdir -p uploads

EXPOSE 8002

ENV LOG_FORMAT=json
ENV LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
