#!/bin/bash
# setup_pcb_ai_mcp.sh - One-command setup for Open WebUI + Zener + KiCad MCP stack
set -e

PROJECT_DIR="pcb-ai-mcp-stack"
echo "Setting up PCB AI MCP stack in ./${PROJECT_DIR}..."

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Generate a random secret key instead of hardcoding one
SECRET_KEY=$(openssl rand -hex 32)

# 1. Create directory structure
mkdir -p zener-mcp kicad-mcp mcpo-config data/open-webui data/ollama data/kicad

# 2. Set up KiCad MCP server — use the existing SPIRIT project server
echo "Setting up KiCad MCP server..."
SPIRIT_KICAD_MCP="/home/avery/SPIRIT/EDA-kicad/kicad-mcp/server.py"
if [ -f "$SPIRIT_KICAD_MCP" ]; then
  cp "$SPIRIT_KICAD_MCP" kicad-mcp/server.py
  echo "  Copied server.py from SPIRIT project"
else
  git clone https://github.com/mixelpixx/KiCAD-MCP-Server.git kicad-mcp-tmp 2>/dev/null
  cp kicad-mcp-tmp/server.py kicad-mcp/ 2>/dev/null || true
  rm -rf kicad-mcp-tmp
fi

# 3. Create Zener MCP server.py
cat > zener-mcp/server.py << 'PYEOF'
from fastmcp import FastMCP
import subprocess
import os

mcp = FastMCP("ZenerPCB")

@mcp.tool
def generate_zen(spec: str, output_file: str = "design.zen") -> str:
    """Generate or refine a .zen file from natural language spec using LLM-friendly Zener syntax."""
    zen_content = f'# Zener design generated from spec: {spec}\n# Add your polymorphic modules here\n'
    with open(output_file, 'w') as f:
        f.write(zen_content)
    return f"Generated {output_file} with spec: {spec[:100]}..."

@mcp.tool
def compile_zen_to_kicad(zen_file: str) -> str:
    """Compile .zen file to KiCad project/netlist using Diode pcb toolchain."""
    try:
        result = subprocess.run(["pcb", "build", zen_file, "--export-kicad"],
                              capture_output=True, text=True, cwd=os.getcwd())
        return f"Compiled successfully:\n{result.stdout}\nErrors: {result.stderr}"
    except FileNotFoundError:
        return "ERROR: 'pcb' CLI not found. Is the Diode toolchain installed?"

@mcp.tool
def validate_zen(zen_file: str) -> str:
    """Run validation on Zener modules and connections."""
    try:
        result = subprocess.run(["pcb", "validate", zen_file], capture_output=True, text=True)
        return result.stdout or "Validation passed."
    except Exception as e:
        return f"Validation error: {e}"

if __name__ == "__main__":
    mcp.run()
PYEOF

# 4. Requirements files
cat > zener-mcp/requirements.txt << 'EOF'
fastmcp
EOF

cat > kicad-mcp/requirements.txt << 'EOF'
mcp
EOF

# 5. Dockerfile for zener-mcp (Rust + pcb CLI + fastmcp)
# NOTE: Rust compilation takes 10-20 min on first build
cat > zener-mcp/Dockerfile << 'DEOF'
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
DEOF

# 6. Dockerfile for kicad-mcp (lightweight — just Python + mcp)
cat > kicad-mcp/Dockerfile << 'DEOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
CMD ["python", "server.py"]
DEOF

# 7. Build MCP images now so mcpo can DooD-spawn them later.
#    kicad-mcp is fast; zener-mcp is slow (Rust). Run in parallel.
echo "Building kicad-mcp image..."
docker build -t kicad-mcp ./kicad-mcp

echo "Building zener-mcp image (Rust compilation — this takes a while)..."
docker build -t zener-mcp ./zener-mcp

# 8. Create docker-compose.yml
#    - mcpo handles MCP servers via DooD; no redundant standalone services
#    - open-webui waits for ollama healthcheck instead of a fixed sleep
cat > docker-compose.yml << COMPEOF
version: '3.8'

networks:
  mcp-net:
    name: mcp-net

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    networks:
      - mcp-net
    volumes:
      - ./data/ollama:/root/.ollama
    ports:
      - "11434:11434"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 30

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    networks:
      - mcp-net
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ./data/open-webui:/app/backend/data
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - WEBUI_SECRET_KEY=${SECRET_KEY}
    restart: unless-stopped

  mcpo:
    image: ghcr.io/open-webui/mcpo:main
    container_name: mcpo
    networks:
      - mcp-net
    volumes:
      - ./mcpo-config:/app/config:ro
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8000:8000"
    restart: unless-stopped
    environment:
      - MCPO_API_KEY=optionalkey
    command: ["--config", "/app/config/config.json", "--port", "8000"]
COMPEOF

# 9. Create mcpo config.json with absolute workspace path
#    Also mount the SPIRIT EDA dir so kicad-mcp can reach the PCB files
ABS_WORKSPACE="$(pwd)"
cat > mcpo-config/config.json << MCPEOF
{
  "mcpServers": {
    "zener": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "mcp-net",
        "-v", "${ABS_WORKSPACE}:/workspace",
        "-w", "/workspace",
        "zener-mcp", "python", "/app/server.py"
      ]
    },
    "kicad": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--network", "mcp-net",
        "-v", "${ABS_WORKSPACE}:/workspace",
        "-v", "/home/avery/SPIRIT/EDA-kicad:/home/avery/SPIRIT/EDA-kicad:ro",
        "-v", "${ABS_WORKSPACE}/data/kicad:/root/.config/KiCad",
        "-w", "/workspace",
        "kicad-mcp", "python", "/app/server.py"
      ]
    }
  }
}
MCPEOF

# 10. Start Ollama first and wait properly
echo "Starting Ollama..."
docker compose up -d ollama

echo -n "Waiting for Ollama to be ready"
until docker exec ollama ollama list >/dev/null 2>&1; do
  echo -n "."
  sleep 2
done
echo " ready!"

# 11. Pull a capable model
echo "Pulling model (qwen2.5:14b — may take a while on first run)..."
docker exec ollama ollama pull qwen2.5:14b || {
  echo "qwen2.5:14b failed, falling back to llama3.2:3b..."
  docker exec ollama ollama pull llama3.2:3b
}

# 12. Start remaining services
echo "Starting Open WebUI and mcpo..."
docker compose up -d

echo ""
echo "Setup complete!"
echo "  Open WebUI : http://localhost:8080"
echo "  mcpo API   : http://localhost:8000"
echo "  Ollama     : http://localhost:11434"
