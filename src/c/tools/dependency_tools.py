# dependency_tools.py
import os
import pandas as pd
import tomli as toml
import re
import ast
import yaml
import sys
import importlib.util
from crewai.tools import tool
def is_builtin_module(module_name):
    return module_name in sys.builtin_module_names or importlib.util.find_spec(module_name) is None

def split_dependency(dep):
    match = re.match(r"([\w\-]+)(?:\[[^\]]+\])?([<>=~!]\s[\d\w\.\*]+)?(;.+)?", dep.strip())
    if match:
        package = match.group(1)
        version = (match.group(2) or "").strip()
        condition = (match.group(3) or "").strip()
        if condition:
            version = f"{version} {condition}".strip()
        return package, version if version else "Unknown"
    return dep, "Unknown"

def parse_setup_py(file_path):
    with open(file_path, 'r') as file:
        setup_content = file.read()
    setup_ast = ast.parse(setup_content)
    install_requires = []
    for node in ast.walk(setup_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'setup':
            for keyword in node.keywords:
                if keyword.arg == 'install_requires' and isinstance(keyword.value, ast.List):
                    install_requires.extend(
                        item.s for item in keyword.value.elts if isinstance(item, ast.Str)
                    )
    return [(file_path,) + split_dependency(dep) for dep in install_requires]

def extract_pipfile_dependencies(pipfile_path):
    dependencies = []
    try:
        pipfile_data = toml.load(pipfile_path)
        for section in ["packages", "dev-packages"]:
            if section in pipfile_data:
                for package, version in pipfile_data[section].items():
                    package, version = split_dependency(f"{package}{version}")
                    dependencies.append((pipfile_path, package, version))
    except Exception as e:
        print(f"Error reading Pipfile {pipfile_path}: {e}")
    return dependencies

def extract_pyproject_dependencies(pyproject_path):
    dependencies = []
    try:
        pyproject_data = toml.load(pyproject_path)
        if "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
            poetry_data = pyproject_data["tool"]["poetry"]
            for section in ["dependencies", "dev-dependencies"]:
                if section in poetry_data:
                    for package, version in poetry_data[section].items():
                        package, version = split_dependency(f"{package}{version}")
                        dependencies.append((pyproject_path, package, version))
        elif "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
            for dep in pyproject_data["project"]["dependencies"]:
                package, version = split_dependency(dep)
                dependencies.append((pyproject_path, package, version))
    except Exception as e:
        print(f"Error reading pyproject.toml {pyproject_path}: {e}")
    return dependencies

def extract_poetry_lock_dependencies(poetry_lock_path):
    dependencies = []
    try:
        with open(poetry_lock_path, "r", encoding="utf-8") as file:
            poetry_lock_data = toml.load(file)
        for package in poetry_lock_data.get("package", []):
            name = package.get("name", "")
            version = package.get("version", "Unknown")
            dependencies.append((poetry_lock_path, name, version))
    except Exception as e:
        print(f"Error reading poetry.lock {poetry_lock_path}: {e}")
    return dependencies

def get_conda_dependencies(env_file):
    dependencies = []
    try:
        with open(env_file, "r") as f:
            env_data = yaml.safe_load(f)
            for dep in env_data.get("dependencies", []):
                if isinstance(dep, str):
                    package, version = split_dependency(dep)
                    dependencies.append((env_file, package, version))
                elif isinstance(dep, dict) and "pip" in dep:
                    for pip_dep in dep["pip"]:
                        package, version = split_dependency(pip_dep)
                        dependencies.append((env_file, package, version))
    except Exception as e:
        print(f"Error reading Conda environment file {env_file}: {e}")
    return dependencies

def get_pip_dependencies(requirements_file):
    dependencies = []
    try:
        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    package, *version = line.split("==")
                    dependencies.append((requirements_file, package.strip(), version[0].strip() if version else "Unknown"))
    except Exception as e:
        print(f"Error reading requirements.txt {requirements_file}: {e}")
    return dependencies

def extract_python_file_dependencies(project_path, python_version):
    dependencies = set()
    pattern = re.compile(r"^\s*(?:import|from)\s+([\w\d_\.]+)")
    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            match = pattern.match(line)
                            if match:
                                module = match.group(1).split(".")[0]
                                if not is_builtin_module(module):
                                    dependencies.add((file_path, module, python_version))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return list(dependencies)

def find_file(root_path, filename):
    for root, _, files in os.walk(root_path):
        if filename in files:
            return os.path.join(root, filename)
    return None

# 🧠 CREWAI TOOL FUNCTION
@tool
def extract_project_dependencies(project_path: str) -> str:
    """
    Extract dependencies from all common dependency files and source code within a Python project directory.
    
    Args:
        project_path (str): The root path of the Python project.
        
    Returns:
        str: Path to the generated CSV file containing all dependencies.
    """
    dependency_files = {
        "pyproject.toml": extract_pyproject_dependencies,
        "poetry.lock": extract_poetry_lock_dependencies,
        "Pipfile": extract_pipfile_dependencies,
        "environment.yml": get_conda_dependencies,
        "requirements.txt": get_pip_dependencies,
        "setup.py": parse_setup_py,
    }

    all_dependencies = []

    for filename, extractor in dependency_files.items():
        file_path = find_file(project_path, filename)
        if file_path:
            try:
                all_dependencies.extend(extractor(file_path))
            except Exception as e:
                print(f"Error extracting from {filename}: {e}")

    all_dependencies.extend(extract_python_file_dependencies(project_path, "Python"))

    # Save to CSV
    csv_file = os.path.join(project_path, "all_dependencies_with_paths.csv")
    df = pd.DataFrame(all_dependencies, columns=["Source Path", "Package", "Version"])
    df.to_csv(csv_file, index=False)

    return f"Dependencies extracted and saved to {csv_file}"