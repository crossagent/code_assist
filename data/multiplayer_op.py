import json
import os
import socket
import subprocess
import threading
import time
import requests
# 默认读取本机的服务
from skywalks_auto.util.tool import make_random_account_uuid

from case_constants import CASE_PROJECT_PATH
from soc_util.soc_tools import send_request, run_cmd


def start_bot_server(branch):
    """

    @return:
    """
    result_dict = {"branch": branch}
    response = send_request("http://192.168.181.52:11451/" + "auto/multiplayer/server_start_process",
                            result_dict)


def get_server_list(is_new=False):
    response = send_request(MultiplayerOperation.auto_server_list_url,
                            {"project_id": 33, "user_uid": "", "is_new": is_new})
    server_info = response.json()
    server_list = server_info["data"]["game_server_list"]
    return server_list


def get_branch_list():
    response = send_request(MultiplayerOperation.auto_server_list_url,
                            {"project_id": 33, "user_uid": ""})
    server_info = response.json()
    branch_list = server_info["data"]["branch"]
    return branch_list


def get_multiplayer_case_info():
    response = send_request(MultiplayerOperation.auto_server_list_url, {"project_id": 33, })
    server_info = response.json()
    account_server_info = server_info["data"]["case_info"]
    return account_server_info


def get_multiplayer_robot_list(server_name):
    """
    根据服务器名获取当前服务器登录的所有机器人信息
    @param server_name:
    @return: {"role_id": role_id, "branch": branch, "account": account, }
    """
    response = send_request(MultiplayerOperation.auto_server_list_url, {"project_id": 33, })
    server_info = response.json()
    bot_info_info = server_info["data"]["bot_info"]
    if server_name in bot_info_info.keys():
        return bot_info_info[server_name]
    return []


def add_multiplayer_server(add_num, branch):
    """
    添加指定数量指定分支的机器人进程
    @param add_num:
    @param branch:
    @return:
    """
    for i in range(add_num):
        response = send_request(MultiplayerOperation.auto_add_server_url, {"branch": branch, })
        server_info = response.json()
        print(server_info)


def login_dev(uid):
    ipAddress = socket.gethostbyname(socket.gethostname())
    result_dict = {
        "deviceInfo": "{\"outerIp\":\"" + ipAddress + "\",\"osSystem\":\"windows\",\"language\":\"zh_CN\",\"scene\":0,\"deviceId\":\"c7f2521f1137e8af5045c2abe0c9d9651fc19dbc\",\"qimei36\":\"\",\"deviceModal\":\"B250M-D2V (Gigabyte Technology Co., Ltd.)\",\"deviceVersion\":\"\",\"deviceManufacturer\":\"unknow\"}",
        "uid": str(uid)}
    response = send_request(f"http://81.69.165.172/login/logindev", result_dict)
    data_json = response.json()
    print(data_json)
    # if data_json["newUser"] == True:
    #     token = data_json["token"]
    #     nickname_result_dict = {
    #         "val": str(uid)}
    #     headers = {}
    #     headers["version"] = "gray"
    #     headers["Authorization"] = "Bearer " + token
    #     nickname_response = requests.post(f"http://81.69.165.172/playerservice/nickname", json=nickname_result_dict,
    #                                       headers=headers)
    #     nickname_data_json = nickname_response.json()
    #     print(nickname_data_json)
    return data_json


def get_role_id(uid):
    data_json = login_dev(uid)
    return data_json["roleId"]


def get_role_token(uid):
    data_json = login_dev(uid)
    return data_json["token"]


