import json
import math
import os, unittest
import random
import threading
import time
import traceback

import numpy as np
import psutil

import requests
import random
from skywalks_auto.core.auto import *
from skywalks_auto.util.tool import get_self_ip, make_random_account_uuid
from skywalks_auto.util.server_tools import write_log_and_upload_file_v2, write_log_and_upload_file
from skywalks_auto.util.time_util import tu
from operation_tools.multiplayer_op import MultiplayerOperation, get_server_list
from soc_util import project_file_path_info
from soc_util.soc_tools import read_xlsx, table_string_2_int_list, soc_down_perf_str_2_info, \
    soc_perf_list_to_performance_platform, ProFiler, soc_down_perf_str_2_info_v2, \
    soc_down_common_str_2_info, soc_down_memory_str_2_info, soc_down_dc_str_2_info_v2, soc_read_performance_data, \
    soc_read_origin_url_data, soc_performance_data_update
from soc_util.time_util import TimeUtil
from soc_util.uwa_tools import read_excel_for_phone, find_report_by_iphone, get_recent_report_list, get_overview_report, \
    tidy_report_v1

def err_win_filter(auto: Automation = None, **kwargs):
    """
    异常窗口过滤
    :return:
    """
    return
    # 里面的逻辑不能少
    if auto is None:
        auto = Automation(__file__, client_type=TestEnv.pc_poco,
                          rpc=True)  # 走到这里一般都进游戏了，这种函数要根据不同游戏进行初始化，后续可以把case_init的逻辑加进来
        print("err_win_filter auto 初始化")
        auto.set_kwargs(**kwargs)
        print("err_win_filter", auto.init_kwargs)
        device_ip = ""
        platform = auto.init_kwargs.get("task_info", {}).get('platform', "pc")
        if platform == "android":
            device_ip = auto.init_kwargs.get('device_ip', "")
            client_type = get_test_env(2)
        elif auto.init_kwargs.get("rpc", False):
            client_type = get_test_env(6)
        elif platform == "exe" or platform == "editor" or platform == "remoteDevices":
            client_type = get_test_env(6)
        else:
            client_type = get_test_env(
                auto.init_kwargs.get('client_type', 5))  # todo 这里可以优化一下，改成根据任务的类型和包体命名规则去拿默认链接类型
        print("err_win_filter client_type", auto.get_client_type(), client_type)
        if auto.get_client_type() != client_type:
            auto.set_client_type(client_type, device_ip)
    # 这里开始是业务逻辑
    # 判断摄像机高度，看看有没有掉到地下
    result_data, result, msg = auto.send_rpc_and_read_result({"camera": {"get": ""}})
    if result:
        if result_data["position"]["y"] < -5:
            raise Exception("掉到地下了")
    return auto


