import ast

# 读取operator.py文件的内容
with open('operation.py', 'r', encoding='utf-8') as file:
    file_content = file.read()

# 解析文件内容，生成AST（抽象语法树）
tree = ast.parse(file_content)

# 定义一个函数，用于提取并打印所有函数名称及其 docstring
def list_functions_with_docstrings(node):
    functions = []
    # 遍历语法树的所有节点
    for child in ast.walk(node):
        # 检查节点是否为函数定义
        if isinstance(child, ast.FunctionDef):
            # 获取函数名称
            func_name = child.name
            # 获取函数的 docstring（如果有）
            docstring = ast.get_docstring(child)
            functions.append((func_name, docstring))
    return functions

# 获取并打印所有函数的名称和 docstring
functions = list_functions_with_docstrings(tree)
print("Functions and their docstrings found in the file:")
for func_name, docstring in functions:
    print(f"Function: {func_name}")
    print(f"Docstring: {docstring if docstring else 'No docstring available'}")
    print('-' * 40)
