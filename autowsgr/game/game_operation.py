import time

from autowsgr.constants.custom_exceptions import ImageNotFoundErr
from autowsgr.constants.image_templates import IMG
from autowsgr.constants.positions import BLOOD_BAR_POSITION
from autowsgr.controller.run_timer import Timer, try_to_get_expedition
from autowsgr.game.get_game_info import check_support_stats, detect_ship_stats
from autowsgr.ocr.ocr import recognize_get_ship
from autowsgr.ocr.ship_name import recognize_ship
from autowsgr.utils.api_image import absolute_to_relative


class Expedition:
    def __init__(self, timer: Timer) -> None:
        self.timer = timer
        self.is_ready = False
        self.last_check = time.time()

    def update(self, force=False):
        self.timer.update_screen()
        if (isinstance(self.timer.now_page, str) and "unknow" in self.timer.now_page) or self.timer.now_page.name not in [
            "expedition_page",
            "map_page",
            "battle_page",
            "exercise_page",
            "decisive_battle_entrance",
        ]:
            if force or time.time() - self.last_check > 1800:
                self.timer.goto_game_page("main_page")
            if self.timer.now_page.name == "main_page":
                self.is_ready = self.timer.check_pixel((933, 454), bgr_color=(45, 89, 255))
        else:
            self.is_ready = self.timer.check_pixel((464, 11), bgr_color=(45, 89, 255))

    def run(self, force=False):
        """检查远征, 如果有未收获远征, 则全部收获并用原队伍继续

        Args:
            force (bool): 是否强制检查
        Returns:
            bool: 是否进行了远征操作
        """
        self.update(force=force)
        if self.is_ready:
            self.timer.goto_game_page("expedition_page")
            flag = try_to_get_expedition(self.timer)
            self.timer.last_expedition_check_time = time.time()


def get_ship(timer: Timer, max_times=1):
    """获取掉落舰船"""
    # TODO: 返回舰船名称
    timer.got_ship_num += 1
    while timer.wait_image([IMG.symbol_image[8]] + [IMG.symbol_image[13]], timeout=1):
        try:
            ship_name, ship_type = recognize_get_ship(timer.screen, timer.ship_names)
        except:
            ship_name, ship_type = "识别失败", "识别失败"
        timer.Android.click(915, 515, delay=0.25, times=1)
        timer.ConfirmOperation()
    timer.logger.info(f"获取舰船: {ship_name} {ship_type}")
    return ship_name, ship_type


def match_night(timer: Timer, is_night):
    """匹配夜战按钮并点击"""
    timer.wait_image(IMG.fight_image[6])
    while timer.wait_image(IMG.fight_image[6], timeout=0.5):
        if is_night:
            timer.Android.click(325, 350, delay=0.5, times=1)
        else:
            timer.Android.click(615, 350, delay=0.5, times=1)


def click_result(timer: Timer, max_times=1):
    """点击加速两页战果界面"""
    timer.wait_images(IMG.fight_image[14])
    while timer.wait_image(IMG.fight_image[14], timeout=0.5):
        timer.Android.click(915, 515, delay=0.25, times=1)


def DestroyShip(timer: Timer):
    """解装舰船，目前仅支持：全部解装+保留装备"""

    if not timer.identify_page("destroy_page"):
        timer.goto_game_page("destroy_page")
    timer.set_page("destroy_page")

    timer.Android.click(90, 206, delay=1.5)  # 点添加
    timer.Android.relative_click(0.91 - 0.5, 0.3 - 0.5, delay=1.5)  # 快速选择
    timer.Android.relative_click(0.915 - 0.5, 0.906 - 0.5, delay=1.5)  # 确定
    timer.Android.relative_click(0.837 - 0.5, 0.646 - 0.5, delay=1.5)  # 卸下装备
    timer.Android.relative_click(0.9 - 0.5, 0.9 - 0.5, delay=1.5)  # 解装
    timer.Android.relative_click(0.38 - 0.5, 0.567 - 0.5, delay=1.5)  # 四星确认


def verify_team(timer: Timer):
    """检验目前是哪一个队伍(1~4)
    含网络状况处理
    Args:
        timer (Timer): _description_

    Raises:
        ImageNotFoundErr: 未找到队伍标志
        ImageNotFoundErr: 不在相关界面

    Returns:
        int: 队伍编号(1~4)
    """
    if timer.identify_page("fight_prepare_page") == False:
        raise ImageNotFoundErr("not on fight_prepare_page")

    for _ in range(5):
        for i, position in enumerate([(64, 83), (186, 83), (310, 83), (430, 83)]):
            if timer.check_pixel(position, bgr_color=(228, 132, 16)):
                return i + 1
        time.sleep(0.2)
        timer.update_screen()

    if timer.process_bad_network():
        return verify_team(timer)

    timer.log_screen()
    raise ImageNotFoundErr()


