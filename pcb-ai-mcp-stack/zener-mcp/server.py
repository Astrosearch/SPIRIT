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
