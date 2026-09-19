FROM node:20-bookworm-slim

# System Python for the tutor engine (sympy / sentence-transformers / anthropic / genai)
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Node backend ---
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# --- Vendored Python tutor engine ---
COPY tutor_engine ./tutor_engine
RUN pip3 install --no-cache-dir --break-system-packages -r tutor_engine/tutor/requirements.txt

ENV TUTOR_ROOT=/app/tutor_engine
ENV PYTHON_PATH=python3
ENV NODE_ENV=production

EXPOSE 3000
CMD ["node", "dist/index.js"]