def MoveTeam(timer: Timer, target, try_times=0):
    """切换队伍
    Args:
        timer (Timer): _description_
        target (_type_): 目标队伍
        try_times: 尝试次数
    Raise:
        ValueError: 切换失败
        ImageNotFoundErr: 不在相关界面
    """
    if try_times > 3:
        raise ValueError("can't change team")

    if timer.identify_page("fight_prepare_page") == False:
        timer.log_screen()
        raise ImageNotFoundErr("not on 'fight_prepare_page' ")

    if verify_team(timer) == target:
        return
    timer.logger.info("正在切换队伍到:" + str(target))
    timer.Android.click(110 * target, 81)
    if verify_team(timer) != target:
        MoveTeam(timer, target, try_times + 1)


def SetSupport(timer: Timer, target, try_times=0):
    """启用战役支援
    Args:
        timer (Timer): _description_
        target (bool, int): 目标状态
    Raise:
        ValueError: 未能成功切换战役支援状态
    """
    target = bool(target)
    timer.goto_game_page("fight_prepare_page")

    if check_support_stats(timer) != target:
        timer.Android.click(628, 82, delay=1)
        timer.Android.click(760, 273, delay=1)
        timer.Android.click(480, 270, delay=1)
        timer.logger.info("开启支援状态成功")

    if timer.is_bad_network(0) or check_support_stats(timer) != target:
        if timer.process_bad_network("set_support"):
            SetSupport(timer, target)
        else:
            raise ValueError("can't set right support")


def quick_repair(timer: Timer, repair_mode=2, ship_stats=None, *args, **kwargs):
    """战斗界面的快速修理
    Args:
        timer (Timer): _description_
        repair_mode:
            1: 快修，修中破
            2: 快修，修大破
    """
    arg = repair_mode
    try:
        if ship_stats == None:
            ship_stats = detect_ship_stats(timer)
        if not any(x in ship_stats for x in [0, 1, 2]):
            time.sleep(1)
            ship_stats = detect_ship_stats(timer)
        if not any(x in ship_stats for x in [0, 1, 2]):
            timer.logger.warning("执行修理操作时没有成功检测到舰船")

        assert type(repair_mode) in [int, list, tuple]
        if type(repair_mode) == int:  # 指定所有统一修理方案
            repair_mode = [repair_mode for _ in range(6)]

        assert len(repair_mode) == 6
        need_repair = [False for _ in range(6)]
        for i, x in enumerate(repair_mode):
            assert x in [1, 2]
            if x == 1:
                need_repair[i] = ship_stats[i + 1] not in [-1, 0]
            elif x == 2:
                need_repair[i] = ship_stats[i + 1] not in [-1, 0, 1]

        if timer.config.DEBUG:
            timer.logger.debug("ship_stats:", ship_stats)
        if any(need_repair) or timer.image_exist(IMG.repair_image[1]):
            timer.Android.click(420, 420, times=2, delay=0.8)  # 进入修理页面
            # 快修已经开始泡澡的船
            pos = timer.get_image_position(IMG.repair_image[1])
            while pos != None:
                timer.Android.click(pos[0], pos[1], delay=1)
                pos = timer.get_image_position(IMG.repair_image[1])
            # 按逻辑修理
            for i in range(1, 7):
                if need_repair[i - 1]:
                    timer.logger.info("WorkInfo:" + str(kwargs))
                    timer.logger.info(str(i) + " Repaired")
                    timer.quick_repaired_cost += 1
                    timer.Android.click(
                        BLOOD_BAR_POSITION[0][i][0],
                        BLOOD_BAR_POSITION[0][i][1],
                        delay=1.5,
                    )
    except AssertionError:
        raise ValueError(f"修理舰船的参数不合法, 请检查你的参数:{arg}")


def get_rewards(timer: Timer):
    """检查任务情况,如果可以领取奖励则领取"""
    timer.goto_game_page("main_page")
    if not timer.check_pixel((694, 457), bgr_color=(45, 89, 255)):
        return "no"
    timer.goto_game_page("mission_page")
    timer.goto_game_page("mission_page")
    if timer.click_image(IMG.game_ui[15]):
        timer.ConfirmOperation(must_confirm=1, timeout=5)
        return "ok"
    elif timer.click_image(IMG.game_ui[12]):
        timer.ConfirmOperation(must_confirm=1)
        return "ok"
    return "no"
    # timer.Android.click(774, 502)


def RepairByBath(timer: Timer):
    """使用浴室修理修理时间最长的单位
    Args:
        timer (Timer): _description_
    """
    timer.goto_game_page("choose_repair_page")
    timer.Android.click(115, 233)
    if not timer.identify_page("choose_repair_page"):
        if timer.identify_page("bath_page"):
            timer.set_page("bath_page")
        else:
            timer.set_page()


def SetAutoSupply(timer: Timer, type=1):
    timer.update_screen()
    NowType = int(timer.check_pixel((48, 508), (224, 135, 35)))
    if NowType != type:
        timer.Android.click(44, 503, delay=0.33)


