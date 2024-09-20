import os

# 设置环境变量
os.environ['LANGCHAIN_TRACING_V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_PROJECT'] = 'code_assist'  # 如果未指定，默认为"default"

import logging
# 配置全局 logger
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

# 创建控制台处理程序并设置日志格式
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 将处理程序添加到 logger 中
logger.addHandler(console_handler)

api_db_path = "./data/faiss_index/multiplayer_op"