class Operation:
    def __init__(self, auto: Automation):
        self.auto = auto
        #7号地图
        self.transmit_list = [[1830, 4, -1447], [-46, 4, -1661]]
        #12号地图
        self.transmit_list_12 = [[815, 4, -1225], [935, 4, -955]]
        self.build_name_dict = {'foundation': "地基", 'roof': "屋顶", 'steps': "地基楼梯", 'ramp': "斜坡",
                                'floor': "地板", 'floor-triangle': "三角地板", 'floor-frame': "地板框架",
                                'floor-triangle-frame': "三角地板框架", 'wall': "墙壁", 'doorway': "门框墙壁",
                                'window': "窗框墙壁", 'wall-frame': "墙壁框架", 'half-wall': "半墙",
                                'low-wall': "1/3墙",
                                'u-shaped-stairs': "U型楼梯", 'stairs-l-shape': "L型楼梯", 'stairs-spiral': "矩形楼梯",
                                'stairs-spiral-triangle': "三角楼梯", 'roof-triangle': "三角屋顶",
                                'triangle-foundation': "三角地基"}
        self.build_lv_dict = {'twig': 0, 'wooden': 1, 'stone': 2, 'metal': 3, 'armored': 4}
        # 建筑等级与材质的对照表 0 通用 11 是wood 6是rock 7是metal
        self.build_lv_material = {'twig': 0, 'wooden': 11, 'stone': 6, 'metal': 7, 'armored': 7}
        self.build_condition_lost = {1: [1, 1, 0.6, 0.6], 2: 0.5, 3: 0.334, 4: 0.334,
                                     5: [0.334, 0.334, 0.334, 0.5], 8: [0.334, 0.2, 0.334, 0.2]}
        #7号地图
        self.horse_transmit_list_7 = [[-550.75, 3.064265, -930.4453], [470.9986, 4.009006, 1285.353], [-1249, 11, 363],
                                    [-926, 3, -1610], [1153, 22, 1418]]
        #12号地图
        self.horse_transmit_list_12 = [[894.8229, 5.099393, -900.1647], [709.724, 24.67768, -279.3724], [238.6402, 26.73364, 79.367],
                                        [-104.6042, 23.82739, 23.26936], [801.024, 9.095385, 1064.549]]
        self.tree_transmit_list = [[1834.186, 2.054282, -1438.386], [-295.1662, 8.539398, 155.4172]]
        self.robot_list = []
        self.role_id = 0  # 角色idw
        self.multi_language_info = {}  # 多语言装备信息
        self.weapon_id_info = {}  # 装备缓存信息
        self.item_info = {}  # 物品缓存信息，用来读取道具总表的内容
        self.weapon_name_info = {}
        self.parts_id_info = {}  # 配件缓存信息
        self.parts_name_info = {}
        self.building_id_info = {}  # 建筑缓存信息
        self.building_name_info = {}
        self.battle_numerical_value_id_info = {}
        self.battle_numerical_value_name_info = {}
        self.case_is_pass = False
        self.case_name = ""
        self.damage_disable = False
        self.performance_test_init_info = {}
        self.account = ""
        self.platform = "pc"
        self.server_name = ""
        self.performance_test = False
        self.perf_info_list = []
        self.perf_start_time = 0
        self.perf_end_time = 0
        self.perf_tag_time_info_list = []
        self.memory_monitor_time = 0
        self.is_2hours = False
        self.server_num = None  # 用来记录服务器是哪个数字
        self.memory_downpath = ''
        self.memory_info_list = []

    def robot_new_some(self, new_num, server_name, branch="new", run_time=10, damage_disable=True, is_yc=False,
                       is_self=False,
                       soc_git_path="", self_ip=""):
        """
        创建一些机器人
        @param new_num:
        @param server_name:
        @param branch:
        @param is_self: 是否在本地启动机器人服务，如果传入是，需要传入soc_git_path，可从project_file_path_info中导入
        @param soc_git_path:本地a4工程路径，到.git文件夹那一层
        @param self_ip:也可以手动启动本地机器人服务，就不用传soc_git_path了，只需要传入机器人服务的IP和端口就行了
        @param run_time:
        @param is_yc:
        @param damage_disable:
        @return:
        """
        for i in range(new_num):
            account = int("1" + make_random_account_uuid())
            robot = MultiplayerOperation(account, branch=branch, is_yc=is_yc, run_time=run_time)
            # robot.auto_server_multiplayer_run_url = "http://192.168.180.156:5885/runCase"
            thread = threading.Thread(target=robot.start_server,
                                      args=(server_name, False, is_self, soc_git_path, self_ip))
            thread.start()
            self.robot_list.append(robot)
        time.sleep(15)
        for robot in self.robot_list:
            if "失败" in robot.login_msg_info.get("data", "失败"):
                self.auto.add_log(f"第{i + 1}个机器人登录失败")
                continue
            if damage_disable:
                print("开启无敌")
                robot.set_player_damage_disable(damage_disable)

    def robot_transmit_to_random_all(self, x, y, z, random_num, is_ground):
        """
        传送到指定的坐标位置附近，以x, y, z为中心，以random_num为边长的方型范围
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param is_ground: 是否落到地面
        @param random_num: 坐标随机范围
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.transmit_to_random, args=(x, y, z, random_num, is_ground))
            thread.start()

    def robot_transmit_to_random_list(self, robot_list, x, y, z, random_num, is_ground):
        """
        传送到指定的坐标位置附近，以x, y, z为中心，以random_num为边长的方型范围
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param is_ground: 是否落到地面
        @param random_num: 坐标随机范围
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.transmit_to_random, args=(x, y, z, random_num, is_ground))
            thread.start()

    def robot_transmit_to(self, robot, x, y, z, is_ground):
        """
        传送到指定的坐标位置附近，以x, y, z为中心，以random_num为边长的方型范围
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param is_ground: 是否落到地面
        @param robot: 机器人对象
        @return:
        """
        thread = threading.Thread(target=robot.transmit_to, args=(x, y, z, is_ground))
        thread.start()

    def robot_transmit_to_all(self, x, y, z, is_ground):
        """
        让所有的机器人传送到指定位置
        @param x:
        @param y:
        @param z:
        @param is_ground:是否在地面，t是在地面
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.transmit_to, args=(x, y, z, is_ground))
            thread.start()
            time.sleep(2)

    def robot_transmit_to_list(self, robot_list, x, y, z, is_ground):
        """
        让所有的机器人传送到指定位置
        @param x:
        @param y:
        @param z:
        @param is_ground:是否在地面，t是在地面
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.transmit_to, args=(x, y, z, is_ground))
            thread.start()

    def robot_move_to_pos(self, robot, x, y, z):
        """
        移动到指定坐标
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param robot: 机器人对象
        @return:
        """
        thread = threading.Thread(target=robot.move_to_pos, args=(x, y, z))
        thread.start()

    def robot_move_to_pos_all(self, x, y, z):
        """
        移动到指定坐标
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.move_to_pos, args=(x, y, z))
            thread.start()

    def robot_move_to_pos_list(self, robot_list, x, y, z):
        """
        移动到指定坐标
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.move_to_pos, args=(x, y, z))
            thread.start()

    def robot_move_pos(self, robot, x, y, z, run_num=5, direction="MoveForward"):
        """
        朝指定坐标移动
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param robot: 机器人对象
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        thread = threading.Thread(target=robot.move_pos, args=(x, y, z, run_num, direction))
        thread.start()

    def robot_move_pos_all(self, x, y, z, run_num=5, direction="MoveForward"):
        """
        朝指定坐标移动
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.move_pos, args=(x, y, z, run_num, direction))
            thread.start()

    def robot_move_pos_list(self, robot_list, x, y, z, run_num=5, direction="MoveForward"):
        """
        朝指定坐标移动
        @param x: 编辑器中SceneCamera的x轴
        @param y: 编辑器中SceneCamera的y轴
        @param z: 编辑器中SceneCamera的z轴
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.move_pos, args=(x, y, z, run_num, direction))
            thread.start()

    def robot_move(self, robot, yaw, run_num=5, direction="MoveForward"):
        """
        朝指定方向移动
        @param yaw: 方向，如果方向大于360，会按照当前方向移动
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        thread = threading.Thread(target=robot.move, args=(yaw, run_num, direction))
        thread.start()

    def robot_move_all(self, yaw, run_num=5, direction="MoveForward"):
        """
        朝指定方向移动
        @param yaw: 方向，如果方向大于360，会按照当前方向移动
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.move, args=(yaw, run_num, direction))
            thread.start()

    def robot_move_list(self, robot_list, yaw, run_num=5, direction="MoveForward"):
        """
        朝指定方向移动
        @param yaw: 方向，如果方向大于360，会按照当前方向移动
        @param run_num:cmd连发次数
        @param direction:前后左右移动 MoveForward  MoveBackward MoveRight MoveLeft
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.move, args=(yaw, run_num, direction))
            thread.start()

    def robot_make_part_all(self, part_path):
        """
        造死羊建筑
        @param part_path:死羊建筑id
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.make_part, args=(part_path,))
            thread.start()

    def robot_make_part_list(self, robot_list, part_path):
        """
        造死羊建筑
        @param part_path:死羊建筑id
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.make_part, args=(part_path,))
            thread.start()

    def robot_make_part(self, robot, part_path):
        """
        造死羊建筑
        @param robot:
        @param part_path:死羊建筑id
        @return:
        """

        thread = threading.Thread(target=robot.make_part, args=(part_path,))
        thread.start()

    def robot_suicide_list(self, robot_list, ):
        """
        自杀
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.suicide, args=())
            thread.start()

    def robot_suicide(self, robot, ):
        """
        自杀
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.suicide, args=())
        thread.start()

    def robot_suicide_all(self, ):
        """
        自杀
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.suicide, args=())
            thread.start()

    def robot_reborn_list(self, robot_list, ):
        """
        复活
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.reborn, args=())
            thread.start()

    def robot_switch_headlights(self, robot, enable: bool):
        """
        开头灯
        """
        thread = threading.Thread(target=robot.switch_headlights, args=(enable,))
        thread.start()

    def robot_switch_headlights_list(self, robot_list, enable: bool):
        """
        开头灯
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.switch_headlights, args=(enable,))
            thread.start()

    def robot_switch_headlights_all(self, enable: bool):
        """
        开头灯
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.switch_headlights, args=(enable,))
            thread.start()

    def robot_switch_weaponlights(self, robot, enable: bool):
        """
        开头灯
        """
        thread = threading.Thread(target=robot.switch_weaponlights, args=(enable,))
        thread.start()

    def robot_switch_weaponlights_list(self, robot_list, enable: bool):
        """
        开头灯
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.switch_weaponlights, args=(enable,))
            thread.start()

    def robot_switch_weaponlights_all(self, enable: bool):
        """
        开头灯
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.switch_weaponlights, args=(enable,))
            thread.start()

    def robot_reborn(self, robot, ):
        """
        复活
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.reborn, args=())
        thread.start()

    def robot_reborn_all(self, ):
        """
        复活

        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.reborn, args=())
            thread.start()

    def robot_wake_up_list(self, robot_list, ):
        """
        起床
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.wake_up, args=())
            thread.start()

    def robot_wake_up(self, robot, ):
        """
        起床
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.wake_up, args=())
        thread.start()

    def robot_wake_up_all(self, ):
        """
        起床
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.wake_up, args=())
            thread.start()

    def robot_gm_add_item(self, robot, resource_name, add_num):
        """
        添加资源
        @param resource_name:
        @param add_num:
        @param robot: 机器人对象
        @return:
        """
        thread = threading.Thread(target=robot.gm_add_item, args=(resource_name, add_num))
        thread.start()

    def robot_move_item_all(self, move_type, move_index, target_index, accessory_to_index=-1):
        """
        移动道具
        @param move_index:
        @param move_type:
        @param target_index:
        @param accessory_to_index:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.move_item,
                                      args=(move_type, move_index, target_index, accessory_to_index))
            thread.start()

    def robot_move_item_list(self, robot_list, move_type, move_index, target_index, accessory_to_index=-1):
        """
        移动道具
        @param move_index:
        @param move_type:
        @param target_index:
        @param accessory_to_index:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.move_item,
                                      args=(move_type, move_index, target_index, accessory_to_index))
            thread.start()

    def robot_move_item(self, robot, move_type, move_index, target_index, accessory_to_index=-1):
        """
        移动道具
        @param robot: 机器人对象
        @param move_index:
        @param move_type:
        @param target_index:
        @param accessory_to_index:
        @return:
        """
        thread = threading.Thread(target=robot.move_item,
                                  args=(move_type, move_index, target_index, accessory_to_index))
        thread.start()

    def robot_gm_add_item_all(self, resource_name, add_num):
        """
        添加资源
        @param resource_name:
        @param add_num:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.gm_add_item, args=(resource_name, add_num))
            thread.start()

    def robot_gm_add_item_list(self, robot_list, resource_name, add_num):
        """
        添加资源
        @param resource_name:
        @param add_num:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.gm_add_item, args=(resource_name, add_num))
            thread.start()

    def robot_out_login(self):
        """
        让所有的机器人退出游戏
        @return:
        """
        for robot_instance in self.robot_list:
            robot_instance.out_login()
        self.robot_list = []

    def robot_reload_ammo_all(self, ammo_id):
        """
        机器人换弹
        @param ammo_id:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.reload_ammo, args=(ammo_id,))
            thread.start()

    def robot_reload_ammo_list(self, robot_list, ammo_id):
        """
        机器人换弹
        @param ammo_id:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.reload_ammo, args=(ammo_id,))
            thread.start()

    def robot_reload_ammo(self, robot, ammo_id):
        """
        机器人换弹
        @param robot:
        @param ammo_id:弹药id
        @return:
        """
        thread = threading.Thread(target=robot.reload_ammo, args=(ammo_id,))
        thread.start()

    def robot_fire1(self, robot, x, y, z, is_fire_continus, throw, fire_num):
        """
        控制机器人集体开火
        @param robot:
        @param x:
        @param y:
        @param z:
        @param is_fire_continus:
        @param throw:
        @param fire_num:
        @return:
        """
        thread = threading.Thread(target=robot.fire1,
                                  args=(x, y, z, is_fire_continus, throw, fire_num))
        thread.start()

    def robot_fire1_all(self, x, y, z, is_fire_continus, throw, fire_num):
        """
        控制机器人集体开火
        @param x:
        @param y:
        @param z:
        @param is_fire_continus:是否连续开火 ,手雷火箭筒用F
        @param throw: 是否投掷物
        @param fire_num:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.fire1,
                                      args=(x, y, z, is_fire_continus, throw, fire_num))
            thread.start()

    def robot_fire1_list(self, robot_list, x, y, z, is_fire_continus, throw, fire_num):
        """
        控制机器人集体开火
        @param x:
        @param y:
        @param z:
        @param is_fire_continus:是否连续开火 ,手雷火箭筒用F
        @param throw: 是否投掷物
        @param fire_num:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.fire1,
                                      args=(x, y, z, is_fire_continus, throw, fire_num))
            thread.start()

    def robot_fire2(self, robot, ):
        """
        控制机器人集体开镜
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.fire2, args=())
        thread.start()

    def robot_fire2_all(self, ):
        """
        控制机器人集体开镜
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.fire2, args=())
            thread.start()

    def robot_fire2_list(self, robot_list):
        """
        控制机器人集体开镜
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.fire2, args=())
            thread.start()

    def robot_up_carrier(self, robot, mountable_id, seat_type, seat_index):
        """
        控制机器人集体上载具
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.up_carrier, args=(mountable_id, seat_type, seat_index))
        thread.start()

    def robot_up_carrier_all(self, mountable_id, seat_type, seat_index):
        """
        控制机器人集体上载具
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.up_carrier, args=(mountable_id, seat_type, seat_index))
            thread.start()

    def robot_up_carrier_list(self, robot_list, mountable_id, seat_type, seat_index):
        """
        控制机器人集体上载具
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.up_carrier, args=(mountable_id, seat_type, seat_index))
            thread.start()

    def robot_down_carrier(self, robot):
        """
        控制机器人集体下载具
        @param robot:
        @return:
        """
        thread = threading.Thread(target=robot.down_carrier, args=())
        thread.start()

    def robot_down_carrier_all(self, ):
        """
        控制机器人集体下载具
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.down_carrier, args=())
            thread.start()

    def robot_down_carrier_list(self, robot_list):
        """
        控制机器人集体下载具
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.down_carrier, args=())
            thread.start()

    def robot_drop_item_list(self, robot_list, box1_id: int, box2_id: int, index_id: int, drop_num: int):
        """
        丢弃指定容器的道具。快捷栏和背包可以丢，身上的需要先移动到背包再丢
        @param robot_list:
        @param box1_id: 主容器id：快捷栏是1,背包是1,装备是1
        @param box2_id: 子容器id:快捷栏是1,背包是0,装备是2
        @param index_id: 道具的位置：从0开始数。装备栏：头盔0，手套5，背心4，上衣3，裤子6，护裙7，鞋子8，眼镜1，面巾2，背包9
        @param drop_num: 丢弃的数量
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.drop_item,
                                      args=(box1_id, box2_id, index_id, drop_num))
            thread.start()

    def robot_use_shortcut_iteam_all(self, iteam_index: int, un_equip: bool = False):
        """
        使用快捷栏
        @param iteam_index:
        @param un_equip:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.use_shortcut_iteam,
                                      args=(iteam_index, un_equip))
            thread.start()

    def robot_use_shortcut_iteam_list(self, robot_list, iteam_index: int, un_equip: bool = False):
        """
        使用快捷栏
        @param iteam_index:
        @param un_equip:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.use_shortcut_iteam,
                                      args=(iteam_index, un_equip))
            thread.start()

    def robot_use_shortcut_iteam(self, robot, iteam_index: int, un_equip: bool = False):
        """
        使用快捷栏
        @param robot:
        @param iteam_index:
        @param un_equip:
        @return:
        """
        thread = threading.Thread(target=robot.use_shortcut_iteam,
                                  args=(iteam_index, un_equip))
        thread.start()

    def robot_gm_clear_inventory_all(self, bagType):
        """
        清空背包
        @param bagType:
        @return:
        """
        for robot in self.robot_list:
            thread = threading.Thread(target=robot.gm_clear_inventory, args=(bagType,))
            thread.start()

    def robot_gm_clear_inventory_list(self, robot_list, bagType):
        """
        清空背包
        @param bagType:
        @param robot_list:
        @return:
        """
        for robot in robot_list:
            thread = threading.Thread(target=robot.gm_clear_inventory, args=(bagType,))
            thread.start()

    def robot_gm_clear_inventory(self, robot, bagType):
        """
        清空背包
        @param robot:
        @param bagType:
        @return:
        """
        thread = threading.Thread(target=robot.gm_clear_inventory, args=(bagType,))
        thread.start()

    def get_camera(self, is_log=True):
        result_data, result, msg = self.auto.send_rpc_and_read_result({"getLocalValue": {"name": "camera"}})
        if not result:
            return {}, False
        else:
            if is_log:
                self.auto.add_log(f"获取属性camera:{msg},值为{result_data}")
        return result_data, result

    def set_visual_angle(self, direction, angle):
        """
        旋转视角
        :param direction:方向  up down left right
        :param angle: 角度
        :return:
        """
        # 上下视野在-86.5 到86.5 之间
        # 方向在0-360之间
        camera_info, is_get = self.get_camera()
        if is_get:
            look_pitch = camera_info["rotation"]["y"]
            look_yaw = camera_info["rotation"]["x"]
            if direction == "up":
                if look_pitch >= 86.5:
                    print("视角高度到上限，无需修改")
                    return
                look_pitch += angle
                if look_pitch > 86.5:
                    look_pitch = 86.5
                self.set_role_pitch(look_pitch)
            elif direction == "down":
                if look_pitch <= -86.5:
                    print("视角高度到上限，无需修改")
                    return
                look_pitch -= angle
                if look_pitch < -86.5:
                    look_pitch = -86.5
                self.set_role_pitch(look_pitch)
            elif direction == "parallel":
                if look_pitch <= -86.5:
                    print("视角高度到上限，无需修改")
                    return
                look_pitch -= look_pitch

                self.set_role_pitch(look_pitch)
            elif direction == "left":
                look_yaw -= angle
                self.set_role_yaw(look_yaw)
            elif direction == "right":
                look_yaw += angle
                self.set_role_yaw(look_yaw)
            else:
                raise Exception("输入的方向不对")
            time.sleep(0.4)
        else:
            raise self.auto.raise_err_and_write_log("视角数据获取失败", 5)

    def hotmap_set_visual_angle(self):
        """
        热力图版_旋转视角4次
        :return:
        """
        angle_array = [0, 90, 180, 270]
        for i in range(4):
            first_angle = angle_array[0]
            angle_array = angle_array[1:] + [first_angle]
            self.set_role_yaw(first_angle)
            time.sleep(0.5)

    def add_resource(self, resource_name, add_num):
        """
        添加道具
        :param resource_name: 资源名
        :param add_num: 数量
        :return:
        """
        resource_id = resource_name  # todo 后续加名字转id的
        try:
            self.gm_rpc("add", f"GMAddItem {resource_id} {add_num}")
        except Exception:
            return False
        return True

    def get_resource(self, resource_name):
        """
        获取资源数量
        @param resource_name:
        @return:
        """
        resource_id = resource_name  # todo 后续加名字转id的
        return self.gm_rpc("get_resource", resource_id, "")

    def get_poco_text(self, poco_name):
        result_data, result, msg = self.poco_text(poco_name, "", "get")
        if not result:
            raise Exception(f"节点{poco_name}text属性获取失败，err:{msg}")
        return result_data

    def get_poco_exist(self, poco_name):
        result_data, result, msg = self.poco_text(poco_name, "", "get")
        if not result:
            return False
        return True

    def poco_text(self, poco_name, set_text, ui_type):
        """
        根据节点获取或者设置节点的text属性
        :param poco_name:
        :param ui_type: get/set
        :param set_text:
        :return:
        """
        return self.auto.send_rpc_and_read_result(
            {"classUI": {"name": poco_name, "value": set_text, "type": ui_type}})

    def set_poco_text(self, poco_name, set_text):
        """
        根据节点获取或者设置节点的text属性
        :param poco_name:
        :param set_text:
        :return:
        """
        result_data, result, msg = self.poco_text(poco_name, set_text, "set")
        if not result:
            print("设置失败", msg)
        return result

    def fire(self):
        """
        开火
        :return:
        """
        self.set_rpc_value("Mc.UserCmd.NowCmd.Fire1", True)

    def fire_V2(self):
        """
        开火,火箭筒
        :return:
        """

        self.controls_role_v2(["Fire1", ], 1, True)
        self.auto.add_log("火箭筒开火")
        time.sleep(1)

    def reload(self):
        """
        换弹
        :return:
        """
        self.touch_key_action(12)
        time.sleep(8)

    def fire2(self):
        """
        开镜
        :return:
        """
        self.touch_key_action(10)

    def check_deserialization_error(self):
        # 检测是否有表格反序列化窗口报错
        # TODO 这个窗口可能是使用的通用提示，以后或许会导致某些窗口出现了但是被点掉
        name = "Stage/GRoot/(Popup) L601-LO601/UiMsgBox(CommonGlobal-UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
        if self.get_poco_exist(name):
            self.auto.auto_touch(name)

    def game_welcome(self):
        # 游戏启动页面
        check_name = "Stage/GRoot/ContentPane/BtnTouch"
        if self.get_poco_exist(check_name):
            self.auto.auto_touch(check_name)
        else:
            name = "Stage/GRoot/(Full Screen) ID501|S501/UiLogin(UiLoginView)/ContentPane/BtnLogin"
            self.auto.auto_touch(name)

    def input_account(self, account_str):
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLogin(UiLoginView)/ContentPane/ComLazyLoader/GLoader/ComLoginWindow/ComAccount/InputTextField"
        print("输入账户", account_str)
        self.account = account_str
        self.set_poco_text(name, account_str)

    def input_name(self, account_str):
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCreateRole(UiCreateRole)/ContentPane/InputTextField"
        print("输入NAME", account_str)
        self.set_poco_text(name, account_str)

    def touch_login_game(self):
        # 点击登录
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLogin(UiLoginView)/ContentPane/ComLazyLoader/GLoader/ComLoginWindow/ComCustomButton/GLoader/BtnLoginNormal"
        self.auto.auto_touch(name)

    def touch_change_head_image(self):
        # 点击更换头像
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCreateRole(UiCreateRole)/ContentPane/BtnNameCard"
        self.auto.auto_touch(name)

    def touch_over_change_head_image(self):
        # 点击取消更换头像
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCreateRole(UiCreateRole)/ContentPane/BtnOption"
        self.auto.auto_touch(name)

    def touch_confirm_name(self):
        # 点击确认昵称
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCreateRole(UiCreateRole)/ContentPane/BtnNameCard.2"
        if self.get_poco_exist(name):
            self.auto.auto_touch(name)

    def touch_check_in(self):
        # 点击签到按钮，用来关闭签到界面
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyMain(LobbyMain-UiLobbyMain)/ContentPane/GList/ComEntrance"
        self.auto.auto_touch(name)

    def in_server_list(self):
        # 进入选服界面
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyMain(UiLobbyMain)/ContentPane/ComLobbyMainRoot/BtnSvrList"
        self.auto.auto_touch(name)

    def find_server(self, server_name):
        # 先判断服务器是否能够读取到
        server_list = []
        while server_name not in server_list:
            server_list = get_server_list(True)
            self.auto.add_log(f"等待服务器{server_name}启动，当前服务器列表{server_list}")
            self.auto.auto_sleep(2)
        # 选择服务器
        server_group_list = ["BtnLeftItem", "BtnLeftItem.1", "BtnLeftItem.2", "BtnLeftItem.3",
                             "BtnLeftItem.4", "BtnLeftItem.5", "BtnLeftItem.7"]
        server_default_list = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComLobbyLeft/GList/Container/Container/"
        for server_group in server_group_list:
            try:
                self.auto.auto_touch(server_default_list + server_group)
                self.auto.auto_sleep(2)
                # server_name = "<Root>/Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(LobbyServerList-UiLobbyServerList)/ContentPane/ComLobbyRight/GList/BtnRightItem"
                # TODO 临时改动
                if server_group == "BtnLeftItem.4":
                    name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComLobbyRight/Container/GList/Container/Container/BtnRightItem"
                    self.auto.auto_touch(name)
                    return
                self.auto.auto_touch(server_name, touch_pass=False, is_include=False)
                return
            except Exception:
                page_num = self.get_max_page_num() - 1
                for i in range(page_num):
                    self.server_page_back()
                    self.auto.auto_sleep(2)
                    try:
                        self.auto.auto_touch(server_name, touch_pass=False, is_include=False, tips_poco=False)
                        return
                    except Exception:
                        # 进行刷新然后重试
                        self.refresh_server_list()
                        self.auto.auto_sleep(2)
                        try:
                            self.auto.auto_touch(server_name, touch_pass=False, is_include=False)
                            return
                        except Exception:
                            pass
        raise self.auto.raise_err_and_write_log(f"指定的服务器{server_name}未找到", 5)

    def refresh_server_list(self):
        """
        刷新服务器列表
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComFloatOPGroup/ComCustomButton/GLoader/BtnRefresh"
        self.auto.auto_touch(name)

    def join_world(self):
        # 进入世界
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ServerInfoPopBox/BtnJoin"
        if self.get_poco_exist(name):
            self.auto.auto_touch(name)

    def get_max_page_num(self):
        # 获取当前页面最大服务器数量
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComFloatOPGroup/ComChangePage/TextField"
        num = self.get_poco_text(name).replace("/", "")
        return int(num)

    def server_page_forward(self):
        # 服务器列表向前翻页
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComFloatOPGroup/ComChangePage/BtnPageSub"
        self.auto.auto_touch(name)

    def server_page_back(self):
        # 服务器列表向后翻页
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyServerList(UiLobbyServerList)/ContentPane/ComFloatOPGroup/ComChangePage/BtnPageSub.1"
        self.auto.auto_touch(name)

    def get_join_queue_up_str(self):
        get_str, is_get = self.auto.get_poco_info(
            "<Root>/Stage/GRoot/(Popup) L601-LO601/UiServerQueueUp(LobbyTeam-UiServerQueueUp)/ContentPane/TextField.1",
            "text")
        if is_get:
            if "排队" in get_str and "：" in get_str:
                get_str_list = get_str.split("：")
                if len(get_str_list) > 1:
                    try:
                        return int(get_str_list[1])
                    except Exception:
                        return get_str[1]
            return 0
        else:
            return 0

    def open_bag(self):
        # todo 界面迭代
        # name = "Stage/GRoot/(HUD) ID201|S201/UiHud(GameHud-UiHudMain)/ContentPane/elemsRoot/UiHudElems_new/ElemEntryGroup/BtnGroupFolder"
        # self.auto.auto_touch(name)
        # time.sleep(1)
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/BtnBagNew"
        self.auto.auto_touch(name)
        time.sleep(1)

    def close_bag(self):
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnBac02"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def close_ornament(self):
        """
        熔炉摆件页面关闭按钮，ps：其他摆件不确定是否可用
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/BtnClose"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def close_water_view_page(self):
        """
        啤酒桶页面关闭
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiWaterCatcher(UiWaterCollection)/ContentPane/ComWaterViewPage/BtnClose"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def wait_loading(self):
        # 通过相机判断是否加载完毕
        wait_num = 30
        while True:
            try:
                wait_num -= 1
                pos_dic, is_get = self.get_camera()
                if is_get:
                    rotation = pos_dic["rotation"]  # 视角
                    position = pos_dic["position"]
                    print("获取摄像机", position)
                    self.open_damage_disable()
                    if position["y"] != 0:  # 这个是地面的高度
                        time.sleep(15)
                        return
                time.sleep(10)
            except Exception:  # 加载中的读条会报错
                time.sleep(10)
            try:
                poco_text = self.get_poco_text("Stage/ContentPane/ComPopMsgBox/TextField")  # 这个应该是个报错弹窗
                raise self.auto.raise_err_and_write_log(f"点击进入游戏后报错，err:{poco_text}", 5)
            except Exception:  # 报错了说明没有弹出这个节点，继续等待就好
                pass
            if wait_num == 5:  # 这个是点击一次没有点到，再点击一次的保护逻辑
                self.join_world()
                self.auto.add_log("二次点击进入游戏按钮，需要注意")
            if wait_num <= 0:
                raise self.auto.raise_err_and_write_log(f"点击进入游戏后等待5分钟，仍未进入游戏，失败", 5)

    def wake_up(self):
        self.auto.auto_sleep(5)
        # 起床
        character_state = self.get_rpc_value("Mc.MyPlayer.MyEntityLocal.CharacterState")
        un_alive_state = self.get_rpc_value("Mc.MyPlayer.MyEntityLocal.UnAliveState")
        if character_state == 1 and un_alive_state == 1:
            self.set_rpc_value("Mc.UserCmd.NowCmd.WakeUpAction", True)
            time.sleep(2)
            self.get_role_id()
            character_state = self.get_rpc_value("Mc.MyPlayer.MyEntityLocal.CharacterState")
            un_alive_state = self.get_rpc_value("Mc.MyPlayer.MyEntityLocal.UnAliveState")
            if character_state == 1 and un_alive_state == 2:
                self.auto.add_log("起床成功")
            else:
                self.auto.add_log("起床失败")

    def login(self, account, server_name):
        self.case_is_pass = True
        self.auto.set_case_name("登录操作")
        self.auto.add_log("开始走登录流程")
        self.check_deserialization_error()
        self.game_welcome()
        self.auto.add_log(f"account{account}")
        # 输入账号
        if "13" in account:
            account = account.replace("13", "123")
        self.input_account(account)
        self.touch_login_game()
        self.auto.auto_sleep(15)
        self.input_name(account)
        self.touch_confirm_name()
        self.auto.auto_sleep(2)
        try:
            self.touch_confirm_name()
            self.auto.auto_sleep(2)
        except Exception:
            pass
        self.close_guide_system()
        self.in_server_list()
        self.find_server(server_name)
        time.sleep(4)
        self.join_world()
        self.wait_loading()
        self.wake_up()
        self.case_is_pass = False
        self.auto.set_case_results(True)
        self.auto.add_log("登录完毕")

    def login_android(self, account, server_name):
        """
        安卓平台的登录方式
        """
        self.check_deserialization_error()
        self.game_welcome()
        # 输入账号
        if "13" in account:
            account = account.replace("13", "123")
        self.input_account(account)
        self.touch_login_game()
        self.auto.auto_sleep(15)
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiNameCard(LobbyNameCard-UiNameCard)/ContentPane/BtnNameCard.1"
        if self.get_poco_exist(name):
            self.input_name(account)
            self.touch_confirm_name()
            self.auto.auto_sleep(2)
            self.touch_confirm_name()
            self.auto.auto_sleep(2)
        self.in_server_list()
        time.sleep(4)
        self.find_server(server_name)
        time.sleep(4)
        self.join_world()
        self.wait_loading()
        self.wake_up()

    def login_case_start(self, server_name):
        """
        用例开始时调用的登录，附带一些状态检测，用于查看是否需要调用登录
        @param server_name:
        @return:
        """
        try:
            pos_dic, is_get = self.get_camera()
        except Exception as e:
            self.auto.add_log(f"用例初始化获取局内场景报错{e}")
            pos_dic, is_get = {}, False
        self.auto.add_log("摄像机状态校验完毕")
        if is_get:
            rotation = pos_dic["rotation"]  # 视角
            position = pos_dic["position"]
            if position["y"] > 0:  # 这个是地面的高度
                time.sleep(5)
        else:
            random_time = random.uniform(0.5, 5)
            time.sleep(random_time)
            self.login(str(int(time.time())), server_name)

    def login_case_start_v2(self, server_name):
        """
        用例开始时调用的登录，附带一些状态检测，用于查看是否需要调用登录
        @param server_name:
        @return:
        """
        try:
            pos_dic, is_get = self.get_camera()
        except Exception as e:
            self.auto.add_log(f"用例初始化获取局内场景报错{e}")
            pos_dic, is_get = {}, False
        self.auto.add_log("摄像机状态校验完毕")
        if is_get:
            rotation = pos_dic["rotation"]  # 视角
            position = pos_dic["position"]
            if position["y"] > 0:  # 这个是地面的高度
                time.sleep(5)
        else:
            random_time = random.uniform(0.5, 5)
            time.sleep(random_time)
            self.auto.add_log(f"本次账号{str(int(time.time() * 100))[2:]}")
            self.login(str(int(time.time() * 100))[2:], server_name)

    def add_resource_and_inspect(self, resource_id, add_num):
        """
        添加道具并校验实际获得的数量
        :param resource_id:
        :param add_num:
        :return:
        """
        old_num = self.get_resource(resource_id)
        self.add_resource(resource_id, add_num)
        time.sleep(1)
        new_num = self.get_resource(resource_id)
        actual_add_num = new_num - old_num
        if actual_add_num == add_num:
            print(f"资源{resource_id}增加数量{add_num}正常")
        else:
            self.auto.raise_err_and_write_log(
                f"查询到资源{resource_id}增加的数量为{actual_add_num}，于预期{add_num}不符, new_num {new_num} old_num{old_num}",
                5)

    def transmit_to_dic(self, pos_list_dic: dict, check=False):
        if not isinstance(pos_list_dic, dict):
            raise Exception("传入的不是一个dict，后边会报错")
        else:
            pos_list = [pos_list_dic["x"], pos_list_dic["y"], pos_list_dic["z"]]
            return self.transmit_to(pos_list, check)

    def add_weapon(self, weapon_list):
        """
        增加传入的枪械
        必须传入list
        @return:
        """
        self.clear_item_all()
        if isinstance(weapon_list, list):
            for weapon_info in weapon_list:
                if isinstance(weapon_info, dict):
                    resource_id = weapon_info["resource_id"]
                    ammo_id = weapon_info["ammo_id"]
                    ammo_num = weapon_info["ammo_num"]
                    # 加道具和子弹
                    self.add_resource_and_inspect(resource_id, 1)
                    self.add_resource_and_inspect(ammo_id, ammo_num)
                    self.auto.auto_sleep(1)
                else:
                    self.auto.raise_err_and_write_log(f"传入的list中的元素{weapon_info}不是字典，请检查格式", 5)
        else:
            self.auto.raise_err_and_write_log(f"传入的不是一个list{weapon_list}，请检查格式", 5)

    def test_gun(self, index, weapon_id):
        """
        测试枪械的操作，开火，换弹，开镜，开镜射击
        """
        index += 1
        old_num = self.get_ammo_num(index)
        self.fire()
        self.auto.auto_sleep(1)
        now_num = self.get_ammo_num(index)
        if now_num == old_num:
            self.auto.add_log(f"手持枪械{weapon_id}开枪后子弹没有变化", False)
        self.touch_key_action(12)
        self.auto.auto_sleep(1)
        reload_num = self.get_ammo_num(index)
        if reload_num == now_num:
            self.auto.add_log(f"枪械{weapon_id}换弹后，子弹数量没有变化", False)
        pos_dic, is_get = self.get_camera()
        old_view = pos_dic['position']['view']
        self.fire2()
        self.auto.auto_sleep(1)
        pos_dic, is_get = self.get_camera()
        now_view = pos_dic['position']['view']
        if old_view == now_view:
            self.auto.add_log(f"武器{weapon_id}开镜后，镜头未变化", False)
        self.fire()
        self.auto.auto_sleep(1)
        now_num = self.get_ammo_num(index)
        if reload_num == now_num:
            self.auto.add_log(f"手持枪械{weapon_id}开镜开枪后子弹没有变化", False)

    def add_equipment(self, equipment_list):
        """
        增加传入的装备并且判断穿上和脱下是否会有属性变化
        必须传入list，可以支持多件装备一起测试, 不能有冲突，不然会报错，不支持附加物品，只有装备栏
        @return:
        """
        if isinstance(equipment_list, list):
            for equipment_info in equipment_list:
                if isinstance(equipment_info, dict):
                    self.clear_item_all()
                    self.auto.auto_sleep(3)
                    old_status = self.get_user_stats()['areaProtections']
                    for k, v in equipment_info.items():
                        self.add_resource_and_inspect(v, 1)
                        self.auto.auto_sleep(1)
                    equipment_wear = self.get_user_item_all("wear")
                    for equipment_id in equipment_info.keys():
                        if equipment_id not in equipment_wear:
                            self.auto.add_log(f"增加装备{equipment_id}后，没有自动穿到身上", False)
                    new_status = self.get_user_stats()['areaProtections']
                    if old_status == new_status:
                        self.auto.add_log(f"穿戴装备后，属性没有任何变化", False)
                    self.clear_item_wear()
                    self.auto.auto_sleep(3)
                    now_status = self.get_user_stats()['areaProtections']
                    if now_status == new_status:
                        self.auto.add_log(f"脱下装备后，属性没有任何变化", False)
                else:
                    self.auto.raise_err_and_write_log(f"传入的list中的元素{equipment_info}不是字典，请检查格式", 5)
        else:
            self.auto.raise_err_and_write_log(f"传入的不是一个list{equipment_list}，请检查格式", 5)

    def transmit_to(self, pos_list: list, check=False,is_vehicle=False):
        """
        传送到指定坐标
        @param pos_list:传送坐标列表，xyz三轴
        @param check:是否传送到地面的，T是传到地面
        :return:
        """
        if len(pos_list) < 3:
            raise Exception("传入的坐标长度不合法，应为3")
        if not isinstance(pos_list, list):
            raise Exception("传入的不是一个list，后边会报错")
        if not is_vehicle:
            camera_info, is_get = self.get_camera()
            if is_get:
                position = camera_info["position"]
                if check:
                    is_y = True
                else:
                    is_y = abs(pos_list[1] - position["y"]) == 0
                if abs(pos_list[0] - position["x"]) == 0 and abs(pos_list[2] - position["z"]) == 0 and is_y:
                    print("太近了，不用传送")
                    return True
        try:
            print("开始传送至", pos_list)
            pos_list.append(check)
            if is_vehicle:
                self.gm_rpc("set", pos_list, "TestSetPlayerPositionWithVehicle")
            else:
                self.gm_rpc("set", pos_list, "TestSetPlayerPosition")
            if is_vehicle:
                time.sleep(3)
            else:
                time.sleep(10)
            camera_info, is_get = self.get_camera()
            if is_get:
                if is_vehicle:
                    print("当前坐标没有超出预期")
                    return True
                now_position = camera_info["position"]
                if position == now_position:
                    self.auto.raise_err_and_write_log("传送前后的位置一致，请确认", 5)
                if abs(pos_list[0] - now_position["x"]) < 3 and abs(pos_list[2] - now_position["z"]) < 3:
                    print("当前坐标没有超出预期")
                    return True
                else:
                    return False
        except Exception:
            return False
        return True

    def hotmap_transmit_to(self, pos_list: list, check=False):
        """
        热力图版_传送到指定坐标
        :return:
        """
        pos_list.append(check)
        self.gm_rpc("set", pos_list, "TestSetPlayerPosition")
        return True

    def random_transmit_to(self, pos_list: list, check=False):
        """
        随机传送到指定范围
        :return:
        """
        pos_list.append(check)
        self.gm_rpc("set", pos_list, "TestSetRandomPlayerPosition")
        return True

    def is_transmit(self, pos_list: list):

        is_msg = self.gm_rpc("set", pos_list, "is_transmit")
        if "不在" in is_msg:
            return True
        else:
            return False

    def call_monster(self, monster_id, call_num, pos_list):
        """
        在指定位置召唤怪物
        @param monster_id: 怪物id
        @param call_num: 数量
        @param pos_list: 坐标
        @return:
        """
        if len(pos_list) < 3:
            raise Exception("传入的坐标长度不合法，应为3")
        try:
            self.gm_rpc("set", [monster_id, call_num] + pos_list, "TestSummonMonster")
            time.sleep(1)
        except Exception:
            return False
        return True

    def drop_item_shortcut(self, index: int, drop_num: int):
        """
        丢弃快捷栏里的东西
        :return:
        """
        try:
            self.gm_rpc("drop", [index, drop_num], "shortcut")
        except Exception:
            return False
        return True

    def drop_item_bag(self, index: int, drop_num: int):
        """
        丢弃背包里的东西
        :return:
        """
        try:
            self.gm_rpc("drop", [index, drop_num], "bag")
        except Exception:
            return False
        return True

    def drop_item_wear(self, index: int, drop_num: int):
        """
        丢弃背包里的东西
        :return:
        """
        try:
            self.gm_rpc("drop", [index, drop_num], "wear")
        except Exception:
            return False
        return True

    def get_item_shortcut(self, index: int, ):
        """
        获取快捷栏里的东西
        :return:
        """
        try:
            result_data = self.gm_rpc("get_box", [index], "shortcut")
            return result_data["count"]
        except Exception:
            return 0

    def get_item_bag(self, index: int):
        """
        获取背包里的东西
        :return:
        """
        try:
            result_data = self.gm_rpc("get_box", [index], "bag")
            return result_data["count"]
        except Exception:
            return 0

    def get_item_wear(self, index: int):
        """
        获取背包里的东西
        :return:
        """
        try:
            result_data = self.gm_rpc("get_box", [index], "wear")
            return result_data["count"]
        except Exception:
            return 0

    def summon_resource(self, entity_type, gather_id, gather_num):
        """
        在脸前头加资源，需要去读枚举和表
        :param entity_type: 资源类型，读枚举
        :param gather_id: 资源id，应该是读表
        :param gather_num: 添加的数量
        # TODO 后续这里得资源类型改成读表会比较方便，表里没有，需要读枚举类
        :return:
        """
        self.gm_rpc("set", [entity_type, gather_id,
                            gather_num, 1.0], "DebugCheatCreateTheEntityHasCount")

    def cheat_create(self, entity_type, entity_table_id):
        """
        在脸前头加资源，需要去读枚举和表
        @param entity_type: 资源类型，读枚举
        @param entity_table_id:表id
        # TODO 后续这里得资源类型改成读表会比较方便，表里没有，需要读枚举类
        :return:
        """
        self.gm_rpc("set", [entity_type, entity_table_id], "DebugCheatCreate")

    def unload(self, entity_id):
        """
        某个武器卸下弹药
        @param entity_id:武器的entity id
        """
        try:
            self.gm_rpc("set", [entity_id], "Unload")
        except Exception:
            pass

    def get_entity_type(self):
        """
        获取entity_type
        :return:list [ore_id,tree_id]
        """
        type_list = []
        self_ip = get_self_ip()

        if self_ip not in project_file_path_info.keys():
            self.auto.raise_err_and_write_log("配置的项目文件路径不存在", 5, False)
        file_path = project_file_path_info[self_ip][
                        "git_path"] + r"\SocCommon\Soc.Common\Soc.Common\Data\Client\EntityTypeEnum.cs"
        self.auto.add_log(file_path)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file_data:
                for line in file_data:
                    if "OreEntity " in line:
                        type_list.append(int(line[-4:-2]))
                    if "TreeEntity" in line:
                        type_list.append(int(line[-4:-2]))
                    if len(type_list) == 2:
                        return type_list

    def set_rpc_value(self, value_path, set_value, add_log=True):
        """
        set_value
        @param value_path:
        @param set_value:
        @param add_log:
        @return:
        """

        result_data, result, msg = self.auto.send_rpc_and_read_result(
            {"setLocalValue": {"name": value_path, "value": set_value}}, False)
        if not result:
            if result_data != None:
                msg = f"{msg}{result_data}"
            self.auto.raise_err_and_write_log("setLocalValue调用失败：{}".format(msg), 5)
        else:
            if add_log:
                self.auto.add_log(f"设置属性{value_path}值为{set_value}:{msg}")

    def set_rpc_value_v1(self, value_path, set_value):
        """
        set_value移动操作需要较快的发包，不做其他校验
        @param value_path:
        @param set_value:
        @return:
        """

        result_data, result, msg = self.auto.send_rpc_and_read_result_v1(
            {"setLocalValue": {"name": value_path, "value": set_value}})
        if not result:
            if result_data != None:
                msg = f"{msg}{result_data}"
            self.auto.raise_err_and_write_log("setLocalValue调用失败：{}".format(msg), 5)

    def remove_self_parts(self):
        """
        删除自己的建筑
        :return:
        """

        self.gm_rpc("set", "", "TestGmRemovePartsByUserId")

    def remove_all_parts(self):
        """
        删除所有的建筑
        :return:
        """
        self.gm_rpc("set", "", "TestGmRemoveAllParts")

    def set_stress(self):
        """
        设置视角
        :return:
        """
        self.gm_rpc("set", "", "TestStressTest")

    def remove_part_by_id(self, part_id):
        """
        移除指定建筑
        :return:
        """
        self.gm_rpc("set", [part_id], "TestRemovePart")

    def get_rpc_value(self, value_path):
        """
        根据路径获取属性的值
        @param value_path:
        @return:
        """
        result_data, result, msg = self.auto.send_rpc_and_read_result({"getLocalValue": {"name": value_path}})
        if not result:
            self.auto.raise_err_and_write_log("getLocalValue调用失败：{},C#getValueByPathOther需要维护".format(msg), 5)
        else:
            self.auto.add_log(f"获取属性{value_path}:{msg},值为{result_data}")
            return result_data

    def touch_key(self, key_name, key_type, func_num=0):
        """
        触发快捷键
        @param key_name:快捷键编号
        @param key_type:action / func  区分两种调用模式，action是调用内置快捷键 func是通过编号调用
        @param func_num:快捷键模块编号，key_type=func时使用
        @return:
        """
        result_data, result, msg = self.auto.send_rpc_and_read_result(
            {"touchKey": {"name": key_name, "type": key_type, "func_num": func_num}})
        if not result:
            self.auto.raise_err_and_write_log("touchKey调用失败：{}".format(msg), 5)
        else:
            self.auto.add_log(f"获取属性{key_name}:{msg}")
            return result_data

    def touch_key_func(self, key_id, func_id):
        """
        调用函数式快捷键，这个功能不太熟，根据历史用例写的 todo
        :param key_id: 快捷键id  214-5增加一下投掷 214-4切换到采集道具并开始采集
        :param func_id:模块编号 214用的多
        :return:
        """
        # 通过函数调用快捷键，一般用于界面ui的快捷键，后续真机端可以使用UI点击
        self.touch_key(key_id, "func", func_id)

    def touch_key_action(self, key_id):
        """
        调用游戏内置快捷键
        :param key_id: 只测试了部分快捷键编号，发现不起作用的编号，请联系李栋
        9开火键1 10开火键2(开镜) 11装弹 12跳跃 14下蹲 15匍匐 16采集 17取消开火 18up 19down 20快捷栏1 21 22 23 24 25快捷栏6 26空手
        27打开背包 28关闭背包 29切换视角 30复活 31自杀 32检视 33救助 34召唤怪物 35跳舞 36唤醒 37结束倒地
        :return:
        """
        self.touch_key(key_id, "action")

    def get_coordinate_interval(self, pos_list):
        """
        计算目标点和当前位置的直线距离
        :param pos_list:transmit_to transmit_to函数的入参，或者是长度为3的列表[x,y,z]世界坐标三轴
        :return:
        """
        if len(pos_list) < 3:
            raise Exception("坐标列表输入长度不足3")
        camera_info, is_get = self.get_camera()
        if is_get:
            position = camera_info["position"]
            point1 = [position["x"], 0, position["z"]]
            point2 = [pos_list[0], 0, pos_list[2]]
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(point1, point2)))
            return distance
        else:
            raise Exception("坐标获取失败")

    def get_user_info(self, rpc_name, get_value, get_type):
        """
        获取角色信息
        @param rpc_name:
        @param get_value:
        @param get_type:
        @return:
        """
        result_data, result, msg = self.auto.send_rpc_and_read_result({"userInfo": {"name": rpc_name,
                                                                                    "value": get_value,
                                                                                    "type": get_type}})
        self.auto.add_log(f"get_user_info:{msg}")
        return result_data, result

    def get_sky_tools(self, rpc_name, get_value, get_type, add_log=True):
        """
        获取角色信息
        @param rpc_name:
        @param get_value:
        @param get_type:
        @param add_log:
        @return:
        """
        result_data, result, msg = self.auto.send_rpc_and_read_result({"Tools": {"name": rpc_name,
                                                                                 "value": get_value,
                                                                                 "type": get_type}})
        if add_log:
            self.auto.add_log(f"get_sky_tools:{msg}")
        return result_data, result

    def collimation_player(self, player_name, position_name="head"):
        """
        瞄准指定的玩家的指定的部位
        @param player_name:
        @param position_name: head头 boby胸 lClavicle左臂  rClavicle右臂 rFoot右腿 lFoot左腿
        @return:
        """
        return self.get_sky_tools(rpc_name="collimation", get_value=player_name, get_type=position_name, )

    def open_close_false_red(self, is_open: bool):
        """
        假红开关
        @param is_open: t/f 打开或者关闭
        @return:
        """
        return self.get_sky_tools(rpc_name="FalseRed", get_value=is_open, get_type="")

    def get_false_red_info(self, is_open: bool):
        """
        获取假红数据
        @param is_open: t/f 用来控制是否清空缓存，F是不拉取数据，清空缓存
        @return:
        """
        return self.get_sky_tools(rpc_name="FalseRedInfo", get_value=is_open, get_type="")

    def get_user_stats(self, entity_id=""):
        """
        获取角色的属性:卡路里，水分，生命值，HP，缓慢恢复。心率，流血，中毒，辐射，湿度，氧气，体温，位置，阵营ID，基础防御，部位防御
        @return:{
        'hunger': int,
        'water': int ,
        'life': int,
        'hp': float,
        'pendingHealth': float,
        'heartRate': float,
        'bleeding': float,
        'poison': float,
        'radiationPoison': float,
        'wetness': float,
        'oxygen': float,
        'temperature': float,
        "pos":[x,y,z]}
        "playCampId":int,
        "baseProtection":[],
        "areaProtections":[]
        """
        result_data = self.get_self_entity()
        return result_data

    def get_user_speed(self, ):
        """
        获取角色的速度属性，X，Y，Z轴分量速度，speed合速度
        @return:{
        'speedX': float,
        'speedY': float,
        'speedZ': float,
        'speed': float
        }
        """
        result_data = self.get_self_entity()
        Vx = result_data["speed"]['speedX']
        Vy = result_data["speed"]['speedY']
        Vz = result_data["speed"]['speedZ']
        speed = math.sqrt(Vx ** 2 + Vy ** 2 + Vz ** 2)
        result_data.update({'speed': speed})
        return result_data

    def get_user_entity(self, entity_type="", is_perf=False):
        """
        获取场景信息
        @return:
        """
        result_data, result = self.get_user_info("entity", [is_perf], entity_type)
        if result:
            return result_data
        else:
            self.auto.raise_err_and_write_log("获取entity数据失败", 5)

    def get_self_entity(self):
        """
        获取自身entity信息
        @return:
        """
        entity_info = self.get_user_entity("PlayerEntity")
        for entity_info_id, entity_info in entity_info.items():
            if entity_info['self']:
                return entity_info

    def get_self_entity_by_name(self, entity_type, table_name):
        """
        根据entity类型和表名字，获取所有符合的entity信息
        @param entity_type:
        @param table_name:
        @return:
        """
        table_id = 0
        if entity_type == "PartEntity":
            self.get_building_info()
            if table_name not in self.building_name_info.keys():
                self.auto.raise_err_and_write_log(f"{table_name}在建筑表中不存在")
            table_id = self.building_name_info[table_name]["造物ID"]
        else:
            self.auto.raise_err_and_write_log(f"{entity_type}类型暂不支持")
        entity_info = self.get_user_entity("PartEntity")
        find_entity_info_list = []
        for entity_info_id, entity_info in entity_info.items():
            if entity_type == entity_info['type'] and table_id == entity_info["TemplateId"] and self.get_role_id() == \
                    entity_info["OwnerId"]:
                find_entity_info_list.append(entity_info)
        return find_entity_info_list

    def get_entity_by_id(self, entity_id: int, entity_type="", is_perf=False):
        """
        根据entity_id，获取entity信息
        @param entity_id:
        @return:
        """
        entity_info = self.get_user_entity(entity_type, is_perf=is_perf)
        for entity_info_id, entity_info in entity_info.items():
            if entity_id == entity_info['EntityId']:
                return entity_info, True
        return {}, False

    def get_entity_hp_by_id(self, entity_id: int, entity_type=""):
        """
        获取指定entity的血量，注意查询的entity有没有血量属性
        @param entity_id:
        @return:
        """
        entity_info, is_get = self.get_entity_by_id(entity_id, entity_type)
        if is_get:
            entity_hp = entity_info.get("Hp", 0)
        else:  # 这里获取不到大概率是因为已经打碎了
            entity_hp = 0
        return entity_hp

    def entity_is_exist(self, entity_id, entity_type="", is_perf=False):
        """
        判断entity是否存在
        @param entity_id:
        @return:
        """
        entity_info = self.get_user_entity(entity_type, is_perf=is_perf)
        for entity_info_id, entity_info in entity_info.items():
            if str(entity_id) == str(entity_info_id):
                return True
        return False

    def get_role_id(self):
        """
        获取role_id
        @return
        """
        if self.role_id == 0:
            self.role_id = self.get_rpc_value("Mc.MyPlayer.MyEntityLocal.RoleId")
        return self.role_id

    def get_entity_list(self, type_list, is_perf=False):
        """
        获取玩家附近的entity
        """
        entity_list = []
        entity_info = {}
        for entity_type in type_list:
            entity_info.update(self.get_user_entity(entity_type, is_perf=is_perf))
        for key, value in entity_info.items():
            entity_list.append(value)
        return entity_list

    def get_ammo_num(self, index):
        """
        获取武器的子弹数
        """
        ammo_num = -1
        entity_id = -1
        entity_info = self.get_user_entity('PlayerEntity')
        for key, value in entity_info.items():
            if 'item' in value:
                entity_id = value['item'][str(index)]['entity_id']
                break
        ammo_info = self.get_user_entity('GunEntity')
        for key, value in ammo_info.items():
            if str(entity_id) == key:
                ammo_num = value['ammoNum']
        return ammo_num

    def get_user_hand(self):
        """
        获取手中武器id和耐久
        @return:dict
        """
        result_data, result = self.get_user_info("hand", "", "")
        if result:
            return result_data
        else:
            self.auto.raise_err_and_write_log("获取手中武器失败", 5)

    def get_user_hand_id(self):
        """
        获取手中武器id
        @return:
        """
        result_data, result = self.get_user_info("hand", "", "")
        if result:
            hand_items_id = dict(result_data)['id']
            print(hand_items_id)
            return hand_items_id
        else:
            return 0

    def get_user_item_all(self, get_type):
        """
        获取角色身上的物品/装备
        @param get_type:bag 背包  shortcut 快捷栏 wear 穿戴
        @return:
        """
        if get_type in ["bag", "shortcut", "wear", ]:
            result_data, result = self.get_user_info("getItem", "", get_type)
            if result:
                return result_data
            else:
                self.auto.raise_err_and_write_log("获取死亡提示语失败", 5)
        else:
            self.auto.raise_err_and_write_log("查询的类型错误，应为bag shortcut wear中的一种", 5)

    def get_client_version(self):
        """
        获取客户端包的版本信息
        @return:
        """
        result_data, result = self.get_user_info("version", "", "")
        return result_data

    def use_item(self, ues_index, ues_type):
        """
        触发背包/装备里的道具
        @param ues_index:处于背包中的格子，从0开始
        @param ues_type:
        @return:
        """
        if ues_type in ["wear", "bag"]:
            if ues_type == "bag" and ues_index <= 20:
                self.tidy_bag()
                result_data, result = self.get_user_info("useItem", ues_index, ues_type)
                print("111", result_data)
                # print("222",result)
            elif ues_type == "bag" and 30 > ues_index > 20:
                self.tidy_bag()
                self.swipe_bag_down()
                print("33333")
                num = ues_index
                row = num // 3 - 7
                column = num % 3
                print(row, column)
                if row == 0 and column == 0:
                    name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                    print(name)
                    self.auto.auto_touch(name)
                    if column != 0:
                        name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.{column}"
                        # final_path = name + f".{column}"
                        print(name)
                        self.auto.auto_touch(name)
                else:
                    if row > 0 and column == 0:
                        name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                        print(name)
                        self.auto.auto_touch(name)
                    else:
                        name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                        print(name)
                        self.auto.auto_touch(name, is_include=False)
            else:
                self.auto.raise_err_and_write_log("使用道具失败,背包范围在0-29", 5)
        else:
            self.auto.raise_err_and_write_log("使用道具类型不存在", 5)

    def get_loot_entity(self):
        """
        获取准心对准的entity
        @return:
        """
        result_data, result = self.get_user_info("getLootEntity", "", "")
        if not result:
            self.auto.add_log("未获取到指向的Entity")
        else:
            self.auto.add_log("获取指向Entity完毕")
            return result_data

    def use_build(self, use_index):
        """
        触发背包/装备里的道具
        @param use_index:处于背包中的格子，从0开始
        @return:
        """
        result_data, result = self.get_user_info("useBuild", use_index, "")
        if not result:
            self.auto.raise_err_and_write_log("使用快捷栏道具失败", 5)
        else:
            self.auto.add_log(result_data)

    def use_tech(self, tech_index, tech_type):
        """
        科技树科技触发
        @param tech_index:按钮的位置
        @param tech_type:main是左侧战斗系生存系按钮，child是里面的小科技位置
        @return:
        """
        if tech_type in ["main", "child"]:
            result_data, result = self.get_user_info("useTech", tech_index, tech_type)
            if not result:
                self.auto.raise_err_and_write_log("点击科技树", 5)
        else:
            self.auto.raise_err_and_write_log("科技树类型不存在", 5)

    def use_item_type(self, index):
        """
        背包物品类型触发
        @return:
        """
        result_data, result = self.get_user_info("itemtype", index, "")
        if not result:
            self.auto.raise_err_and_write_log("点击背包物品类型", 5)

    def use_small_map(self):
        """
        触发小地图
        @return:
        """
        result_data, result = self.get_user_info("smallMap", "", "")
        if not result:
            self.auto.raise_err_and_write_log("点击小地图失败", 5)

    def use_make_item(self, tech_index):
        """
        触发制造界面
        @param tech_index:按钮的位置
        @return:
        """
        result_data, result = self.get_user_info("makeItem", tech_index, "")
        print(result_data)
        if not result:
            self.auto.raise_err_and_write_log("制造物不存在", 5)

    def find_make_item(self, item_name):
        """
        在制造界面中寻找物品
        @param item_name:物品的名称
        @return:
        """
        make_group_list = ["GList/BtnCraftType", "GList/BtnCraftType.2", "GList/BtnCraftType.3",
                           "GList/BtnCraftType.4", "GList/BtnCraftType.5"]
        is_find = False
        for make_group in make_group_list:
            if is_find:
                break
            self.auto.auto_touch(make_group)
            self.auto.auto_sleep(2)
            make_unit = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/GLoader/ComCraft/GList/ComCraftIcon"
            for index in range(17):
                if index == 0:
                    make_node_text = make_unit + "/TextField"
                else:
                    make_node_text = make_unit + "." + str(index) + "/TextField"
                unit_name = self.get_poco_text(make_node_text)
                if unit_name == item_name:
                    self.use_make_item(index)
                    is_find = True
                    break
                index += 1
        if not is_find:
            self.auto.raise_err_and_write_log("未找到物品", 5)

    def make_item(self, number):
        """
        调节制作数量并制作
        @param number:需要的数量
        @return:
        """
        num = (
            "Stage/GRoot/(Full Screen) ID501|S501/UiCraft(UiCraft)/ContentPane/ComCraftRoot/GLoader/ComCraft/ComCraftInfo/ComCraftInfoTitle/TextField")
        text_num = int(self.get_poco_text(num))
        craft_num = (
            "Stage/GRoot/(Full Screen) ID501|S501/UiCraft(UiCraft)/ContentPane/ComCraftRoot/GLoader/ComCraft/ComCraftInfo/BtnCraftNum.1")
        while text_num != number:
            if text_num > number:
                self.auto.auto_touch(craft_num)
                text_num -= 1
            else:
                self.auto.auto_touch(craft_num + ".1")
                text_num += 1
        craft = (
            "Stage/GRoot/(Full Screen) ID501|S501/UiCraft(UiCraft)/ContentPane/ComCraftRoot/GLoader/ComCraft/ComCraftInfo/ComCustomButton/GLoader/BtnCraftStart")
        self.auto.auto_touch(craft)

    def use_bag_item(self, ues_index):
        """
        触发背包的道具
        @param ues_index:处于背包中的格子，从0开始
        @return:
        """
        self.use_item(ues_index, "bag")

    def use_wear_item(self, ues_index):
        """
        触发装备里的道具
        @param ues_index:处于背包中的格子，从0开始
        @return:
        """
        self.use_item(ues_index, "wear")

    def bag_item_equip(self):
        """
        使用道具，穿
        @return:
        """
        poco_name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/Container/Container/5"
        self.auto.auto_touch(poco_name)

    def bag_item_take_off(self):
        """
        使用道具，脱
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComTipsMain/GList/Container/Container/TakeOff"
        self.auto.auto_touch(poco_name)

    def bag_item_eat(self):
        """
        使用道具，吃
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComTipsMain/GList/Container/Container/Eat"
        self.auto.auto_touch(poco_name)

    def bag_item_split(self):
        """
        使用道具，拆分
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComTipsMain/GList/Container/Container/Split"
        self.auto.auto_touch(poco_name)

    def bag_item_split_confirm(self):
        """
        拆分界面的拆分按钮，点击进行确认拆分
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComPopSplit/BtnPopupSplit"
        self.auto.auto_touch(poco_name)

    def bag_item_drop(self):
        """
        使用道具，丢弃
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComTipsMain/GList/Container/Container/Drop"
        self.auto.auto_touch(poco_name)

    def bag_item_part_drop(self):
        """
        使用道具，批量丢弃
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComTipsMain/GList/Container/Container/PartDrop"
        self.auto.auto_touch(poco_name)

    def bag_item_organize(self):
        """
        使用道具，批量丢弃
        @return:
        """
        poco_name = "Stage/GRoot/ContentPane/ComInventoryMainNew/ComInventoryMainOrgainze"
        self.auto.auto_touch(poco_name)

    def move_item(self, move_index, move_type, target_index, cell_index=0):
        """
        移动身上的道具
        @param move_index:移动道具的位置
        @param move_type:移动类型 s2b快捷键到背包   b2s背包到快捷键  b2o背包到异端容器 o2b异端容器到背包
        @param target_index:移动道具的目标位置
        @param cell_index:目标容器的子容器编号，一般从上到下、从左到右由0递增，特殊情况如下：
        熔炉：燃料0，矿物1，产出2
        研究台： 研究物0，消耗废料1，研究成果2
        @return:
        """
        if move_type in ["s2b", "b2s", "b2o", "o2b"]:
            result_data, result = self.get_user_info("moveItem", [move_index, target_index, cell_index], move_type)
            if not result:
                self.auto.raise_err_and_write_log("移动道具失败", 5)
        else:
            self.auto.raise_err_and_write_log("查询的类型错误，应为s2b b2s b2o o2b中的一种", 5)

    def open_build(self):
        """
        进入建造界面
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.36/BtnStartBuild"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(5)
        # if not self.touch_upgrade_is_return():
        #     self.auto.auto_touch(name)
        #     self.auto.auto_sleep(5)
        # if not self.touch_upgrade_is_return():
        #     self.auto.raise_err_and_write_log("建筑界面打开失败", 5)

    def close_build(self):
        """
        关闭建造界面
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.36/BtnStartBuild"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(4)
        # if self.touch_upgrade_is_return():
        #     name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.37/BtnStartBuild"
        #     self.auto.auto_touch(name)
        #     self.auto.auto_sleep(4)
        # if self.touch_upgrade_is_return():
        #     self.auto.raise_err_and_write_log("建筑界面关闭失败", 5)

    def is_in_build(self):
        """
        判断是否在建筑界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemBuild/GList/Container/Container/BtnBuildSencondType"
        return self.get_poco_exist(name)

    def build_toggle_build(self):
        """
        切换至建造模式
        :return:
        """
        # 这个好像没人用过，就不改了
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(GameHud-UiHudMain)/ContentPane/UiHudElems/ToggleConstructType/BtnSelectConstructType.1"
        self.auto.auto_touch(name)

    def build_toggle_repair(self):
        """
        切换至修理模式
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(GameHud-UiHudMain)/ContentPane/UiHudElems/ToggleConstructType/BtnSelectConstructType"
        self.auto.auto_touch(name)

    def do_build(self):
        """
        进行建造
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemBtnBuildOK"
        self.auto.auto_touch(name)

    def do_build_operation(self, build_name, err_num=5, is_rotate=False, is_up=True, **kwargs):
        """
        执行建造操作,必须要用这个函数建造，因为建筑建造有红色状态检测，是红的就没办法造
        @param build_name: 建筑的名字
        @param err_num:视角检索次数，如果超过这个次数的视角旋转都无法建造，就当做失败
        @param is_rotate:建筑本身是否需要旋转
        @param is_up:是否需要抬头低头来使建筑完成建造
        @return:
        """
        # 先拉取视角，看看上下方向是不是要变了
        is_build = False
        run_num = 0
        while not is_build:
            is_build = self.do_build_rpc(build_name, **kwargs)
            if not is_build:
                up_or_down = False
                pos_dic, is_get = self.get_camera()
                if is_get:
                    rotation = pos_dic["rotation"]  # 视角
                    position = pos_dic["position"]
                    # T是上，F是下
                    if rotation["y"] > 40:
                        up_or_down = False
                    elif rotation["y"] < -60:
                        up_or_down = True
                    else:
                        up_or_down = False
                else:
                    self.auto.raise_err_and_write_log("摄像机数据获取失败", 5)
                if up_or_down:
                    direction = "up"
                else:
                    direction = "down"
                if is_up:
                    self.set_visual_angle(direction, 5)
                if is_rotate:
                    self.build_rotate()
                self.set_visual_angle("left", 5)
                run_num += 1
                if err_num <= run_num:
                    self.close_build()
                    self.auto.raise_err_and_write_log(f"建造了{run_num}次都没有成功，请检查", 5)

    def do_build_operation_log(self, build_name, log_num=5, is_rotate=False, is_up=True, **kwargs):
        """
        执行建造操作,必须要用这个函数建造，因为建筑建造有红色状态检测，是红的就没办法造
        @param build_name: 建筑的名字
        @param log_num:视角检索次数，如果超过这个次数的视角旋转都无法建造，就当做失败。不要报错
        @param is_rotate:建筑本身是否需要旋转
        @param is_up:是否需要抬头低头来使建筑完成建造
        @return:
        """
        # 先拉取视角，看看上下方向是不是要变了
        is_build = False
        run_num = 0
        while not is_build:
            is_build = self.do_build_rpc(build_name, **kwargs)
            if not is_build:
                up_or_down = False
                pos_dic, is_get = self.get_camera()
                if is_get:
                    rotation = pos_dic["rotation"]  # 视角
                    position = pos_dic["position"]
                    # T是上，F是下
                    if rotation["y"] > 40:
                        up_or_down = False
                    elif rotation["y"] < -60:
                        up_or_down = True
                    else:
                        up_or_down = False
                else:
                    self.auto.raise_err_and_write_log("摄像机数据获取失败", 5)
                if up_or_down:
                    direction = "up"
                else:
                    direction = "down"
                if is_up:
                    self.set_visual_angle(direction, 5)
                if is_rotate:
                    self.build_rotate()
                self.set_visual_angle("left", 5)
                run_num += 1
                if log_num <= run_num:
                    self.auto.add_log(f"建造了{run_num}次都没有成功，请检查", 5)
                    return

    def gm_rpc(self, rpc_name, gm_value, gm_type="", need_err=True, is_log=True):
        # 调用unity内置rpc接口
        if gm_value == "":
            gm_value = []
        result_data, result, msg = self.auto.send_rpc_and_read_result({"callGM": {"name": rpc_name,
                                                                                  "value": gm_value,
                                                                                  "type": gm_type}}, is_err=False)
        if not result:
            if need_err:
                self.auto.raise_err_and_write_log(f"gm_rpc type:{gm_type} name {rpc_name} 调用失败：{msg}，{result_data}",
                                                  5)
        else:
            if is_log:
                self.auto.add_log(f"方法：{rpc_name}调用：{gm_value} 结果：{result_data}")
        return result_data

    def gm_rpc_v3(self, rpc_name, gm_value, gm_type="", need_err=True, is_log=True):
        # 调用unity内置rpc接口
        if gm_value == "":
            gm_value = []
        result_data, result, msg = self.auto.send_rpc_and_read_result({"callGM": {"name": rpc_name,
                                                                                  "value": gm_value,
                                                                                  "type": gm_type}}, is_err=False)
        if not result:
            if need_err:
                self.auto.raise_err_and_write_log(f"gm_rpc type:{gm_type} name {rpc_name} 调用失败：{msg}，{result_data}",
                                                  5)
        else:
            if is_log:
                self.auto.add_log(f"方法：{rpc_name}调用：{gm_value} 结果：{result_data}")
        return result_data, result

    def gm_rpc_v2(self, rpc_name, gm_value, gm_type=""):
        # 调用unity内置rpc接口
        if gm_value == "":
            gm_value = []
        result_data, result, msg = self.auto.send_rpc_and_read_result({"callGM": {"name": rpc_name,
                                                                                  "value": gm_value,
                                                                                  "type": gm_type}}, is_err=False)
        self.auto.add_log(f"方法：{rpc_name}调用：{gm_value} 结果：{result_data}")
        return result_data, result

    def do_build_rpc(self, build_name, **kwargs):
        """
        通过节点进行建造，会先判断一下状态能不能造，如果可以会直接造
        :return:
        """
        try:
            is_build_msg = self.is_build(build_name)
            print(is_build_msg)
            if "建筑节点未找到,无法判断状态" == is_build_msg:
                return False
            elif "红色,无法建造" == is_build_msg:
                return False
            elif "可以建造" == is_build_msg:
                self.gm_rpc("build", build_name, need_err=kwargs.get("need_err", True))
                return True
            else:
                return False
        except Exception:
            pass
        return False

    def is_this_build(self, build_name):
        """
        判断当前选中的拟建体是不是指定的建筑
        @param build_name:
        @return:
        """
        try:
            is_build_msg = self.is_build(build_name)
            print(is_build_msg)
            if "建筑节点未找到,无法判断状态" == is_build_msg:
                return False
            elif "红色,无法建造" == is_build_msg:
                return True
            elif "可以建造" == is_build_msg:
                return True
            else:
                return False
        except Exception:
            pass
        return False

    def is_build(self, build_name):
        """
        判断是否可以建造
        @param build_name:
        @return:
        """
        try:
            return self.gm_rpc("is_build", build_name, need_err=False)
        except Exception:
            return False

    def find_scene_rpc(self):
        """
        查询场景中的内容，目前只能查建筑
        :return:
        """

        return self.gm_rpc("findScene", "", is_log=False)

    def get_perf_devices_id(self):
        """
        获取性能测试中设备信息
        :return:
        """

        return self.gm_rpc("get", "", "perf_info")

    def get_dc_count(self, is_open=True):
        """
        获取当前坐标面向方向的面数，这个数据会积累，需要定时清理，每次请求这个会清理，性能
        :return:
        """
        self.auto.add_log(f"DC采集{is_open}")
        return self.gm_rpc("get", [is_open], "CalculateDC", is_log=False, need_err=False)

    def get_server_time(self):
        """
        获取当前服务器时间
        :return:
        """
        return self.gm_rpc("get", "", "server_time")

    def get_map_id(self):
        """
        获取当前服务器地图id
        :return:
        """
        result_dic = self.gm_rpc("get", "", "map_id")
        map_id = result_dic['map_id']
        return map_id

    def get_sky_color(self):
        """
        获取当前光源变化
        :return:
        """
        return self.gm_rpc("get", "", "sky_color")

    def get_light_num(self):
        """
        获取当前光源总数
        :return:
        """
        return self.gm_rpc("get", "", "light_num")

    def get_is_onmount(self):
        """
        获取当前角色是否在载具上
        :return:
        """
        is_on_mount = False
        is_get = True
        result_dic = self.gm_rpc("get", "", "is_on_mount")
        if result_dic["is_on_mount"] == "True":
            is_on_mount= True
        elif result_dic["is_on_mount"] == "False":
            is_on_mount= False
        else:
            self.auto.add_log("获取是否在载具上功能异常")
            is_get = False
        return is_on_mount, is_get

    def has_any_mounted(self):
        """
        获取当前角色是否在驾驶位
         :return
        """
        HasAnyMounted = False
        is_get = True
        result_has_any_mounted = self.gm_rpc("get", "", "HasAnyMounted")
        if result_has_any_mounted["HasAnyMounted"] == "True":
            HasAnyMounted = True
        elif result_has_any_mounted["HasAnyMounted"] == "False":
            HasAnyMounted = False
            is_get = False
        else:
            self.auto.add_log("获取是否在驾驶位接口功能异常")
            is_get = False
        return HasAnyMounted, is_get
    def find_build_by_name(self, build_name):
        """
        查询建造的物体是否成功，理论上只能查一个，要在造之前调move_self_parts函数删掉所有建筑
        :return:
        """
        scene_dic = self.find_scene_rpc()
        parts_name_list = scene_dic["parts"]
        for parts_name in parts_name_list:
            if build_name in parts_name:
                return True
        return False

    def get_pos_monument(self):
        """
        获取当前位置遗迹相对坐标
        :return:
        """
        result_dic, result = self.gm_rpc_v3("get", "", "TestGetPlayerLocalPosInMonument")
        if result == True:
            return result_dic
        else:
            self.auto.add_log("没有找到遗迹，请在遗迹范围内")

    def get_globalpos_monument(self, monument, x, y, z):
        """
        通过遗迹相对坐标获取世界坐标
        :return:
        """
        result_dic, result = self.gm_rpc_v3("get", [monument, x, y, z], "TestPlayerTeleportToMonument")
        if result == True:
            return result_dic
        else:
            self.auto.add_log("获取失败，请检查遗迹名输入是否有误")

    def use_shortcut_item(self, index: int):
        """
        选择快捷栏里的东西
        :param index:
        :return:
        """
        self.touch_key_func(index, 214)

    def build_rotate(self):
        """
        旋转建筑的角度
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemBtnTurnRight01"
        self.auto.auto_touch(name)

    def build_edit_confirm(self):
        """
        建筑编辑确认
        :return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/EditConstructionPanel/btnProcessPart"
        self.auto.auto_touch(name)

    def up(self):
        self.controls_role("Up")

    def down(self):
        self.controls_role("Down")

    def controls_role(self, move_type: str):
        """
        操作角色
        @param move_type:移动的类型
        @return:
        """
        """
        /// 向前移动
        public bool MoveForward
        /// 向后移动
        public bool MoveBackward
        /// 向右移动
        public bool MoveRight
        /// 向左移动
        public bool MoveLeft
        /// 是否向前连续移动
        public bool MoveForwardContinuous
        /// 是否向后连续移动
        public bool MoveBackwardContinuous
        /// 是否向右连续移动
        public bool MoveRightContinuous
        /// 是否向左连续移动
        public bool MoveLeftContinuous
        /// 跳跃
        public bool Jump
        /// 连续跳跃
        public bool JumpContinus
        /// Idle
        public bool Idle
        /// 是否连续Idle
        public bool IdleContinus
        /// Walk
        public bool Walk
        /// 是否连续Walk
        public bool WalkContinus
        /// Run
        public bool Run
        /// 是否连续Run
        public bool RunContinus
        /// 急速跑
        public bool Sprint  
        /// 是否连续急速跑       
        public bool SprintContinus
        /// 下蹲
        public bool Crouch
        /// 连续下蹲
        public bool CrouchContinus
        /// 匍匐（趴下）
        public bool Crawl
        /// 连续匍匐（趴下）
        public bool CrawlContinus
        /// 开火取消
        public bool FireCancel
        /// 开火1
        public bool Fire1
        /// 连续开火1
        public bool Fire1Continus
        /// 开火2键（右键，开镜 手雷投掷远抛 等特殊攻击方式）
        public bool Fire2
        /// 连续开火2键（右键，开镜）
        public bool Fire2Continus
        /// AI呼救
        public bool Recourse = false;
        /// 换弹
        public bool Reload
        /// 连续换弹
        public bool ReloadContinus
        /// 检视
        public bool Review        
        /// 连续检视
        public bool ReviewContinus
        /// 救助
        public bool Aid
        /// 连续救助
        public bool AidContinus
        /// 自杀
        public bool Suicide
        /// 连续自杀
        public bool SuicideContinus        
        /// 交互
        public bool Interaction
        /// 长按交互
        public bool InteractionContinus
        /// 拾取
        public bool PickUp
        /// 长按拾取
        public bool PickUpContinus
        /// 表演
        public bool ShowAction
        /// 攻击行为
        public bool AttackAction
        /// 检视
        public bool Dance
        /// 连续检视
        public bool DanceContinus
        /// 起床
        public bool WakeUpAction
        /// 结束倒地
        public bool EndWound
        /// fly
        public bool Fly
        /// 向上
        public bool Up
        /// 持续向上
        public bool UpContinue
        /// 向下
        public bool Down
        /// 持续向下
        public bool DownContinue
        /// 观察者
        public bool Observer
        """
        for i in range(20):
            self.set_rpc_value_v1("Mc.UserCmd.NowCmd." + move_type, True)

    def controls_role_v2(self, move_type_list, run_num: int = 20, set_value=True):
        """
        操作角色
        @param move_type_list:移动的类型列表
        @param run_num:连续操作的次数
        @param set_value:连续操作的次数
        @return:
        """
        if len(move_type_list) > 1:
            cmd_list = []
            for move_type in move_type_list:
                cmd_list.append("Mc.UserCmd.NowCmd." + move_type)
            run_cmd = "、".join(cmd_list)
        else:
            run_cmd = "Mc.UserCmd.NowCmd." + move_type_list[0]
        for i in range(run_num):
            self.set_rpc_value_v1(run_cmd, set_value)

    def find_item_index(self, resource_id, get_type):
        """
        获取角色身上的物品/装备
        @param resource_id:需要找的资源的id
        @param get_type:bag 背包  shortcut 快捷栏 wear 穿戴
        @return:
        """
        if get_type in ["bag", "shortcut", "wear", ]:
            result_list = self.get_user_item_all(get_type)
            print(result_list)
            for i in range(len(result_list)):
                if result_list[i] == resource_id:
                    return i, True
        return 0, False

    def clear_item_shortcut(self, clear_i=-1):
        """
        清空快捷栏 默认是全部清空
        @param clear_i: 当指定的话，就清空指定的位置
        @return:
        """
        result_list = self.get_user_item_all("shortcut")
        for i in range(len(result_list)):
            if clear_i != -1:
                if i != clear_i:
                    continue
            item_id = result_list[i]
            if item_id != 0:
                num = self.get_item_shortcut(i)
                is_drop = self.drop_item_shortcut(i, num)
                if not is_drop:
                    break
                time.sleep(0.1)

    def clear_item_bag(self):
        """
        清空背包
        @return:
        """
        result_list = self.get_user_item_all("bag")
        for i in range(len(result_list)):
            item_id = result_list[i]
            if item_id != 0:
                num = self.get_item_bag(i)
                is_drop = self.drop_item_bag(i, num)
                if not is_drop:
                    break
                time.sleep(0.1)

    def clear_item_wear(self):
        """
        清空身上
        @return:
        """
        result_list = self.get_user_item_all("wear")
        for i in range(len(result_list)):
            if result_list[i] != 0:
                self.drop_item_wear(i, 1)

    def move_to(self, direction, move_num=11):
        """
        向指定方向移动11次
        @param direction: 方向
        @param move_num:移动的次数
        @return:
        """
        pos_dic, is_get = self.get_camera()
        if is_get:
            rotation = pos_dic["rotation"]  # 视角
            position = pos_dic["position"]
            for i in range(move_num):
                self.controls_role(direction)
            distance = self.get_coordinate_interval(
                [position["x"], position["y"], position["z"]])
            if distance > 10:
                return True, ""
            else:
                return False, f"向{direction}方向移动失败"
        else:
            return False, "摄像机数据获取失败"

    def move_to_pos(self, x, y, z, run_num=5, distance_limiting=2, add_pitch=10, transfer_help=False, is_vehicle=False,
                    is_fly=False, check_angle=10, limit_time=0, is_boat=False):
        """
        移动到指定坐标
        @param x:
        @param y:
        @param z:
        @param run_num:每次矫正方向后移动的距离
        @param distance_limiting:最大限制距离，有些载具行为没办法停的太近
        @param add_pitch:瞄准的视角高度补偿
        @param transfer_help: 是否开启智能传送辅助，复杂场景建议开启
        @param is_vehicle：是否为地面载具
        @param check_angle： 设置角度检查的范围，仅载具可用（因为人可以转视角，不用角度判定）
        @return:
        """

        # 判断载具角度
        def is_angle_within_range(angle_A, angle_B, tolerance=check_angle):
            # 判定当前角度是否在目标角度+-check_angle范围内
            lower_bound = angle_B - tolerance
            upper_bound = angle_B + tolerance
            lower_bound = lower_bound % 360
            upper_bound = upper_bound % 360
            if lower_bound <= upper_bound:
                return lower_bound <= angle_A <= upper_bound
            else:
                return angle_A >= lower_bound or angle_A <= upper_bound

        old_distance = 0
        run_stop_num = 0
        run_time_num = 0
        is_broken = False
        start_time = time.time()
        while True:
            if limit_time != 0:
                if time.time() - start_time > limit_time:
                    return False, is_broken
            result_data, result = self.get_sky_tools(rpc_name="move_collimation",
                                                     get_value={"x": x, "y": y, "z": z, }, get_type="", add_log=False)
            if result:
                pitch = result_data["pitch"]
                yaw = result_data["yaw"]
                distance = result_data["distance"]
                height_diff = result_data["heightDiff"]
                if distance < 30:
                    run_num = 1
                if old_distance != 0 and abs(old_distance - distance) < 1:
                    # 这里说明上次移动的距离有点近，可能是被卡住了
                    print("两次坐标移动间距较短")
                    run_stop_num += 1
                if run_stop_num == 2 and not transfer_help and not is_vehicle:
                    # 说明在一个地方卡很久了
                    yaw += 90  # 改一下方向
                    self.controls_role_v2(["MoveForward", "Jump"])
                    run_num = 10
                if run_stop_num > 4:
                    # 这里处理进到死胡同之后传送出去
                    # transfer_help：直接传， is_vehicle：倒车后绕行， 其他：传送至目标点附近
                    if transfer_help:
                        self.hotmap_transmit_to([x, y, z], False)
                        break
                    if is_vehicle:
                        if is_boat:
                            is_broken = True
                            print("快艇长时间不动了，可能搁浅")
                            return False, is_broken
                        self.move_to("MoveBackward", 3)
                        time.sleep(2)
                        self.controls_role_v2(["MoveLeft", "MoveForward"], 30)
                        self.move_to("MoveForward", 3)
                        time.sleep(1)
                        self.controls_role_v2(["MoveRight", "MoveForward"], 15)
                        run_stop_num = 0
                        continue
                    else:
                        pos_dic, is_get = self.get_camera(False)
                        move_x = pos_dic["position"]["x"]
                        if move_x < x:
                            move_x += 5
                        else:
                            move_x -= 5
                        move_y = pos_dic["position"]["y"] + 50
                        move_z = pos_dic["position"]["z"]
                        if move_z < z:
                            move_z += 5
                        else:
                            move_z -= 5
                        self.transmit_to([move_x, move_y, move_z])
                        run_stop_num = 0
                if old_distance > distance - 1 or old_distance == 0 or run_stop_num == 2 or is_vehicle:
                    old_distance = distance
                # else:
                #     print("越跑越远了，载具不能掉头的会出现这种情况")
                #     return False
                if distance < distance_limiting:
                    print("到达目的地")
                    return True, is_broken
                pos_dic, is_get = self.get_camera(False)
                pre_x = pos_dic["position"]["x"]
                pre_y = pos_dic["position"]["y"]
                pre_z = pos_dic["position"]["z"]
                pre_yaw = pos_dic["rotation"]["x"]
                if is_boat:
                    if pre_y < 0.5:
                        is_broken = True
                        print("相机低于0.5m，可能翻船了")
                        return False, is_broken
                if is_vehicle:
                    # 载具转向寻路
                    if is_angle_within_range(pre_yaw, yaw):
                        is_check = True
                    else:
                        is_check = False
                    count = 0
                    max_count = 30
                    while not is_check:
                        if pre_yaw < yaw:
                            if abs(yaw - pre_yaw) <= 180:
                                self.controls_role_v2(["MoveRight", "MoveForward"], 3)
                            else:
                                self.controls_role_v2(["MoveLeft", "MoveForward"], 3)
                        else:
                            if abs(pre_yaw - yaw) <= 180:
                                self.controls_role_v2(["MoveLeft", "MoveForward"], 3)
                            else:
                                self.controls_role_v2(["MoveRight", "MoveForward"], 3)
                        pos_dic, is_get = self.get_camera(False)
                        pre_x = pos_dic["position"]["x"]
                        pre_z = pos_dic["position"]["z"]
                        pre_yaw = pos_dic["rotation"]["x"]
                        if is_angle_within_range(pre_yaw, yaw):
                            is_check = True
                        else:
                            is_check = False
                        count += 1
                        if count == max_count:
                            print(f"调整了{max_count}次都没调整到位，可能卡住了")
                            run_stop_num = 5
                            break
                elif is_fly:
                    self.set_role_pitch(0)
                    self.set_role_yaw(yaw)
                else:
                    self.set_role_pitch(pitch + add_pitch)
                    self.set_role_yaw(yaw)
                if run_num > 1 and not is_vehicle:
                    for i in range(run_num):
                        run_time_num += 1
                        self.running()
                        # 加一个报警，有的地方会导致掉到地下
                        if run_time_num % 2 == 0:  # 每两次测一下
                            pos_dic, is_get = self.get_camera(False)
                            if is_get:
                                position = pos_dic["position"]
                                if position["y"] < - 5:  # 这个是地面的高度
                                    self.auto.add_log(f"坐标{position}处可能会跌落地下", False)
                                if height_diff - distance < 3:
                                    y = position["y"]
                else:
                    run_time_num += 1
                    self.controls_role("MoveForward")
                    # old_distance = 0  # 因为这里移动距离是短，为了避免被强制转向
                if transfer_help:
                    pos_dic, is_get = self.get_camera(False)
                    cur_x = float(pos_dic["position"]["x"])
                    cur_z = float(pos_dic["position"]["z"])
                    cur_vector = np.array([cur_x, cur_z])
                    pre_vector = np.array([float(pre_x), float(pre_z)])
                    target_vector = np.array([float(x), float(z)])
                    move_vector = cur_vector - pre_vector
                    direction_vector = target_vector - cur_vector
                    if np.dot(direction_vector, move_vector) >= 0:
                        pass
                    else:
                        if not is_fly:
                            self.hotmap_transmit_to([x, y, z], False)
                        return True, is_broken
                if run_time_num % 2 == 0:  # 每两次测一下
                    pos_dic, is_get = self.get_camera(False)
                    if is_get:
                        position = pos_dic["position"]
                        if position["y"] < - 5:  # 这个是地面的高度
                            self.auto.add_log(f"坐标{position}处可能会跌落地下", False)
                        if height_diff - distance < 3:
                            y = position["y"]
            else:
                return True, is_broken

    def collimation_to_pos(self, x, y, z, add_pitch=20, add_yaw=0):
        """
        瞄准指定坐标
        @param x:
        @param y:
        @param z:
        @param add_pitch:视角抬高补偿
        @param add_yaw:视角抬高补偿
        @return:
        """
        result_data, result = self.get_sky_tools(rpc_name="move_collimation",
                                                 get_value={"x": x, "y": y, "z": z, }, get_type="", add_log=False)
        print(result_data)
        if result:
            pitch = result_data["pitch"]
            yaw = result_data["yaw"]
            self.set_role_pitch(pitch + add_pitch)
            self.set_role_yaw(yaw + add_yaw)
        return result_data

    def set_role_pitch(self, pitch):
        """
        设置视角-上下
        @param pitch:
        @return:
        """
        self.set_rpc_value("Mc.Control.RotationControl.Pitch", pitch, False)

    def set_role_yaw(self, yaw):
        """
        设置视角-左右
        @param yaw:
        @return:
        """
        self.set_rpc_value("Mc.Control.RotationControl.Yaw", yaw, False)

    def running(self):
        """
        奔跑
        @return:
        """
        self.controls_role_v2(["MoveForward", "Run", "RunContinus", "Sprint", "SprintContinus"])

    def climb(self):
        """
        攀爬 爬上地基等操作
        @return
        """
        self.controls_role_v2(["MoveForward", "Jump"])

    def kill_myself(self):
        """
        传送到高空自杀
        """
        # 关闭无敌
        self.close_damage_disable()
        # 需要一个固定坐标可以死亡
        self.transmit_to([-1021, 50, -351])
        # 获取玩家状态
        # 这里多等几秒防止误报
        self.auto.auto_sleep(15)
        user_info = self.get_user_stats()
        life = user_info["hp"]
        # 判断是否进入濒死状态
        if life == 30 or life == 31:
            self.auto.auto_sleep(35)
            user_info = self.get_user_stats()
            life = user_info["hp"]
            print("00000", life)
            if life == 0:
                return True
            else:
                # 此时小概率自动复活触发，再来一次
                self.auto.auto_sleep(15)
                self.transmit_to([-1096, 60, -194], True)
                self.auto.auto_sleep(35)
                user_info = self.get_user_stats()
                life = user_info["hp"]
                print("11111", life)
                if life == 0:
                    return True
        else:
            return False

    def respawn_die(self):
        """
        点击淘汰点附近复活，并且点击重生
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnPointList/GList/Container/Container/RespawnGroupCom/RespawnGroupPointCom/RespawnListBtn"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(1)
        self.reborn()
        return True

    def bed_respawn(self):
        """
        床位复活，并且点击重生
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnPointList/GList/Container/Container/RespawnGroupCom.2/RespawnGroupPointCom/RespawnListBtn"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(1)
        self.reborn()
        return True

    def use_weapon_item(self, use_id, index=0):
        """
        切换到指定武器
        @param use_id:武器表id
        @param index: 武器位置
        @return:
        """
        # 先看看在不在手里
        weapon_id = self.get_user_hand_id()
        if weapon_id == use_id:
            return
        else:
            self.clear_item_shortcut()
        # 上面走完了没有，说明快捷栏也没有
        self.auto.auto_sleep(2)
        self.add_resource_and_inspect(use_id, 1)
        self.auto.auto_sleep(2)
        self.use_shortcut_item(index)
        self.auto.auto_sleep(2)
        weapon_id = self.get_user_hand_id()
        if weapon_id == use_id:
            return
        else:
            self.auto.raise_err_and_write_log("完蛋，debug吧", 5)

    def touch_build_father(self, num_str):
        """
        点击建筑栏中的建筑，主函数，维护这一个就行了，其他的路径是一样的
        @param num_str:
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.24/ElemBuild/ComBuildItemListNew/GList/Container/Container/ComBuildPanelIcon" + num_str
        self.auto.auto_touch(name)

    def touch_build_type(self, num_str):
        """
        点击建筑栏中的不同种类，选择墙壁，地基，门窗，天花板，楼梯。主函数，维护这一个就行了，其他的路径是一样的
        @param num_str:
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.23/ElemBuild/GList/Container/Container/BtnBuildSencondType" + num_str
        self.auto.auto_touch(name)
        self.auto.auto_sleep(2)

    def touch_type_1(self):
        """
        点击对应编号位置的建筑种类，无需维护
        备注一下，拟建体的类别选择4或者5之后，地基类会因为不显示而销毁，所以1不能够再回到地基类别了
        @return:
        "摆件"
        """
        self.swipe_build_type_left()
        self.touch_build_type("")

    def touch_type_2(self):
        """
        点击对应编号位置的建筑种类，无需维护
        @return:
        “地基”
        """
        self.swipe_build_type_left()
        self.touch_build_type(".1")

    def touch_type_3(self):
        """
        点击对应编号位置的建筑种类，无需维护
        @return:
        “墙壁”
        """
        self.swipe_build_type_left()
        self.touch_build_type(".2")

    def touch_type_4(self):
        """
        点击对应编号位置的建筑种类，无需维护
        @return:
        "天花板"
        """
        self.swipe_build_type_right()
        self.touch_build_type(".3")

    def touch_type_5(self):
        """
        点击对应编号位置的建筑种类，无需维护
        @return:
        “门窗”
        """
        self.swipe_build_type_right()
        self.touch_build_type(".4")

    def touch_type_6(self):
        """
        点击对应编号位置的建筑种类，无需维护
        @return:
        “楼梯”
        """
        self.swipe_build_type_right()
        self.touch_build_type(".5")

    def swipe_build_type_left(self):
        """
        建造界面建筑栏滑到最左边
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemBuild/GList",
            swipe_value=["left", 0])
        self.auto.auto_sleep(1)

    def swipe_build_type_right(self):
        """
        建造界面建筑栏滑到最右边
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemBuild/GList",
            swipe_value=["right", 1])
        self.auto.auto_sleep(1)

    def touch_build_1(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father("")

    def touch_build_2(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".1")

    def touch_build_3(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".2")

    def touch_build_4(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".3")

    def touch_build_5(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".4")

    def touch_build_6(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".5")

    def touch_build_7(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".6")

    def touch_build_8(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".7")

    def touch_build_9(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".8")

    def touch_build_10(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".9")

    def touch_build_F1(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".10")

    def touch_build_F2(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".11")

    def touch_build_F3(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".12")

    def touch_build_F4(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".13")

    def touch_build_F5(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".14")

    def touch_build_F6(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".15")

    def touch_build_F7(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".16")

    def touch_build_F8(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".17")

    def touch_build_F9(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".18")

    def touch_build_F10(self):
        """
        点击对应编号位置的建筑，无需维护
        @return:
        """
        self.touch_build_father(".19")

    def build_panel_switch_1(self):
        """
        建筑列表翻页
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemBuild/ComBuildItemListNew/BtnBuildPanelSwitch"
        self.auto.auto_touch(name)

    def build_panel_switch_2(self):
        """
        建筑列表翻页,向后翻页
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemBuild/ComBuildItemListNew/BtnBuildPanelSwitch.1"
        self.auto.auto_touch(name)

    def user_stats_inspect(self):
        """
        角色状态检查，判断是不是健康状态
        @return:{'hunger': int, 'life': int, 'water': int}
        """
        result_data = self.get_self_entity()
        if result_data["hunger"] == 0:
            return False
        if result_data["life"] == 0:
            return False
        if result_data["water"] == 0:
            return False
        return True

    def set_module_name(self, module_name):
        """
        用例初始化需要调用的一些逻辑
        @param module_name:
        @return:
        """
        self.auto.set_module_name(module_name)
        # self.platform = self.auto.init_kwargs.get("task_info", {}).get('platform', "pc")
        # if self.platform == "android":
        #     ProFiler.start_pro_filer_unity()

    def case_over(self):
        """
        用例结束了，清理环境
        @return:
        """
        if "kwargs" in self.auto.init_kwargs["case_info"].keys():
            if "exe_name" in self.auto.init_kwargs["case_info"]["kwargs"].keys():
                if self.auto.init_kwargs["case_info"]["kwargs"]["exe_name"] != "":
                    # 检测exe是否存在 不存在进行报错
                    process_exists = False
                    for process in psutil.process_iter(['pid', 'name']):
                        if process.name() == "SocClient.exe":
                            process_exists = True
                            if process.status() != "running":
                                process_status = process.status()
                                self.auto.add_log(f"当前客户端存在但是状态为{process_status}", False)
                    if not process_exists:
                        self.auto.add_log("当前客户端进程已经不存在，可能遭遇了闪退", False)
        if self.is_2hours:
            if self.server_num is not None:
                # 调用接口发送重启服务器指令
                pipelines_token = "c9caf335129144d9aed2a30ce6d73842"
                url = f'http://devops-bk.wd.com/ms/process/api/external/pipelines/{pipelines_token}/build'
                headers = {"content-type": "application/json"}
                post_json = {'SERVER_NAME': f"dev-shipping", 'SERVER_ID': self.server_num, "DELETE_SAVE": "None"}
                pipelines_response = requests.post(url, json=post_json, headers=headers)
                print(pipelines_response)
                time.sleep(300)
                # 重启完成后判断服务器是否能够找到
                wait_num = 0
                server_list = []
                server_name = f"【shipping_release】性能-{self.server_num}"
                while server_name not in server_list:
                    server_list = get_server_list(True)
                    self.auto.add_log(f"等待服务器{server_name}启动，当前服务器列表{server_list}")
                    wait_num += 1
                    self.auto.auto_sleep(5)
                    if wait_num > 60:
                        self.auto.raise_err_and_write_log("重启后接近十分钟服务器都找不到，需要查询原因", 9)
                now_server_list = self.case_sql_server_tools_get("2hours_server", lock=True).get('case_info', [])
                now_server_list.remove(self.server_num)
                self.case_sql_server_tools_set("2hours_server", now_server_list, lock=False)
        self.auto.write_log_to_file(close_socket=True)
        # if self.platform == "android":
        #     ProFiler.stop_pro_filer_unity()

    def await_poco_client(self):
        """
        等待客户端启动
        @return:
        """
        device_ip = self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]
        if device_ip == '127.0.0.1':
            device_ip = get_self_ip()
        # 如果是安卓包，才会做这个检测，其他都默认可以正常进入游戏
        apk = self.auto.init_kwargs["task_info"]["game_git_info"]["apk"]
        if apk == "":
            return True
        self.auto.add_log(f"等待游戏启动,{device_ip}")
        try:
            response = requests.post("http://192.168.181.52:11454/tools/auto/uwa_poco_devices",
                                     json={"type": "get", "project_id": 33, "version": "", "state": "",
                                           "ip": device_ip})
            devices_info = response.json()
            if devices_info["success"]:
                devices_state = devices_info["data"]["devices_state"]
                if devices_state == "init":
                    self.auto.add_log(f"{device_ip}的设备启动游戏了")
                    return True
        except Exception as e:
            print(f"等待{device_ip}启动poco client报错{e}")
        return False

    def __touch_android_permissions_popup_window(self, ):
        """
        检测安卓权限弹窗
        @return:
        """
        touch_list = ["允许", "始终允许","ok","OK"]
        device_ip = self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]
        pos_list, is_ok = self.auto.ocr_get_text_pos(touch_list)
        self.auto.add_log(f"安卓设备{device_ip}检测是否有权限弹窗{pos_list}")
        if is_ok:
            get_ui_dic = self.auto.devices_send_dict({"type": "get_ui"})
            print(get_ui_dic)
            for touch_text in touch_list:
                if touch_text in get_ui_dic["data"]:
                    self.auto.devices_send_dict({"type": "click_text", "data": touch_text})
                    break
            return True
        else:
            self.auto.add_log(f"设备{device_ip}检测权限弹窗失败，{pos_list}")
        return False

    def __touch_ios_permissions_popup_window(self, ):
        """
        检测ios权限弹窗
        @return:
        """
        device_ip = self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]
        self.auto.add_log(f"ios设备{device_ip}检测是否有权限弹窗")
        get_ui_dic = self.auto.devices_send_dict({"type": "get_ui", "data": "Sure"})
        if len(get_ui_dic["data"]) > 0:
            self.auto.devices_send_dict({"type": "click_text", "data": get_ui_dic["data"][0]})
            return True
        get_ui_dic = self.auto.devices_send_dict({"type": "get_ui", "data": "允许"})
        if len(get_ui_dic["data"]) > 0:
            self.auto.devices_send_dict({"type": "click_text", "data": get_ui_dic["data"][0]})
            return True
        return False

    def __touch_permissions_popup_window(self, ):
        """
        检测安卓权限弹窗
        @return:
        """
        device_type = self.auto.init_kwargs["task_info"]["device_info"]["type"]
        if device_type == "ios":
            return self.__touch_ios_permissions_popup_window()
        elif device_type == "android":
            return self.__touch_android_permissions_popup_window()
        else:
            ...

    def game_is_open(self, await_time: int):
        """
        等待并检测游戏启动
        @param await_time: 分钟
        @return:
        """
        if self.auto.init_kwargs["link_type"] in [TestEnv.devices, TestEnv.devices_rpc]:
            for i in range(20):
                # 游戏启动的瞬间就会去注册
                poco_start = self.await_poco_client()  # 只有poco客户端才会上传这个信息，不过目前没有非poco客户端连跑用例
                if poco_start:
                    time.sleep(10)
                    break
                else:
                    self.auto.add_log("等待poco客户端启动")
                    time.sleep(60)
        for i in range(await_time * 6):
            try:  # 先校验一下poco能不能连上
                self.auto.get_new_poco_dic()
                return True  # 链接上了直接返回
            except Exception:
                try:
                    # 游戏启动的瞬间就会去注册，但是后面又会被权限弹窗卡主，判断注册了之后再去看权限弹窗
                    self.__touch_permissions_popup_window()
                    time.sleep(10)
                except Exception:
                    pass
            time.sleep(10)
        return False

    def case_init(self, damage_disable=False, is_health_judge=True, is_performance="True", is_battle=False,
                  is_2hours=False):
        """
        用例初始化函数，用于检查是否满足用例执行的通用逻辑，如有模块单独的检查条件，不要写在这里面
        @param damage_disable:是否开启无敌
        @param is_2hours: 是否是两小时，如果是，用新的找服务器逻辑
        @return:
        """
        if not is_health_judge:
            self.damage_disable = True
        self.case_name = ""
        if self.case_is_pass:
            msg = "游戏登录失败，跳过用例"
            self.auto.add_log(f"case_init {msg}")
            return msg
        if is_2hours:
            self.auto.auto_sleep(random.randint(0, 50))
            while True:
                if self.server_num is not None:
                    break
                now_server_list = self.case_sql_server_tools_get("2hours_server", lock=True).get('case_info', [])
                self.auto.add_log(
                    f"当前获取的服务器列表为{now_server_list} {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}")
                num = 0
                for num in range(6):
                    if num not in now_server_list:
                        self.server_num = num
                        now_server_list.append(num)
                        self.case_sql_server_tools_set("2hours_server", now_server_list)
                        break
                self.case_sql_server_tools_get("2hours_server", lock=False)
                if self.server_num is not None:
                    self.auto.add_log(f"当前设备要进的服务器为 【shipping_release】性能-{self.server_num}")
                    break
                self.auto.auto_sleep(5)
            self.auto.init_kwargs["case_info"]['server_name'] = f"【shipping_release】性能-{self.server_num}"
        self.server_name = self.auto.init_kwargs["case_info"].get('server_name', "")
        if self.server_name == "默认本地服" or self.server_name == "":
            self.server_name = os.getlogin()
        print("self.auto.init_kwargs", self.auto.init_kwargs)
        is_open = self.game_is_open(10)
        if not is_open:
            self.case_is_pass = True
            msg = f"{self.auto.task_id} poco启动失败，无法执行用例"
            self.auto.add_log(msg)
            return msg
        # todo 需要解决游戏重新启动的问题
        if is_battle:
            self.login_case_start_v2(self.server_name)
        else:
            self.login_case_start(self.server_name)
        self.init_pro_sight()  # 初始化一下这个数据，登录进入游戏的时候就会收集了，先关掉，等用例开始的时候再打开
        if damage_disable and not self.damage_disable:
            self.open_damage_disable()
        self.auto.auto_sleep(2)
        result_data, result = self.get_camera()
        if result:
            if result_data["position"]["y"] == 0:
                self.case_is_pass = True
                msg = "游戏启动失败，跳过用例"
                self.auto.add_log(msg)
                return msg
        else:
            self.case_is_pass = True
            msg = "游戏启动失败，跳过用例"
            self.auto.add_log(msg)
            return msg
        if not self.damage_disable:
            is_health = self.user_stats_inspect()
            if not is_health:
                self.case_is_pass = True
                msg = "没有处于健康状态，剩下的跳过"
                self.auto.add_log(msg)
                return msg
        if is_performance == "True":
            self.start_performance_test()
        return ""

    def set_case_name(self, case_name):
        """
        设置用例名
        @param case_name:
        @return:
        """
        self.auto.set_case_name(case_name)
        self.case_name = case_name
        self.auto.add_log(f"开始执行用例{case_name}")
        if self.case_is_pass:
            self.auto.add_log(f"用例前置条件检测失败，跳过用例{case_name}")
            raise unittest.SkipTest(f"用例前置条件检测失败，跳过用例{case_name}")

    def case_end(self):
        """
        用例执行结束统一需要调用的逻辑
        @return:
        """
        time.sleep(3)
        self.stop_performance_test()
        # self.auto.exit_app("")
        self.case_name = ""

    def close_damage_disable(self, ):
        """
        关闭无敌
        @return:
        """

        try:
            self.damage_disable = False
            self.gm_rpc("set", [False], "TestSetPlayerDamageDisable")
            print("无敌关闭")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_damage_disable(self, ):
        """
        开启无敌
        @return:
        """
        try:
            self.damage_disable = True
            self.gm_rpc("set", [True], "TestSetPlayerDamageDisable")
            self.auto.add_log("无敌开启")
            time.sleep(1)
        except Exception:
            return False
        return True

    def suicide(self):
        """
        自杀
        @return:
        """
        try:
            self.gm_rpc("set", [True], "Suicide")
            print("自杀")
            time.sleep(1)
        except Exception:
            return False
        return True

    def reborn_rpc(self, is_random=False):
        """
        复活
        @param is_random:是否随机复活
        @return:
        """
        try:
            self.gm_rpc("set", [is_random], "Reborn")
            print("复活")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_guide_system(self, ):
        """
        开启控件引导系统
        @return:
        """
        try:
            self.gm_rpc("set", [True], "TestSetGuideSystemOpen")
            time.sleep(1)
        except Exception:
            return False
        return True

    def close_guide_system(self, ):
        """
        开启控件引导系统
        @return:
        """
        try:
            self.gm_rpc("set", [False], "TestSetGuideSystemOpen")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_monster_ai(self, ):
        """
        开启怪物AI
        @return:
        """
        try:
            self.gm_rpc("set", [True], "ToggleAiState")
            print("ai开启")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_bot_enable(self, ):
        """
        打开机器人的移动攻击行为
        @return:
        """
        try:
            self.gm_rpc("set", [True], "SwitchBotEnable")
            time.sleep(1)
        except Exception:
            return False
        return True

    def close_bot_enable(self, ):
        """
        关闭机器人的移动攻击行为
        @return:
        """
        try:
            self.gm_rpc("set", [False], "SwitchBotEnable")
            time.sleep(1)
        except Exception:
            return False
        return True

    def set_sky_time(self, set_time):
        """
        设置服务器时间，修改天空颜色
        @set_time: 设置的时间 0为黑夜 12为中午 18为傍晚
        @return:
        """
        try:
            self.gm_rpc("set", [set_time], "SetSkyTime")
            print(f"设置时间为{set_time}")
            time.sleep(1)
        except Exception:
            return False
        return True

    def close_monster_ai(self, ):
        """
        关闭怪物AI
        @return:
        """
        try:
            self.gm_rpc("set", [False], "ToggleAiState")
            print("ai关闭")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_part(self, is_open):
        """
        开启建筑无限建造模式
        @return:
        """
        try:
            self.gm_rpc("set", [is_open], "TestSetNoConsumptionMode")
            print(f"设置无限建造{is_open}")
            time.sleep(1)
        except Exception:
            return False
        return True

    def close_auto_pick(self, ):
        """
        关闭自动拾取
        @return:
        """
        try:
            self.set_rpc_value("Mc.GatherItemPickable.isAutoPickSetting", False)
            print("自动拾取关闭")
            time.sleep(1)
        except Exception:
            return False
        return True

    def open_auto_pick(self, ):
        """
        打开自动拾取
        @return:
        """
        try:
            self.set_rpc_value("Mc.GatherItemPickable.isAutoPickSetting", True)
            print("自动拾取关闭")
            time.sleep(1)
        except Exception:
            return False
        return True

    def clear_item_all(self):
        """
        清空身上三个栏的东西
        @return:
        """
        self.clear_item_shortcut()
        self.clear_item_wear()
        self.clear_item_bag()

    def adjust_perspective(self, ):  # todo ？ 看看后续是不是要废弃
        """
        调整视角
        @param :
        @return:
        """
        # 先拉取视角，看看上下方向是不是要变了
        pos_dic, is_get = self.get_camera()
        up_or_down = True  # T是上，F是下
        if is_get:
            rotation = pos_dic["rotation"]  # 视角
            position = pos_dic["position"]
            if rotation["y"] > 60:  # 抬头太高就没用了
                up_or_down = False
            else:
                up_or_down = True
        else:
            self.auto.raise_err_and_write_log("摄像机数据获取失败", 5)

    def distance(self, now, old):
        # 计算摄像机移动直线距离
        a = now['x'] - old['x']
        b = now['z'] - old['z']
        c = math.sqrt(a ** 2 + b ** 2)
        return c

    def build_part(self, part_type, pos_x, pos_y, pos_z, angle_x, angle_y, angle_z, scale_x, scale_y, scale_z,
                   target_part_id, item_uid, gm_mode, mark_id, combo_id):
        """
        根据坐标复原录制的建筑
        :return:
        """
        try:
            self.gm_rpc("build_part",
                        [part_type, pos_x, pos_y, pos_z, angle_x, angle_y, angle_z, scale_x, scale_y, scale_z,
                         target_part_id, item_uid, gm_mode, mark_id, combo_id])
            return True
        except Exception:
            pass
        return False

    def battle_is_join_start(self):
        """
        查询是否在炸家选择阵营界面
        @return:
        """
        return self.auto.is_exist("选择阵营")

    def touch_bomb_home_akt(self):
        """
        点击进攻方
        @return:
        """
        self.auto.auto_touch(
            "<Root>/Stage/GRoot/(Popup) L601-LO601/UiSelectCamp(GameSelectCamp-UiSelectCamp)/ContentPane/GList/CampCard.1")

    def touch_bomb_home_ok(self):
        """
        点击确认
        @return:
        """
        self.auto.auto_touch(
            "<Root>/Stage/GRoot/(Popup) L601-LO601/UiSelectCamp(GameSelectCamp-UiSelectCamp)/ContentPane/confirmBtn")

    def battle_is_over(self):
        """
        查询一下是否在炸家结束界面
        @return:
        """
        return self.auto.is_exist("Proceed to Next Round")

    def bomb_home_next(self):
        """
        点击下一局
        @return:
        """
        return self.auto.auto_touch("Proceed to Next Round")

    def bomb_home_is_start(self):
        """
        炸家是否开始
        @return:
        """
        if self.auto.is_exist("玩家不足"):
            return True
        elif self.auto.is_exist("摧毁领地柜"):
            return True
        elif self.auto.is_exist("保护领地柜"):
            return True
        else:
            return False

    def bomb_home_battle_is_start(self):
        """
        炸家是否开始
        @return:
        """
        if self.auto.is_exist("玩家不足"):
            return False
        elif self.auto.is_exist("摧毁领地柜"):
            return True
        elif self.auto.is_exist("保护领地柜"):
            return True
        else:
            return False

    def open_cmd(self):
        """
        开启录制
        @return:
        """
        try:
            self.gm_rpc("set", [True], "CmdOpen")
        except Exception:
            return False
        return True

    def close_cmd(self):
        """
        开启录制
        @return:
        """
        try:
            self.gm_rpc("set", [False], "CmdOpen")
        except Exception:
            return False
        return True

    def open_fly(self):
        """
        开启飞行
        @return:
        """
        try:
            self.gm_rpc("set", [True], "fly")
        except Exception:
            return False
        return True

    def close_fly(self):
        """
        关闭飞行
        @return:
        """
        try:
            self.gm_rpc("set", [False], "fly")
        except Exception:
            return False
        return True

    def save_variants(self):
        """
        获取并保存shader变体文件
        :return:
        """
        self.auto.add_log(f"shader保存{True}")
        return self.gm_rpc("set", [], "SaveCompiledVariants")

    def open_dc(self):
        """
        获取当前坐标面向方向的面数，这个数据会积累，需要定时清理，每次请求这个会清理
        :return:
        """
        self.auto.add_log(f"DC采集{True}")
        return self.gm_rpc("set", [True], "CalculateDCV2", is_log=False, need_err=False)

    def close_dc(self):
        """
        获取当前坐标面向方向的面数，这个数据会积累，需要定时清理，每次请求这个会清理
        :return:
        """
        self.auto.add_log(f"DC采集{False}")
        try:
            dc_info = self.gm_rpc("set", [False], "CalculateDCV2", is_log=False, need_err=False)
            print(dc_info)
            try:
                dc_data = json.loads(dc_info)
                perf_down_path = dc_data["returnValue"]["downPath"]
                perf_info_dic = soc_down_dc_str_2_info_v2(perf_down_path)
                # self.auto.add_case_run_send_smg(perf_info_dic)
                self.perf_info_list.append(
                    {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                     "tags": self.perf_tag_time_info_list, "title": "DC", "origin_url": perf_down_path,
                     "data": perf_info_dic})
            except Exception:
                print("dc_info", dc_info)
        except Exception:
            print("CalculateDCV2报错。拿采集数据失败")
            return

    def open_performance_test(self):
        """
        开始收集性能数据
        :return:
        """
        # return
        if "kwargs" in self.auto.init_kwargs["case_info"].keys():
            if "exe_name" in self.auto.init_kwargs["case_info"]["kwargs"].keys():
                if self.auto.init_kwargs["case_info"]["kwargs"]["exe_name"] != "":
                    return
        self.auto.add_log(f"PerfDataMonitor采集{True}")
        return self.gm_rpc("get", [True], "PerfDataMonitor")

    # def open_win_open_cost_rec(self):
    #     """
    #     开始收集xyc的性能数据
    #     :return:
    #     """
    #     self.auto.add_log(f"WinOpenCostRec采集{True}")
    #     return self.gm_rpc("get", [True], "WinOpenCostRec")
    #
    # def close_win_open_cost_rec(self):
    #     """
    #     结束收集xyc的性能数据
    #     :return:
    #     """
    #     self.auto.add_log(f"WinOpenCostRec采集{False}")
    #     performance_info = self.gm_rpc("get", [False], "WinOpenCostRec", )
    #     self.auto.add_case_run_send_smg(f"xyc专用链接：{performance_info}", is_group=True)

    def close_performance_test(self):
        """
        结束收集性能数据
        :return:
        """
        # try:
        #     self.close_win_open_cost_rec()
        # except Exception:
        #     self.auto.add_log("WinOpenCostRec函数获取数据报错")
        try:
            self.auto.add_log(f"PerfDataMonitor采集{False}")
            performance_info = self.gm_rpc("get", [False, "profiler_end"], "PerfDataMonitor", )
        except Exception:
            self.auto.add_log("PerfDataMonitor函数获取数据报错")
            return
        try:
            profiler_data = json.loads(performance_info["profiler"])
            perf_down_path = profiler_data["returnValue"]["downPath"]
            perf_info_dic = soc_down_perf_str_2_info_v2(perf_down_path)
            # self.auto.add_case_run_send_smg(perf_info_dic)
            self.perf_info_list.append(
                {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": self.perf_tag_time_info_list, "title": "profiler_end", "origin_url": perf_down_path,
                 "data": perf_info_dic})
        except Exception as e:
            self.auto.add_log(f"{performance_info} performance_info profiler 解析报错:{traceback.format_exc()}")
        try:
            common_data = json.loads(performance_info["common"])
            common_down_path = common_data["returnValue"]["downPath"]
            common_info_list_dic = soc_down_common_str_2_info(common_down_path)
            # self.auto.add_case_run_send_smg(common_info_list_dic)
            self.perf_info_list.append(
                {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": self.perf_tag_time_info_list, "title": "common", "origin_url": common_down_path,
                 "data": common_info_list_dic})
        except Exception as e:
            self.auto.add_log(f"{performance_info} performance_info common 解析报错:{traceback.format_exc()}")
        try:
            common_data = json.loads(performance_info["memory"])
            common_down_path = common_data["returnValue"]["downPath"]
            common_info_list_dic = soc_down_memory_str_2_info(common_down_path)
            # self.auto.add_case_run_send_smg(common_info_list_dic)
            self.perf_info_list.append(
                {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": self.perf_tag_time_info_list, "title": "memory", "origin_url": common_down_path,
                 "data": common_info_list_dic})
        except Exception as e:
            self.auto.add_log(f"{performance_info} performance_info memory 解析报错:{traceback.format_exc()}")
        try:
            errorcount = int(performance_info["errorcount"])
            # self.auto.add_case_run_send_smg(common_info_list_dic)
            self.perf_info_list.append(
                {"type": "int", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": [], "title": "errorcount", "origin_url": "",
                 "data": errorcount})
        except Exception as e:
            self.auto.add_log(f"{performance_info} performance_info errorcount 解析报错:{traceback.format_exc()}")
        try:
            average_fps = performance_info["averagefps"]
            # self.auto.add_case_run_send_smg(common_info_list_dic)
            self.perf_info_list.append(
                {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": [], "title": "averagefps", "origin_url": "",
                 "data": average_fps})
        except Exception as e:
            self.auto.add_log(f"{performance_info} performance_info averagefps 解析报错:{traceback.format_exc()}")

    def performance_info_to_sql(self):
        """
        把性能数据上传到性能平台数据库
        @return:
        """
        phone = read_excel_for_phone()
        info = get_recent_report_list(days=1, pageNo=0, pageSize=10)
        try:
            try:
                module = self.auto.init_kwargs["case_info"]["case_file_name"]
                case_class_name = self.auto.init_kwargs["case_info"]["case_class_name"]
                case_file_path = self.auto.init_kwargs["case_info"]["case_file_path"]
                case = self.auto.init_kwargs["case_info"]["case_def_name"]
                project_version = self.auto.init_kwargs["case_info"]["version"]
                branch = self.auto.init_kwargs["task_info"]["game_git_info"]["branch"]
                task_id = self.auto.init_kwargs["case_info"]["task_id"]
                device_name = self.auto.init_kwargs["task_info"]["device_info"]["device_name"]
                devices_uid = self.auto.init_kwargs["task_info"]["device_info"]["device_id"]
                device_ip = self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]
            except Exception:
                module = ""
                case_class_name = ""
                case_file_path = ""
                case = ""
                project_version = ""
                branch = ""
                task_id = 0
                device_name = ""
                devices_uid = ""
                device_ip = ""
            err_msg_ = soc_read_performance_data(self.perf_info_list)
            origin_url_paty = soc_read_origin_url_data(self.perf_info_list)
            tag_list = []
            for perf_tag_time_info in self.perf_tag_time_info_list:
                tag_list.append(perf_tag_time_info["tag"])
            report, url = find_report_by_iphone(info, phone, device_name)
            if report:
                report_id = report.get('id', None)
                report_info = get_overview_report(report_id)
                get_dict = tidy_report_v1(report_info, url)
                self.perf_info_list.append({"type": "json", "title": 'uwa', "origin_url": url, "data": get_dict})
            performance_data_info = {"case_data": self.perf_info_list,
                                     "tags": tag_list,
                                     "version": project_version,
                                     "project_id": 33,
                                     "branch": branch,
                                     "case_uid": f"{case_file_path}{module}{case_class_name}{case}",
                                     "task_id": task_id,
                                     "device_name": device_name,
                                     "devices_uid": devices_uid,
                                     "device_ip": device_ip,
                                     "case_name": self.case_name, }
            look_path, down_path = write_log_and_upload_file(json.dumps(performance_data_info))
            err_msg = f"{self.case_name} 入库性能数据：[详情请点击]({look_path}) 原始数据：[详情请点击]({origin_url_paty})"
            self.auto.add_case_run_send_smg(err_msg, is_group=True, is_print=False)
            up_msg = soc_performance_data_update(performance_data_info)
            self.auto.add_case_print(up_msg, is_print=False)
            look_path, down_path = write_log_and_upload_file(err_msg_)
            err_msg = f"{self.case_name} profiler性能数据：[详情请点击]({look_path}) 原始数据：[详情请点击]({origin_url_paty})"
            self.auto.add_case_run_send_smg(err_msg, is_group=True, is_print=False)
        except Exception:
            print("性能，解析性能数据报错", traceback.format_exc())

    def performance_info_to_sql_v2(self):
        """
        把内存性能数据上传到性能平台数据库
        @return:
        """
        try:
            try:
                module = self.auto.init_kwargs["case_info"]["case_file_name"]
                case_class_name = self.auto.init_kwargs["case_info"]["case_class_name"]
                case_file_path = self.auto.init_kwargs["case_info"]["case_file_path"]
                case = self.auto.init_kwargs["case_info"]["case_def_name"]
                project_version = self.auto.init_kwargs["case_info"]["version"]
                branch = self.auto.init_kwargs["task_info"]["game_git_info"]["branch"]
                task_id = self.auto.init_kwargs["case_info"]["task_id"]
                device_name = self.auto.init_kwargs["task_info"]["device_info"]["device_name"]
                devices_uid = self.auto.init_kwargs["task_info"]["device_info"]["device_id"]
                device_ip = self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]
            except Exception:
                module = ""
                case_class_name = ""
                case_file_path = ""
                case = ""
                project_version = ""
                branch = ""
                task_id = 0
                device_name = ""
                devices_uid = ""
                device_ip = ""
            tag_list = []
            self.memory_info_list.append({"type": "json", "title": 'memoryprof', "data": self.memory_downpath})
            for perf_tag_time_info in self.perf_tag_time_info_list:
                tag_list.append(perf_tag_time_info["tag"])
            performance_data_info = {"case_data": self.memory_info_list,
                                     "tags": tag_list,
                                     "version": project_version,
                                     "project_id": 33,
                                     "branch": branch,
                                     "case_uid": f"{case_file_path}{module}{case_class_name}{case}",
                                     "task_id": task_id,
                                     "device_name": device_name,
                                     "devices_uid": devices_uid,
                                     "device_ip": device_ip,
                                     "case_name": self.case_name, }
            up_msg = soc_performance_data_update(performance_data_info)
            self.auto.add_case_print(up_msg, is_print=False)
        except Exception:
            print("性能，解析性能数据报错", traceback.format_exc())

    def open_memory_monitor(self):
        """
        开始收集性能数据
        :return:
        """
        try:
            package_type = self.get_package_type()
            if package_type != "debug":
                return
            self.memory_monitor_time = time.time()
            print("开始内存性能收集")
            result_data, result = self.gm_rpc_v2("get", [True], "MemoryMonitor", )
            print(result_data, result)
        except Exception:
            pass  # rpc会因为手机卡住而报错捕获一下就好

    def close_memory_monitor(self):
        """
        结束收集性能数据
        :return:
        """
        performance_info = []
        try:
            package_type = self.get_package_type()
            if package_type != "debug":
                return
            time_num = time.time() - self.memory_monitor_time
            if time_num < 30:
                self.auto.add_log("性能数据收集时间间隔较短")
                time.sleep(time_num)
            performance_info, result = self.gm_rpc_v2("get", [False], "MemoryMonitor", )
            if not result:
                self.auto.add_log("手机包不是debug包")
                return
        except Exception as e:
            self.auto.add_log(f"MemoryMonitor文件请求失败，err:{e}")
            pass
        if len(performance_info) > 1:
            for i in range(60):
                response = requests.get("http://192.168.186.130:8000/result.txt")
                file_content = response.text
                self.auto.add_log(
                    f"{self.auto.init_kwargs['task_info']['device_info']['device_ip']}检测文件是否上传完毕{performance_info}")
                if performance_info[0] in file_content and performance_info[1] in file_content:
                    break
                else:
                    time.sleep(30)
            self.auto.add_log("文件上传完毕，开始发送对比")
            time.sleep(10)
            data = f"{performance_info[0]},{performance_info[1]}"
            url = "http://192.168.186.130:8000/split"
            try:
                response = requests.post(url, data, timeout=2)
            except Exception:
                pass
            file1_name = performance_info[0].replace(".snap", "")
            file2_name = performance_info[1].replace(".snap", "")
            # snap1_down_path = f"http://192.168.186.130:8000/{file1_name}_Overview_{file2_name}.csv"
            snap1_down_path = f"http://192.168.186.130:8000/{file1_name}_OutData_{file2_name}.csv"
            snap2_down_path = f"http://192.168.186.130:8000/{file1_name}_Compare_{file2_name}.csv"
            self.auto.add_case_run_send_smg(f"性能对比表1(分析需要很久，多等一会)：{snap1_down_path}", is_group=True)
            self.auto.add_case_run_send_smg(f"性能对比表2(分析需要很久，多等一会)：{snap2_down_path}", is_group=True)
            # down_path = f"http://192.168.186.130:8000/{file1_name}_Overview1_{file2_name}.csv"
            # self.auto.add_case_run_send_smg(f"扩展链接(分析需要很久，多等一会)：{down_path}", is_group=True)
            # down_path = f"http://192.168.186.130:8000/{file1_name}_Overview.csv"
            # self.auto.add_case_run_send_smg(f"扩展链接1(分析需要很久，多等一会)：{down_path}", is_group=True)
            # down_path = f"http://192.168.186.130:8000/{file2_name}_Overview.csv"
            # self.auto.add_case_run_send_smg(f"扩展链接2(分析需要很久，多等一会)：{down_path}", is_group=True)
            # down_path = f"http://192.168.186.130:8000/{file1_name}_Overview1.csv"
            # self.auto.add_case_run_send_smg(f"扩展链接3(分析需要很久，多等一会)：{down_path}", is_group=True)
            # down_path = f"http://192.168.186.130:8000/{file2_name}_Overview1.csv"
            # self.auto.add_case_run_send_smg(f"扩展链接4(分析需要很久，多等一会)：{down_path}", is_group=True)
            down_path = f"http://192.168.186.130:8000/{file1_name}_split.csv"
            self.auto.add_case_run_send_smg(f"扩展链接5(分析需要很久，多等一会)：{down_path}", is_group=True)
            down_path = f"http://192.168.186.130:8000/{file2_name}_split.csv"
            self.memory_downpath = down_path
            self.auto.add_case_run_send_smg(f"扩展链接6(分析需要很久，多等一会)：{down_path}", is_group=True)
            down_path = f"http://192.168.186.130:8000/{file1_name}.snap"
            self.auto.add_case_run_send_smg(f"扩展链接：{down_path}", is_group=True)
            down_path = f"http://192.168.186.130:8000/{file2_name}.snap"
            self.auto.add_case_run_send_smg(f"扩展链接：{down_path}", is_group=True)

    def init_pro_sight(self):
        """
        登录进入游戏的时候就会收集了，先关掉，等用例开始的时候再打开，第二个bool是控制是否上传的  tx平台
        @return:
        """
        self.gm_rpc("set", [False, False], "ProSightOpen", need_err=False)

    def open_pro_sight(self):
        """
        打开数据收集开关，第二个bool是控制是否上传的  tx平台
        @return:
        """
        self.gm_rpc("set", [True, False], "ProSightOpen", need_err=False)
        self.performance_test_init_info["ProSightStartTime"] = tu.time_format_time_v2("%Y-%m-%d %H:%M:%S")

    def close_pro_sight(self):
        """
        关闭数据收集开关，并上传数据，第二个bool是控制是否上传的  tx平台
        @return:
        """
        try:
            self.gm_rpc("set", [False, True], "ProSightOpen")
        except Exception:
            pass

    def init_pro_filer(self):
        """
        清理帧数缓存
        @return:
        """
        timestamp = str(time.time())
        self.gm_rpc("set", [True, "clear", timestamp], "ProfilerOpen", need_err=False)

    def open_pro_filer(self):
        """
        打开帧数据收集开关
        @return:
        """
        timestamp = str(time.time())
        self.gm_rpc("set", [True, "", timestamp], "ProfilerOpen", need_err=False)

    def close_pro_filer(self, tag=""):
        """
        关闭帧数据收集开关
        @return:
        """
        if tag:
            tag = f"profiler_{tag}"
        else:
            tag = f"profiler"
        pro_filer_info = self.gm_rpc("set", [False, "", tag], "ProfilerOpen", need_err=False)
        try:
            pro_filer_data = json.loads(pro_filer_info)
            perf_down_path = pro_filer_data["returnValue"]["downPath"]
            perf_info_dic = soc_down_perf_str_2_info_v2(perf_down_path)
            self.auto.add_case_print(f"调用ProfilerOpen获取文件{pro_filer_info}")
            self.perf_info_list.append(
                {"type": "json", "start_time": self.perf_start_time, "end_time": self.perf_end_time,
                 "tags": [], "title": tag, "origin_url": perf_down_path,
                 "data": perf_info_dic})
        except Exception as e:
            print(pro_filer_info, "ProfilerOpen profiler 解析报错", e)

    def uwa_open(self):
        """
        开启uwa数据开关，在调用关闭函数前多次调用无效
        @param note:备注，注明这条uwa平台上的数据是什么用例传上来的，需要符合   日期+手动/自动+用例名+包体 规则
        @return:
        """
        package_type = self.get_package_type()
        note = f"{TimeUtil.full_now_v2()}自动{self.case_name}{package_type}"
        timestamp = str(time.time())
        self.gm_rpc("set", ["open", note, timestamp], "UWAOpen", need_err=False)

    def get_package_type(self):
        """
        获取包类型，后面根据需求看看是不是要换成返回字符串
        @return:
        """
        result_data = self.gm_rpc("get", "", "package_type")
        try:
            is_debug = result_data["debug"]
            if is_debug:
                package_type = "debug"
            else:
                package_type = "release"
        except Exception:
            package_type = "release"
        self.auto.add_log(f"获取到当前包体：{package_type}")
        return package_type

    def uwa_up(self):
        """
        上传uwa数据，在调用关闭前无效
        @return:
        """
        timestamp = str(time.time())
        self.gm_rpc("set", ["up", "", timestamp], "UWAOpen", need_err=False)

    def uwa_tag(self, tag_msg):
        """
        给数据打标记，必须在开始收集数据后调用
        @return:
        """
        timestamp = str(time.time())
        self.gm_rpc("set", ["tag", tag_msg, timestamp], "UWAOpen", need_err=False)
        self.self_profiler_tag(tag_msg)

    def self_profiler_tag(self, tag_msg):
        """
        婉璐性能数据收集接口
        @param tag_msg:
        @return:
        """
        self.perf_tag_time_info_list.append({"time": time.time(), "tag": tag_msg})

    def uwa_close(self):
        """
        关闭uwa数据收集，在开始后调用生效，多次调用无效
        @return:
        """
        timestamp = str(time.time())
        try:
            self.gm_rpc("set", ["close", "", timestamp], "UWAOpen")
        except Exception:
            pass
        try:
            performance_info, result = self.gm_rpc_v2("get", [False], "UploadDevProfiler", )
            if len(performance_info) == 0:
                self.auto.add_log("手机包不是debug包")
                return
        except Exception as e:
            time.sleep(3)
            self.auto.add_log(f"UploadDevProfiler请求失败，err:{e}")
        try:
            performance_info_list, result = self.gm_rpc_v2("get", [False], "GetDevProfiler", )
            if len(performance_info_list) > 0:
                for i in range(60):
                    response = requests.get("http://192.168.186.130:8000/result.txt")
                    file_content = response.text
                    self.auto.add_log(f"检测文件是否上传完毕{performance_info_list}")
                    is_find = True
                    for performance_info in performance_info_list:
                        if performance_info not in file_content:
                            is_find = False
                    if is_find:
                        break
                    else:
                        time.sleep(30)
                for performance_info in performance_info_list:
                    snap1_down_path = f"http://192.168.186.130:8000/{performance_info}"
                    self.auto.add_case_run_send_smg(f"详细的帧数据：{snap1_down_path}", is_group=True)
        except Exception as e:
            self.auto.add_log(f"获取GetDevProfiler数据报错:{traceback.format_exc()}")

    def add_perf_tag(self, tag_msg):
        """
        添加性能标记
        @param tag_msg:标记内容
        @return:
        """
        self.close_pro_filer(tag_msg)
        # self.init_pro_filer()
        self.open_pro_filer()

    def start_performance_test(self):

        self.perf_info_list = []
        self.perf_start_time = time.time()
        self.perf_end_time = 0
        self.perf_tag_time_info_list = []
        self.performance_test = True
        if "kwargs" in self.auto.init_kwargs["case_info"].keys():
            if "memory" in self.auto.init_kwargs["case_info"]["kwargs"].keys():
                self.open_memory_monitor()
                return
        self.open_pro_sight()
        self.open_dc()
        self.open_performance_test()
        # self.open_win_open_cost_rec()

    def stop_performance_test(self):
        self.perf_end_time = time.time()
        if self.performance_test:
            self.close_pro_sight()
            if "kwargs" in self.auto.init_kwargs["case_info"].keys():
                if "memory" in self.auto.init_kwargs["case_info"]["kwargs"].keys():
                    self.close_memory_monitor()
                    self.performance_info_to_sql_v2()
                    return
            self.close_dc()
            self.close_performance_test()
            self.performance_info_to_sql()
            self.perf_info_list = []
            self.perf_start_time = 0
            self.perf_end_time = 0
            self.perf_tag_time_info_list = []

    def open_gm_ui(self):
        """
        开启gm ui界面
        @return:
        """
        try:
            self.gm_rpc("set", [True], "GmOpen")
        except Exception:
            return False
        return True

    def close_gm_ui(self):
        """
        关闭gm ui界面
        @return:
        """
        try:
            self.gm_rpc("set", [False], "GmOpen")
        except Exception:
            return False
        return True

    def finsh_fusebox_game(self, fuseboxentityid):
        """
        完成接线游戏
        @return:
        """
        try:
            self.gm_rpc("set", [fuseboxentityid], "FinshFuseBoxGame")
        except Exception:
            return False
        return True

    def trigger_interact(self, entityid):
        """
        交互IO，开关/门
        @return:
        """
        try:
            self.gm_rpc("set", [entityid], "OnTriggerInteract")
        except Exception:
            return False
        return True

    def onbatch_upgrade(self, ):
        """
        打开一键升级材料选择框
        @return:
        """
        try:
            self.gm_rpc("set", [], "OpenUpgradeBox")
        except Exception:
            return False
        return True

    def vehicle_add_oil(self, num):
        """
        接口给载具加油
        @return:
        """
        try:
            self.gm_rpc("set", [num], "VehicleAddResource")
        except Exception:
            return False
        return True

    def close_uiloading(self, is_open):
        """
        关闭短距离传送loading界面
        @return:
        """
        try:
            self.gm_rpc("set", [is_open], "UiloadingGmSwitch")
        except Exception:
            return False
        return True

    def katyusha_fire(self, katyushar_id, targetX, targetY, targetZ):
        """
        喀秋莎开火
        @return:
        """
        try:
            self.gm_rpc("set", [katyushar_id, targetX, targetY, targetZ], "KatyusharFire")
        except Exception:
            return False
        return True

    def katyusha_stopcd(self, katyushar_id):
        """
        喀秋莎刷新冷却缩减
        @return:
        """
        try:
            self.gm_rpc("set", [katyushar_id], "KatyusharStopCd")
        except Exception:
            return False
        return True

    def console_cmd(self, cmd_msg):
        """
        发送服务端cmd
        @return:
        """
        try:
            self.gm_rpc("set", [cmd_msg], "ConsoleCmd")
        except Exception:
            return False
        return True

    def calculate_require_path(self, now_x, now_y, now_z, target_x, target_y, target_z):
        """
        发送两点坐标，服务端计算mesh寻路路径
        @return:
        """
        try:
            self.gm_rpc("set", [now_x, now_y, now_z, target_x, target_y, target_z], "CalculateRequirePath")
        except Exception:
            return False
        return True

    def get_require_path(self, ):
        """
        获取两点间路径列表
        @return:
        """
        try:
            result_data = self.gm_rpc("get", [], "GetRequirePath")
        except Exception:
            return False
        return result_data

    def get_path_to_target(self, target_x, target_y, target_z):
        """
        获取从自身点位到目标点的路径列表
        @return:
        """
        camera_info, is_get = self.get_camera(False)
        base_pos = camera_info["position"]
        self.calculate_require_path(float(base_pos["x"]), float(base_pos["y"]), float(base_pos["z"]), target_x,
                                    target_y, target_z)
        self.auto.auto_sleep(5)
        path_list = self.get_require_path()
        if path_list == False:
            self.auto.add_log("没有找到路径列表")
        else:
            return path_list

    def set_speed_gear(self, speed_gear):
        """
        修改移动速度
        @return:
        """
        try:
            self.gm_rpc("set", [speed_gear], "SetSpeedGear")
        except Exception:
            return False
        return True

    def up_car_by_entity(self, car_entity_id, seat_type, seat_index):
        """
        发接口上车
        @param car_entity_id:
        @param seat_type:载具类型，车 马 都是1
        @param seat_index:上的位置 -1
        @return:
        """
        try:
            self.gm_rpc("set", [car_entity_id, seat_type, seat_index], "WantsMount")
        except Exception:
            return False
        return True

    def switch_push(self, entity_id):
        """
        发接口推载具
        """
        try:
            self.gm_rpc("set", [entity_id], "WantsPush")
        except Exception:
            return False
        return True

    def switch_lockvehicle(self, entity_id):
        """
        发接口载具上锁
        """
        try:
            self.gm_rpc("set", [entity_id], "RemoteCallLockVehicle")
        except Exception:
            return False
        return True

    def release_lockvehicle(self, entity_id):
        """
        发接口载具解锁
        """
        try:
            self.gm_rpc("set", [entity_id], "UnlockVehicle")
        except Exception:
            return False
        return True

    def down_car_by_now(self):
        """
        发接口下车，直接下当前的车辆，不需要参数
        """
        try:
            self.gm_rpc("set", "", "WantsDismount")
        except Exception:
            return False
        return True

    def set_game_quality(self, quality_level):
        """
        设置画质
        @param quality_level:
        @return:
        """
        if quality_level not in ["极低", "低质量", "标准", "高清", ]:
            self.auto.raise_err_and_write_log("设置画质输入错误", 5)
        if quality_level == "极低":
            set_value = "VeryLow"
        elif quality_level == "低质量":
            set_value = "Low"
        elif quality_level == "标准":
            set_value = "Standard"
        else:
            set_value = "High"
        try:
            self.gm_rpc("set", [set_value], "SetGameQuality")
        except Exception:
            return False
        return True

    def add_vehicle(self, vehicle_type, pos_list=[]):
        """
        添加载具
        :param vehicle_type: 载具类型 快艇 speed_boat 木舟 wooden_boat 2模块载具 2_module 3模块载具 3_module 4模块载具 4_module
        soc马 horse_soc 迷你直升机 mini_helicopter 直升机 helicopter
        :return:
        """
        vehicle_info = {
            "speed_boat": {"id": 22030001, "method": "SpawnVehicle"},
            "wooden_boat": {"id": 11010043, "method": "SpawnVehicle"},
            "horse_soc": {"id": 22030010, "method": "SpawnVehicle"},
            "mini_helicopter": {"id": 22030007, "method": "SpawnVehicle"},
            "helicopter": {"id": 22030006, "method": "SpawnVehicle"},
            "2_module": {"id": 10001, "method": "SpawnVehicleModuleCar"},
            "3_module": {"id": 10010, "method": "SpawnVehicleModuleCar"},
            "4_module": {"id": 22030005, "method": "SpawnVehicleModuleCar"}
        }

        try:
            if vehicle_type in vehicle_info:
                vehicle = vehicle_info[vehicle_type]
                value = [vehicle["id"]] + pos_list[:3] if pos_list else [vehicle["id"]]
                self.gm_rpc("set", value, vehicle["method"])
                time.sleep(1)
                return True
            else:
                self.auto.raise_err_and_write_log("载具类型不存在", 5)
        except Exception:
            return False
        return True

    def recover_construction(self, construction_name, x, y, z, rotate_y):
        """
        导入建筑
        :param construction_name: 建筑名称
        :param x:  x 坐标
        :param y:  y 坐标
        :param z:  z 坐标
        :param rotate_y: y轴偏移
        :return:
        """
        try:
            self.gm_rpc("set", [construction_name, x, y, z, rotate_y], "RecoverConstruction")
        except Exception:
            return False
        return True

    def modify_property(self, propId, amount, entityid=""):
        """
        修改人物属性
        :param propId:属性代号 0(HP) 1(心跳) 2(卡路里) 3(水分) 4(流血) 5(缓慢恢复) 6(舒适度) 7(温度)  9(辐射中毒) 10(湿度) 11(中毒)
        :param amount:在原来属性值上增减，可以为负数
        :return:
        """
        try:
            self.gm_rpc("set", [propId, amount, entityid], "TestModifyProperty")
        except Exception:
            return False
        return True

    def send_hitrequest(self, damage_type, amount):
        """
        发起一次伤害请求，暂时为自己对自己造成一个伤害
        :param damage_type:  各伤害类型数字标号 0为通用
        :param amount:  初始伤害量，实际结果不一定准确
        :return:
        """
        # todo 后续可增加详细配置，如谁对谁造成伤害，选择造成伤害部位，是否无视防御等
        try:
            self.gm_rpc("set", [damage_type, amount], "TestSendHitRequest")
        except Exception:
            return False
        return True

    def sv_switch(self, entity_id):
        """
        切换开关
        :param entity_id:
        :return:
        """
        try:
            self.gm_rpc("set", [entity_id], "sv_switch")
        except Exception:
            return False
        return True

    def touch_Prop_detail(self):
        # 点击物品信息
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ConTipsTitle/BtnDetail"
        self.auto.auto_touch(name)

    def touch_Prop_tab(self, num_str):
        """
        点击物品详情中的不同种类：掉落和交易，制造和蓝图，分解，可用于制造
        @param num_str:
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiItemDetail(UiItemDetail)/ContentPane/GList/Container/Container/BtnMenu" + num_str
        self.auto.auto_touch(name)

    def touch_Prop_tab1(self):
        """
        点击掉落和交易，无需维护
        @return:
        """
        self.touch_Prop_tab("")

    def touch_Prop_tab2(self):
        """
        点击制造和蓝图，无需维护
        @return:
        """
        self.touch_Prop_tab(".1")

    def touch_Prop_tab3(self):
        """
        点击分解，无需维护
        @return:
        """
        self.touch_Prop_tab(".2")

    def touch_Prop_tab4(self):
        """
        点击可用于制造，无需维护
        @return:
        """
        self.touch_Prop_tab(".3")

    def touch_details_to_bag(self):
        """
        物品详情返回背包
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiItemDetail(UiItemDetail)/ContentPane/BtnBack"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def touch_tech_to_bag(self):
        """
        科技树退出键
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTechTree(UiTechTree)/ContentPane/ComTechTree/BtnBack"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def touch_creat_to_home(self):
        """
        制造界面退出按钮
        @return
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCraft(UiCraft)/ContentPane/ComCraftRoot/FullScreenTopbar/FullScreenBack"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def touch_switch_burn(self):
        """
        熔炉营火等摆件主功能交互
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn"
        self.auto.auto_touch(name)

    def touch_pickall_product(self):
        """
        生产材料全部取出
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideOven/ComOtherSideOven/BtnPickAll"
        self.auto.auto_touch(name)

    def touch_bag_tomake(self):
        """
        背包页进入制作
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnInventory.1"
        self.auto.auto_touch(name)

    def touch_tech_tomake(self):
        """
        科技界面解锁后点击的立即制作
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTechTree(UiTechTree)/ContentPane/ComTechTree/TechTreeInfo/BtnJumpCraft"
        self.auto.auto_touch(name)

    def touch_bag_totech(self):
        """
        背包、制作进入研发
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnInventory.2"
        self.auto.auto_touch(name)

    def touch_upgrade(self):
        """
        建筑升级
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/ComInteractiveBtn"
        self.auto.auto_touch(name)

    def touch_upgrade_type_father(self, num):
        """
        建筑升级类型中的1类型
        @return:
        """
        name = f"Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/EditConstructionPanel/btnUpgradeType1{num}"
        self.auto.auto_touch(name)

    def touch_upgrade_type1(self):
        """
        建筑升级类型中的1类型
        @return:
        """
        self.touch_upgrade_type_father(1)

    def touch_upgrade_type2(self):
        """
        建筑升级类型中的2类型
        @return:
        """
        self.touch_upgrade_type_father(2)

    def touch_upgrade_type3(self):
        """
        建筑升级类型中的3类型
        @return:
        """
        self.touch_upgrade_type_father(3)

    def touch_upgrade_type4(self):
        """
        建筑升级类型中的4类型
        @return:
        """
        self.touch_upgrade_type_father(4)

    def touch_upgrade_do(self):
        """
        建筑升级确定
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/EditConstructionPanel/btnProcessPart"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(2)

    def touch_upgrade_del(self):
        """
        建筑升级删除
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/EditConstructionPanel/btnDestroyPart"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(2)
        self.touch_upgrade_del_warn_ok()

    def touch_upgrade_del_warn_ok(self):
        """
        删除建筑提示支撑力页面确认按钮
        @return:
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopTitleMsgBox/GList/BtnPopupBtn"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            self.auto.auto_sleep(2)
            return True
        else:
            print("654")
        return False

    def touch_upgrade_return(self):
        """
        建筑升级界面返回
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.37/BtnStartBuild"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(3)
        # if self.touch_upgrade_is_return():
        #     name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEndBuild"
        #     self.auto.auto_touch(name)
        #     self.auto.auto_sleep(3)

    def touch_upgrade_is_return(self):
        """
        判断建筑界面的返回按钮在不在了
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEndBuild"
        return_value, is_visible = self.auto.get_poco_info(name, "visible")
        return return_value

    def touch_upgrade_maintain(self):
        """
        建筑升级维修
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/EditConstructionPanel/btnRepair"
        self.auto.auto_touch(name)

    def open_tech_tree(self):
        """
        打开科技树界面
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnTechTree"
        self.auto.auto_touch(name)

    def touch_techtree(self, num_int):
        """
        点击科技树
        @param num_int: 0 基础科技树 1 一级科技树 2 二级科技树 3 三级科技树
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTechTree(UiTechTree)/ContentPane/ComTechTree/BtnLabel"
        list = [0, 1, 2, 3]
        if num_int in list:
            if num_int != 0:
                name = name + "." + str(num_int)
            self.auto.auto_touch(name)
        else:
            print("没有此分类的科技树")

    def open_setting(self):
        """
        打开设置
        @return:
        """
        try:
            self.get_poco_text(
                "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnSetting")
        except:
            name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnGroupFolder"
            self.auto.auto_touch(name)
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnSetting"
        self.auto.auto_touch(name)

    def close_setting(self):
        """
        关闭设置
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/ComNavTab/BtnCommonBack"
        self.auto.auto_touch(name)

    def open_layout(self):
        # todo:界面迭代全要改
        """
        打开操作设置并打开自定义布局
        @return:
        """
        self.open_setting()
        name2 = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/ComNavTab/GList/Container/Container/BtnNavTab.1"
        self.auto.auto_touch(name2)
        name3 = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/GLoader/ContentControl/ComBigCard/GList/Container/BtnBigCardCase/BtnCharacters"
        self.auto.auto_touch(name3)

    def gm_suicide(self):
        """
        GM自杀
        @return:
        """
        suicide = 'Stage/GRoot/(Full Screen) ID501|S501/UiSetting(GameSetting-UiSetting)/ContentPane/ComSettingPanel/BtnPicAndText.1'
        determine = 'Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList//Container/BtnPopupBtn'
        self.open_setting()
        self.auto.auto_touch(suicide)
        self.auto.auto_sleep(1)
        self.auto.auto_touch(determine)
        self.auto.auto_sleep(5)
        user_info = self.get_user_stats()
        life = user_info["hp"]
        if life == 0:
            self.auto.add_log("自杀成功")
        else:
            self.auto.raise_err_and_write_log("自杀失败", 5)

    def close_layout(self):
        """
        退出自定义布局
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/ComHudMainElemUpper/GLoader/ComCustomPanel/BtnQuit"
        self.auto.auto_touch(name)

    def enlarge_map(self):
        """
        放大地图
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiMainMap(UiMainMap)/ContentPane/MainMapWidgets/ComSlider/Button1"
        self.auto.auto_touch(name)

    def close_map(self):
        """
        关闭地图
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiMainMap(UiMainMap)/ContentPane/MainMapWidgets/Button2"
        self.auto.auto_touch(name)

    def open_weapon_shortcut(self):
        """
        打开武器快捷栏
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemWeapons/BtnElemWeaponChooseTab"
        self.auto.auto_touch(name)

    def close_weapon_shortcut(self):
        """
        关闭武器快捷栏
        @return:
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiHudWeaponChoose(UiHudWeaponChoose)/ContentPane/UiHudElems/ElemWeapons/BtnElemWeaponChooseTab"
        self.auto.auto_touch(name)

    def touch_item_shortcut(self):
        """
        打开/关闭物品快捷栏
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemShortcutsNew/BeltMenuFolder"
        self.auto.auto_touch(name)

    def touch_interactiveList(self, index_str=""):
        """
        点击交互菜单
        @return:
        """
        name = f"Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn{index_str}"
        self.auto.auto_touch(name)

    def touch_interactiveList_1(self):
        """
        点击交互菜单编号.1
        @return:
        """
        self.touch_interactiveList(".1")

    def pick_up_item(self, index_str=""):
        """
        拾取当前地面上的物品
        @return:
        """
        name = f"Stage/GRoot/ContentPane/elemsRoot/UiHudElems_new/ComPickableItemsList/GList/ComTitleItemsList/GList/Container/BtnPickListItem{index_str}"
        self.auto.auto_touch(name)

    def pick_up_item_1(self):
        """
        拾取当前地面上的物品 第2个
        """
        self.pick_up_item(".1")

    def car_module_interface_fuel(self):
        """
        点击载具界面燃油按钮
        @return:
        """
        # 点击 燃油
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComVehicleRolling/Container/Container/ComVehicleStatusAndOil/ComAddResource2/BtnAddResource"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(2)

    def car_module_interface_fuel_confirm(self):
        # 点击 确认添加
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComHandlePanel/ComHandle/BtnHandle"
        self.auto.auto_touch(name)
        self.auto.auto_sleep(2)

    def car_add_fuel(self, add_num=500):
        """
        给载具加油,ps:需要在载具的操作列表已经弹出的情况下使用
        @param add_num:添加的数量
        @return:
        """
        is_touch = False
        self.add_resource(12020006, add_num)
        self.auto.auto_sleep(1)
        # 校验燃油数量
        res_num_before = self.get_resource(12020006)
        if res_num_before != add_num:
            self.auto.add_log(f"添加燃油失败！", False)
        # self.touch_interactiveList(".3")
        # try:
        #     self.auto.auto_touch("Operation")
        # except:
        #     try:
        #         self.auto.auto_touch("操作")
        #     except:
        self.touch_interactiveList(".2")
        self.auto.auto_sleep(2)
        # self.car_module_interface_fuel()
        # self.auto.auto_sleep(2)
        # self.car_module_interface_fuel_confirm()
        self.vehicle_add_oil(add_num)
        # 点击 关闭
        self.close_ornament()
        self.auto.auto_sleep(2)

    def open_electricalmode(self):
        """
        打开电器界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemBuild/BtnElecFirstType"
        self.auto.auto_touch(name)

    def open_wiremode(self):
        """
        打开电线界面
        @return:
        """
        # 这个不知道是哪个界面
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/ComHudMainElemLower/UiHudElems/GLoader.24/ElemBuild/ComBuildItemListNew/GList/Container/Container/ComBuildPanelIcon"
        self.auto.auto_touch(name)

    def close_nowmode(self):
        """
        关闭当前建造界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.36/BtnStartBuild"
        self.auto.auto_touch(name)

    def open_chat(self):
        """
        打开聊天界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemChatNew/BtnChat"
        self.auto.auto_touch(name)

    def close_chat(self):
        """
        关闭聊天界面
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiChat(UiChat)/ContentPane/Back"
        self.auto.auto_touch(name)

    def open_team(self):
        """
        打开组队界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.58/ElemLeftTab/TabItem02"
        self.auto.auto_touch(name)

    def open_team1(self):
        """
        打开组队界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.58/ElemLeftTab/btnTeamNew"
        self.auto.auto_touch(name)

    def close_team(self):
        """
        关闭组队界面
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/BtnClose"
        self.auto.auto_touch(name)

    def open_speakerpanel(self):
        """
        打开扬声器界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemSpeaker/CommonBtn"
        self.auto.auto_touch(name)

    def switch_speaker(self, num_int):
        """
        切换扬声器
        @param num_int: 世界语音:0 关闭语音:1 队伍语音:2
        @return:
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiSpeaker(UiSpeaker)/ContentPane/ComSpeakerPanel/BtnSpeaker"
        list = [0, 1, 2]
        if num_int in list:
            if num_int != 0:
                name = name + "." + str(num_int)
            self.auto.auto_touch(name)
        else:
            print("没有此扬声器设置")

    def open_micpanel(self):
        """
        打开麦克风界面
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemMic/CommonBtn"
        self.auto.auto_touch(name)

    def touch_btnok(self):
        """
        道具建造确认
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.16/ElemBtnBuildOK/btnProcessPart"
        self.auto.auto_touch(name)

    def build_equipment(self, build_id, build_name):
        """
        摆件设备获取、建造
        @return:
        """
        self.add_resource_and_inspect(build_id, 1)
        self.auto.auto_sleep(1)
        index, is_have = self.find_item_index(build_id, "shortcut")
        if is_have:
            self.use_shortcut_item(index)
        else:
            self.auto.add_log(f"没有获取到摆件", False)
            return
        build_allname = build_name + "_Holding"
        self.do_build_operation(build_name=build_allname, err_num=100, need_err=False)
        self.auto.auto_sleep(2)
        # 检测是否被放置使用
        index, is_have = self.find_item_index(build_id, "shortcut")
        if not is_have:
            print(f"{build_name}摆件放置成功，从快捷栏中消失")
        else:
            self.auto.add_log(f"快捷栏中仍有{build_name}，摆件放置失败", False)

    def touch_BackBtn(self):
        """
        BackBtn节点返回
        @return:
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemCommonBtn2"
        if self.auto.is_exist(name):
            self.auto.auto_touch(name)
            return True
        return False

    def unlock_tech(self):
        """
        解锁科技树
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTechTree(UiTechTree)/ContentPane/ComTechTree/TechTreeInfo/BtnUnlockLacking"
        self.auto.auto_touch(name)

    def random_res(self):
        """
        随机复活
        @return:
        """
        self.auto.auto_sleep(1)
        try:
            self.close_PictureMsgBox()
        except:
            pass
        random_res = 'Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnPointList/GList/Container/Container/RespawnGroupCom.1/RespawnGroupPointCom/RespawnListBtn'
        self.auto.auto_touch(random_res)
        self.auto.auto_sleep(1)
        self.reborn()

    def nearby_res(self):
        """
        附近复活
        @return:
        """
        nearby_res = 'Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnPointList/GList/Container/Container/RespawnGroupCom/RespawnGroupPointCom/RespawnListBtn'
        self.auto.auto_touch(nearby_res)
        self.auto.auto_sleep(1)
        self.reborn()

    def sleepbag_res(self):
        """
        床位复活
        @return:
        """
        sleepbag_name = 'Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnPointList/GList/Container/Container/RespawnGroupCom.2/RespawnGroupPointCom/RespawnListBtn'
        self.auto.auto_touch(sleepbag_name)
        self.auto.auto_sleep(1)
        self.reborn()

    def reborn(self):
        """
        死亡界面点击复活按钮
        @return:
        """
        reborn = 'Stage/GRoot/(Full Screen) ID501|S501/UiRespawn(UiRespawn)/ContentPane/UiRespawnBtn/RespawnBtn'
        self.auto.auto_touch(reborn)
        self.auto.auto_sleep(1)
        comfirm = 'Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn'
        self.auto.auto_touch(comfirm)

    def self_rescue(self):
        """
        自救
        @return:
        """
        name = 'Stage/GRoot/ContentPane/DyingBtn/BtnWithBar/SelfRescueBtn'
        self.auto.auto_touch(name)

    def drink(self):
        """
        点击喝水按钮（仅水瓶）
        @return:
        """
        drink = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemDrinkWater/BtnDrinkWater"
        self.auto.auto_touch(drink)

    def close_PictureMsgBox(self):
        """
        关闭生存手册教学大弹窗
        @return:
        """
        try:
            notice = 'Stage/GRoot/(Notice) ID701|S701/UiPicBox(UiPicBox)/ContentPane/ComPopPictureMsgBox/BtnClose2'
            self.auto.auto_touch(notice)
        except:
            pass

    def switch_throw_mode(self):
        """
        切换近投/远投
        @return:
        """
        name = 'Stage/GRoot/(HUD) L201-LO201/UiHud(GameHud-UiHudMain)/ContentPane/elemsRoot/UiHudElems/ElemSwitch/ElemCommonBtn5'
        self.auto.auto_touch(name)

    def get_wear_attr(self):
        """
        获取人物防御属性
        @return:
        """
        attr_list = []
        for i in range(10):
            if i == 0:
                part1 = "/ComPlayerWholeAttr"
                part2 = "/BtnPlayerWholeAttr"
            if 1 <= i < 4:
                part1 = "/ComPlayerWholeAttr"
                part2 = "/BtnPlayerWholeAttr" + "." + str(i)
            if i == 4:
                part1 = "/ComPlayerPartAttr"
                part2 = "/BtnPlayerAttr"
            if i == 5:
                part1 = "/ComPlayerPartAttr"
                part2 = "/BtnPlayerAttr.1"
            if i == 6:
                part1 = "/ComPlayerPartAttr.1"
                part2 = "/BtnPlayerAttr"
            if i == 7:
                part1 = "/ComPlayerPartAttr.1"
                part2 = "/BtnPlayerAttr.1"
            if i == 8:
                part1 = "/ComPlayerPartAttr.2"
                part2 = "/BtnPlayerAttr"
            if i == 9:
                part1 = "/ComPlayerPartAttr.2"
                part2 = "/BtnPlayerAttr.1"
            main = "Stage/GRoot/(Full Screen) ID501|S501/UiInventoryPlayerAttrs(GameInventory-UiInventoryPlayerAttrs)/ContentPane" + part1 + "/GList" + part2 + "/TextField.1"
            text = self.get_poco_text(main)
            if text == "--":
                wear_attr = 0
            else:
                wear_attr = int(text.split("%")[0])
            attr_list.append(wear_attr)
        return attr_list

    def switch_mic(self, num_int):
        """
        切换麦克风
        @param num_int: 世界麦克风:0 关闭麦克风:1 队伍麦克风:2 世界按键说话:3 队伍按键说话:4
        @return:
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiMic(UiMic)/ContentPane/ComMicPanel"
        if num_int == 0:
            name = name + "/BtnFreeMicro"
        elif 1 <= num_int <= 2:
            name = name + "/BtnFreeMicro." + str(num_int)
        elif num_int == 3:
            name = name + "/BtnHoldMicro"
        elif num_int == 4:
            name = name + "/BtnHoldMicro." + str(num_int)
        self.auto.auto_touch(name)

    def get_weapon_ammo_num(self, index):
        """
        获取快捷键栏武器的子弹数
        @param index:
        @return:
        """
        if index == 6:
            ammo_index_poco_name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemWeapons/ComWeaponHudIcon/Container/TextField"
        else:
            ammo_index_poco_name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemWeapons/ComWeaponHudIcon.1/Container/TextField"
        now_num = self.get_poco_text(ammo_index_poco_name)
        return now_num

    # 获取 系统研发表，原 科技表
    def get_tc_excel(self):
        res = {}
        try:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "97_系统_研发表（原科技表）.xlsx")
            table_info = read_xlsx(table_path)
            weapon_info_list = table_info["系统_科技"]
            index = 0
            for weapon_info in weapon_info_list:
                _dict = {
                    int(str(weapon_info['节点id'])[0]): {
                        int(weapon_info['物品id']): {
                            "index": index,
                            "order_by": int(str(weapon_info['节点id'])[-2:]),
                            "blueprintIds": self.formatter_ingredients(weapon_info['蓝图id']),
                            "ingredientsIds": self.formatter_ingredients(weapon_info['必要材料ID']),
                            "ingredientsNum": self.formatter_ingredients(weapon_info['必要材料数量']),
                        }
                    }
                }
                if int(str(weapon_info['节点id'])[-3]) not in res.keys():
                    res[int(str(weapon_info['节点id'])[-3])] = _dict
                else:
                    if int(str(weapon_info['节点id'])[0]) not in res[int(str(weapon_info['节点id'])[-3])]:
                        res[int(str(weapon_info['节点id'])[-3])].update(_dict)
                    else:
                        res[int(str(weapon_info['节点id'])[-3])][int(str(weapon_info['节点id'])[0])].update(
                            _dict[int(str(weapon_info['节点id'])[0])])
            res = self.formatter_tc(res)
            return res
        except Exception as e:
            return res

    def get_blueprint_excel(self):
        item = {}
        try:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "98_蓝图表.xlsx")
            table_info = read_xlsx(table_path)
            weapon_info_list = table_info["蓝图总表"]
            index = 0
            for weapon_info in weapon_info_list:
                _dict = {
                    "index": index,
                    "ingredientsIds": self.formatter_ingredients(weapon_info['制造所需材料']),
                    "ingredientsNum": self.formatter_ingredients(weapon_info['材料数量']),
                    "ItemId": int(weapon_info['关联成品道具ID']),
                    "name": str(weapon_info['蓝图道具名称'])
                }
                if int(weapon_info['蓝图ID']) not in item.keys():
                    item[int(weapon_info['蓝图ID'])] = _dict
                else:
                    item.update(_dict)
            return item
        except Exception as e:
            return item

    def formatter_ingredients(self, item):
        try:
            if not item:
                return []
            if isinstance(item, str) and ';' in item:
                items_list = item.split(';')
                items_int_list = [int(item) for item in items_list]
                return items_int_list
            else:
                return [int(item)]
        except Exception as e:
            print(e)
            print(item)

    def formatter_tc(self, data):
        for first_level_key, first_level_value in data.items():
            for second_level_key, second_level_value in first_level_value.items():
                for index, item in enumerate(second_level_value):
                    # 添加option属性，包含层级和下标
                    item['option'] = [first_level_key, second_level_key, index]
        return data

    def get_id_multi_language(self):
        """
        将多语言表的英文名和ID对上
        @return: {"Wood Double Door":10010003}
        """
        if not self.weapon_id_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "93_多语言_道具主表.xlsx")
            table_info = read_xlsx(table_path)
            id_info_list = table_info["多语言_道具名称"]
            for id_info in id_info_list:
                if "道具_总表@41_道具_总表.xlsx" in id_info['key名']:
                    if id_info['英文文案'] not in self.multi_language_info:
                        self.multi_language_info[id_info['英文文案']] = id_info['key名'].split("|")[-1].split("|")[-1]
            return self.multi_language_info

    # 获取近战武器表
    def get_weapon_throw_info(self, excel_name, table_name):
        if not self.weapon_id_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      excel_name)
            table_info = read_xlsx(table_path)
            weapon_info_list = table_info[table_name]
            for weapon_info in weapon_info_list:
                if "ID" in weapon_info.keys():
                    self.weapon_id_info[int(weapon_info["ID"])] = weapon_info
            return self.weapon_id_info

    def get_item_info(self, excel_name, table_name):
        if not self.item_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      excel_name)
            table_info = read_xlsx(table_path)
            weapon_info_list = table_info[table_name]
            for weapon_info in weapon_info_list:
                if "ID" in weapon_info.keys():
                    self.item_info[int(weapon_info["id"])] = weapon_info
            return self.item_info

    # 获取近战武器表
    def get_weapon_melee_info(self, excel_name, table_name):
        if not self.weapon_id_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      excel_name)
            table_info = read_xlsx(table_path)
            weapon_info_list = table_info[table_name]
            for weapon_info in weapon_info_list:
                if "近战武器ID" in weapon_info.keys():
                    self.weapon_id_info[int(weapon_info["近战武器ID"])] = weapon_info
            return self.weapon_id_info

    def get_weapon_info(self, ):
        """
        获取武器信息
        @return: {'##comment': None, '枪械ID': '90010003', '使用类别': '怪物专用',
         '枪械类型': None, '枪械名称': '武装tank主炮', '是否单发': 'true', '射击模式': '1',
          '点射后不能开火的时间': None, '是否自动创建预制': 'false', '耐久扣除基础值': '1.5',
           '蓄力耐久': None, '随机击发概率': None, '击发后座力': None, '音频识别': 'AKM',
           'FP武器动画状态机挂哪个层级': None, 'TP武器动画状态机挂哪个层级': None, '武器挂接类型': '0',
           '可使用配件': None, '槽位数量': 0, '可使用子弹类型': '90010003',
           '武器消耗资源类型': None, '蓄力武器最小伤害系数 ': None, '蓄力武器最小速度系数': None,
           '子弹飞行速度系数': 1, '子弹伤害系数': 1, '距离衰减系数': 1, '射速': 5000, '开火结束时长': '800',
           '开火结束后延迟时间': None, '机瞄FOV': 35, '腰射GunFov': '50', '基础弹夹数量': 1, '部署时间': '2200',
            '换弹时间': 7167, '实际换弹时间': 6667, '单次换弹数': -1, '换弹start时间': '0', 'start阶段上弹时间': None,
             '换弹end时间': '0', '换弹结束可开火时间': None, '松手开火时间': None, '执行拉栓延迟时间': None, '拉栓时间': None,
             '可开火时间': None, '空仓换弹时间': None, '实际空仓换弹时间': None, '最短拉弓时间': None, '弓箭撒放时长': None,
             '开镜逻辑时长': 267, '开镜动画时间': 267, '开镜gunfov变化时长': 267, '关镜逻辑时长': 267, '关镜动画时间': 267,
             '关镜gunfov变化时长': 267, '进阶拉弓时长': None, '进阶拉弓取消时长': None, '检视时长': None, '快速切枪状态时长': 500,
             '疾跑换弹融合权重': 0.3, '开关镜散布变化完成百分比': 0, '使用散布': 1, '使用viewkick': '7', '使用gunkick': None, '受击镜头ID': 1,
             '死亡力引用': None, '子弹能量加成系数': '1', '子弹最大穿透次数加成系数': '1', 'tp遮挡收枪距离': '0.2', '枪械挂左手还是右手': None,
             'TP-枪械挂左手还是右手': 2, 'NewTP-枪械挂左手还是右手': '2', '生效的辅助瞄准类型': 14, '开火吸附百分比': '0.6', '开火吸附时长': '0.3',
             '开火吸附距离限制(m 以内生效)': '80', '开镜吸附延迟': 0.4, '开镜吸附有效距离': '40', '开镜吸附角速度': 50, '启用跟随吸附的状态': 2, '跟随吸附生效距离m': 30,
              '魔法子弹吸附配置': '0,20,2.20,0.5;20,50,0.8,0.5', '魔法子弹生效类型': '21,1,4,7,10,11;17,2,0,4,10', '产生噪音': '10',
              '引用怪物听觉id': '1001', '需要隐藏的HudUI': '259;273;274;275;281', '第三人称roll晃动的百分比': None, '玩家中线吸附配置': '20,0.5,15', '怪物中线吸附配置': '20,1,15'}
        """
        if not self.weapon_id_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "42_道具_远程武器表.xlsx")
            table_info = read_xlsx(table_path)
            if not table_info:
                self.auto.add_log(f"远程武器表:{table_path}")
                return {}, {}
            weapon_info_list = table_info["道具_远程武器表"]
            for weapon_info in weapon_info_list:
                weapon_info["枪械ID"] = int(weapon_info["枪械ID"])
                if isinstance(weapon_info["可使用子弹类型"], str):
                    int_list, is_ok = table_string_2_int_list(weapon_info["可使用子弹类型"])
                else:
                    int_list, is_ok = [weapon_info["可使用子弹类型"]], True
                if is_ok:
                    weapon_info["可使用子弹类型"] = int_list
                else:
                    weapon_info["可使用子弹类型"] = []
                if "枪械ID" in weapon_info.keys():
                    self.weapon_id_info[int(weapon_info["枪械ID"])] = weapon_info
                if "枪械名称" in weapon_info.keys():
                    self.weapon_name_info[weapon_info["枪械名称"]] = weapon_info
        return self.weapon_id_info, self.weapon_name_info

    def get_building_info(self, ):
        """
        获取摆件和建筑的基础信息
        zhangyx:
        可建造位置注解：11仅可摆放在地板 12仅可摆放在场景地面 13仅可摆放在墙面 14仅可摆放在地基和地板 15地板，地基，场景地面 16地板，墙面，场景地面，地基 17仅水中可摆放 18地基，地板，墙面 19地基 100不可摆放
        @return:{'##comment': '木块', '造物ID': 19010009, 'Colleciotn类型': None, '可建造位置': 100, '##配置检查': '=IFERROR(IF(MATCH(B178,建筑_伤害表!B:B,0)>0,""),"未配伤害表")',
         '造物名称': 'DebrisWall', '资源名称': 'debris_wall', '造物1.2倍': None, '是否需要加载缩放之后的资源': None, '是否有额外拟建体': None,
         '造物类型': 3, '附加功能': None, '消耗系数': None, '科技组ID': None, '容器ID': None, '交互ID': None, '是否允许在别人的领地范围内建造': 1,
          '是否吸附在其他造物': None, '能不能拾取': None, '是否需要建造权': None, '是否需要空容器': None, '被破坏是否留下小木盒子': None, '减少数值': None,
           '资源路径': 'BuildingAccessory', '名称关联': '木块', '描述关联': '木块', '描述标签': '屋顶', '摆件放置音效': 'Svl_Build_Deploy_WoodDoor',
            '摆件破碎音效': 'Svl_Build_Wood_Crash', '建筑客户端模块': None, '建筑服务器模块': None, '建筑模拟服模块': None, '是否可拆除': None, '是否可维修': 1,
             '是否无视领地权限': None, '旋转角度': None, '放置前旋转': None, '放置后旋转': None, '拟建体最远距离': None, '是否腐蚀': None, '腐蚀系数': 0,
              '腐蚀延迟': None, '腐蚀持续': None, '腐蚀等级': None, '吸附最远距离': 9, '摆放特效参数': None, '是否可以接收水': None, None: None, '是否能上锁': None,
               '是否需要拟建结合体': None, '放置时自动创建摆件': None, '吸附距离纠正长度': None, '吸附距离纠正宽度': None, '数量限制': None, '回收权类型': None,
               '删除权类型': None, '交互权类型': None, '密码权类型': 2, '建造权类型': 1, '是否可升级': None, '升级目标Id': None, '建造标签': None, '建筑图标': None,
               '建筑特效': None, '材料': None, '材料数量': None, '升级系数': None, '对应预设组id': None, '未找到吸附点提示': None, '角度检测不通过提示': None,
               '地面检测不通过提示': None, '是否可以移动': None, '是否可以切换吸附点': None, '造物图标': None, '开关门动画播放时间': None, '是否为预设组子建筑': None,
                '显示优先级': None, '移动cd': None, '维修类型': None, 'AOI距离': 0}
        """
        if not self.building_name_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "21_系统_建筑表.xlsx")
            table_info = read_xlsx(table_path)
            building_info_list = table_info["建筑_结构造物表"]
            build_expend_info_list = table_info["建筑_建筑等级表"]
            build_expend_dic = {}
            for build_expend_info in build_expend_info_list:
                expend_id = build_expend_info["消耗道具"]
                expend_num = build_expend_info["数量"]
                expend_level = build_expend_info["等级名称"]
                build_expend_dic[expend_level] = {"消耗道具": expend_id, "数量": expend_num}
            for table_info in building_info_list:
                part_name = table_info["##comment"]
                part_id = table_info["造物ID"]
                table_info["消耗"] = build_expend_dic
                self.building_id_info[part_id] = table_info
                self.building_name_info[part_name] = table_info
        return self.building_id_info, self.building_name_info

    def collimation_entity(self, entity_id, entity_type="", is_perf=False, **kwargs):
        """
        瞄准指定的entity
        @param entity_id:
        @return:
        """

        all_entity_dic = self.get_user_entity(entity_type, is_perf=is_perf)
        entity_id_str = str(entity_id)
        if entity_id_str in all_entity_dic.keys():
            print(f"瞄准entity{entity_id}")
            entity_dic = all_entity_dic[entity_id_str]
            add_yaw = kwargs.get("collimation_yaw", 0)
            add_pitch = kwargs.get("collimation_pitch", 0)
            self.collimation_to_pos(entity_dic["pos"]["x"], entity_dic["pos"]["y"], entity_dic["pos"]["z"],
                                    add_pitch=add_pitch,
                                    add_yaw=add_yaw)
            return True
        else:
            print("entity不存在，无法瞄准")
            return False

    def move_to_entity(self, entity_id, entity_type="", is_perf=False):
        """
        项指定的entity移动/靠近
        @param entity_id:
        @return:
        """
        all_entity_dic = self.get_user_entity(entity_type, is_perf=is_perf)
        entity_id_str = str(entity_id)
        if entity_id_str in all_entity_dic.keys():
            entity_dic = all_entity_dic[entity_id_str]
            self.move_to_pos(entity_dic["pos"]["x"], entity_dic["pos"]["y"], entity_dic["pos"]["z"], 1)
        else:
            print("entity不存在，无法瞄准")

    def transmit_to_entity(self, entity_id, entity_type="", is_perf=False):
        """
        传送到指定的entity，并且瞄准
        @param entity_id:
        @return:
        """
        all_entity_dic = self.get_user_entity(entity_type, is_perf=is_perf)
        entity_id_str = str(entity_id)
        if entity_id_str in all_entity_dic.keys():
            entity_dic = all_entity_dic[entity_id_str]
            self.transmit_to(
                [float(entity_dic["pos"]["x"]), float(entity_dic["pos"]["y"]), float(entity_dic["pos"]["z"]) - 1])
            self.collimation_entity(entity_id)
        else:
            print("entity不存在，无法瞄准")

    def get_pitch_yaw(self):
        """
        获取当前视角
        @return:
        """
        pos_dic, is_get = self.get_camera()
        if not is_get:
            self.auto.add_log(f"获取当前视角失败", False)
            return 0, 0
        rotation = pos_dic["rotation"]  # 视角
        pitch = rotation["y"]
        yaw = rotation["x"]
        return pitch, yaw

    def build_advanced(self, build_id, **kwargs):
        """
        建造高级建筑
        @return:
        """
        build_info = self.building_id_info[build_id]
        build_name = build_info["造物名称"]
        build_name_ch = build_info["##comment"]  # 建筑中文名称
        # 默认在建筑没打开的界面
        if not self.is_in_build():
            self.open_build()
        old_entity_info_list = self.get_self_entity_by_name("PartEntity", build_name_ch)
        old_entity_id_list = []
        for old_entity_info in old_entity_info_list:
            old_entity_id_list.append(old_entity_info["EntityId"])
        print(f"开始建造建筑--{build_name_ch}")
        build_index_num = build_info["核心建筑位置"]
        build_p = build_info["建造标签"]  # 建造位置，跟从建筑栏选择图标有关
        add_num = build_info["消耗"]["Twig"]["数量"]
        build_consume_num = build_info["消耗系数"]
        if build_consume_num:
            add_num = math.ceil(add_num * float(build_consume_num))
        build_type = build_info["可建造位置"]
        resource_id = 12030001
        old_num = self.get_resource(resource_id)
        add_pitch = kwargs.get("build_pitch", 0)
        #   14仅可摆放在地基和地板   18地基，地板，墙面 19地基
        if build_type == 14 or build_type == 18 or build_type == 19:
            print(f"开始建造建筑--{build_name_ch}的前置建筑地基")
            self.close_build()
            old_pitch, old_yaw = self.get_pitch_yaw()
            self.set_role_pitch(-35 + add_pitch)
            self.auto.auto_sleep(1)
            foundation_id = 1
            if build_id == 18:
                foundation_id = 2
            build_list = self.build_advanced(foundation_id)  # 递归造一个地基
            # 建筑造完要回归视角，造完前置建筑后，视角要还原，后置建筑才能造
            self.set_role_yaw(old_yaw)
            self.set_role_pitch(old_pitch)
            self.open_build()
            if len(build_list) == 0:
                self.auto.add_log(f"前置地基建筑失败，{build_name_ch}建筑终止建造", False)
                return []
        elif build_type == 13:  # 13仅可摆放在墙面
            print(f"开始建造建筑--{build_name_ch}的前置建筑墙面")
            self.close_build()
            # old_pitch, old_yaw = self.get_pitch_yaw()
            # 先造一个墙
            self.set_role_pitch(-20 + add_pitch)  # 这里预先设置一个视角用来造墙
            build_list = self.build_advanced(9, collimation_entity=True)  # 递归造一个墙壁
            # self.set_role_yaw(old_yaw) 瞄准墙壁就不用恢复视角了，直接造到墙上就好了
            # self.set_role_pitch(old_pitch)
            if len(build_list) == 0:
                self.auto.add_log(f"前置墙壁建筑失败，{build_name_ch}建筑终止建造", False)
                return []
            self.set_role_pitch(0)  # 这个墙造好了，把视角固定到墙上
            self.open_build()
        elif build_type == 11:  # 11仅可摆放在地板 todo 这个还要调整一下任务垂直高度，后面有了再调
            print(f"开始建造建筑--{build_name_ch}的前置建筑地板")
            self.close_build()
            old_pitch, old_yaw = self.get_pitch_yaw()
            self.set_role_pitch(0 + add_pitch)
            # 再造一个地板
            build_list = self.build_advanced(5)  # 递归造一个地板
            self.set_role_yaw(old_yaw)
            self.set_role_pitch(old_pitch)
            if len(build_list) == 0:
                self.auto.add_log(f"前置地板建筑失败，{build_name_ch}建筑终止建造", False)
                return []
            self.open_build()
        elif build_type == 17 or build_type == 100:  # 17仅水中可摆放 100不可摆放
            self.close_build()
            # 水里和不可摆放的先不管
            return []
        else:  # 12仅可摆放在场景地面 15地板，地基，场景地面 16地板，墙面，场景地面，地基
            self.set_role_pitch(-35 + add_pitch)
            pass
        # 建造
        self.auto.auto_sleep(0.5)
        if build_p == 5:
            # 第一格 地基
            self.touch_type_2()
        elif build_p == 1:
            # 天花板
            self.touch_type_4()
        elif build_p == 2:
            #  墙壁
            self.touch_type_3()
        elif build_p == 3:
            # 门窗
            self.touch_type_5()
        elif build_p == 4:
            # 楼梯
            self.touch_type_6()
        elif build_p == 6:
            # 第0格
            self.touch_type_1()
        else:  # 31-35
            # todo 电力的后续再写
            self.auto.add_log("电力后续再写，按失败处理", False)
            self.close_build()
            return []
        self.auto.auto_sleep(1)
        if build_index_num is not None:  # 这里是建筑
            self.add_resource_and_inspect(resource_id, add_num)
            self.auto.auto_sleep(1)
            self.use_build(build_index_num - 1)
            self.auto.auto_sleep(1)
        else:  # 这里是摆件
            self.add_resource_and_inspect(build_id, 1)
            self.auto.auto_sleep(1)
            self.use_build(0)
        new_add_num = self.get_resource(resource_id)
        is_this = self.is_this_build(build_name + "_Holding")
        if not is_this:
            print("建筑选取失败")
            self.close_build()
            return []
        self.do_build_up_down(build_name + "_Holding")
        self.auto.auto_sleep(2)
        entity_info_list = self.get_self_entity_by_name("PartEntity", build_name_ch)
        entity_id_list = []
        build_entity_info_list = []
        if len(entity_info_list) == 0:
            self.auto.add_log(f"建筑 {build_name_ch} 建造失败", False)
        else:
            for entity_info in entity_info_list:
                if entity_info["TemplateId"] == build_id:
                    build_entity_info_list.append(entity_info)
                    if kwargs.get("collimation_entity", False):
                        entity_id = entity_info["EntityId"]
                        self.collimation_entity(entity_id, **kwargs)
                    entity_id_list.append(entity_info["EntityId"])
            if len(entity_id_list) > len(old_entity_id_list):
                self.auto.add_log(f"建筑 {build_name_ch} 建造成功", True)
            else:
                self.auto.add_log(f"建筑 {build_name_ch} 建造失败", False)
        new_num = self.get_resource(resource_id)
        if old_num == new_num:
            self.auto.add_log(f"建筑 {build_name_ch} 材料消耗正常", True)
        else:
            if new_add_num == new_num:
                self.auto.add_log(f"建筑 {build_name_ch} 建造材料消耗异常，失败，未消耗材料 {old_num} {new_num}", False)
            else:
                self.auto.add_log(
                    f"建筑 {build_name_ch} 建造材料消耗异常，失败，消耗材料数和预期不符 {old_num} {new_num}", False)
        self.close_build()
        return build_entity_info_list

    def do_build_up_down(self, build_name, err_num=50):
        """
        执行建造操作,必须要用这个函数建造，因为建筑建造有红色状态检测，是红的就没办法造
        @param build_name: 建筑的名字
        @param err_num:视角检索次数，如果超过这个次数的视角旋转都无法建造，就当做失败
        @return:
        """
        # 先拉取视角，看看上下方向是不是要变了
        is_build = False
        run_num = 0
        direction = "up"
        while not is_build:
            is_build = self.do_build_rpc(build_name)
            if not is_build:
                pos_dic, is_get = self.get_camera(False)
                if is_get:
                    rotation = pos_dic["rotation"]  # 视角
                    position = pos_dic["position"]
                    # T是上，F是下
                    if rotation["y"] >= 80:
                        direction = "down"
                    elif rotation["y"] <= -80:
                        direction = "up"
                    self.set_visual_angle(direction, 5)
                else:
                    self.auto.raise_err_and_write_log("摄像机数据获取失败", 5)
                run_num += 1
                if err_num <= run_num:
                    self.auto.raise_err_and_write_log(f"建造了{run_num}次都没有成功，请检查", 5)

    def build_upgrade_num(self, build_id, num, entity_id=0):
        """
        将建筑升级至指定等级
        @param build_id:建筑id
        @param num:需要升级的等级,1-4为升级，5为删除，切要传入entity_id
        @param entity_id:用于删除之后判断有没有删除成功的
        @return:
        """
        self.auto.add_log(f"开始建筑升级至 {num} 级", True)
        if not self.is_in_build():
            self.open_build()
        build_info = self.building_id_info[build_id]
        if num == 1:
            up_resource_name = "Wood"
            add_num = build_info["消耗"][up_resource_name]["数量"]
            resource_id = build_info["消耗"][up_resource_name]["消耗道具"]
        elif num == 2:
            up_resource_name = "Stone"
            add_num = build_info["消耗"][up_resource_name]["数量"]
            resource_id = build_info["消耗"][up_resource_name]["消耗道具"]
        elif num == 3:
            up_resource_name = "Sheet Metal"
            add_num = build_info["消耗"][up_resource_name]["数量"]
            resource_id = build_info["消耗"][up_resource_name]["消耗道具"]
        elif num == 4:
            up_resource_name = "Armored"
            add_num = build_info["消耗"][up_resource_name]["数量"]
            resource_id = build_info["消耗"][up_resource_name]["消耗道具"]
        elif num == 5:
            up_resource_name = ""
            add_num = 0
            resource_id = 0
        else:
            return
        if add_num != 0 and resource_id != 0:
            old_num = self.get_resource(resource_id)
            self.add_resource_and_inspect(resource_id, add_num)
            old_entity_hp = self.get_entity_hp_by_id(entity_id)
        self.touch_upgrade()  # 点击升级按钮
        if num == 1:
            self.touch_upgrade_type1()
        elif num == 2:
            self.touch_upgrade_type2()
        elif num == 3:
            self.touch_upgrade_type3()
        elif num == 4:
            self.touch_upgrade_type4()
        elif num == 5:
            self.touch_upgrade_del()
            self.auto.auto_sleep(1)
        else:
            return
        self.touch_upgrade_do()  # 确认升级
        new_entity_hp = self.get_entity_hp_by_id(entity_id)
        if add_num != 0 and resource_id != 0:
            new_num = self.get_resource(resource_id)
            if old_num == new_num:
                self.auto.add_log(f"建筑升级至 {up_resource_name} 材料消耗正常", True)
            else:
                self.auto.add_log(f"建筑升级至 {up_resource_name} 建造材料消耗异常，失败", False)
            if old_entity_hp <= new_entity_hp:
                self.auto.add_log(f"建筑升级至 {up_resource_name} 建筑血量增加异常，失败", False)
            else:
                self.auto.add_log(f"建筑升级至 {up_resource_name} 建筑血量增加正常", True)
        else:
            if entity_id == 0:
                self.auto.add_log("没有传入entity_id，无法判断是否删除成功")
            else:
                is_exist = self.entity_is_exist(entity_id)
                if is_exist:
                    self.auto.add_log(f"建筑{build_id}删除失败", False)
                else:
                    self.auto.add_log(f"建筑{build_id}删除成功", True)
        self.touch_upgrade_return()
        self.close_build()

    def get_battle_numerical_value_info(self, ):
        """
        获取战斗_数值表信息
        @return:{'##': '装备防御', 'id': 13010001, '防御名称': '面罩', '密度': None, '通用': 0, '饥饿': 0, '口渴': 0, '寒冷': 0, '溺水': 0,
        '燃烧': 0, '流血': 0, '毒性': 0, '自杀': 0, '子弹': 0.05, '劈砍': 0.1, '钝击': 0.1, '跌落': 0, '辐射': 0, '撕咬': 0.03, '捅刺': 0.1,
         '爆炸': 0, '辐射暴露': 0.03, '寒冷暴露': 0.1, '腐蚀': 0, '电击': 0, '箭矢': 0.05, '车辆': 0, '碰撞': 0, '水枪': 0}
        """
        if not self.battle_numerical_value_name_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "62_战斗_数值.xlsx")
            table_info = read_xlsx(table_path, pass_num=4, key_num=3)
            building_info_list = table_info["战斗数值_防御"]
            for table_info in building_info_list:
                part_name = table_info["防御名称"]
                part_id = table_info["id"]
                self.battle_numerical_value_id_info[part_id] = table_info
                self.battle_numerical_value_name_info[part_name] = table_info
        return self.battle_numerical_value_id_info, self.battle_numerical_value_name_info

    def get_parts_info(self, ):
        """
        获取战斗_数值表信息
        @return:{'##type': None, 'id': 16030001, '配件类型': '3', '挂点': attach_8xscope, '特殊挂点': None, '辅助瞄准系数': 0.6, 'FOV': 7.5, '开镜逻辑时长': 267, '开镜动画': 267,
        '开镜gunfov变化时长': 267, '关镜逻辑时长': 400, '关镜动画时间': 430, '关镜gunfov变化时长': 450, '开镜灵敏度默认系数': 1.2, '开火灵敏度默认系数': 1.2, '倍镜ui路径': None, '垂直后座(%)': None, '开关节点名称': None, '弹容量修正（%）': None, '伤害修正（%）': None,
         '子弹初速修正（%）': None, '射速修正（%）': None, '散布修正(%)': None, '枪口特效修正': None, '产生噪音': 0, '引用怪物听觉id': None}
        """
        if not self.parts_name_info:
            table_path = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), "table",
                                      "44_道具_枪械配件表.xlsx")
            table_info = read_xlsx(table_path, pass_num=3, key_num=0)
            building_info_list = table_info["道具_枪械配件表"]
            for table_info in building_info_list:
                part_name = table_info["配件名称"]
                part_id = table_info["配件ID"]
                self.parts_name_info[part_name] = table_info
                self.parts_id_info[part_id] = table_info
            return self.parts_id_info, self.parts_name_info

    def fire_to_entity_by_id(self, entity_id, fire_num: int, weapon_name, **kwargs):
        """
        朝指定的entity开火，如果要检测建筑承伤数量，需要传入check_fire_num(检查数)，bullet_id(子弹id)
        @param entity_id:
        @param fire_num:
        @param weapon_name:使用的武器
        @return:
        """
        test = False
        self.auto.add_log(f"开始进行开枪检测 {weapon_name} 开 {fire_num}")
        self.get_weapon_info()
        print(self.weapon_name_info)
        if isinstance(weapon_name, str):
            if weapon_name not in self.weapon_name_info.keys():
                self.auto.raise_err_and_write_log(f"枪械{weapon_name}在表中不存在，请检查", 5)
            weapon_id = self.weapon_name_info[weapon_name]["枪械ID"]
        elif isinstance(weapon_name, int):
            weapon_id = weapon_name
            test = True
        is_ok = self.collimation_entity(entity_id)
        if is_ok:
            # 判断手里有没有枪
            hand_weapon_id = self.get_user_hand_id()
            if weapon_id != hand_weapon_id and hand_weapon_id != 0:
                self.drop_item_shortcut(6, 1)
                self.drop_item_shortcut(7, 1)
                self.add_resource_and_inspect(weapon_id, 1)
                self.auto.auto_sleep(2)
                if test:
                    self.use_shortcut_item(5)
                else:
                    self.use_shortcut_item(6)
                self.auto.auto_sleep(6)
            if hand_weapon_id == 0:
                self.add_resource_and_inspect(weapon_id, 1)
                self.auto.auto_sleep(2)
                if test:
                    self.use_shortcut_item(5)
                else:
                    self.use_shortcut_item(6)
                self.auto.auto_sleep(6)
            # 判断枪里有没有子弹
            bullet_id = kwargs.get("bullet_id", 0)
            # bullet_id = self.check_shortcut_weapon_ammo_num(6, weapon_id, bullet_id)
            if fire_num == 0:
                # 这里的逻辑说明是要打到碎
                old_entity_hp = self.get_entity_hp_by_id(entity_id)
                entity_info, is_get = self.get_entity_by_id(entity_id)
                if not is_get:
                    self.auto.raise_err_and_write_log("实体不存在，信息获取失败", 5)
                _fire_num = 0
                while old_entity_hp > 0:
                    self.fire()
                    self.auto.auto_sleep(1)
                    _fire_num += 1
                    new_entity_hp = self.get_entity_hp_by_id(entity_id)
                    self.auto.add_log(
                        f"枪械{weapon_id}使用子弹{bullet_id}开第{_fire_num}枪，entity还剩{new_entity_hp}血")
                    if old_entity_hp == new_entity_hp:
                        self.auto.add_log(f"枪械{weapon_id}使用子弹{bullet_id}开第{_fire_num}枪时没有检测到伤害，失败",
                                          False)
                    old_entity_hp = new_entity_hp
                check_fire_num = kwargs.get("check_fire_num", 0)
                if check_fire_num != 0:
                    if check_fire_num != _fire_num:
                        entity_table_id = entity_info["TemplateId"]
                        self.auto.add_log(
                            f"建筑{entity_table_id}受到枪械{weapon_id}使用子弹{bullet_id}开{_fire_num}枪后销毁",
                            False)
                return _fire_num, True
            else:
                old_entity_hp = self.get_entity_hp_by_id(entity_id)
                for i in range(fire_num):
                    self.fire()
                    if test:
                        self.auto.auto_sleep(15)
                    else:
                        self.auto.auto_sleep(1)
                    new_entity_hp = self.get_entity_hp_by_id(entity_id)
                    self.auto.add_log(f"枪械{weapon_id}使用子弹{bullet_id}开第{i + 1}枪，entity还剩{new_entity_hp}血")
                    if old_entity_hp == new_entity_hp:
                        self.auto.add_log(f"枪械{weapon_id}使用子弹{bullet_id}开第{i + 1}枪时没有检测到伤害，失败",
                                          False)
                    old_entity_hp = new_entity_hp
                return fire_num, True
        else:
            self.auto.raise_err_and_write_log("实体不存在，无法攻击", 5)
        return fire_num, False

    def test_build_upgrade(self, entity_id, build_lv):
        """
        建筑升级的接口
        """
        try:
            self.gm_rpc("set", [entity_id, build_lv], "EditUpgradePart")
        except Exception:
            return False
        return True

    def build_numerical_build(self):
        """
        建造建筑数值测试专用的建筑，并且在建筑前先将自己的建筑清除
        传送到指定位置，并且初始化视角，然后移除自己的建筑搭建固定的建筑，并将地基都升级为钢铁
        """
        self.remove_self_parts()
        self.transmit_to([425.5, 12.5, -1969], False)
        self.auto.auto_sleep(5)
        self.set_role_pitch(0)
        self.set_role_yaw(0)
        self.auto.auto_sleep(2)
        self.recover_construction("build_numerical", 426, 12, -1963, 130)
        self.auto.auto_sleep(5)
        entity_info_list = self.get_user_entity("PartEntity")
        for entity_id in entity_info_list:
            entity_info = entity_info_list[entity_id]
            if entity_info['TemplateId'] == 1:
                build_entity_id = entity_info["EntityId"]
                self.test_build_upgrade(build_entity_id, 5)

    def build_hp_judge(self, old_hp, now_hp, bullet_num, real_num):
        """
        如果子弹数量或者使用数量过高，则使用判断的方式进行约数判断，否则会耗时太久
        """
        # 将前后的血量传进来
        # 拿到子弹数
        if now_hp == 0 and bullet_num != real_num:
            self.auto.add_log("实际消耗子弹与子弹数量不一致，需要进行检查", False)
        hp = (old_hp - now_hp) / real_num
        if abs(hp * bullet_num - old_hp) < 10:
            # todo 给10点血作为容错，后续再观察是否会有问题
            self.auto.set_case_results(True)
        else:
            self.auto.add_log("计算后建筑的血量误差大于了10点血量，需要进行检查", False)
            self.auto.set_case_results(False)

    def build_numerical_explosive(self, entity_id, **kwargs):
        """
        投掷/爆炸类武器的测试
        """
        # TODO 需要处理哑炮逻辑
        bullet_num = kwargs.get("bullet_num", None)
        weapon_name = kwargs.get("weapon_name", None)
        weapon_id = self.multi_language_info[weapon_name]
        old_hp = self.get_entity_hp_by_id(entity_id)
        real_num = 0
        if bullet_num < 10:
            real_num = bullet_num
        else:
            real_num = 10
        self.add_resource(weapon_id, real_num)
        self.collimation_entity(entity_id)
        self.use_shortcut_item(5)
        self.auto.auto_sleep(3)
        # 循环投掷
        for i in range(0, real_num):
            self.fire()
            self.auto.auto_sleep(1)
        # 让子弹飞一会！
        self.auto.auto_sleep(15)
        now_hp = self.get_entity_hp_by_id(entity_id)
        if bullet_num > 10:
            self.build_hp_judge(old_hp, now_hp, bullet_num, real_num)
        else:
            if now_hp == 0:
                self.auto.set_case_results(True)
            else:
                self.auto.add_log("没有将对应的建筑进行爆破，需要检查", False)

    def build_numerical_melee(self, entity_id, building_lv, **kwargs):
        """
        近战/近战投掷 类型的测试
        """
        self.clear_item_all()
        weapon_info_dict = self.get_weapon_melee_info("45_道具_手持道具表.xlsx", "手持道具_近战武器表")
        item_info_dict = self.get_item_info("41_道具_总表.xlsx", "道具_总表")
        lose_list = [6, 7, 11, 0]  # todo 后续改，太临时了
        bullet_num = kwargs.get("bullet_num", None)
        weapon_type = kwargs.get("weapon_type", None)
        bullet_name = kwargs.get("bullet_name", None)
        weapon_name = kwargs.get("weapon_name", None)
        weapon_id = self.multi_language_info[weapon_name]
        max_condition = item_info_dict[weapon_id]['maximumDurability']
        material_type = weapon_info_dict[weapon_id]['materialtype']
        building_condition_id = self.build_lv_material[building_lv]
        if isinstance(self.build_condition_lost[material_type], int):
            # 消耗的耐久
            lose_condition = self.build_condition_lost[material_type]
        else:
            index = lose_list[building_condition_id]
            lose_condition = self.build_condition_lost[material_type][index]
        if bullet_name == "Workbench Refill" or bullet_name == "Lit":
            self.auto.add_log(f"当前的方式无需进行测试，{bullet_name}", True)
            self.auto.set_case_results(True)
            return
        old_hp = self.get_entity_hp_by_id(entity_id)
        self.add_resource(weapon_id, 1)
        self.auto.auto_sleep(2)
        self.use_shortcut_item(1)
        if weapon_type == "throw":
            self.fire2()
            self.auto.auto_sleep(2)
        self.fire()
        now_hp = self.get_entity_hp_by_id(entity_id)
        real_num = lose_condition / max_condition
        self.build_hp_judge(old_hp, now_hp, bullet_num, real_num)

    def build_numerical_gun(self, entity_id, **kwargs):
        """
        枪械类武器测试
        """
        self.clear_item_all()
        bullet_num = kwargs.get("bullet_num", None)
        bullet_name = kwargs.get("bullet_name", None)
        weapon_name = kwargs.get("weapon_name", None)
        weapon_id = self.multi_language_info[weapon_name]
        bullet_id = self.multi_language_info[bullet_name]
        self.add_resource(weapon_id, 1)
        old_hp = self.get_entity_hp_by_id(entity_id)
        self.use_shortcut_item(6)
        self.auto.auto_sleep(5)
        # todo完成一个枪械换弹药的操作
        entity_id = self.get_user_hand()['entity_id']
        self.unload(entity_id)
        self.clear_item_bag()
        self.auto.auto_sleep(2)
        self.add_resource(bullet_id, 1)
        self.auto.auto_sleep(2)
        self.reload()
        self.auto.auto_sleep(5)
        self.fire()
        self.auto.auto_sleep(2)
        now_hp = self.get_entity_hp_by_id(entity_id)
        self.build_hp_judge(old_hp, now_hp, bullet_num, 1)

    def test(self):
        """
        测试函数，无实际意义
        """
        if self.server_name is None:
            self.server_name = random.randint(0, 100)
        self.auto.add_log(f"测试服务器名为{self.server_name}")

    def build_numerical_test_tools(self, building_name, building_lv, **kwargs):
        """
        建筑数值专用测试函数，主要是针对所有的建筑模块不同等级和所有武器进行测试
        kwargs中可以传入参数
        build_defense 建筑防御，如果不传就不在意，如果传了就要确定对准的是建筑防御的哪一面
        weapon_type 使用的是哪种类型的武器，不同武器的攻击方式不同，通过entity_id进行不同的攻击
        weapon_name 使用的武器名称叫什么
        bullet_name 使用的子弹是什么，需要先确定类型再确定这个子弹的含义是什么
        bullet_num  使用多少子弹，具体要看什么武器，枪械类是子弹数量，近战类是消耗多少对应武器
        @param building_name 建筑名称，现在会传入一个英文名
        @param building_lv 建筑等级，目前会传入twig等英文
        @return
        """
        self.transmit_to([425.5, 12.5, -1969])
        building_name_chinese = self.build_name_dict[building_name]
        building_id_info, building_name_info = self.get_building_info()
        # 此函数使用前需要确认，人物已经传送到了指定的海面上，建筑的导入位置和偏移等都定死
        # 首先确定附近是否有要寻找的对应建筑，不考虑效率,如果没有则进行清理重新召唤
        building_is_have = False
        entity_info_list = self.get_user_entity("PartEntity")
        build_pos = []
        build_entity_id = 0
        for entity_id in entity_info_list:
            entity_info = entity_info_list[entity_id]
            if entity_info['TemplateId'] == building_name_info[building_name_chinese]['造物ID']:
                build_entity_id = entity_info["EntityId"]
                build_pos = [entity_info['pos']['x'], entity_info['pos']['y'], entity_info['pos']['z']]
                building_is_have = True
        if not building_is_have:
            self.build_numerical_build()
            entity_info_list = self.get_user_entity("PartEntity")
            for entity_id in entity_info_list:
                entity_info = entity_info_list[entity_id]
                if entity_info['TemplateId'] == building_name_info[building_name_chinese]['造物ID']:
                    build_entity_id = entity_info["EntityId"]
                    build_pos = [entity_info['pos']['x'], entity_info['pos']['y'], entity_info['pos']['z']]
        # 进行建筑的测试
        # 只需要z+2或者3就可以在建筑的前方 打弱点防御，如果z -2或者3 则就是建筑的后方，打强防御
        build_defense = kwargs.get("build_defense", None)
        weapon_type = kwargs.get("weapon_type", None)
        # 打防御强的一边，即在空中攻击建筑
        if len(build_pos) == 0:
            self.auto.add_log(f"在{building_name}的{building_lv}测试过程中，没有获取到建筑的pos，需要检查", False)
        else:
            if build_defense == "hard":
                if weapon_type == "melee" or weapon_type == "throw":
                    self.transmit_to([float(build_pos[0]), float(build_pos[1]), float(build_pos[2]) - 1])
                else:
                    self.transmit_to([float(build_pos[0]), float(build_pos[1]), float(build_pos[2]) - 2.5])
            else:
                if weapon_type == "melee" or weapon_type == "throw":
                    self.transmit_to([float(build_pos[0]), float(build_pos[1]), float(build_pos[2]) + 1])
                else:
                    self.transmit_to([float(build_pos[0]), float(build_pos[1]), float(build_pos[2]) + 2.5])
        self.auto.auto_sleep(3)
        self.clear_item_all()
        weapon_name = kwargs.get("weapon_name", None)
        # 爆炸类，比如手雷燃烧瓶等
        if weapon_type == "explosive" and weapon_name != "MLRS Rocket":
            self.build_numerical_explosive(build_entity_id, **kwargs)
        # 近战和近战的投掷
        if weapon_type == "melee" or weapon_type == "throw":
            self.build_numerical_melee(build_entity_id, building_lv, **kwargs)
        # 枪械的测试
        if weapon_type == "guns":
            self.build_numerical_gun(build_entity_id, **kwargs)
        else:
            self.auto.add_log(f"当前的武器类型{weapon_type}不支持或者不需要测试，请检查", False)
        self.remove_part_by_id(build_entity_id)

    def build_advanced_case_tools(self, building_name, subjoin_func_list=None, **kwargs):
        """
        建造单个建筑用例的通用函数，瞄准偏了穿collimation_yaw 或collimation_pitch，建造偏了传build_pitch做仰角补偿
        @param building_name:
        @param subjoin_func_list:附加函数类型，造完建筑需要开枪或者升级等，如果有入参，可以通过**kwargs传入
        @return:
        """
        if subjoin_func_list is None:
            subjoin_func_list = []
        self.remove_self_parts()
        self.open_damage_disable()
        building_id_info, building_name_info = self.get_building_info()
        case_first_pos = [822.7856, 3.406349, -1268.801]
        self.transmit_to(case_first_pos, True)
        self.auto.add_log(f"初始化用例位置,{case_first_pos}")
        self.set_role_yaw(0)
        building_info = building_name_info[building_name]
        building_id = building_info["造物ID"]
        build_type = building_info["可建造位置"]
        if build_type == 17 or build_type == 100:
            self.auto.add_log(f"建筑{building_name} {build_type}暂不支持建造，失败", False)
            self.auto.set_case_results(False)
            return
        # 这里走通用建造逻辑
        entity_info_list = self.build_advanced(building_id, **kwargs)
        if entity_info_list:
            for entity_info in entity_info_list:
                entity_id = entity_info["EntityId"]
                self.collimation_entity(entity_id, **kwargs)
                if "build_upgrade_num" in subjoin_func_list:
                    if "build_lv" in kwargs.keys():
                        build_lv = kwargs.get("build_lv", 1)
                        self.build_upgrade_num(build_id=building_id, num=build_lv, entity_id=entity_id)
                    else:
                        for i in range(5):
                            self.build_upgrade_num(build_id=building_id, num=i + 1, entity_id=entity_id)
                print(subjoin_func_list)
                if "fire_to_entity_by_id" in subjoin_func_list:  # 对建筑进行开火检测，如果要检测建筑承伤数量，需要传入check_fire_num(检查数)，bullet_id(子弹id)
                    fire_num = kwargs.get("fire_num", 0)
                    if "fire_num" in kwargs.keys():
                        kwargs.pop("fire_num")
                    weapon_name = kwargs.get("weapon_name", "AK-47突击步枪")
                    if "weapon_name" in kwargs.keys():
                        kwargs.pop("weapon_name")
                    self.fire_to_entity_by_id(entity_id, fire_num, weapon_name, **kwargs)
                if "nothing_to_build" in subjoin_func_list:
                    self.nothing_to_build(entity_id)
            self.auto.set_case_results(True)
        else:
            self.auto.set_case_results(False)
        time.sleep(3)
        check_recovery = kwargs.get("check_recovery", False)
        if check_recovery:
            pass
        else:
            self.remove_self_parts()

    def check_shortcut_weapon_ammo_num(self, shortcut_num, weapon_id, bullet_id=0):
        """
        检查手里的枪有没有子弹，如果没有就加点/装弹
        @param shortcut_num:
        @param weapon_id:
        @param bullet_id:子弹id
        @return:
        """
        bullet_num = self.get_weapon_ammo_num(shortcut_num)  # 判断一下枪里子弹数量
        if bullet_num == 0:
            if weapon_id in self.weapon_id_info.keys():
                weapon_info = self.weapon_id_info[weapon_id]
                if len(weapon_info["可使用子弹类型"]) > 0:
                    if bullet_id == 0:
                        bullet_id = weapon_info["可使用子弹类型"][0]
                    else:
                        if bullet_id not in weapon_info["可使用子弹类型"]:
                            self.auto.raise_err_and_write_log(f"传入的枪械子弹类型{bullet_id}在表中查不到，无法装弹", 5)
                    add_bullet_num = weapon_info["基础弹夹数量"]
                    bag_bullet_num = self.get_resource(bullet_id)
                    if bag_bullet_num == 0:  # 判断身上有没有子弹
                        self.add_resource_and_inspect(weapon_id, add_bullet_num)
                else:
                    self.auto.raise_err_and_write_log("枪械子弹类型在表中查不到，无法装弹", 5)
            else:
                self.auto.raise_err_and_write_log(f"枪械道具{weapon_id}在表中不存在", 5)
            self.reload()
        return bullet_id

    def use_part(self, building_name):
        """
        使用摆件
        @param building_name: 摆件entity表名字
        @return:
        """
        building_info = self.building_name_info[building_name]
        used_type = building_info["是否可以使用"]  # todo 等old_z加类型判断怎么使用
        entity_table_id = building_info["造物ID"]
        entity_info = self.get_user_entity("PartEntity")
        for entity_info_id, entity_info in entity_info.items():
            if entity_table_id == entity_info["TemplateId"] and self.get_role_id() == entity_info["OwnerId"]:
                # 根据表id判断，是要细分某些重点的摆件具体的操作
                entity_id = entity_info["EntityId"]
                if used_type == "":  # todo
                    self.touch_interactiveList()  # 只是点一下开关，如果没有报错，说明交互界面出来了
                    self.auto.add_log(f"摆件实体{entity_id}操作成功")
                    return
                elif used_type == "":  # todo  # 这里进入是统一的入口，退出的话需要遍历一下了
                    self.touch_interactiveList()  # 只是点一下开关，如果没有报错，说明交互界面出来了
                    self.auto.auto_sleep(2)
                    is_close = self.close_bag()
                    if not is_close:
                        is_close = self.close_ornament()
                        if not is_close:
                            is_close = self.touch_details_to_bag()
                            if not is_close:
                                is_close = self.touch_tech_to_bag()
                                if not is_close:
                                    is_close = self.close_water_view_page()
                                    if not is_close:
                                        is_close = self.touch_BackBtn()
                    if not is_close:
                        self.auto.raise_err_and_write_log(f"摆件实体{entity_id}页面无法关闭，缺少关闭操作", 5)
                    else:
                        self.auto.add_log(f"摆件实体{entity_id}页面关闭成功")
                        return
        self.auto.raise_err_and_write_log(f"摆件{entity_table_id}实体不存在，无法操作", 5)

    def up_car(self):
        """
        上载具
        @return:
        """
        # self.touch_interactiveList(".1")
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn"
        self.auto.auto_touch(name)

    def down_car(self):
        """
        下载具
        @return:
        """
        poco_name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.38/ElemGetOff/SkillBtn2"
        if self.auto.is_exist(poco_name):
            self.auto.auto_touch(poco_name)

    def open_car_light(self):
        """
        下载具
        @return:
        """
        poco_name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemLight/ElemCommonBtn6"
        if self.auto.is_exist(poco_name):
            self.auto.auto_touch(poco_name)

    def open_engine(self):
        """
        打开载具引擎界面
        @return:
        """
        poco_name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.51/ElemEngine/SkillBtn2"
        self.auto.auto_touch(poco_name)

    def open_fuel(self):
        """
        打开载具燃料界面
        @return:
        """
        poco_name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComVehicleRolling/Container/Container/ComVehicleStatusAndOil/ComAddResource2/BtnAddResource"
        self.auto.auto_touch(poco_name)

    def open_oil(self):
        """
        打开载具加油界面
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComVehicleRolling/Container/Container/ComVehicleStatusAndOil/ComAddResource/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name)

    def add_oil(self):
        """
        添加载具加油
        @return:
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComHandlePanel/ComHandle/BtnHandle"
        self.auto.auto_touch(name)

    def up_package_case_info(self, package_info: dict, case_devices_ip, json_file_path):
        """
        向服务注册包体信息，用于非poco包的冒烟流程，内置用例执行
        @param package_info:
        @param case_devices_ip:
        @param json_file_path:
        @return:
        """
        if not os.path.exists(json_file_path):
            self.auto.raise_err_and_write_log("json文件不存在", 5)
        with open(json_file_path, 'r', encoding='utf-8') as f:
            bug_info_str = f.read()
        up_data = {"package_info": package_info, "type": "up_json", "server_name": self.server_name,
                   "case_json_str": bug_info_str, "ip": case_devices_ip, "project_id": 33, }
        response = requests.post("http://192.168.181.52:11454/tools/auto/case_test/package_test_info", json=up_data)
        data_info = response.json()
        if data_info["success"]:
            print(data_info["message"])
        else:
            self.auto.raise_err_and_write_log("json文件不存在", 5)

    def get_package_case_result(self, package_info: dict, case_devices_ip):
        """
        向服务获取包体信息，用于非poco包的冒烟流程，内置用例执行，调用的地方需要有获取次数上限
        @param package_info:
        @param case_devices_ip:
        @return:
        """
        try:
            up_data = {"package_info": package_info, "type": "get_result",
                       "ip": case_devices_ip, "project_id": 33, }
            response = requests.post("http://192.168.181.52:11454/tools/auto/case_test/package_test_info", json=up_data)
            data_info = response.json()
            return data_info["data"]
        except Exception:
            return {}

    def find_entity_and_move(self, entity_type, is_perf=False):
        """
        查找附近的entity，并朝最近的移动过去，如果离得太远，会先传送一下
        @param entity_type:
        @return:
        """
        entity_list = []
        entity_info = self.get_user_entity(entity_type, is_perf=is_perf)
        for key, value in entity_info.items():
            entity_list.append(value)
        camera_info, is_get = self.get_camera(False)
        now_pos = camera_info["position"]
        # 挑一个最近的
        old_distance = 100
        get_entity_info = {}
        is_find = False
        for entity_info in entity_list:
            old_pos = entity_info["pos"]
            template_id = entity_info["TemplateId"]
            if entity_type == "VehicleModuleEntity" and template_id not in [12061014, 12061015, 12061001]:
                continue
            get_distance = self.distance(old_pos, now_pos)
            if get_distance < old_distance:
                get_entity_info = entity_info
                old_distance = get_distance
                is_find = True
        entity_id = get_entity_info.get("EntityId", 0)
        template_id = get_entity_info.get("TemplateId", 0)
        if entity_id == 0 or not is_find:
            self.auto.raise_err_and_write_log("entity查询失败", 5)
        x = get_entity_info["pos"]["x"]
        y = get_entity_info["pos"]["y"]
        z = get_entity_info["pos"]["z"]
        if entity_type in ["VehicleModuleEntity", "VehicleEntity"]:
            if template_id == 22030001:
                # 快艇特殊处理
                self.transmit_to([x, y + 2, z], False)
                self.set_role_pitch(-87)
            else:
                self.gm_fly_to_pos(x, y + 3, z, 2, 0, True)
                self.auto.auto_sleep(2)
                self.collimation_entity(entity_id, entity_type=entity_type, is_perf=is_perf)
        else:
            random_x = random.choice([random.uniform(-1.5, -1), random.uniform(1, 1.5)])
            random_z = random.choice([random.uniform(-1.5, -1), random.uniform(1, 1.5)])
            self.move_to_pos(x + random_x, y, z + random_z, run_num=2, transfer_help=True)
            self.collimation_entity(entity_id, entity_type=entity_type, is_perf=is_perf)
        return entity_id

    def bag_player_info(self):
        """
        点击背包界面中的状态栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnViewFullBody"
        self.auto.auto_touch(name)

    def bag_player_info_return(self):
        """
        点击背包界面中的状态栏返回
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiPlayerViewer(UiPlayerViewer)/ContentPane/UiPlayerViewerContent/BtnCommonBack"
        self.auto.auto_touch(name)

    def full_bag(self):
        """
        塞满背包
        """
        try:
            self.gm_rpc("add", f"GMFillUpWithItems")
        except Exception:
            return False
        return True

    def tidy_bag(self):
        """
        点击背包中的整理按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/ComInventoryMainBottom/ComInventoryMainOrgainze"
        self.auto.auto_touch(name)

    def bag_quick_delete(self):
        """
        点击背包中的快速删除按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/ComInventoryMainBottom/ComInventoryMainBatchDrop"
        self.auto.auto_touch(name)

    def case_sql_server_tools_get(self, find_key, lock=None):
        """
        用于查询用例存入数据库的数据
        加锁的时候必须要对应解锁，否则会锁死
        @param find_key:
        @return:
        """
        # task_id = self.auto.init_kwargs.get("case_info", {}).get("task_id", 0)
        url = 'http://192.168.181.52:11454/auto/task/case_tools_info'
        if lock is not None:
            json = {"info_key": find_key, "get": True, "lock": lock, "info": {}}
            if lock:
                try:
                    response = requests.post(url, json=json)
                except Exception as e:
                    print(e)
                    return {}
            else:
                response = requests.post(url, json=json)
        else:
            json = {"info_key": find_key, "get": True, "info": {}}
            response = requests.post(url, json=json)
        info_dic = response.json()
        self.auto.add_log(info_dic)
        print(info_dic)
        time.sleep(1)
        return info_dic["data"]

    def case_sql_server_tools_set(self, find_key, set_info, lock=None):
        """
        用于用例存入数据库数据
        加锁的时候必须要对应解锁，否则会锁死
        @param find_key:
        @param set_info:
        @return:
        """
        # task_id = self.auto.init_kwargs.get("case_info", {}).get("task_id", 0)
        url = 'http://192.168.181.52:11454/auto/task/case_tools_info'
        if lock is not None:
            json = {"info_key": find_key, "get": False, "lock": lock, "info": set_info}
            if lock:
                try:
                    response = requests.post(url, json=json)
                except Exception:
                    return None, False
            else:
                response = requests.post(url, json=json)
        else:
            json = {"info_key": find_key, "get": False, "info": set_info}
            response = requests.post(url, json=json)
        info_dic = response.json()
        self.auto.add_log(info_dic)
        return info_dic["data"], True

    def world_chat(self, content):
        """
        世界频道聊天
        """
        if content:
            try:
                self.gm_rpc("set", [content], "world")
            except Exception:
                return False
            return True

    def private_chat(self, toRoleId, content):
        """
        世界频道聊天
        """
        if content:
            try:
                self.gm_rpc("set", [toRoleId, content], "private")
            except Exception:
                return False
            return True

    def private_channel(self):
        """
        点击私聊频道
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiChat(UiChat)/ContentPane/GList/Container/Container/BtnChannelType.1"
        self.auto.auto_touch(name)

    def add_friend(self, role_id, role_name):
        """
        加好友
        """
        try:
            self.gm_rpc("set", [role_id, role_name], "AddFriend")
        except Exception:
            return False
        return True

    def open_friend(self):
        """
        打开好友
        @return:
        """
        try:
            self.get_poco_text(
                "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnLobbyIconFriend")
        except:
            name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnGroupFolder"
            self.auto.auto_touch(name)
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnLobbyIconFriend"
        self.auto.auto_touch(name)

    def friend_request_list(self):
        """
        打开好友请求列表
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyFriend(UiLobbyFriend)/ContentPane/BtnRequestList"
        self.auto.auto_touch(name)

    def close_friend_request_list(self):
        """
        打开好友请求列表
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyFriend(UiLobbyFriend)/ContentPane/ComRequestList/BtnClose"
        self.auto.auto_touch(name)

    def agree_all(self):
        """
        打开好友
        """
        try:
            self.get_poco_text(
                "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyFriend(UiLobbyFriend)/ContentPane/ComRequestList/BtnAgreeAll")
        except:
            self.auto.raise_err_and_write_log("no friend request!", 5)
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnLobbyIconFriend"
        self.auto.auto_touch(name)

    def del_friend(self):
        """
        删除好友
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyFriend(UiLobbyFriend)/ContentPane/GList/Container/Container/ComFriends/BtnFriendsOp.1"
        self.auto.auto_touch(name)
        name = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
        self.auto.auto_touch(name)

    def close_friend(self):
        """
        关闭好友界面
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyFriend(UiLobbyFriend)/ContentPane/BtnBack"
        self.auto.auto_touch(name)

    def team_invite(self, role_id):
        """
        发送队伍邀请
        """
        try:
            self.gm_rpc("set", [role_id], "TeamInvite")
        except Exception:
            return False
        return True

    # def open_team(self):
    #     """
    #     打开组队界面
    #     """
    #     name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader/ElemLeftTab/TabItem.1"
    #     self.auto.auto_touch(name)

    def team_invite_list(self):
        """
        跳转到处理邀请界面
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/BtnInvitedEntry"
        self.auto.auto_touch(name)

    def close_team(self):
        """
        关闭组队界面
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/BtnClose"
        self.auto.auto_touch(name)

    def accecpt_team_invite(self):
        """
        通过队伍列表接受队伍邀请
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/ContentTeamInvitedInfo/GList/Container/Container/IteamTeamInvitedInfo.1/BtnAcceptInvite"
        self.auto.auto_touch(name)

    def refuse_team_invite(self):
        """
        通过队伍列表拒绝队伍邀请
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/ContentTeamInvitedInfo/GList/Container/Container/IteamTeamInvitedInfo.1/BtnRefuseInvite"
        self.auto.auto_touch(name)

    def team_tab(self):
        """
        点击队伍界面的队伍页签
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/BtnTeamTab"
        self.auto.auto_touch(name)

    def leave_team_dating(self):
        """
        主动点击离队按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyTeam(UiLobbyTeam)/ContentPane/BtnClose"
        self.auto.auto_touch(name)
        time.sleep(0.5)
        name = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
        self.auto.auto_touch(name)

    def kick_out(self):
        """
        队长踢人（只踢走第一个）
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/ContentTeam/ContentTeamHas/GList/Container/Container/ItemTeammatesInfo.1/BtnAuthorEntry"
        self.auto.auto_touch(name)
        time.sleep(1)
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiTeam(UiTeam)/ContentPane/ContentTeam/ContentTeamHas/ComAuthor/GList/Container/BtnAuthority.4"
        self.auto.auto_touch(name)
        time.sleep(1)
        name = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
        self.auto.auto_touch(name)

    def open_gun_flashlight(self):
        """
        点击按钮形式开枪灯
        """
        name = 'Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.2/ElemFlashLight/ElemCommonBtn4'
        self.auto.auto_touch(name)

    def one_click_removal(self):
        """
        异端容器内物品一键取出
        """
        name = 'Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComLazyLoader.2/GLoader/ComInventoryOthersideToolBar/BtnOthersideOrganize.3'
        self.auto.auto_touch(name)

    def close_fusebox(self):
        """
        关闭保险盒
        """
        name = 'Stage/GRoot/(Full Screen) ID501|S501/UiSwipeCardGame(UiSwipeCardGame)/ContentPane/BtnBack'
        self.auto.auto_touch(name)

    def uwa_case_init(self):
        """
        自动化用例调用uwa的初始化逻辑
        @return:
        """
        # 先把这个设备的状态置为默认
        response = requests.post("http://192.168.181.52:11454/tools/auto/uwa_poco_devices",
                                 json={"type": "set", "project_id": 33, "version": "", "state": "default",
                                       "ip": self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]})
        self.auto.add_log("初始化注册", response.text)
        time.sleep(1)
        this_branch = self.auto.init_kwargs["task_info"]["game_git_info"]["branch"]
        response = requests.post("http://192.168.181.40:12345/auto/uwa/up_file",
                                 json={"pk_url": self.auto.init_kwargs["task_info"]["game_git_info"]["apk"],
                                       "branch": this_branch})
        up_file_dict = response.json()
        time.sleep(1)
        self.auto.add_log("上传包", up_file_dict)
        if "下载成功" in up_file_dict["message"]:
            self.auto.add_log("启动uwa包更新流水线")
            time.sleep(10)
            if this_branch == "trunk":
                response = requests.post(
                    "http://192.168.181.42/atx/api/v2/open/run?apiToken=trunk_update")  # 调用uwa的流水线，把刚刚上传的包注册一下
            elif this_branch == "shipping":
                response = requests.post(
                    "http://192.168.181.42/atx/api/v2/open/run?apiToken=shipping_update")  # 调用uwa的流水线，把刚刚上传的包注册一下
            time.sleep(60 * 5)
        time.sleep(1)
        self.auto.add_log("启动uwa用例流水线")
        if this_branch == "trunk":
            response = requests.post(
                "http://192.168.181.42/atx/api/v2/open/run?apiToken=trunk_4v4")  # 调用uwa的流水线，启动装包和启动游戏逻辑
        elif this_branch == "shipping":
            response = requests.post(
                "http://192.168.181.42/atx/api/v2/open/run?apiToken=shipping_4v4")  # 调用uwa的流水线，启动装包和启动游戏逻辑
        time.sleep(60 * 5)
        while True:
            self.auto.add_log("等待游戏启动")
            time.sleep(60)
            response = requests.post("http://192.168.181.52:11454/tools/auto/uwa_poco_devices",
                                     json={"type": "get", "project_id": 33, "version": "", "state": "",
                                           "ip": self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]})
            devices_info = response.json()
            if devices_info["success"]:
                devices_state = devices_info["data"]["devices_state"]
                if devices_state == "init":
                    self.auto.add_log("uwa的设备启动游戏了")
                    break

    def uwa_case_end(self):
        """
        自动化用例跑完了，发通知给uwa释放设备
        @return:
        """
        response = requests.post("http://192.168.181.52:11454/tools/auto/uwa_poco_devices",
                                 json={"type": "set", "project_id": 33, "version": "", "state": "end",
                                       "ip": self.auto.init_kwargs["task_info"]["device_info"]["device_ip"]})
        self.auto.add_log("通知uwa释放设备")

    def bag_quit(self):
        """
        退出背包
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnBac02"
        self.auto.auto_touch(name)

    def open_set(self):
        """
        打开设置
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnSetting"
        self.auto.auto_touch(name)

    def open_gm(self):
        """
        打开gm指令
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/GLoader/ContentBasics/Container/Container/BtnSwitch.3"
        self.auto.auto_touch(name)

    # def open_set_porcedure(self):
    #     """
    #     打开设置程序指令
    #     """
    #     name = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/GList/Container/Container/BtnSettingTab.9"
    #     self.auto.auto_touch(name)
    # def open_set_porcedure_offense_prop(self):
    #     """
    #     获取炸家进攻道具
    #     """
    #     name = "Stage/GRoot/(Full Screen) ID501|S501/UiSetting(UiSetting)/ContentPane/ComSettingPanel/GLoader.9/UiDebug/ComDebugPanel/ContentCheat/GList/Container/Container/ItemCheatList.17"
    #     self.auto.auto_touch(name)
    def click_bag_weapon(self):
        """
        背包武器栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.1"
        self.auto.auto_touch(name)

    def click_bag_ammunition(self):
        """
        背包弹药栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.2"
        self.auto.auto_touch(name)

    def click_bag_costume(self):
        """
        背包服饰栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.3"
        self.auto.auto_touch(name)

    def click_bag_consumables(self):
        """
        背包消耗品栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.4"
        self.auto.auto_touch(name)

    def click_bag_architecture(self):
        """
        背包建筑栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.5"
        self.auto.auto_touch(name)

    def click_bag_blueprint(self):
        """
        背包蓝图栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.6"
        self.auto.auto_touch(name)

    def click_bag_goods(self):
        """
        背包物品栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.7"
        self.auto.auto_touch(name)

    def click_bag_resource(self):
        """
        背包资源栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab.8"
        self.auto.auto_touch(name)

    def click_bag_tool(self):
        """
        背包工具栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1/Container/Container/ComInventoryMainTypeTab"
        self.auto.auto_touch(name)

    def click_bag_equipment(self):
        """
        背包装备栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/BtnInventoryToolTab01.1/Inventory_Container_btn_05"
        self.auto.auto_touch(name)

    def click_bag_equipment_1(self):
        """
        背包装备栏第一个枪械
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComWeaponItemIcon"
        self.auto.auto_touch(name)

    def click_bag_equipment_2(self):
        """
        背包装备栏第2个枪械
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComWeaponItemIcon.1"
        self.auto.auto_touch(name)

    def click_bag_equipment_skin(self):
        """
        背包装备栏第一个枪械皮肤
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ConTipsTitle/BtnSkin"
        self.auto.auto_touch(name)

    def click_bag_equipment_skin_return(self):
        """
        背包装备栏枪械皮肤返回
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiSelectSkin(UiSelectSkin)/ContentPane/btnBack"
        self.auto.auto_touch(name)

    def click_bag_equipment_discharge(self):
        """
        背包装备栏卸下1装备
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/Container/Container/23"
        self.auto.auto_touch(name)

    def click_bag_equipment_discharge_2(self):
        """
        背包装备栏卸下弹药
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/Container/Container/7"
        self.auto.auto_touch(name)

    def click_bag_add_on(self):
        """
        背包附加物品栏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/BtnInventoryToolTab01"
        self.auto.auto_touch(name)

    def swipe_bag_type_down(self):
        """
        背包综合栏向下滑动
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList.1",
            swipe_value=["down", 5])
        self.auto.auto_sleep(1)

    def swipe_bag_fabricate_1_down(self):
        """
        背包制造常用页面向下滑动
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/GLoader/ComCraft/GList",
            swipe_value=["down", 1])
        self.auto.auto_sleep(1)

    def swipe_bag_fabricate_down(self):
        """
        背包制造栏向下滑动
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/GList.1",
            swipe_value=["down", 5])
        self.auto.auto_sleep(1)

    def click_bag_shortcut1(self):
        """
        背包快捷栏2
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.1/ComItemIcon"
        self.auto.auto_touch(name)

    def click_bag_weapon1(self):
        """
        背包武器1
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComWeaponItemIcon"
        self.auto.auto_touch(name)

    def click_bag_weapon2(self):
        """
        背包武器2
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComWeaponItemIcon.1"
        self.auto.auto_touch(name)

    def click_bag_weapon_Switch_bullet(self):
        """
        背包武器_切换子弹按钮
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ConTipsTitle/ComTipsAmmoInfo/BtnTipsAmmoChange"
        self.auto.auto_touch(name)

    def click_bag_weapon_Switch_bullet_1(self):
        """
        背包武器_切换子弹——第1种子弹
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiAmmoChange(UiAmmoChange)/ContentPane/ComAmmoChangeContent/GList/Container/Container/ComItemIcon"
        self.auto.auto_touch(name)

    def click_bag_weapon_Switch_bullet_2(self):
        """
        背包武器_切换子弹——第2种子弹
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiAmmoChange(UiAmmoChange)/ContentPane/ComAmmoChangeContent/GList/Container/Container/ComItemIcon.1"
        self.auto.auto_touch(name)

    def click_bag_weapon_demount(self):
        """
        背包武器_卸下武器
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/ComInventoryRoot/Container/Container/23"
        self.auto.auto_touch(name)

    def click_bag_weapon_equip(self):
        """
        背包武器_装备武器
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/ComInventoryRoot/Container/Container/22"
        self.auto.auto_touch(name)

    def click_bag_costume_equip(self):
        """
        背包武器_装备服饰
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/Container/Container/5"
        self.auto.auto_touch(name)

    def click_bag_shortcut2(self):
        """
        背包快捷栏3
        """
        name1 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.2/ComItemIcon"
        self.auto.auto_touch(name1)

    def click_bag_shortcut3(self):
        """
        背包快捷栏4
        """
        name2 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.3/ComItemIcon"
        self.auto.auto_touch(name2)

    def click_bag_shortcut4(self):
        """
        背包快捷栏5
        """
        name4 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.4/ComItemIcon"
        self.auto.auto_touch(name4)

    def click_bag_shortcut5(self):
        """
        背包快捷栏6
        """
        name5 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.5/ComItemIcon"
        self.auto.auto_touch(name5)

    def click_bag_shortcut(self):
        """
        背包快捷栏1
        """
        name5 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name5)

    def click_bag_shortcut5(self):
        """
        背包快捷栏5
        """
        name5 = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryShortcuts/GList/Container/ComItemIconLoader.5/ComItemIcon"
        self.auto.auto_touch(name5)

    def click_bag_shortcut_discard(self):
        """
        背包——快捷栏——丢弃
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovableGList/Container/Container/11"
        self.auto.auto_touch(name)

    def click_bag_shortcut_takeout(self):
        """
        背包——快捷栏——取出快捷键
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovableGList/Container/Container/25"
        self.auto.auto_touch(name)

    def click_bag_shortcut_split(self):
        """
        背包——快捷栏——拆分
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovableGList/Container/Container/10"
        self.auto.auto_touch(name)

    def click_bag_shortcut_splitdiscard(self):
        """
        背包——快捷栏——拆分丢弃
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovableGList/Container/Container/12"
        self.auto.auto_touch(name)

    def click_bag_shortcut_split_add(self):
        """
        背包——快捷栏——拆分_加号
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemSplit(UiItemSplit)/ContentPane/ComPopSplit/BtnPopupNum.1"
        self.auto.auto_touch(name)

    def click_bag_shortcut_split_reduce(self):
        """
        背包——快捷栏——拆分_减号
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemSplit(UiItemSplit)/ContentPane/ComPopSplit/BtnPopupNum"
        self.auto.auto_touch(name)

    def click_bag_shortcut_split_confirm(self):
        """
        背包——快捷栏——拆分_拆分
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemSplit(UiItemSplit)/ContentPane/ComPopSplit/BtnPopupSplit"
        self.auto.auto_touch(name)

    def click_bag_shortcut_split_confirm2(self):
        """
        背包——快捷栏——拆分_部分丢弃
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemSplit(UiItemSplit)/ContentPane/ComPopSplit/BtnPopupSplit.2"
        self.auto.auto_touch(name)

    def click_bag_tomake_add(self):
        """
        背包制造——工具制作数量——加号
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/GLoader/ComCraft/ComCraftInfo/BtnCraftNum.1"
        self.auto.auto_touch(name)

    def click_bag_tomake_make(self):
        """
        背包制造——工具制作数量——立即制作
        """

        name = "Stage/GRoot/(Full Screen) ID501|S501/UiCraft(UiCraft)/ContentPane/ComCraftRoot/ComCraft/ComCraftInfo/BtnCraftStart"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue1(self):
        """
        背包制造——常用
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue2(self):
        """
        背包制造——收藏
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.1"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue3(self):
        """
        背包制造——工具
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.2"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue4(self):
        """
        背包制造——武器
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.3"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue5(self):
        """
        背包制造——弹药
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.4"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue6(self):
        """
        背包制造——服饰
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.5"
        self.auto.auto_touch(name)

    def click_bag_tomake_catalogue7(self):
        """
        背包制造——建筑
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/GLoader/ComCraft/GList/Container/Container/BtnCraftType.6"
        self.auto.auto_touch(name)

    def swipe_bag_down(self):
        """
        背包向下滑动
        """
        self.auto.auto_swipe(
            "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList",
            swipe_value=["down", 5])
        self.auto.auto_sleep(1)

    def bag_prop(self, resource_id):
        """
        触发背包中道具
        """
        index, is_have = self.find_item_index(resource_id, "bag")
        if is_have:
            print(index)
        num = index
        row = num // 3
        column = num % 3
        print(row, column)
        if num > 11:
            self.swipe_bag_down()
        if num <= 11:
            row = num // 3
            column = num % 3
            print(row, column)
            if row == 0 and column == 0:
                name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                print(name)
                self.auto.auto_touch(name)
                if column != 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.{column}"
                    # final_path = name + f".{column}"
                    print(name)
                    self.auto.auto_touch(name)
            else:
                if row > 0 and column == 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                    print(name)
                    self.auto.auto_touch(name)
                else:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                    print(name)
                    self.auto.auto_touch(name, is_include=False)
        if num > 11 and num <= 20:
            row = num // 3 - 1
            column = num % 3
            print(row, column)
            if row == 0 and column == 0:
                name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                print(name)
                self.auto.auto_touch(name)
                if column != 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.{column}"
                    # final_path = name + f".{column}"
                    print(name)
                    self.auto.auto_touch(name)
            else:
                if row > 0 and column == 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                    print(name)
                    self.auto.auto_touch(name)
                else:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                    print(name)
                    self.auto.auto_touch(name, is_include=False)
        if num > 20 and num <= 29:
            row = num // 3 - 7
            column = num % 3
            print(row, column)
            if row == 0 and column == 0:
                name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                print(name)
                self.auto.auto_touch(name)
                if column != 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.{column}"
                    # final_path = name + f".{column}"
                    print(name)
                    self.auto.auto_touch(name)
            else:
                if row > 0 and column == 0:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                    print(name)
                    self.auto.auto_touch(name)
                else:
                    name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                    print(name)
                    self.auto.auto_touch(name, is_include=False)

    def bag_click_every(self, get_type):
        """
        遍历触发背包中道具，遍历前先整理背包
        @param get_type:bag 背包
        @return:
        """
        self.tidy_bag()
        if get_type in ["bag"]:
            result_list = self.get_user_item_all(get_type)
            # print(result_list)
            eight_digit_items = [item for item in result_list if isinstance(item, int) and len(str(item)) == 8]
            print(eight_digit_items)
            for i in range(len(eight_digit_items)):
                print(i)
                num = i
                if num <= 11:
                    row = num // 3
                    column = num % 3
                    print(row, column)
                if num == 11:
                    self.swipe_bag_down()
                if num > 11 and num <= 20:
                    row = num // 3 - 1
                    column = num % 3
                    print(row, column)
                    if row == 0 and column == 0:
                        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                        print(name)
                        self.auto.auto_touch(name)
                    else:
                        if row == 0 and column != 1:
                            name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                            final_path = name + f".{column}"
                            print(name)
                            self.auto.auto_touch(final_path)
                        else:
                            if row > 0 and column == 0:
                                name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                                print(name)
                                self.auto.auto_touch(name)
                            else:
                                name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                                print(name)
                                self.auto.auto_touch(name, is_include=False)
                if num > 20 and num <= 29:
                    row = num // 3 - 7
                    column = num % 3
                    print(row, column)
                    if row == 0 and column == 0:
                        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                        print(name)
                        self.auto.auto_touch(name)
                    else:
                        if row == 0 and column != 1:
                            name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
                            final_path = name + f".{column}"
                            print(name)
                            self.auto.auto_touch(final_path)
                        else:
                            if row > 0 and column == 0:
                                name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon"
                                print(name)
                                self.auto.auto_touch(name)
                            else:
                                name = f"Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.{row}/Container/GList/Container/ComItemIcon.{column}"
                                print(name)
                                self.auto.auto_touch(name, is_include=False)

    def build_quit(self):
        """
        建筑退出
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.36/ElemEndBuild"
        self.auto.auto_touch(name)

    def open_wood_cabinet(self):
        """
        打开木制储物柜按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn"
        self.auto.auto_touch(name)

    def open_cabinet_click_storage(self):
        """
        储物柜一键存入按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryOthersideToolBar/BtnOthersideOrganize"
        self.auto.auto_touch(name)

    def open_cabinet_click_2(self):
        """
        储物柜批量丢弃按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryOthersideToolBar/BtnOthersideOrganize.1"
        self.auto.auto_touch(name)

    def open_cabinet_click_3(self):
        """
        储物柜批量转移按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryOthersideToolBar/BtnOthersideOrganize.2"
        self.auto.auto_touch(name)

    def open_cabinet_click_4(self):
        """
        储物柜批量一键取出按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryOthersideToolBar/BtnOthersideOrganize.3"
        self.auto.auto_touch(name)

    def open_cabinet_click_5(self):
        """
        储物柜整理按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryOthersideToolBar/BtnOthersideOrganize.4"
        self.auto.auto_touch(name)

    def bag_equip_costume1(self):
        """
        装备栏服饰1按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComInventoryWearNew/ComInventoryToolWearIcon/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name)

    def bag_equip_costume2(self):
        """
        装备栏服饰2按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComInventoryWearNew/ComInventoryToolWearIcon.1/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name)

    def bag_equip_costume3(self):
        """
        装备栏服饰3按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComInventoryWearNew/ComInventoryToolWearIcon.2/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name)

    def bag_equip_costume4(self):
        """
        装备栏服饰4按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryToolsNew/ComInventoryEquipment/ComInventoryWearNew/ComInventoryToolWearIcon.3/ComItemIconLoader/ComItemIcon"
        self.auto.auto_touch(name)

    def bag_equip_costume_demount(self):
        """
        装备栏卸下服饰按钮
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiItemTips(UiItemTips)/ContentPane/ComTipsMain/ComTipsMovable/GList/Container/Container/9"
        self.auto.auto_touch(name)

    def main_interface_Shortcut_bar2(self):
        """
        主界面快捷栏2按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemShortcutsNew/GList/Container/ComBeltIcon.1/ComItemIcon"
        self.auto.auto_touch(name)

    def main_interface_Shortcut_bar4(self):
        """
        主界面快捷栏4按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemShortcutsNew/GList/Container/ComBeltIcon.3/ComItemIcon"
        self.auto.auto_touch(name)

    def main_interface_Shortcut_bar5(self):
        """
        主界面快捷栏4按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemShortcutsNew/GList/Container/ComBeltIcon.4/ComItemIcon"
        self.auto.auto_touch(name)

    def Shortcut_bar_bulid(self):
        """
        主界面快捷栏道具建造按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.22/ElemBtnBuildOK/btnProcessPart"
        self.auto.auto_touch(name)

    def Shortcut_bar_bulid_quit(self):
        """
        主界面快捷栏道具建造_取消按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHud(UiHudMain)/ContentPane/UiHudElems/GLoader.21/ElemCommonBtn2"
        self.auto.auto_touch(name)

    def bag_Clothing_panel_1(self):
        """
        背包服饰栏第一格
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon"
        self.auto.auto_touch(name)

    def bag_Clothing_panel_2(self):
        """
        背包服饰栏第2格
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.1"
        self.auto.auto_touch(name)

    def bag_Clothing_panel_3(self):
        """
        背包服饰栏第3格
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow/Container/GList/Container/ComItemIcon.2"
        self.auto.auto_touch(name)

    def bag_Clothing_panel_4(self):

        """
        背包服饰栏第4格
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComInventoryMainNew/GList/Container/Container/ComInventoryMainRow.1/Container/GList/Container/ComItemIcon"
        self.auto.auto_touch(name)

    def nothing_to_build(self, entity_id):
        """
        没什么用的摆件的判断，比如非陷阱类的防御工事
        """
        hp = self.get_entity_hp_by_id(entity_id)
        if hp:
            return True
        return False

    def open_publishteam(self):
        """
        打开招募界面
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyMain(UiLobbyMain)/ContentPane/ComLobbyMainRoot/BtnRecruit"
        self.auto.auto_touch(name)

    def quick_join(self):
        """
        点击快速加入按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiRecruit(UiRecruit)/ContentPane/BtnQuickJoin"
        self.auto.auto_touch(name)

    def open_team_recall(self):
        """
        打开队伍界面的招募
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiLobbyTeam(UiLobbyTeam)/ContentPane/BtnRecruit"
        self.auto.auto_touch(name)

    def close_team_recall(self):
        """
        关闭队伍界面的招募
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiRecruit(UiRecruit)/ContentPane/BtnClose"
        self.auto.auto_touch(name)

    def open_team_chat(self):
        """
        打开队伍界面的聊天
        """
        name = 'Stage/GRoot/(Full Screen) ID501|S501/UiLobbyTeam(UiLobbyTeam)/ContentPane/ComLobbyChat/BtnChat'
        self.auto.auto_touch(name)

    def close_team_chat(self):
        """
        关闭队伍界面的聊天
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiChatLobby(UiChat)/ContentPane/Back"
        self.auto.auto_touch(name)

    def close_car_maintain(self):
        """
        关闭载具维修界面
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/BtnClose"
        self.auto.auto_touch(name)

    def open_horse_bag(self):
        """
        马背包装备栏2
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComVehicleRolling/Container/Container/GList/Container/ComAddResArea2/GList/Container/ComAddResource2.1/BtnAddResource"
        self.auto.auto_touch(name)

    def open_horse_horsebag(self):
        """
        打开马背包
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComVehicleRolling/Container/Container/GList/Container/ComAddResArea2.1/GList/Container/ComAddResource2/BtnAddResource"
        self.auto.auto_touch(name)

    def equip_horse_weapon(self):
        """
        打开马背包后装备栏装备按钮
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiOtherSide(UiOtherSide)/ContentPane/AnchorComOtherSideVehicle/ComOtherSideVehicle/ComHandlePanel2/BtnHandle2"
        self.auto.auto_touch(name)

    def open_horse_horsebag_All_in(self):
        """
        马背包一键存入
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/ComLazyLoader.2/GLoader/ComInventoryOthersideToolBar/BtnOthersideOrganize"
        self.auto.auto_touch(name)

    def quit_horse_horsebag(self):
        """
        退出马背包
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiInventory(UiInventory)/ContentPane/ComInventoryRoot/BtnBac02"
        self.auto.auto_touch(name)

    def fly_to_pos(self, x, y, z, run_num=2, distance_limiting=10, is_up=True, is_down=True):
        """
        使用move_to飞行至目标点
        """
        self.open_fly()
        if is_up:
            for i in range(5):
                self.up()
        self.move_to_pos(x, y, z, run_num, distance_limiting, is_fly=True, transfer_help=True)
        if is_down:
            self.close_fly()
            time.sleep(10)

    def gm_fly_to_pos(self, x, y, z, speed, speed_v2=0, is_close_fly=True):
        """
        使用gm飞行至目标点
        speed一段速度，speed_v2为主体飞行结束后，进行精确飞行，为0则不进行精确飞行
        is_close_fly 飞行结束后默认关闭飞行
        """
        self.open_fly()
        result_data, result = self.get_sky_tools(rpc_name="move_collimation",
                                                 get_value={"x": x, "y": y, "z": z, }, get_type="", add_log=False)
        print("计算方位和距离", result_data)
        if result:
            pitch = result_data["pitch"]
            yaw = result_data["yaw"]
            self.set_role_yaw(yaw)
            self.gm_rpc("set", [x, y, z, speed], "TestFlyToPos")
        while True:
            time.sleep(5)
            pos, is_get = self.get_camera(False)
            distance = self.distance(pos['position'], {"x": x, "y": y, "z": z})
            if distance <= speed:
                break
        if speed_v2 != 0:
            result_data, result = self.get_sky_tools(rpc_name="move_collimation",
                                                     get_value={"x": x, "y": y, "z": z, }, get_type="", add_log=False)
            print("计算方位和距离", result_data)
            if result:
                pitch = result_data["pitch"]
                yaw = result_data["yaw"]
                self.set_role_yaw(yaw)
                self.gm_rpc("set", [x, y, z, speed_v2], "TestFlyToPos")
                while True:
                    time.sleep(5)
                    pos, is_get = self.get_camera(False)
                    distance = self.distance(pos['position'], {"x": x, "y": y, "z": z})
                    if distance <= speed_v2:
                        break
        if is_close_fly:
            self.close_fly()
            time.sleep(2)

    def give_up(self):
        """
        放弃自救
        """
        try:
            name = "Stage/GRoot/(GamePlayOverlay) ID301|S301/UiDying(UiDying)/ContentPane/TextBtn"
            self.auto.auto_touch(name)
        except Exception as e:
            pass
        time.sleep(1)
        try:
            name2 = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
            self.auto.auto_touch(name2)
        except Exception as e:
            pass

    def open_survival_manual(self):
        """
        打开生存手册
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemEntryGroup/BtnManual"
        self.auto.auto_touch(name)

    def survival_manual(self):
        """
        打开生存手册全部分支
        """
        for i in range(5):
            if i == 0:
                name = "Stage/GRoot/(Full Screen) ID501|S501/UiSurvivalManual(UiSurvivalManual)/ContentPane/CommonTab/GList/Container/Container/BtnTab"
                self.auto.auto_touch(name)
            else:
                name = f"Stage/GRoot/(Full Screen) ID501|S501/UiSurvivalManual(UiSurvivalManual)/ContentPane/CommonTab/GList/Container/Container/BtnTab.{i}"
                self.auto.auto_touch(name)
            time.sleep(2)

    def quit_survival_manual(self):
        """
        退出生存手册
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiSurvivalManual(UiSurvivalManual)/ContentPane/CommonTab/BtnBack"
        self.auto.auto_touch(name)

    def open_surprised(self):
        """
        进入惊喜玩法或商店按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn"
        self.auto.auto_touch(name)

    def quit_surprised(self):
        """
        退出惊喜玩法
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiSurprisePlay(UiSurprisePlay)/ContentPane/BtnClose"
        self.auto.auto_touch(name)

    def quit_shop(self):
        """
        退出商店
        """
        name = "Stage/GRoot/(Full Screen) ID501|S501/UiShop(UiShop)/ContentPane/BackBtn(1)"
        self.auto.auto_touch(name)

    def click_weapon(self):
        """
        武器1
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemWeapons/ComWeaponHudIcon"
        self.auto.auto_touch(name)

    def get_weapon_condition(self, index):
        '''
        获取指定栏位武器的耐久度
        '''
        dict_data = self.get_user_entity()
        condition, max_condition = 0, 0
        for key, value in dict_data.items():
            OwnerEntityId = value.get("OwnerEntityId")
            if value.get('Position') == index:
                condition = value.get('Condition')
                max_condition = value.get('MaxCondition')
        return condition, max_condition

    def click_make(self):
        """
        制造按钮
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/BtnCraft"
        self.auto.auto_touch(name)

    def click_resurgence(self):
        """
        复活后弹窗确定
        """
        name = "Stage/GRoot/(Popup) ID601|S601/UiMsgBox(UiMsgBox)/ContentPane/ComPopMsgBox/GList/Container/Container/BtnPopupBtn"
        self.auto.auto_touch(name)

    def push_car(self):
        """
        推动载具
        """
        name = "Stage/GRoot/(HUD) ID201|S201/UiHud(UiHudMain)/ContentPane/UiHudElems/ElemInteractiveList/ComInteractiveList/GList/Container/Container/ComInteractiveBtn.3"
        self.auto.auto_touch(name)

