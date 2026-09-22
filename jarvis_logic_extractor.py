import ast
import os

FILES = [
    'part1_FIXED.py', 'part2_FIXED.py', 'part3_FIXED.py', 'part4_FIXED.py',
    'part5_FIXED.py', 'part6_FIXED.py', 'part7_FIXED.py', 'part8_FIXED.py',
    'part9_FIXED.py', 'part10_FIXED.py', 'part11_FIXED.py', 'part12_FIXED.py',
    'jarvis_FIXED.py'
]

BASE_DIR = r'c:\jarvis'
OUTPUT_FILE = os.path.join(BASE_DIR, 'Jarvis_Master_Logic.md')

def extract_logic():
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write("# JARVIS MASTER TRADING LOGIC (RAG KNOWLEDGE BASE)\n\n")
        out.write("This document contains the core institutional trading rules, AI fusion logic, and risk management strategies extracted directly from the Jarvis codebase. It is designed to act as the primary knowledge base for the local Ollama RAG system.\n\n")
        
        for filename in FILES:
            filepath = os.path.join(BASE_DIR, filename)
            if not os.path.exists(filepath):
                continue
                
            out.write(f"## MODULE: {filename}\n\n")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                
                # Extract global configurations (all caps assignments)
                configs = []
                for node in tree.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id.isupper():
                                try:
                                    if isinstance(node.value, ast.Constant):
                                        configs.append(f"- **{target.id}**: {node.value.value}")
                                    elif isinstance(node.value, ast.Dict):
                                        configs.append(f"- **{target.id}**: [Configuration Dictionary]")
                                except:
                                    pass
                
                if configs:
                    out.write("### System Configurations & Risk Limits\n")
                    out.write("\n".join(configs) + "\n\n")
                
                # Extract Brains and Strategy Logic (Classes)
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        docstring = ast.get_docstring(node)
                        # We only care about major engines/brains/validators
                        if any(k in node.name for k in ['Brain', 'Engine', 'Master', 'Validator', 'AI', 'System', 'Predictor', 'Detector']):
                            out.write(f"### Component: {node.name}\n")
                            if docstring:
                                out.write(f"{docstring}\n\n")
                            else:
                                out.write(f"Handles specific market analysis and logic for {node.name}.\n\n")
                                
                            # Extract key methods like analyze, detect, calculate
                            for method in node.body:
                                if isinstance(method, ast.FunctionDef):
                                    if any(keyword in method.name for keyword in ['detect', 'calculate', 'analyze', 'fuse', 'validate', 'generate', 'template', 'predict', 'size', 'risk']):
                                        mdoc = ast.get_docstring(method)
                                        if mdoc:
                                            # Clean up docstring
                                            mdoc_clean = mdoc.strip().replace('\n', ' ')
                                            out.write(f"- **Rule/Logic ({method.name})**: {mdoc_clean}\n")
                                        else:
                                            # If no docstring, just note the capability
                                            out.write(f"- **Capability**: System can {method.name.replace('_', ' ').strip()}\n")
                            out.write("\n")
                            
            except Exception as e:
                out.write(f"> Error parsing {filename}: {str(e)}\n\n")
                
    print(f"Successfully extracted Jarvis logic to {OUTPUT_FILE}")

if __name__ == "__main__":
    extract_logic()
