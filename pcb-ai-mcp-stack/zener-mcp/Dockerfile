FROM python:3.12-slim

RUN apt-get update && apt-get install -y git curl build-essential \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && export PATH="/root/.cargo/bin:${PATH}" \
    && cargo install --git https://github.com/diodeinc/pcb pcb \
    && apt-get purge -y git curl build-essential && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV PATH="/root/.cargo/bin:${PATH}"
CMD ["python", "server.py"]
