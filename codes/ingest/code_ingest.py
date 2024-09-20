import ast
from langchain_openai import OpenAIEmbeddings
import os
from langchain_community.vectorstores import FAISS

# 解析并提取函数信息的类
class ClassAndFunctionVisitor(ast.NodeVisitor):
    def __init__(self, module_name):
        self.module_name = module_name
        self.functions_data = []

    def visit_ClassDef(self, node):
        class_name = node.name
        for class_body_node in node.body:
            if isinstance(class_body_node, ast.FunctionDef):
                self.visit_FunctionDef(class_body_node, class_name=class_name)

    def visit_FunctionDef(self, node, class_name=None):
        func_name = node.name
        func_docstring = ast.get_docstring(node) or func_name
        func_args = [arg.arg for arg in node.args.args]
        
        # 将函数信息存储为元数据
        function_metadata = {
            "function_name": func_name,
            "args": func_args,
            "class_name": class_name or "GLOBAL",
            "module_name": self.module_name
        }
        
        # 将元数据和向量存储
        self.functions_data.append((func_docstring, function_metadata))

# 解析Python文件，提取函数信息并生成向量
def parse_python_file(file_path):
    # 从文件路径中提取模块名称（文件名去掉扩展名）
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    
    with open(file_path, "r", encoding="utf-8") as file:
        tree = ast.parse(file.read(), filename=file_path)
    
    visitor = ClassAndFunctionVisitor(module_name)
    visitor.visit(tree)
    return visitor.functions_data

if __name__ == "__main__":
    # 替换为你要分析的 Python 文件路径
    functions_data = parse_python_file("C:/Soc/soc_auto_case/operation_tools/multiplayer_op.py")

    vector_store = FAISS.from_texts(
        texts=[func_docstring for func_docstring, _ in functions_data],
        embedding=OpenAIEmbeddings(model = "text-embedding-3-large"),
        metadatas=[metadata for _, metadata in functions_data]
    )

    vector_store.save_local("./data/faiss_index/multiplayer_op")