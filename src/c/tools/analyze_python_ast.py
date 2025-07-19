# analyze_python_ast.py
import ast
import os
from fpdf import FPDF
from crewai.tools import tool  # ✅ CrewAI tool decorator

class ImportUsageVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.usage = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module
        for alias in node.names:
            self.imports.append((f"{module}.{alias.name}", node.lineno))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            full_name = f"{node.value.id}.{node.attr}"
            self.usage.append((full_name, node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node):
        self.generic_visit(node)  # ✅ Let NodeVisitor handle it naturally

def analyze_repo(repo_path):
    results = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.normpath(os.path.join(root, file))
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=file_path)
                        visitor = ImportUsageVisitor()
                        visitor.visit(tree)

                        for module, line in visitor.imports:
                            results.append((file_path, "import", module, line))

                        for symbol, line in visitor.usage:
                            results.append((file_path, "usage", symbol, line))

                    except Exception as e:
                        results.append((file_path, "error", str(e), -1))
    return results

def generate_pdf_report(results, output_file="ast_report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Python Import and Usage Report", ln=True, align='C')
    for file_path, category, symbol, line in results:
        line_str = f"{file_path} | {'IMPORT' if category.lower() == 'import' else 'USAGE'} | {symbol} | Line: {line}"

        pdf.cell(200, 10, txt=line_str, ln=True)

    pdf.output(output_file)
    return output_file

# 🧠 CREWAI TOOL FUNCTION
@tool
def generate_ast_usage_pdf(project_path: str) -> str:
    """
    Analyze Python imports and usage in source code and generate a PDF report.

    Args:
        project_path (str): Path to the Python project.

    Returns:
        str: Path to the generated PDF file.
    """
    print(f"🔍 Scanning project: {project_path}")
    results = analyze_repo(project_path)
    output_pdf = os.path.join(project_path, "ast_report.pdf")
    generate_pdf_report(results, output_pdf)
    return f"📄 AST usage report saved to: {output_pdf}"