def Supply(timer: Timer, ship_ids=[1, 2, 3, 4, 5, 6], try_times=0):
    """补给指定舰船

    Args:
        timer (Timer): _description_
        ship_ids (list, optional): 补给舰船列表, 可以为单个整数表示单艘舰船. Defaults to [1, 2, 3, 4, 5, 6].

    Raises:
        ValueError: 补给失败
        TypeError: ship_ids 参数有误
    """
    if try_times > 3:
        raise ValueError("can't supply ship")

    if isinstance(ship_ids, int):
        ship_ids = [ship_ids]

    timer.Android.click(293, 420)
    for x in ship_ids:
        if not isinstance(x, int):
            raise TypeError("ship must be represent as a int but get" + str(ship_ids))
        timer.Android.click(110 * x, 241)

    if timer.is_bad_network(0):
        timer.process_bad_network("supply ships")
        Supply(timer, ship_ids, try_times + 1)


def ChangeShip(timer: Timer, fleet_id, ship_id=None, name=None, pre=None, ship_stats=None):
    """切换舰船(不支持第一舰队)"""
    if fleet_id is not None:
        timer.goto_game_page("fight_prepare_page")
        MoveTeam(timer, fleet_id)
        if fleet_id >= 5:
            # 切换为预设编队
            # 暂不支持
            return

    # 切换单船
    if ship_stats is None:
        ship_stats = detect_ship_stats(timer)
    if name is None and ship_stats[ship_id] == -1:
        return
    timer.Android.click(110 * ship_id, 250, delay=0)
    res = timer.wait_images([IMG.choose_ship_image[1], IMG.choose_ship_image[2]], after_get_delay=0.4, gap=0)
    if res == 1:
        timer.Android.click(839, 113)

    if name is None:
        timer.Android.click(83, 167, delay=0)
        timer.wait_pages("fight_prepare_page", gap=0)
        return

    timer.Android.click(700, 30, delay=0)
    timer.wait_image(IMG.choose_ship_image[3], gap=0, after_get_delay=0.1)

    timer.Android.text(name)
    timer.Android.click(50, 50, delay=0.5)
    time.sleep(0.5)
    # OCR识别舰船
    if not name in timer.ship_names:
        timer.ship_names.append(name)
    ship_info = recognize_ship(timer.get_screen()[:, :1048], timer.ship_names)

    # 查找识别结果中要选的舰船
    found_ship = next((ship for ship in ship_info if ship[0] == name), None)
    # 点击舰船
    if found_ship is None:
        timer.logger.error(f"Can't find ship {name},ocr result:{ship_info}")
        # raise ValueError(f"Can't find ship {name}")
        timer.logger.debug("Try to click the first ship")
        if ship_stats[ship_id] == -1:
            timer.Android.click(83, 167, delay=0)
        else:
            timer.Android.click(183, 167, delay=0)
    else:
        center = ((found_ship[1][0][0] + found_ship[1][1][0]) / 2, (found_ship[1][0][1] + found_ship[1][2][1]) / 2)
        rel_center = absolute_to_relative(center, timer.Android.resolution)
        timer.Android.relative_click(*rel_center)

    timer.wait_pages("fight_prepare_page", gap=0)


def ChangeShips(timer: Timer, fleet_id, ship_names):
    """更换编队舰船

    Args:
        fleet_id (int): 2~4,表示舰队编号

        ship_names (舰船名称列表):

    For example:
        ChangeShips(timer, 2, [None, "萤火虫", "伏尔塔", "吹雪", "明斯克", None, None])

    """
    timer.logger.info(f"Change Fleet {fleet_id} to {ship_names}")
    if fleet_id is not None:
        timer.goto_game_page("fight_prepare_page")
        MoveTeam(timer, fleet_id)
    if fleet_id == 1:
        raise ValueError("change member of fleet 1 is unsupported")
    ship_stats = detect_ship_stats(timer)
    for i in range(1, 7):
        if ship_stats[i] != -1:
            ChangeShip(timer, fleet_id, 1, None, ship_stats=ship_stats)
    ship_names = ship_names + [None] * 6
    for i in range(len(ship_names)):
        if ship_names[i] == "":
            ship_names[i] = None
    time.sleep(0.3)
    ship_stats = detect_ship_stats(timer)
    for i in range(1, 7):
        ChangeShip(timer, fleet_id, i, ship_names[i], ship_stats=ship_stats)


def get_new_things(timer: Timer, lock=0):
    pass


def cook(timer: Timer, position: int):
    """食堂做菜
    Args:
        position (int): 第几个菜谱
    """
    if position < 1 or position > 3:
        raise ValueError(f"不支持的菜谱编号:{position}")
    POSITION = [None, (318, 276), (420, 140), (556, 217)]
    timer.goto_game_page("canteen_page")
    timer.Android.click(*POSITION[position])
    try:
        timer.click_image(IMG.restaurant_image[1], timeout=7.5, must_click=True)
        timer.logger.info("做菜成功")
        return True
    except:
        timer.logger.error(f"不支持的菜谱编号:{position}, 请检查该菜谱是否有效, 或者检查今日用餐次数是否已经用尽")
        return False