def console_tools(server_name, args_str):
    """
    给机器人发送命令行指令
    压测服务器命令行修改参数
    @param server_name:
    @param args_str:
    @return:
    """
    old_path = os.getcwd()
    # 设置新的工作目录
    new_path = os.path.join(CASE_PROJECT_PATH, "soc_server_tools")
    os.chdir(new_path)
    exe_path = os.path.join(CASE_PROJECT_PATH, "soc_server_tools", "SocConsole.exe")
    parameters = ["-k", server_name, "-c", args_str]
    process = subprocess.Popen([exe_path] + parameters, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output, error = process.communicate()
    # 打印程序执行结果
    if process.returncode == 0:
        print("程序执行成功，输出:\n", output)
    else:
        print("程序执行出错，错误信息:\n", error)
    os.chdir(old_path)
    # result_dict = {"funcName": "ConsoleTools", "isCase": True, "branch": self.branch, "project_id": 33,
    #                "funcValue": {"roleId": self.role_id, "server_name": server_name, "args": args_str}}
    # response = soc_util.soc_tools.send_request(MultiplayerOperation.auto_server_multiplayer_run_url, result_dict)
    # return response.json()


def robot_self_run_thread(soc_git_path):
    """
    在本地启动一个机器人服务，只允许调用一次
    @param soc_git_path:本地a4工程路径，到.git文件夹那一层
    @return:
    """
    if not soc_git_path:
        return ""
    is_build = dotnet_self_build_robot(soc_git_path)
    if is_build:
        thread = threading.Thread(target=dotnet_self_robot_run, args=(soc_git_path,))
        thread.start()
        self_ip = socket.gethostbyname(socket.gethostname())
        return self_ip
    return ""


def dotnet_self_build_robot(soc_git_path):
    """
    编译本地环境的机器人工程
    @param soc_git_path:A4\Soc\SocServer\SocWorld\src\SocBotServer
    @return:
    """
    robot_path = os.path.join(soc_git_path, "SocServer", "SocWorld", "src", "SocBotServer")
    net_log_list = []
    run_cmd(
        f'{soc_git_path[:2]} &&cd {robot_path} && dotnet build SocBotServer.csproj --configuration Debug',
        net_log_list)
    print(net_log_list)
    is_build = False
    if len(net_log_list) > 0:
        for net_log in net_log_list:
            if "个错误" in net_log:
                err_str_list = net_log.replace(" ", "").split("个")
                if len(err_str_list) > 1:
                    err_num = int(err_str_list[0])
                    if err_num > 0:
                        print("机器人服务编译失败")
                        return False
                    else:
                        is_build = True
    if is_build:
        cd_path = os.path.join(soc_git_path, "SocCommon", "BotTools")
        exe_path = os.path.join(cd_path, "SocBotServer.exe")
        if os.path.exists(exe_path):
            return True
    print("机器人服务编译失败")
    return False


def dotnet_self_robot_run(soc_git_path):
    """
    执行本地环境的机器人工程
    @param soc_git_path:A4\Soc\SocServer\SocWorld\src\SocBotServer
    @return:
    """
    old_path = os.getcwd()
    cd_path = os.path.join(soc_git_path, "SocCommon", "BotTools")
    exe_path = os.path.join(cd_path, "SocBotServer.exe")
    if os.path.exists(exe_path):
        os.chdir(cd_path)
        # 构造命令字符串
        command = f"\"{exe_path}\""
        # 调用子进程以管理员权限运行 .exe 程序
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout = process.stdout
        if stdout:
            for line in iter(process.stdout.readline, b''):
                try:
                    line = line.decode().rstrip()
                except UnicodeDecodeError:
                    # 有些命令输出的是gbk编码, 需要兼容
                    line = line.decode('gbk').rstrip()
                print(line)
        os.chdir(old_path)
    else:
        print("机器人启动程序不存在，启动失败")


class MultiplayerOperation:
    # auto_server_multiplayer_run_url = "http://192.168.180.55:5885/runCase"
    auto_server_multiplayer_run_url = "http://192.168.181.52:11451/" + "auto/multiplayer/run"
    # 获取服务器列表的
    auto_server_list_url = "http://192.168.181.52:11451/" + "auto/multiplayer/multiplayer_info"
    auto_add_server_url = "http://192.168.181.52:11451/" + "auto/multiplayer/add_multiplayer_server"

    def __init__(self, account=0, branch="new", is_yc=False, run_time=10):
        """

        @param account:
        @param branch:
        @param is_yc:
        @param run_time:
        """
        self.run_time = run_time
        # 指令的url
        branch_list = get_branch_list()
        if "new" in branch:
            branch_name = "trunk"
            if "_new" in branch:
                branch_info_list = branch.split("_new")
                branch_name = branch_info_list[0]
            branch_num_max = 0
            for branch_str in branch_list:
                if "_" in branch_str:
                    branch_str_info_list = branch_str.split("_")
                    if len(branch_str_info_list) == 2:
                        branch_num_str = branch_str_info_list[1]
                    if len(branch_str_info_list) > 2:
                        branch_num_str = branch_str_info_list[2]
                    try:
                        branch_num = int(branch_num_str)
                    except Exception:
                        branch_num = 0
                    if branch_num > branch_num_max and branch_name in branch_str:
                        branch_num_max = branch_num
                        self.branch = branch_str
        else:
            self.branch = branch
        if self.branch not in branch_list:
            raise Exception(f"分支传入错误，不在{branch_list}中")

        if account == 0:
            self.account = make_random_account_uuid()
        else:
            self.account = account
        if is_yc:
            self.role_id = self.account
        else:
            self.role_id = get_role_id(self.account)
        self.login_msg_info = {}

    def start_server(self, server_name, is_ignored=True, is_self=False, soc_git_path="", self_ip="", tcp=True):
        """
        启动一个客户端，需要传入分支、运行时间、账号、服务器，用于机器人工具
        @param server_name: 服务器
        @param is_ignored: 是否获取entity
        @param is_self: 是否在本地启动机器人服务，如果传入是，需要传入soc_git_path
        @param soc_git_path:本地a4工程路径，到.git文件夹那一层
        @param self_ip:自己已经起好服时，直接传入自己的ip和端口
        @param tcp: True/False(kcp连接)
        @return:
        """
        if self.account == "":
            raise Exception("没有设置账号，无法开始用例")

        if is_self and soc_git_path:
            self_ip = robot_self_run_thread(soc_git_path)
            self_ip = f"{self_ip}:5885"
            time.sleep(3)
        result_dict = {"funcName": "Login", "branch": self.branch, "run_time": self.run_time, "project_id": 33,
                       "isCase": False,
                       "funcValue": {"roleId": self.role_id, "account": self.account, "server_name": server_name,
                                     "is_ignored": is_ignored, "tcp": tcp,
                                     "campId": 0, "user_uid": self.account}, "bot_server": self_ip, }
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        self.login_msg_info = response.json()
        print(self.login_msg_info)
        print(self.account, self.branch, server_name)
        return self.login_msg_info

    def run_case(self, case_name, args=None):
        """
        执行一个压测case
        @param case_name: 服务器
        @param args: 压测脚本额外参数
        @return:
        """
        funcValue = {"roleId": self.role_id}
        if args is not None:
            for args_k, args_v in args.items():
                funcValue[args_k] = args_v
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": case_name, "isCase": True,
                       "funcValue": funcValue}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        # response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        response_dic = response.json()
        print(f"用例{case_name}执行完毕")

    def run_cmd(self, cmd_id, frame=30):
        """
        执行一个压测case
        @param cmd_id:
        @param frame:
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "runCmd", "isCase": True,
                       "funcValue": {"roleId": self.role_id, "id": cmd_id, "frame": frame}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        return response.json()

    def case_start(self):
        """
        压测集结点，开始启动
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "CaseStart", "isCase": True,
                       "funcValue": {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        return response.json()

    def stop_server(self):
        """
        关闭当前账号机器人
        @return:
        """
        if self.role_id == "":
            return
        send_dict = {"branch": self.branch, "project_id": 33, "funcName": "outLogin", "isCase": False,
                     "funcValue": {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, send_dict)
        print(response.json())

    def jump(self, yaw):
        """
        跳
        @param yaw:跳的方向
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "Jump", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "yaw": yaw}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def make_part(self, part_path):
        """
        在身前建造一个指定配置的建筑
        @param part_path:建筑配置名
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "RecoverConstruction", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "part_path": part_path}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def add_people_team(self, add_role_id):
        """
        邀请人入队
        @param add_role_id:邀请的人的role id
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "TeamSendInvite_V2", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "role_id": add_role_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def get_info(self):
        """
        获取机器人的信息
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "info", "isCase": False,
                       "funcValue": {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def get_self_entity_id(self):
        """
        获取机器人的entity_id
        @return:
        """
        entity_info_dic = self.get_info()
        for entity_id, entity_info in entity_info_dic.items():
            if entity_info["type"] == "PlayerEntity":
                if entity_info["self"]:
                    return entity_id, True
        return 0, False

    def transmit_to(self, x, y, z, is_ground=True):
        """
        传送到指定的坐标位置
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param is_ground: 是否落到地面
        @return:
        """

        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "TransmitTo", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "x": int(x), "y": int(y), "z": int(z), "isFly": is_ground}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def transmit_to_random(self, x, y, z, random_num: int, is_ground=True):
        """
        传送到指定的坐标位置附近，以x, y, z为中心，以random_num为边长的方型范围
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param is_ground: 是否落到地面
        @param random_num: 坐标随机范围
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "TransmitToRandom", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "x": int(x), "y": int(y), "z": int(z),
                                     "offset_quantity": random_num,
                                     "isFly": is_ground}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move(self, yaw, run_num=5, direction="MoveForward"):
        """
        跑
        @param yaw: 方向，如果方向大于360，会按照当前方向移动
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "Move", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "yaw": yaw, "direction": direction, "runNum": run_num, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move_pos(self, x, y, z, run_num=5, direction="MoveForward"):
        """
        朝指定位置移动
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "MovePos", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "x": x, "y": y, "z": z, "runNum": run_num,
                                     "direction": direction,
                                     }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move_to_pos(self, x, y, z, direction="MoveForward"):
        """
        移动到某个坐标，
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "MoveToPos", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "x": x, "y": y, "z": z, "direction": direction,
                                     }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def use_shortcut_iteam(self, iteam_index: int, un_equip: bool):
        """
        使用快捷栏中的道具
        @param iteam_index:快捷栏编号，从0开始
        @param un_equip :暂时没整明白，先传F
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "UseShortcutIteam", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "index": iteam_index, "unEquip": un_equip}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def gm_add_item(self, resource_name, add_num):
        """
        添加道具
        @param resource_name: 道具的id
        @param add_num: 添加的数量
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "GMAddItem", "isCase": False,
                       "funcValue": {"resource_name": str(resource_name), "roleId": self.role_id,
                                     "add_num": str(add_num), }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def profiler_switch(self, switch: bool):
        """
        开关压测服profiler收集
        @param switch: t是开始收集/f是结束收集
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "ProfilerSwitch", "isCase": False,
                       "funcValue": {"roleId": self.role_id,
                                     "switch": switch, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def kill_monster(self, distance: int):
        """
        杀死身边指定范围内的怪
        @param distance: 范围 -1 杀死全部
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "GMKillMonster", "isCase": False,
                       "funcValue": {"distance": distance, "roleId": self.role_id,
                                     }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def toggle_player_novice(self, is_open: bool):
        """
        让ai持续攻击，f是持续，t是打不过就跑
        @param is_open:
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "GMTogglePlayerNovice", "isCase": False,
                       "funcValue": {"isOpen": is_open, "roleId": self.role_id,
                                     }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def gm_clear_inventory(self, bagType: int):
        """
        清空背包
        @param bagType: 背包的种类
        @return:
        """
        result_dict = {"branch": self.branch, "project_id": 33, "funcName": "GmClearInventory", "isCase": False,
                       "funcValue": {"roleId": self.role_id, "bagType": str(bagType), }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def fire1(self, x: int, y: int, z: int, is_fire_continus: bool, throw: bool, fireNum: int):
        """
        开火
        @param x: 目标坐标
        @param y: 目标坐标
        @param z: 目标坐标
        @param is_fire_continus:是否连续开火 ,手雷火箭筒用F
        @param throw: 是否投掷物
        @return:
        """
        result_dict = {'funcName': 'FireTo', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {'x': x, 'y': y, 'z': z, "roleId": self.role_id,
                                     'isFire1Continus': is_fire_continus, "throw": throw, "fireNum": fireNum}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def fire2(self, ):
        """
        开镜
        @return:
        """
        result_dict = {'funcName': 'Fire2', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def test_summon_monster(self, x: int, y: int, z: int, monster_id: int, call_num: int):
        """
        在指定坐标添加指定数量的指定怪物
        @param x:
        @param y:
        @param z:
        @param monster_id: 怪物id
        @param call_num: 添加的数量
        @return:
        """
        result_dict = {'funcName': 'TestSummonMonster', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {'monster_id': monster_id, "roleId": self.role_id, 'call_num': call_num, 'x': x,
                                     'z': z, 'y': y}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def create_entity(self, entity_type: int, template_id: int, gather_num: int):
        """
        在脸前头加指定数量的指定资源
        @param entity_type: 资源类型
        @param template_id: 资源id
        @param gather_num: 添加的数量
        @return:
        """
        result_dict = {'funcName': 'DebugCheatCreateTheEntityHasCount', "branch": self.branch, "project_id": 33,
                       "isCase": False,
                       'funcValue': {'entity_type': entity_type, "roleId": self.role_id, 'template_id': template_id,
                                     'gather_num': gather_num}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def set_player_damage_disable(self, is_open: bool):
        """
        开关无敌
        @param is_open: T/F
        @return:
        """
        result_dict = {'funcName': 'TestSetPlayerDamageDisable', "branch": self.branch, "project_id": 33,
                       "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'is_open': is_open}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def set_player_ignoreCondition(self, is_open: bool):
        """
        设置是否消耗枪耐久
        @param is_open: T/F
        @return:
        """
        result_dict = {'funcName': 'TestIgnoreCondition', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'set': is_open, "is_open": is_open}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def remove_self_parts(self):
        """
        移除自己的建筑
        @return:
        """
        result_dict = {'funcName': 'TestGmRemovePartsByUserId', "branch": self.branch, "project_id": 33,
                       "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def out_login(self):
        """
        退出登录
        @return:
        """
        print(f"{self.role_id}退出游戏")
        result_dict = {'funcName': 'outLogin', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def reborn(self):
        """
        复活
        @return:
        """
        result_dict = {'funcName': 'Reborn', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        time.sleep(8)
        return user_info_dic["data"]

    def suicide(self):
        """
        自杀
        @return:
        """
        result_dict = {'funcName': 'Suicide', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        time.sleep(1)
        return user_info_dic["data"]

    def wake_up(self):
        """
        起床
        @return:
        """
        result_dict = {'funcName': 'WakeUp', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        time.sleep(3)
        return user_info_dic["data"]

    def robot_pos(self):
        """
        信任客户端坐标，用于飞天
        @return:
        """
        result_dict = {'funcName': 'TestStressTest', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def fire_to_robot(self, role_id):
        """
        瞄准机器人开火
        @param role_id:
        @return:
        """
        result_dict = {'funcName': 'FireToUser', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, "role_id": role_id, "name": ""}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def collimation_to_entity(self, entity_id):
        """
        瞄准指定entity
        @param entity_id:
        @return:
        """
        result_dict = {'funcName': 'CollimationEntity', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, "entity_id": entity_id, "name": ""}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def reload_ammo(self, ammo_id):
        """
        换弹
        @param ammo_id: 弹药id
        @return:
        """
        result_dict = {'funcName': 'ReloadAmmo', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'ammo_id': ammo_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        time.sleep(8)
        return user_info_dic["data"]

    def drop_item(self, box1_id: int, box2_id: int, index_id: int, drop_num: int):
        """
        丢弃指定容器的道具。快捷栏和背包可以丢，身上的需要先移动到背包再丢
        @param box1_id: 主容器id：快捷栏是1,背包是1,装备是1
        @param box2_id: 子容器id:快捷栏是1,背包是0,装备是2
        @param index_id: 道具的位置：从0开始数。装备栏：头盔0，手套5，背心4，上衣3，裤子6，护裙7，鞋子8，眼镜1，面巾2，背包9
        @param drop_num: 丢弃的数量
        @return:
        """
        result_dict = {'funcName': 'DropItem', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'box1_id': box1_id, 'box2_id': box2_id,
                                     'index_id': index_id,
                                     'drop_num': drop_num}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def use_item(self, item_uid: int, count: int):
        """
        使用/穿戴道具
        @param item_uid: 道具id
        @param count: 使用的数量
        @return:
        """
        result_dict = {'funcName': 'UseItem', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'item_uid': item_uid, 'count': count}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move_item_to_path(self, box1F_id: int, box2F_id: int, indexF_id: int, box1T_id: int, box2T_id: int,
                          indexT_id: int):
        """
        移动指定容器的道具到另一个容器的指定位置。快捷栏和身上的有物品类型限制，背包的可以随意移动
        @param box1F_id: 道具当前主容器id：快捷栏是1,背包是1,装备是1
        @param box2F_id: 道具当前子容器id:快捷栏是1,背包是0,装备是2
        @param indexF_id: 道具当前的位置：从0开始数。装备栏：头盔0，手套5，背心4，上衣3，裤子6，护裙7，鞋子8，眼镜1，面巾2，背包9
        @param box1T_id: 道具目标主容器id：快捷栏是1,背包是1,装备是1
        @param box2T_id: 道具目标子容器id:快捷栏是1,背包是0,装备是2
        @param indexT_id: 道具目标的位置：从0开始数。装备栏：头盔0，手套5，背心4，上衣3，裤子6，护裙7，鞋子8，眼镜1，面巾2，背包9

        @return:
        """
        result_dict = {'funcName': 'MoveItemToPath', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'box1F_id': box1F_id, 'box2F_id': box2F_id,
                                     'indexF_id': indexF_id,
                                     'box1T_id': box1T_id, 'box2T_id': box2T_id, 'indexT_id': indexT_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move_accessory_to_path(self, box1F_id: int, box2F_id: int, indexF_id: int, box1T_id: int, box2T_id: int,
                               indexT_id: int, value: int):
        """
        移动配件
        @return:
        """
        result_dict = {'funcName': 'MoveItemToPath', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'box1F_id': box1F_id, 'box2F_id': box2F_id,
                                     'indexF_id': indexF_id,
                                     'box1T_id': box1T_id, 'box2T_id': box2T_id, 'indexT_id': indexT_id,
                                     'value': value}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def move_item(self, move_type, move_index, target_index, accessory_to_index=-1):
        """
        移动身上的道具，支持移动配件
        @param move_index:移动道具的位置
        @param move_type:移动类型 s2b快捷键到背包   b2s背包到快捷键 b2z 背包到装备身上
        @param target_index:移动道具的目标位置
        @param accessory_to_index: 配件需要移动的位置
        @return:
        """

        if move_type in ["s2b", "b2s", "b2z"]:
            if move_type == "s2b":
                box1F_id, box2F_id, indexF_id, box1T_id, box2T_id, indexT_id = 1, 1, move_index, 1, 0, target_index
            elif move_type == "b2s":
                box1F_id, box2F_id, indexF_id, box1T_id, box2T_id, indexT_id = 1, 0, move_index, 1, 1, target_index
            elif move_type == "b2z":
                box1F_id, box2F_id, indexF_id, box1T_id, box2T_id, indexT_id = 1, 0, move_index, 1, 2, target_index
            else:
                print("类型错误，应为s2b b2s中的一种")
                return
            if accessory_to_index >= 0:
                self.move_accessory_to_path(box1F_id, box2F_id, indexF_id, box1T_id, box2T_id, indexT_id,
                                            accessory_to_index)
            else:
                self.move_item_to_path(box1F_id, box2F_id, indexF_id, box1T_id, box2T_id, indexT_id)
        else:
            print("类型错误，应为s2b b2s b2z中的一种")

    def switch_headlights(self, enable: bool):
        """
        开头灯
        @return:
        """
        light_type = 1
        result_dict = {'funcName': 'SetEquipEnable', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'light_type': light_type, 'enable': enable}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def switch_weaponlights(self, enable: bool, accessory_id: int):
        """
        开枪灯
        @return:
        """
        light_type = 2
        result_dict = {'funcName': 'SetEquipEnable', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'light_type': light_type, 'enable': enable,
                                     'accessory_id': accessory_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def up_carrier(self, mountable_id, seat_type, seat_index):
        """
        上载具
        @param mountable_id: 载具的EntityID
        @param seat_type:貌似是载具类型，需要录制接口区分  车和马的话目前传1会上驾驶位
        @param seat_index:貌似是上的位置，需要录制接口区分 车和马的话目前传-1会上驾驶位
        @return:
        """
        result_dict = {'funcName': 'WantsMount', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, 'mountable_id': mountable_id, 'seat_type': seat_type,
                                     'seat_index': seat_index}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def down_carrier(self, ):
        """
        下载具
        @return:
        """
        result_dict = {'funcName': 'WantsDismount', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def accept_team_invite(self, role_id: int):
        """
        接收队伍邀请
        @param role_id:
        @return:
        """
        result_dict = {'funcName': 'TeamAcceptInvite_V2', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, "role_id": role_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def reject_team_invite(self, role_id: int):
        """
        拒绝队伍邀请
        @param role_id:
        @return:
        """
        result_dict = {'funcName': 'TeamRefuseInvite_V2', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, "role_id": role_id}}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]

    def leave_team(self):
        """
        主动退出队伍
        @return:
        """
        result_dict = {'funcName': 'SendLeaveTeam', "branch": self.branch, "project_id": 33, "isCase": False,
                       'funcValue': {"roleId": self.role_id, }}
        response = send_request(self.auto_server_multiplayer_run_url, result_dict)
        user_info_dic = response.json()
        return user_info_dic["data"]
