# -*- coding: utf-8 -*-
"""男性摄影-提示词自选搭配

女性版「权威摄影」的同框架兄弟节点：
    同一套 92 项字段 / 三层密度 / 确定性随机种子 / 中英双语输出 / 模块分段排版，
    但词库整份换成男性人像（脸型·眉鼻唇·胡须·肌肉·男装·男性姿态·男性写真主题）。

数据全部放在 data/male/*.json：
    fields[字段名] = {module, lv, options:[{l 显示值, z 中文片段, e 英文片段, b 精简片段}]}
    lv = 1 核心 / 2 标准 / 3 细节     —— 决定「提示词密度」时这个字段要不要出现
"""

import json
import logging
import random
import re
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parent / "data" / "male"

FOLLOW_PRESET = "跟随预设"
RANDOM_CHOICE = "随机抽取"
EMPTY_CHOICE = "不使用"
CUSTOM_PRESET = "自定义组合"
MAX_SEED = 0xFFFFFFFFFFFFFFFF

PROMPT_DENSITIES = ["精简", "标准", "详细"]
RANDOM_SCOPES = [
    "局部微调（动作、表情、色彩、质感）",
    "同主题重拍（保留主题和人物）",
    "跨风格混搭（全部字段）",
]
PROMPT_JOIN_POSITIONS = ["自由提示词在前", "结构化模块在前"]
LAYOUT_OPTIONS = ["按模块分段", "连续拼接"]

# ---------------------------------------------------------------- 字段骨架
MODULES = [
    ("主题", ["画面比例", "成像媒介", "写真大类", "写真主题", "年龄阶段",
              "族裔大类", "地域族裔分支", "气质类型", "场合氛围"]),
    ("人物", ["脸型", "轮廓细节", "眉形", "眼型", "瞳色", "眼睑特征", "鼻型",
              "唇形", "胡须", "肤色", "肤质", "体毛", "刺青", "基础身形",
              "身量观感", "肌肉线条", "肩背体态", "手部特征"]),
    ("发型", ["发色模式", "发色", "发色色调", "染色方式", "头发长度",
              "发质与卷度", "发型造型", "额前处理", "头部配饰"]),
    ("服装", ["穿搭结构", "外套类型", "外套颜色", "外套材质", "外套图案",
              "内搭类型", "内搭颜色", "内搭材质", "裤装类型", "裤装颜色",
              "裤装材质", "版型细节", "袜装", "鞋履", "服装配件", "腕表配饰"]),
    ("姿态", ["画面瞬间", "基础姿态", "身体方向", "身体重心", "肩颈状态",
              "手部动作", "腿部动作", "头部方向", "视线", "表情"]),
    ("场景", ["场景大类", "场景地点", "时间切片", "天气状态", "前景框景",
              "背景环境", "环境细节", "空间材质", "空间层次"]),
    ("光影", ["主光来源", "光线方向", "光线质地", "照明落点", "阴影表现",
              "主配色", "色温倾向", "画面对比"]),
    ("镜头", ["景别", "画面布局", "等效焦段", "拍摄距离", "机位", "景深", "对焦位置"]),
    ("收尾", ["影像风格", "细节质地", "高光处理", "颗粒质感", "画面情绪", "后期调色"]),
]
FIELD_ORDER = [name for _m, names in MODULES for name in names]
MODULE_OF = {name: mod for mod, names in MODULES for name in names}

# 只做分类、不进正文的字段
CONTROL_ONLY = {"场景大类", "族裔大类", "发色模式"}

ASPECT_RESOLUTIONS = {
    "2:3竖构图": (832, 1248), "3:4竖构图": (768, 1024), "4:5竖构图": (896, 1120),
    "9:16竖构图": (720, 1280), "9:21竖构图": (576, 1344), "1:1方形构图": (1024, 1024),
    "3:2横构图": (1248, 832), "4:3横构图": (1024, 768), "5:4横构图": (1120, 896),
    "16:9横构图": (1280, 720), "21:9横构图": (1344, 576),
}
PIXEL_BUDGET_MODE = "固定比例总像素"
RESOLUTION_INPUTS = {
    "分辨率模式": (
        ["原推荐尺寸", "按总像素计算", PIXEL_BUDGET_MODE],
        {"default": PIXEL_BUDGET_MODE,
         "tooltip": "默认保持画面比例并接近目标总像素；已有工作流保留保存的尺寸计算方式。"},
    ),
    "目标总像素": (
        "FLOAT", {"default": 1.0, "min": 0.1, "max": 16.0, "step": 0.1,
                  "tooltip": "用于按像素计算，每单位为 1024×1024 像素。"},
    ),
    "尺寸对齐倍数": (
        "INT", {"default": 8, "min": 8, "max": 128, "step": 4,
                "tooltip": "宽高按此倍数取整。"},
    ),
    "目标总像素（万）": (
        "FLOAT", {"default": 100.0, "min": 10.0, "max": 1600.0, "step": 10.0,
                  "tooltip": "输入 100、200、300，分别表示 100 万、200 万、300 万像素。"},
    ),
}

USER_MODULE_INPUTS = {
    "画面基础": "用户画面基础片段",
    "人物": "用户人物片段",
    "发型": "用户发型片段",
    "服装": "用户服装片段",
    "姿态动作": "用户姿态动作片段",
    "场景": "用户场景片段",
    "摄影": "用户摄影片段",
    "视觉表现": "用户视觉表现片段",
    "自定义": "用户自定义片段",
}


# ---------------------------------------------------------------- 词库加载
def _load_libraries():
    fields = {}
    presets = {}
    for path in sorted(LIB_ROOT.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # 单个文件坏了不影响其它
            logging.debug("[SunsetMale] 词库读取失败 %s：%s" % (path.name, exc))
            continue
        if path.name.startswith("90_"):
            presets.update(data.get("presets") or {})
            continue
        for name, spec in (data.get("fields") or {}).items():
            if name in fields:
                logging.debug("[SunsetMale] 字段重复，后者被忽略：%s（%s）" % (name, path.name))
                continue
            fields[name] = spec
    return fields, presets


_LIB, PRESET_TABLE = _load_libraries()

FIELD_TEXT, FIELD_EN, FIELD_BRIEF, FIELD_LEVEL = {}, {}, {}, {}
FIELD_OPTIONS = {}
for _name in FIELD_ORDER:
    _spec = _LIB.get(_name)
    if not _spec:
        logging.debug("[SunsetMale] 词库缺字段：%s" % _name)
        continue
    _opts = _spec.get("options") or []
    FIELD_OPTIONS[_name] = [o["l"] for o in _opts]
    FIELD_TEXT[_name] = {o["l"]: o.get("z") or o["l"] for o in _opts}
    FIELD_EN[_name] = {o["l"]: o.get("e") or "" for o in _opts}
    FIELD_BRIEF[_name] = {o["l"]: o.get("b") or (o.get("z") or o["l"]).split("，")[0]
                          for o in _opts}
    FIELD_LEVEL[_name] = int(_spec.get("lv") or 2)

# ---------------------------------------------------------------- 从属索引
def _load_index():
    """族裔大类 → 地域族裔分支、场景大类 → 场景地点、配套字段 → 场景大类。"""
    path = LIB_ROOT / "05_index.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        logging.debug("[SunsetMale] 索引读取失败 %s：%s" % (path.name, exc))
        return {}, {}, {}
    return (data.get("branchOf") or {}, data.get("sceneOf") or {},
            data.get("packageOf") or {})


BRANCH_OF_ETHNICITY, SCENE_OF_LOCATION, PACKAGE_OF = _load_index()
LOCATIONS_OF_SCENE = {}
for _place, _scene_cat in SCENE_OF_LOCATION.items():
    LOCATIONS_OF_SCENE.setdefault(_scene_cat, []).append(_place)
BRANCH_PARENT = {}
for _eth_cat, _branches in BRANCH_OF_ETHNICITY.items():
    for _b in _branches:
        if _b != "大类通用外观":
            BRANCH_PARENT[_b] = _eth_cat

# 场景配套：预设里每个场景地点都配了前景/背景/细节，换场景时整套跟着换
SCENE_PACKAGE_FIELDS = ("前景框景", "背景环境", "环境细节", "空间材质", "空间层次")
SCENE_PACKAGE = {}
for _values in PRESET_TABLE.values():
    _place = (_values or {}).get("场景地点")
    if not _place:
        continue
    _pkg = {k: _values[k] for k in SCENE_PACKAGE_FIELDS if _values.get(k)}
    if _pkg:
        SCENE_PACKAGE.setdefault(_place, _pkg)

PRESET_OPTIONS = [name for name in PRESET_TABLE if name] + [CUSTOM_PRESET]


def library_stats():
    total = sum(len(v) for v in FIELD_OPTIONS.values())
    return {"fields": len(FIELD_OPTIONS), "options": total, "presets": len(PRESET_TABLE)}


# ---------------------------------------------------------------- 取值
def _pick(seed_pool, rng):
    return rng.choice(seed_pool) if seed_pool else ""


# 「跨风格混搭」之外，这几项本来就该自由换：动作 / 表情 / 色彩 / 质感
JITTER_FIELDS = {
    "手部动作", "腿部动作", "身体方向", "身体重心", "肩颈状态",
    "头部方向", "视线", "表情",
    "主配色", "色温倾向", "画面对比",
    "细节质地", "高光处理", "颗粒质感", "后期调色",
}


# 随机抽取时只从「不容易出戏」的项里抽（用户手动选的时候仍然能选全部）
SAFE_POOL = {
    "刺青": ["无刺青", "小臂图腾", "手背图案"],
    "体毛": ["无明显体毛", "手臂细软", "小臂明显"],
    "服装配件": ["不佩戴", "皮质皮带", "斜挎包", "双肩包", "相机背带", "金属钥匙扣"],
    "腕表配饰": ["不佩戴", "机械钢表", "黑盘皮带表", "智能手表", "金属手链"],
}
SIT_HINTS = ("坐", "蹲", "跪", "卧", "盘腿", "鸽子式")
WALK_HINTS = ("走过", "行走", "走进", "经过", "停步", "迈步", "转身离开", "推门")
DRIVE_HANDS = ("方向盘", "手搭车窗")
# 只有场景本身在车里/车边，方向盘和车窗才成立
CAR_SCENE_HINTS = ("车内", "座舱", "驾驶", "停车场", "车库", "加油站", "车门",
                   "副驾", "后座", "越野车", "卡车", "出租车")
# 手选了车里的动作/瞬间时，把场景换成这些
CAR_PLACES = ("驾驶座车内", "副驾座位")
# 只有车里才做得出的画面瞬间
CAR_MOMENTS = ("拉开车门", "上车关门", "摇下车窗", "踩下油门", "关上车门",
               "系上安全带", "发动引擎", "摇上车窗", "握方向盘")
SEATED_HINTS = ("坐", "骑", "马背", "蹲", "跪", "卧", "盘腿", "鸽子式")
LEG_NEEDS_SEAT = ("坐姿", "膝部交叠", "横杆", "马镫", "盘腿", "池水", "侧卧",
                  "地面屈膝", "鸽子式")
# 腿部动作 → 需要什么姿态（手选腿部动作时，把姿态改成对得上的那个）
# 只有站着才成立的腿部动作 / 重心
STANDING_LEGS = ("双脚自然平行", "自然迈步")
CROUCH_HINTS = ("蹲",)
# 坐着 / 蹲着时该用的腿部动作
SEATED_LEGS = ("坐姿双膝并拢", "坐姿双腿偏向一侧", "坐姿一腿稍向前", "膝部交叠坐姿", "脚踝交叉")
CROUCH_LEGS = ("双脚分开微屈膝", "运动式屈膝支撑", "屈膝抱腿")
# 蹲着却写着「坐在椅子上」的那些腿部/重心/手部
SEAT_ONLY_LEGS = ("横杆", "坐姿", "膝部交叠", "椅背")
LEG_TO_POSE = (
    ("盘腿", "盘腿而坐"), ("侧卧", "沙滩侧卧"), ("马镫", "马背坐姿"),
    ("脚蹬", "骑行姿态"), ("池水", "泳池边坐姿"), ("横杆", "高脚椅坐姿"),
    ("鸽子", "低位鸽子式"), ("跪", "跪坐"), ("蹲", "蹲姿"),
    ("地面屈膝", "地面侧坐"), ("屈膝", "椅子前缘坐姿"),
    ("膝部交叠", "椅子前缘坐姿"), ("坐姿", "椅子前缘坐姿"),
)
# 画面瞬间 → 需要什么姿态
MOMENT_TO_POSE = (
    ("坐在台阶", "地面侧坐"), ("坐在床沿", "沙发放松坐姿"),
    ("蹲下", "蹲姿"), ("盘腿", "盘腿而坐"), ("跪坐", "跪坐"),
    ("侧卧", "沙滩侧卧"), ("坐在", "椅子前缘坐姿"),
)

# 发长等级：0 寸头 → 7 及背
HAIR_RANK = {"寸头": 0, "短碎发": 1, "盖耳短发": 2, "齐耳长度": 3,
             "齐颈长度": 4, "锁骨长度": 5, "肩下长发": 6, "及背长发": 7}
# 造型对发长的要求（下限, 上限）；没列出的不设限
STYLE_HAIR_SPAN = {
    "圆寸": (0, 0), "板寸": (0, 0), "卡尺寸头": (0, 0), "平头": (0, 0),
    "侧边铲青": (0, 1), "莫西干": (0, 1), "飞机头": (1, 2),
    "背头": (2, 3), "油头三明治": (2, 3), "顶部蓬松": (2, 3),
    "中长发": (4, 6), "半扎发": (5, 7), "低马尾": (4, 7), "高马尾": (4, 7),
    "丸子头": (4, 7), "直发披肩": (6, 7), "狼尾": (5, 7),
}
COLOR_OF_WORD = {"白": "燕麦白", "黑": "纯黑", "灰": "浅灰", "蓝": "深蓝",
                 "红": "砖红", "绿": "橄榄绿", "棕": "深棕", "米": "米杏",
                 "杏": "米杏", "驼": "驼色"}

# 外套类型 → 该类型真实会用的面料（避免「牛仔夹克 + 磨砂皮」这种组合）
OUTER_MATERIAL = {
    "牛仔夹克": ("水洗牛仔",),
    "皮夹克": ("头层牛皮", "羊羔绒皮", "磨砂皮"),
    "机车皮衣": ("头层牛皮", "磨砂皮"),
    "飞行夹克": ("尼龙面料", "太空棉", "羊羔绒皮"),
    "工装夹克": ("硬挺帆布", "涂层帆布", "灯芯绒"),
    "教练夹克": ("尼龙面料", "功能性软壳"),
    "棒球夹克": ("羊毛混纺", "尼龙面料"),
    "羽绒服": ("尼龙面料", "太空棉", "摇粒绒"),
    "棉服": ("尼龙面料", "太空棉"),
    "派克大衣": ("尼龙面料", "防水涂层", "抓绒内里"),
    "长风衣": ("硬挺帆布", "涂层帆布", "精纺羊毛"),
    "短风衣": ("硬挺帆布", "涂层帆布", "亚麻混纺"),
    "呢子大衣": ("羊毛混纺", "精纺羊毛", "粗花呢"),
    "双面呢大衣": ("羊毛混纺", "精纺羊毛"),
    "羊毛大衣": ("羊毛混纺", "精纺羊毛", "粗花呢"),
    "冲锋衣": ("防水涂层", "功能性软壳", "尼龙面料"),
    "软壳外套": ("功能性软壳", "抓绒内里"),
    "针织开衫": ("针织羊毛", "亚麻混纺", "丝绸混纺"),
    "连帽卫衣": ("摇粒绒", "针织羊毛"),
    "衬衫外穿": ("亚麻混纺", "丝绸混纺", "水洗牛仔"),
    "休闲西装": ("精纺羊毛", "羊毛混纺", "亚麻混纺"),
    "双排扣西装": ("精纺羊毛", "粗花呢"),
    "无结构西装": ("精纺羊毛", "亚麻混纺", "丝绸混纺"),
    "定制燕尾服": ("精纺羊毛",),
    "马甲": ("硬挺帆布", "精纺羊毛", "尼龙面料"),
    "工装背心": ("硬挺帆布", "涂层帆布"),
    "防护背心": ("尼龙面料", "功能性软壳"),
}

# 裤装类型 → 该类型真实会用的颜色
PANTS_COLOR = {
    "直筒牛仔裤": ("浅牛仔蓝", "深靛蓝", "纯黑", "沙色"),
    "修身牛仔裤": ("浅牛仔蓝", "深靛蓝", "纯黑"),
    "阔腿牛仔裤": ("浅牛仔蓝", "深靛蓝", "燕麦白"),
    "工装裤": ("沙色", "军绿", "深炭灰", "橄榄绿"),
    "束脚工装裤": ("沙色", "军绿", "深炭灰"),
    "战术裤": ("沙色", "军绿", "墨绿"),
    "西装裤": ("深炭灰", "纯黑", "藏青", "深棕"),
    "羊毛西裤": ("深炭灰", "藏青", "浅灰"),
    "运动裤": ("深炭灰", "纯黑", "浅灰", "藏青"),
    "慢跑裤": ("深炭灰", "纯黑", "浅灰"),
    "卫裤": ("浅灰", "深炭灰", "纯黑", "燕麦白"),
    "灯芯绒裤": ("深棕", "驼色", "橄榄绿", "奶茶色"),
    "皮裤": ("纯黑", "深棕"),
    "亚麻长裤": ("燕麦白", "米杏", "沙色", "奶茶色"),
    "卡其裤": ("沙色", "驼色", "米杏", "橄榄绿"),
    "背带裤": ("深靛蓝", "深炭灰", "沙色"),
    "骑行短裤": ("纯黑", "深炭灰"),
    "运动短裤": ("纯黑", "深炭灰", "藏青"),
    "沙滩短裤": ("沙色", "灰蓝", "燕麦白"),
}

# 基础身形 → 与之不冲突的肌肉线条
MUSCLE_OF_SHAPE = {
    "中年微发福": ("线条平缓", "干练结实"),
    "清瘦": ("线条平缓", "手臂清晰", "干练结实"),
    "精瘦有线条": ("手臂清晰", "腹肌隐约", "小臂血管", "干练结实", "腰腹收紧"),
    "自然匀称": ("线条平缓", "手臂清晰", "肩部饱满", "干练结实"),
    "肩宽胸厚": ("肩部饱满", "胸肌厚实", "背阔明显", "颈部粗壮", "力量型体态"),
    "壮硕厚实": ("胸肌厚实", "背阔明显", "力量型体态", "运动员体型", "颈部粗壮"),
}

# 等效焦段 → 合理的景深上限
# 头发表面处理与寸头不兼容的那些
BUZZ_BAD_TEXTURE = ("蓬松发量", "大波浪", "细碎卷", "自然卷", "微卷", "半干湿发", "凌乱发束")
SUIT_OUTER = ("休闲西装", "双排扣西装", "无结构西装", "定制燕尾服")
# 「版型细节」里属于上装 / 属于裤装的说法，合成时按这个插位置
FIT_TOP = ("oversize", "落肩袖", "正肩线", "侧开衩", "双排扣", "单排扣",
           "翻领", "立领", "无领", "短款", "长款")
FIT_BOTTOM = ("高腰", "低腰", "抽绳腰头", "翻边裤脚")
NO_ULTRA_SHALLOW = {"28mm", "35mm", "40mm", "手机主摄"}

# 文案里已经写死「自然」的发色，不能同时说漂后上色、一次性喷雾
UNDYED_HAIR = ("自然黑", "灰白", "花白", "纯白")
DYE_OPS = ("根部补色", "挑染", "渐变染", "局部片染", "漂后上色", "染后新生", "一次性喷雾")
# 这些色调本身就是「染过的痕迹」
DYE_TONES = ("自然褪色", "带挑染", "发尾偏浅", "根部偏深")

# 主光来源 → 它实际能给出的光线质地
HARD_LIGHTS = ("直射阳光", "日落阳光", "镜头方向硬闪", "柔化直闪", "霓虹灯牌",
               "车灯光", "投影光", "篝火", "烛光", "室内钨丝灯")
SOFT_LIGHTS = ("阴天天光", "窗户日光", "大型柔光箱", "雷达罩美人光", "环形补光",
               "柔光灯板", "反射补光", "室内顶光", "手机屏幕光", "叶隙阳光")
HARD_TEXTURES = ("清晰硬光", "高光鲜明", "斑驳光影", "逆光剪影")
SOFT_TEXTURES = ("极柔和", "柔和散射", "均匀平光", "柔和定向", "发光逆光", "伦勃朗光", "蝴蝶光")
# 能同时给出冷暖两路光的光源
MULTI_LIGHTS = ("霓虹灯牌", "橱窗灯光", "车灯光", "投影光", "篝火", "烛光", "手机屏幕光")

# 这些天气才配得上「日照」「长影」
SUNNY_WEATHER = ("晴朗日照", "薄云天气", "雨后彩虹", "初秋微风", "湿润夏日", "海风")

# 内搭类型 → 它真实会用的面料
INNER_MATERIAL = {
    "白衬衫": ("府绸", "牛津纺", "棉麻混纺", "丝光棉", "法兰绒"),
    "浅蓝衬衫": ("府绸", "牛津纺", "棉麻混纺", "丝光棉"),
    "牛仔衬衫": ("水洗做旧棉",),
    "格纹衬衫": ("法兰绒", "棉麻混纺", "牛津纺"),
    "条纹衬衫": ("府绸", "牛津纺", "棉麻混纺"),
    "半开襟衬衫": ("府绸", "棉麻混纺", "莫代尔"),
    "丝质衬衫": ("真丝",),
    "亚麻衬衫": ("亚麻", "棉麻混纺"),
    "中式立领": ("亚麻", "棉麻混纺", "真丝"),
    "黑T": ("纯棉", "棉麻混纺", "莫代尔", "速干面料"),
    "白T": ("纯棉", "丝光棉", "莫代尔"),
    "灰T": ("纯棉", "棉麻混纺", "莫代尔"),
    "印花T": ("纯棉", "丝光棉"),
    "长袖T": ("纯棉", "莫代尔", "混纺弹力"),
    "宽松T": ("纯棉", "棉麻混纺", "莫代尔"),
    "高领毛衣": ("羊绒", "美利奴羊毛", "粗针织", "针织棉"),
    "圆领毛衣": ("美利奴羊毛", "针织棉", "粗针织", "羊绒"),
    "V领针织": ("美利奴羊毛", "针织棉", "羊绒"),
    "半高领打底": ("羊绒", "莫代尔", "美利奴羊毛"),
    "polo衫": ("丝光棉", "纯棉", "混纺弹力"),
    "连帽卫衣内搭": ("针织棉", "抓绒", "纯棉"),
    "无袖背心": ("纯棉", "针织棉", "莫代尔"),
    "素色背心": ("纯棉", "针织棉", "莫代尔"),
    "背带打底": ("针织棉", "纯棉", "莫代尔"),
    "运动紧身衣": ("速干面料", "混纺弹力"),
    "压缩打底衫": ("速干面料", "混纺弹力"),
    "球衣": ("速干面料",),
    "衬衫加毛背心": ("府绸", "美利奴羊毛", "针织棉"),
    "浴袍": ("纯棉", "莫代尔"),
}

# 裤装类型 → 它真实会用的面料
PANTS_MATERIAL = {
    "直筒牛仔裤": ("硬挺牛仔", "弹力牛仔", "水洗牛仔"),
    "修身牛仔裤": ("弹力牛仔", "硬挺牛仔", "水洗牛仔"),
    "阔腿牛仔裤": ("硬挺牛仔", "水洗牛仔", "弹力牛仔"),
    "工装裤": ("斜纹棉", "防撕裂尼龙", "厚重棉布"),
    "束脚工装裤": ("斜纹棉", "防撕裂尼龙", "弹力混纺"),
    "战术裤": ("防撕裂尼龙", "斜纹棉"),
    "西装裤": ("精纺羊毛", "混纺西裤料"),
    "羊毛西裤": ("精纺羊毛", "混纺西裤料"),
    "运动裤": ("针织运动料", "速干面料", "抓绒内里"),
    "慢跑裤": ("针织运动料", "速干面料"),
    "卫裤": ("针织运动料", "抓绒内里", "弹力混纺"),
    "灯芯绒裤": ("灯芯绒",),
    "皮裤": ("涂层皮革", "绒面革"),
    "亚麻长裤": ("亚麻", "棉麻混纺"),
    "卡其裤": ("斜纹棉", "厚重棉布"),
    "休闲长裤": ("斜纹棉", "混纺西裤料", "弹力混纺", "厚重棉布"),
    "九分裤": ("斜纹棉", "精纺羊毛", "混纺西裤料", "硬挺牛仔"),
    "阔腿长裤": ("精纺羊毛", "混纺西裤料", "亚麻", "斜纹棉", "硬挺牛仔"),
    "背带裤": ("硬挺牛仔", "斜纹棉", "水洗牛仔"),
    "骑行短裤": ("速干面料", "弹力混纺"),
    "运动短裤": ("速干面料", "针织运动料"),
    "沙滩短裤": ("亚麻", "棉麻混纺", "速干面料"),
}

# 服装材质 → 与之匹配的服装类型（反向表在 _reverse 定义之后生成）

# 头部方向 → 与之匹配的视线
GAZE_OF_HEAD = {
    "头部上扬": ("仰望上方", "视线略高于镜头", "直视镜头"),
    "头部轻微低下": ("低头看地", "看向手中物品", "看向画面左侧近处", "看向画面右侧近处"),
    "头部正对镜头": ("直视镜头", "柔和看向镜头", "侧目看向镜头", "闭眼"),
    "头部转向左侧": ("看向画面左侧近处", "看向左侧远处"),
    "头部转向右侧": ("看向画面右侧近处", "看向右侧远处"),
    "向左回眸": ("看向画面左侧近处", "看向左侧远处", "直视镜头"),
    "向右回眸": ("看向画面右侧近处", "看向右侧远处", "直视镜头"),
}
UPWARD_GAZE = ("仰望上方", "视线略高于镜头")

# 鞋履 → 与之搭得上的袜装（板鞋不配商务袜）
SOCKS_OF_SHOE = {
    "牛津鞋": ("深灰商务袜", "黑色短袜", "中筒袜", "不露袜"),
    "德比鞋": ("深灰商务袜", "黑色短袜", "中筒袜", "不露袜"),
    "尖头皮鞋": ("深灰商务袜", "黑色短袜", "不露袜"),
    "切尔西靴": ("黑色短袜", "中筒袜", "不露袜"),
    "皮质乐福鞋": ("不露袜", "裸脚", "黑色短袜"),
    "白色板鞋": ("白色短袜", "黑色短袜", "运动袜", "不露袜", "裸脚"),
    "黑色板鞋": ("白色短袜", "黑色短袜", "运动袜", "不露袜", "裸脚"),
    "高帮帆布鞋": ("白色短袜", "中筒袜", "黑色短袜"),
    "低帮帆布鞋": ("白色短袜", "不露袜", "裸脚", "黑色短袜"),
    "运动跑鞋": ("运动袜", "白色短袜", "黑色短袜"),
    "老爹鞋": ("白色短袜", "运动袜", "黑色短袜"),
    "工装靴": ("中筒袜", "运动袜", "黑色短袜"),
    "马丁靴": ("黑色短袜", "中筒袜"),
    "户外登山鞋": ("中筒袜", "运动袜"),
    "沙漠靴": ("黑色短袜", "中筒袜", "不露袜"),
    "雨靴": ("中筒袜", "黑色短袜"),
    "钉鞋": ("运动袜", "白色短袜"),
    "拖鞋": ("裸脚", "不露袜"),
    "凉鞋": ("裸脚", "不露袜"),
    "赤脚": ("裸脚", "不露袜"),
}

# ---------------------------------------------------------------- 反向表
# 手选了从属项（面料/颜色/袜子/肌肉/视线）时，把搭档的那一项改成对得上的
def _reverse(table):
    out = {}
    for key, values in table.items():
        for value in values:
            out.setdefault(value, []).append(key)
    return out


OUTER_OF_MATERIAL = _reverse(OUTER_MATERIAL)
PANTS_OF_COLOR = _reverse(PANTS_COLOR)
SHAPE_OF_MUSCLE = _reverse(MUSCLE_OF_SHAPE)
HEAD_OF_GAZE = _reverse(GAZE_OF_HEAD)
SHOE_OF_SOCKS = _reverse(SOCKS_OF_SHOE)
INNER_OF_MATERIAL = _reverse(INNER_MATERIAL)
PANTS_OF_MATERIAL = _reverse(PANTS_MATERIAL)
# 本色/原生发色才配得上「未做染色」
NATURAL_HAIR = ("自然黑", "深棕", "栗棕", "冷棕", "浅棕", "灰棕", "蓝黑",
                "灰白", "花白", "纯白")
DYE_MODES = ("全头染", "根部补色", "挑染", "渐变染", "局部片染", "漂后上色")

# 「发色模式＝整体发色」时，染色方式与色调由发色统一推导
HAIR_DYE_MODE = {
    "自然黑": "本色", "深棕": "本色", "栗棕": "本色", "冷棕": "本色", "浅棕": "本色",
    "灰棕": "本色", "亚麻": "全头染", "银灰": "全头染", "白金": "漂后上色",
    "红棕": "全头染", "酒红": "全头染", "蓝黑": "本色", "墨绿": "全头染",
    "橄榄棕": "全头染", "巧克力棕": "全头染", "灰白": "自然花白",
    "花白": "自然花白", "纯白": "本色",
}
HAIR_TONE_OF = {
    "自然黑": "冷调", "深棕": "暖调", "栗棕": "暖调", "冷棕": "冷调", "浅棕": "暖调",
    "亚麻": "低饱和", "银灰": "冷调", "白金": "低饱和", "红棕": "暖调", "酒红": "暖调",
    "蓝黑": "冷调", "墨绿": "低饱和", "橄榄棕": "低饱和", "灰棕": "冷调",
    "巧克力棕": "暖调", "灰白": "冷调", "花白": "中性调", "纯白": "冷调",
}


# 白天的场景不套夜色调色
BRIGHT_TIMES = ("晴朗清晨", "上午晚些时候", "正午", "夏日午后", "阴天下午",
                "初秋午后", "黎明破晓", "冬日午后", "雨后清晨")
NIGHT_GRADES = ("冷蓝夜色", "紫调夜色")
DAY_GRADES = ("实拍直出", "日系低对比", "奶油柔光", "胶片暖调", "低饱和冷调", "冷暖对比")

# 半身以内的景别，主光落不到腿上
NO_LEG_LIGHT_FRAMING = ("面部特写", "头肩近景", "胸部以上", "腰部以上", "坐姿半身", "局部特写")

# 阴雨雾霾天气下不搭的高饱和配色
MUTED_WEATHER = ("阴天", "多云", "细雨", "薄雾", "大雨", "雷雨将至", "小雪", "雨后")
BOLD_PALETTES = ("紫蓝霓虹", "马卡龙色系", "珊瑚粉与薄荷绿", "日落橙紫", "港风绿红",
                 "黑白红", "黑红金", "香槟粉与深棕黑", "裸粉与奶油色", "青橙对照")
MUTED_PALETTES = ("浅灰与暖白", "冷灰与蓝", "黑白灰阶", "莫兰迪色系", "暖灰与玄黑",
                  "奶油米杏", "大地绿棕", "森林绿棕", "白与银灰", "暖棕与奶白",
                  "冷蓝与暖黄", "商品中性色")
OUTDOOR_HINTS = ("室外", "街", "路", "公园", "山", "海", "林", "沙滩", "庭院",
                 "码头", "广场", "草原", "天台", "桥", "集市", "露营", "港",
                 "湖", "溪", "瀑布", "田野", "雪", "沙漠", "草原", "巷", "堤")
# 阳光充沛的天气：手选高饱和配色时，天气让路
BRIGHT_WEATHER = ("晴朗日照", "薄云天气", "湿润夏日", "初秋微风", "雨后彩虹", "多云")
# 夜景时间：手选夜色调色时，时间让路
NIGHT_TIMES = ("夜间", "深夜", "入夜不久", "蓝调时刻", "月光之夜")
# 长焦段：手选极浅景深时，焦段让路
TELE_LENS = ("50mm", "65mm", "70mm", "85mm", "105mm", "135mm")
FULL_BODY_FRAMING = ("全身构图", "带环境全身", "环境人像", "动态全身")
MATURE_AGES = ("50–59岁", "60岁以上")
YOUNG_AGES = ("18–24岁", "25–31岁")
# 手选了这些颜色时，内搭直接换成自带该色的款式
INNER_OF_COLOR = {"纯黑": "黑T", "燕麦白": "白T", "浅灰": "灰T"}

# 只发生在夜里的场景，配清晨/正午就是错的
NIGHT_PLACES = ("鸡尾酒吧", "月夜森林", "夜市灯火", "夜市摊位", "玻璃幕墙都市夜景",
                "夜间便利店", "复古迪斯科舞厅", "未来赛博街区")
NIGHT_OK_TIMES = NIGHT_TIMES + ("傍晚", "暮色黄昏", "日落前金色时刻")
NIGHT_WEATHER = ("薄云天气", "多云", "阴天", "细雨", "雨后", "薄雾", "海风",
                 "小雪", "雷雨将至", "大雨", "湿润夏日", "初秋微风")
# 成像格式类的影像风格，必须和成像媒介对得上
FORMAT_STYLE_MEDIA = {
    "全画幅相机": ("专业数码相机摄影", "全画幅微单摄影", "数码单反摄影"),
    "便携数码相机": ("便携数码相机摄影", "早期CCD数码摄影"),
    "手机摄影": ("手机计算摄影",),
    "CCD数码相机": ("早期CCD数码摄影", "便携数码相机摄影"),
    "中画幅相机": ("中画幅数码摄影", "中画幅胶片摄影"),
    "彩色负片": ("35毫米胶片摄影", "中画幅胶片摄影", "一次性胶片相机摄影"),
    "反转片": ("35毫米胶片摄影", "中画幅胶片摄影"),
    "黑白胶片": ("35毫米胶片摄影", "中画幅胶片摄影"),
    "即时成像相纸": ("即时成像相纸摄影",),
    "一次性胶片相机": ("一次性胶片相机摄影", "35毫米胶片摄影"),
    "数码单反": ("数码单反摄影", "专业数码相机摄影", "全画幅微单摄影"),
    "微单相机": ("全画幅微单摄影", "半画幅微单摄影", "专业数码相机摄影"),
}
GENERIC_STYLES = ("时尚画报", "直闪抓拍", "商业商品摄影", "电影剧照")
# 冬季单品 vs 夏季单品：同时出现就是季节错乱
WARM_OUTER = ("羽绒服", "棉服", "派克大衣", "呢子大衣", "双面呢大衣", "羊毛大衣",
              "针织开衫", "连帽卫衣", "飞行夹克", "羊羔绒皮")
WARM_INNER = ("高领毛衣", "圆领毛衣", "V领针织", "半高领打底", "连帽卫衣内搭",
              "衬衫加毛背心")
WARM_ACC = ("针织冷帽",)
SUMMER_LOWER = ("沙滩短裤", "运动短裤", "骑行短裤")
SUMMER_SHOES = ("凉鞋", "拖鞋")
SUMMER_TO_WARM_LOWER = {"沙滩短裤": "亚麻长裤", "运动短裤": "运动裤", "骑行短裤": "运动裤"}
# 需要专门场景才成立的姿态
SPECIAL_POSE = {"持剑站立": ("东方传统",), "马背坐姿": ("草原", "马", "牧场", "沙漠"),
                "骑行姿态": ("骑行", "公路", "单车", "自行车"),
                "单车侧坐": ("骑行", "公路", "单车", "自行车")}
# 主光来源分室内 / 室外 / 都行
OUTDOOR_LIGHTS = ("直射阳光", "叶隙阳光", "日落阳光", "阴天天光", "篝火",
                  "霓虹灯牌", "橱窗灯光", "车灯光")
INDOOR_LIGHTS = ("窗户日光", "大型柔光箱", "雷达罩美人光", "环形补光", "柔光灯板",
                 "室内钨丝灯", "室内顶光", "反射补光", "投影光", "烛光")
ANY_LIGHTS = ("镜头方向硬闪", "柔化直闪", "手机屏幕光")
SUN_LIGHTS = ("直射阳光", "叶隙阳光", "日落阳光", "阴天天光")
SUN_SHADOWS = ("日落长影", "枝叶投影")
# 运动套装 / 西装套装各自该配什么
SPORT_OUTER = ("教练夹克", "软壳外套", "冲锋衣", "连帽卫衣", "棒球夹克",
               "工装背心", "防护背心")
SPORT_LOWER = ("运动裤", "慢跑裤", "卫裤", "骑行短裤", "运动短裤")
SPORT_SHOE = ("运动跑鞋", "老爹鞋", "白色板鞋", "黑色板鞋", "钉鞋", "高帮帆布鞋")
SUIT_LOWER = ("西装裤", "羊毛西裤")
SUIT_SHOE = ("牛津鞋", "德比鞋", "尖头皮鞋", "切尔西靴", "皮质乐福鞋")


def _repair(fields, name, allowed, rng, fixed):
    """name 不在 allowed 里就改它；它是手选的则改不动，返回 False 让调用方换搭档。

    这是整套一致性规则的总闸门：手选的字段永远不会被悄悄改掉。
    """
    pool = [v for v in allowed if v in FIELD_OPTIONS.get(name, ())]
    if not pool or fields.get(name) in pool:
        return True
    if name in fixed:
        return False
    fields[name] = rng.choice(pool) if rng is not None else pool[0]
    return True


def _swap_partner(fields, name, candidates, rng, fixed):
    """改不掉主字段时，退一步改它的搭档（搭档是手选的就彻底作罢）。"""
    if name in fixed or not candidates:
        return False
    pool = [v for v in candidates if v in FIELD_OPTIONS.get(name, ())]
    if not pool:
        return False
    fields[name] = rng.choice(pool) if rng is not None else pool[0]
    return True


def _color_word(label):
    head = (label or "")[:3]
    for word, color in COLOR_OF_WORD.items():
        if word in head:
            return color
    return ""


def _plain_option(name, rng):
    """挑一个名字里不带颜色的款式。"""
    pool = [v for v in FIELD_OPTIONS.get(name, ()) if not _color_word(v)]
    return rng.choice(pool) if pool and rng is not None else (pool[0] if pool else "")


def _align_color(fields, type_field, color_field, rng=None, fixed=frozenset()):
    """「白衬衫」配「藏青」这种自相矛盾的颜色拉回来。

    颜色是手选的 → 换一件不带颜色的同类别款式，不去动用户选的色。
    """
    implied = _color_word(fields.get(type_field))
    if not implied or implied not in FIELD_OPTIONS.get(color_field, ()):
        return
    current = fields.get(color_field)
    if current in (None, implied):
        fields[color_field] = implied
        return
    if color_field in fixed:
        plain = _plain_option(type_field, rng)
        if plain:
            fields[type_field] = plain
        return
    fields[color_field] = implied


def _random_of(name, rng):
    pool = SAFE_POOL.get(name)
    if pool:
        pool = [v for v in pool if v in FIELD_OPTIONS.get(name, ())]
        if pool:
            return rng.choice(pool)
    return _pick(FIELD_OPTIONS[name], rng)


def _gated_pool(name, fields):
    """大类的从属字段，随机时只在大类范围里抽。"""
    options = list(FIELD_OPTIONS.get(name, ()))
    if name == "地域族裔分支":
        group = BRANCH_OF_ETHNICITY.get(fields.get("族裔大类") or "") or ()
        narrowed = [v for v in group if v in options]
        if narrowed:
            return narrowed
    elif name == "场景地点":
        group = LOCATIONS_OF_SCENE.get(fields.get("场景大类") or "") or ()
        narrowed = [v for v in group if v in options]
        if narrowed:
            return narrowed
    return options


def _pick_for(name, preset, scope, fields, rng):
    """随机抽取一个值。

    随机抽取是「这一项交给你随便抽」，一定从整个词库里抽，
    只会被三件事收窄：大类从属（族裔分支、场景地点）、场景配套、容易出戏的黑名单。
    """
    if name in SCENE_PACKAGE_FIELDS:
        return _pick_package(name, fields, rng)
    pool = _narrow_safe(name, _gated_pool(name, fields))
    return rng.choice(pool)


# 跟随预设时，随机范围决定哪些字段可以跳出预设值
def _follows_preset(scope, name):
    module = MODULE_OF.get(name, "")
    if scope == RANDOM_SCOPES[0]:
        return name not in JITTER_FIELDS
    if scope == RANDOM_SCOPES[1]:
        return module in ("主题", "人物", "场景") or name in PROFILE_ANCHORS
    return False


# 同主题重拍里，除了三段整体保留，这几项也属于「主题身份」，别动
PROFILE_ANCHORS = {"写真主题", "写真大类", "年龄阶段", "族裔大类", "地域族裔分支",
                   "基础身形", "身量观感"}


GENERIC_CHARS = set("室间厅馆场区内外的与和及店楼景光球拍网灯墙桌椅机")
# 这些两字词太泛，算匹配会误伤（羽毛球馆 ≠ 攀岩馆，但都带「室内」）
GENERIC_GRAMS = {"室内", "室外", "明亮", "开阔", "宽敞", "安静", "干净", "复古",
                 "现代", "高级", "传统", "城市", "自然", "日常"}
GENERIC_CHARS |= set("".join(GENERIC_GRAMS))


def _place_score(place, value):
    """配套项和场景名的贴合度：共用两字词最重，共用单字次之，泛用字不算。"""
    def grams(text):
        out = set()
        for i in range(max(0, len(text) - 1)):
            gram = text[i:i + 2]
            if gram in GENERIC_GRAMS:
                continue
            if all(ch in GENERIC_CHARS for ch in gram):
                continue
            out.add(gram)
        return out

    score = 3 * len(grams(place) & grams(value))
    score += sum(1 for ch in set(place) & set(value) if ch not in GENERIC_CHARS)
    return score


# 这三项找不到同名配套时宁可不写，也别把别的场地的道具搬进来
DROP_IF_UNMATCHED = ("环境细节", "前景框景", "背景环境")


def _package_pool(name, place, scene_cat):
    # 户外没有「空间材质」这回事，整条不写
    if name == "空间材质" and scene_cat == "自然户外":
        return []
    place_text = FIELD_TEXT.get("场景地点", {}).get(place, "")
    texts = FIELD_TEXT.get(name, {})
    table = PACKAGE_OF.get(name) or {}
    pool = [v for v in FIELD_OPTIONS.get(name, ())
            if table.get(v) in (scene_cat, "通用") and v != place
            and not (v in place or place in v)
            and not (place_text and texts.get(v) and texts[v] in place_text)]
    if not pool or not place:
        return pool
    scored = [(v, _place_score(place, v)) for v in pool]
    best = max(s for _v, s in scored)
    if best > 0:
        return [v for v, s in scored if s == best]
    # 认不出这个场地的配套，就整条不写——场景本身的描述已经交代了环境
    return [] if name in DROP_IF_UNMATCHED else pool


def _pick_package(name, fields, rng):
    """前景/背景/细节/材质/层次：先看预设配套，再在同类别里挑与场景名最贴的。"""
    place = fields.get("场景地点") or ""
    package = SCENE_PACKAGE.get(place) or {}
    value = package.get(name)
    if value in FIELD_OPTIONS.get(name, ()) and value != place:
        return value
    scene_cat = fields.get("场景大类") or SCENE_OF_LOCATION.get(place) or ""
    pool = _package_pool(name, place, scene_cat)
    return rng.choice(pool) if pool else ""


def _narrow_safe(name, pool):
    """随机时避开容易出戏的项，但只在池子够用时收窄，避免把用户限定的大类抽空。"""
    safe = SAFE_POOL.get(name)
    if not safe:
        return pool
    narrowed = [v for v in pool if v in safe]
    return narrowed if len(narrowed) >= 2 else pool


def _style_fits(style, rank):
    """这个发型在给定发长下成不成立。"""
    span = STYLE_HAIR_SPAN.get(style)
    if span is None or rank is None:
        return True
    return span[0] <= rank <= span[1]


def _harmonize(fields, rng=None, fixed=frozenset()):
    """把互斥组合拉回合理状态。

    fixed = 用户手选的字段。每条规则都先改「没被手选」的那一项；
    改不动才去换手选项的搭档；两边都是手选的，就保留用户的选择。
    """
    fixed = set(fixed or ())

    def put(name, value):
        fields[name] = value

    def seated_of(value):
        return any(k in (value or "") for k in SEATED_HINTS)

    def move_to_car():
        """手选的瞬间/手部动作需要车，就把场景换成车内。"""
        if "场景地点" in fixed:
            return False
        place = rng.choice(CAR_PLACES) if rng is not None else CAR_PLACES[0]
        put("场景地点", place)
        parent = SCENE_OF_LOCATION.get(place)
        if parent and "场景大类" not in fixed:
            put("场景大类", parent)
        _reapply_package(fields, fixed, place, rng)
        return True

    # ---------------- 服装：外套 / 内搭 / 穿搭结构
    outer = fields.get("外套类型")
    inner = fields.get("内搭类型")
    if outer == "无外套":
        wanted = [k for k in ("外套颜色", "外套材质", "外套图案") if fields.get(k)]
        if wanted and any(k in fixed for k in wanted) and "外套类型" not in fixed:
            # 手选了外套颜色/面料，说明其实想要一件外套
            pool = ()
            if "外套材质" in wanted:
                pool = OUTER_OF_MATERIAL.get(fields.get("外套材质") or "", ())
            fields["外套类型"] = (rng.choice(pool) if rng else pool[0]) if pool else "衬衫外穿"
            outer = fields["外套类型"]
    if fields.get("外套类型") == "无外套":
        for key in ("外套颜色", "外套材质", "外套图案"):
            if key not in fixed:
                fields.pop(key, None)
        if (fields.get("穿搭结构") in ("外套叠穿", "内搭加外套", "西装套装")
                and "穿搭结构" not in fixed):
            put("穿搭结构", "单件上装")

    if fields.get("内搭类型") == "无内搭":
        outer = fields.get("外套类型")
        if not outer or outer == "无外套":
            if "内搭类型" not in fixed:
                put("内搭类型", "黑T")
        else:
            color = fields.get("内搭颜色")
            if "内搭颜色" in fixed and color and "内搭类型" not in fixed:
                put("内搭类型", INNER_OF_COLOR.get(color, "长袖T"))
            else:
                for key in ("内搭颜色", "内搭材质"):
                    if key not in fixed:
                        fields.pop(key, None)

    if fields.get("穿搭结构") == "西装套装":
        if (not _repair(fields, "外套类型", SUIT_OUTER, rng, fixed)
                and "穿搭结构" not in fixed):
            put("穿搭结构", "内搭加外套")
    if (fields.get("内搭类型") == "无内搭"
            and fields.get("穿搭结构") in ("外套叠穿", "内搭加外套")
            and "穿搭结构" not in fixed):
        put("穿搭结构", "单件上装")

    outer = fields.get("外套类型")
    inner = fields.get("内搭类型")
    if (fields.get("穿搭结构") == "单件上装"
            and outer not in (None, "无外套") and inner not in (None, "无内搭")):
        if "穿搭结构" in fixed:
            # 手选了「单件上装」就把外套摘掉，结构说了算
            if "外套类型" not in fixed:
                put("外套类型", "无外套")
                for key in ("外套颜色", "外套材质", "外套图案"):
                    if key not in fixed:
                        fields.pop(key, None)
        else:
            put("穿搭结构", "内搭加外套")

    # ---------------- 发型：发长与造型
    length = fields.get("头发长度") or ""
    style = fields.get("发型造型") or ""
    rank = HAIR_RANK.get(length)
    if rank is not None and not _style_fits(style, rank):
        span = STYLE_HAIR_SPAN.get(style) or (0, 7)
        lengths_ok = [k for k, v in HAIR_RANK.items()
                      if span[0] <= v <= span[1] and k in FIELD_OPTIONS.get("头发长度", ())]
        styles_ok = [s for s in FIELD_OPTIONS.get("发型造型", ()) if _style_fits(s, rank)]
        if "发型造型" in fixed and lengths_ok:
            # 造型是手选的，把发长挪进它允许的范围（找最接近的）
            put("头发长度", min(lengths_ok, key=lambda k: abs(HAIR_RANK[k] - rank)))
        elif "头发长度" in fixed and styles_ok:
            put("发型造型", rng.choice(styles_ok) if rng else styles_ok[0])
        elif lengths_ok:
            put("头发长度", min(lengths_ok, key=lambda k: abs(HAIR_RANK[k] - rank)))
        elif styles_ok:
            put("发型造型", rng.choice(styles_ok) if rng else styles_ok[0])

    if fields.get("头发长度") == "寸头" and fields.get("发质与卷度") in BUZZ_BAD_TEXTURE:
        if "发质与卷度" in fixed:
            if "头发长度" not in fixed:
                put("头发长度", "盖耳短发")
        else:
            put("发质与卷度", "服帖紧实")

    style = fields.get("发型造型") or ""
    if style in ("背头", "油头三明治", "飞机头", "顶部蓬松"):
        # 只要前发不是「全部后梳」或「额头全露」，就一定是矛盾的
        if "额前处理" not in fixed and fields.get("额前处理") not in ("全部后梳", "额头全露"):
            put("额前处理", "全部后梳")

    # ---------------- 姿态：画面瞬间 / 腿部 / 重心 / 手部
    pose = fields.get("基础姿态") or ""
    moment = fields.get("画面瞬间") or ""
    place = fields.get("场景地点") or ""
    seated = seated_of(pose)
    in_car = any(k in place for k in CAR_SCENE_HINTS)

    # 持剑/骑马/骑行这些姿态要专门的场景
    pose_now = fields.get("基础姿态") or ""
    hints = SPECIAL_POSE.get(pose_now)
    if hints and pose_now not in fixed:
        scene_text = place + (fields.get("场景大类") or "") + (fields.get("写真大类") or "")
        if not any(h in scene_text for h in hints):
            _repair(fields, "基础姿态", ["自然站立", "侧身站立", "墙边轻靠", "行走中停步"], rng, fixed)

    if not in_car and any(k in moment for k in CAR_MOMENTS):
        if "画面瞬间" in fixed:
            in_car = move_to_car()
        elif "画面瞬间" not in fixed:
            neutral = ("侧头倾听", "开口说话") if seated else ("停下脚步", "整理袖口")
            put("画面瞬间", rng.choice(neutral) if rng else neutral[0])
            moment = fields["画面瞬间"]

    if any(k in moment for k in WALK_HINTS) and seated:
        if "基础姿态" not in fixed:
            put("基础姿态", "行走中停步")
            seated = False
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "停下脚步")
            moment = fields["画面瞬间"]

    if (any(k in moment for k in ("坐在", "盘腿", "侧卧", "蹲下", "跪坐"))
            and not seated):
        if "基础姿态" not in fixed:
            target = next((p for k, p in MOMENT_TO_POSE if k in moment), "椅子前缘坐姿")
            put("基础姿态", target)
            seated = True
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "停下脚步")
            moment = fields["画面瞬间"]

    head_acc = fields.get("头部配饰") or ""
    if moment == "戴上帽子" and "帽" not in head_acc:
        if "画面瞬间" in fixed and "头部配饰" not in fixed:
            put("头部配饰", "棒球帽")
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "抬头看天")
    if moment == "拉下头盔" and "安全帽" not in head_acc:
        if "画面瞬间" in fixed and "头部配饰" not in fixed:
            put("头部配饰", "安全帽")
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "抬头看天")
    if moment == "松开领带" and "衬衫" not in (fields.get("内搭类型") or ""):
        if "画面瞬间" in fixed and "内搭类型" not in fixed:
            put("内搭类型", "白衬衫")
            if "内搭颜色" not in fixed:
                put("内搭颜色", "燕麦白")
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "整理袖口")

    pose = fields.get("基础姿态") or ""
    seated = seated_of(pose)
    if any(k in pose for k in ("盘腿", "跪坐", "侧卧", "鸽子式")):
        if "腿部动作" in fixed:
            if "基础姿态" not in fixed:
                put("基础姿态", "椅子前缘坐姿")
                pose = "椅子前缘坐姿"
                seated = True
        else:
            fields.pop("腿部动作", None)

    legs = fields.get("腿部动作") or ""
    if "腿部动作" in fixed and not seated and any(k in legs for k in LEG_NEEDS_SEAT):
        if "基础姿态" not in fixed:
            put("基础姿态", next((p for k, p in LEG_TO_POSE if k in legs), "椅子前缘坐姿"))
            pose = fields["基础姿态"]
            seated = True
    legs = fields.get("腿部动作") or ""
    pose = fields.get("基础姿态") or ""
    if "脚蹬" in legs and "骑行" not in pose and "单车" not in pose:
        if "腿部动作" in fixed and "基础姿态" not in fixed:
            put("基础姿态", "骑行姿态")
            seated = True
        elif "腿部动作" not in fixed:
            put("腿部动作", "双脚自然平行")
    if "马镫" in legs and "马背" not in pose:
        if "腿部动作" in fixed and "基础姿态" not in fixed:
            put("基础姿态", "马背坐姿")
            seated = True
        elif "腿部动作" not in fixed:
            put("腿部动作", "双脚自然平行")

    legs = fields.get("腿部动作") or ""
    if not seated and "腿部动作" not in fixed and any(k in legs for k in LEG_NEEDS_SEAT):
        put("腿部动作", "双脚自然平行")

    # 反过来：已经坐/蹲着了，就不该写「双脚自然平行站立」
    if seated and "腿部动作" not in fixed and any(k in legs for k in STANDING_LEGS):
        crouching = any(k in (fields.get("基础姿态") or "") for k in CROUCH_HINTS)
        pool = [v for v in (CROUCH_LEGS if crouching else SEATED_LEGS)
                if v in FIELD_OPTIONS.get("腿部动作", ())]
        if pool:
            put("腿部动作", rng.choice(pool) if rng else pool[0])
        legs = fields.get("腿部动作") or ""

    # 蹲着不该有「坐骨重心」「高脚椅横杆」「椅背」这些椅子上的东西
    crouching = any(k in (fields.get("基础姿态") or "") for k in CROUCH_HINTS)
    if crouching:
        if fields.get("腿部动作") and "腿部动作" not in fixed:
            for key in SEAT_ONLY_LEGS:
                if key in (fields.get("腿部动作") or ""):
                    pool = [v for v in FIELD_OPTIONS.get("腿部动作", ())
                            if not any(k in v for k in SEAT_ONLY_LEGS)
                            and not any(k in v for k in STANDING_LEGS)]
                    if pool:
                        put("腿部动作", rng.choice(pool) if rng else pool[0])
                    break
        if ("坐骨" in (fields.get("身体重心") or "")
                and "身体重心" not in fixed):
            put("身体重心", "双脚均衡承重")
        if ("椅背" in (fields.get("手部动作") or "")
                and "手部动作" not in fixed):
            put("手部动作", "搭在膝上")

    if not seated and "坐骨" in (fields.get("身体重心") or ""):
        if "身体重心" in fixed and "基础姿态" not in fixed:
            put("基础姿态", "椅子前缘坐姿")
            seated = True
        elif "身体重心" not in fixed:
            put("身体重心", "双脚均衡承重")

    hands = fields.get("手部动作") or ""
    in_car = any(k in (fields.get("场景地点") or "") for k in CAR_SCENE_HINTS)
    if any(k in hands for k in DRIVE_HANDS) and not in_car:
        if "手部动作" in fixed:
            move_to_car()
        elif "手部动作" not in fixed:
            put("手部动作", "搭在膝上" if seated else "双手插兜")
    if "撑地" in hands and not seated:
        if "手部动作" in fixed and "基础姿态" not in fixed:
            put("基础姿态", "地面侧坐")
            seated = True
        elif "手部动作" not in fixed:
            put("手部动作", "双手插兜")

    _align_color(fields, "外套类型", "外套颜色", rng, fixed)
    _align_color(fields, "内搭类型", "内搭颜色", rng, fixed)

    # ---------------- 年龄与灰白须发
    age = fields.get("年龄阶段") or ""
    gray = {"发色": fields.get("发色") in ("灰白", "花白", "纯白"),
            "胡须": fields.get("胡须") in ("灰白胡", "白须长者"),
            "眉形": fields.get("眉形") == "灰白眉"}
    if age in YOUNG_AGES and any(gray.values()):
        if any(k in fixed for k, hit in gray.items() if hit):
            # 手选了灰白须发，年龄让路
            if "年龄阶段" not in fixed:
                put("年龄阶段", rng.choice(MATURE_AGES) if rng else MATURE_AGES[0])
        else:
            if gray["发色"]:
                put("发色", "自然黑")
            if gray["胡须"]:
                put("胡须", "短胡茬")
            if gray["眉形"]:
                put("眉形", "自然粗眉")

    # 二十几岁不写「中年微发福」
    if fields.get("年龄阶段") in YOUNG_AGES and fields.get("基础身形") == "中年微发福":
        if "基础身形" in fixed:
            if "年龄阶段" not in fixed:
                put("年龄阶段", rng.choice(MATURE_AGES) if rng else MATURE_AGES[0])
        else:
            _repair(fields, "基础身形",
                    [v for v in FIELD_OPTIONS.get("基础身形", ()) if v != "中年微发福"],
                    rng, fixed)

    # 夜市/酒吧这类场景只能发生在夜里
    place = fields.get("场景地点") or ""
    if any(k in place for k in NIGHT_PLACES):
        if (fields.get("时间切片") not in NIGHT_OK_TIMES
                and "时间切片" not in fixed):
            put("时间切片", rng.choice(NIGHT_TIMES) if rng else NIGHT_TIMES[0])
        if fields.get("天气状态") == "晴朗日照" and "天气状态" not in fixed:
            put("天气状态", rng.choice(NIGHT_WEATHER) if rng else NIGHT_WEATHER[0])

    # 成像媒介 ↔ 影像风格：半画幅机身不能说成中画幅质感
    style_val = fields.get("影像风格") or ""
    media = fields.get("成像媒介") or ""
    allowed_media = FORMAT_STYLE_MEDIA.get(style_val)
    if allowed_media and media not in allowed_media:
        if "影像风格" in fixed and "成像媒介" not in fixed:
            put("成像媒介", allowed_media[0])
        else:
            pool = [s for s, medias in FORMAT_STYLE_MEDIA.items() if media in medias]
            _repair(fields, "影像风格", pool + list(GENERIC_STYLES), rng, fixed)

    # 穿搭结构：说了运动套装就得穿运动那一套，说了西装套装就得配西裤皮鞋
    structure = fields.get("穿搭结构") or ""
    if structure == "运动套装":
        _repair(fields, "外套类型", SPORT_OUTER, rng, fixed)
        _repair(fields, "裤装类型", SPORT_LOWER, rng, fixed)
        _repair(fields, "鞋履", SPORT_SHOE, rng, fixed)
    elif structure == "西装套装":
        _repair(fields, "裤装类型", SUIT_LOWER, rng, fixed)
        _repair(fields, "鞋履", SUIT_SHOE, rng, fixed)

    # 季节：冷帽/大衣配沙滩短裤说不通
    warm = (fields.get("外套类型") in WARM_OUTER or fields.get("内搭类型") in WARM_INNER
            or fields.get("头部配饰") in WARM_ACC)
    if warm:
        for key, summer in (("裤装类型", SUMMER_LOWER), ("鞋履", SUMMER_SHOES)):
            if fields.get(key) in summer:
                if key in fixed:
                    for name, pool in (("外套类型", WARM_OUTER), ("内搭类型", WARM_INNER),
                                       ("头部配饰", WARM_ACC)):
                        if name not in fixed and fields.get(name) in pool:
                            if name == "头部配饰":
                                put(name, "不佩戴")
                            else:
                                _repair(fields, name, [v for v in FIELD_OPTIONS.get(name, ())
                                                       if v not in pool], rng, fixed)
                else:
                    target = SUMMER_TO_WARM_LOWER.get(fields.get(key), "运动跑鞋")
                    if target in FIELD_OPTIONS.get(key, ()):
                        put(key, target)

    # 主光来源 ↔ 室内外：室内场景别写「直射阳光」「篝火」
    place_now = fields.get("场景地点") or ""
    outdoor = (not place_now) or any(k in place_now for k in OUTDOOR_HINTS)
    light = fields.get("主光来源") or ""
    if light:
        if outdoor and light in INDOOR_LIGHTS:
            _repair(fields, "主光来源", OUTDOOR_LIGHTS + ANY_LIGHTS, rng, fixed)
        elif not outdoor and light in OUTDOOR_LIGHTS:
            _repair(fields, "主光来源", INDOOR_LIGHTS + ANY_LIGHTS, rng, fixed)

    # 夜里不写太阳光和日落长影
    if fields.get("时间切片") in NIGHT_TIMES:
        if fields.get("主光来源") in SUN_LIGHTS:
            _repair(fields, "主光来源",
                    [v for v in FIELD_OPTIONS.get("主光来源", ()) if v not in SUN_LIGHTS], rng, fixed)
        if fields.get("阴影表现") in SUN_SHADOWS and fields.get("主光来源") not in SUN_LIGHTS:
            _repair(fields, "阴影表现",
                    [v for v in FIELD_OPTIONS.get("阴影表现", ()) if v not in SUN_SHADOWS], rng, fixed)
        # 夜里不可能「晴朗日照」
        if (fields.get("天气状态") == "晴朗日照" and "天气状态" not in fixed):
            put("天气状态", rng.choice(NIGHT_WEATHER) if rng else NIGHT_WEATHER[0])

    # 阴天/多云/下雨：不会有直射阳光，也不会有日落长影
    weather_now = fields.get("天气状态") or ""
    if weather_now in MUTED_WEATHER:
        if (fields.get("主光来源") in ("直射阳光", "日落阳光")
                and "主光来源" not in fixed):
            pool = (("阴天天光", "窗户日光") if outdoor
                    else ("柔光灯板", "大型柔光箱", "反射补光"))
            put("主光来源", rng.choice(pool) if rng else pool[0])
        if fields.get("阴影表现") in SUN_SHADOWS:
            if "阴影表现" in fixed:
                if "天气状态" not in fixed:
                    put("天气状态", rng.choice(SUNNY_WEATHER) if rng else SUNNY_WEATHER[0])
            else:
                _repair(fields, "阴影表现",
                        [v for v in FIELD_OPTIONS.get("阴影表现", ()) if v not in SUN_SHADOWS],
                        rng, fixed)

    # 冷暖混合光要有多处光源才说得通（放在光质对齐之前，免得改完又被判矛盾）
    if (fields.get("光线质地") == "混合色光"
            and fields.get("主光来源") not in MULTI_LIGHTS):
        if "光线质地" not in fixed:
            light_here = fields.get("主光来源") or ""
            pool = SOFT_TEXTURES if light_here in SOFT_LIGHTS else HARD_TEXTURES
            pool = [v for v in pool if v in FIELD_OPTIONS.get("光线质地", ())]
            if pool:
                put("光线质地", rng.choice(pool) if rng else pool[0])
        else:
            _repair(fields, "主光来源", MULTI_LIGHTS, rng, fixed)

    # 主光来源 ↔ 光线质地：直射光说不出「均匀散射」
    light_now = fields.get("主光来源") or ""
    texture_now = fields.get("光线质地") or ""
    if light_now in SOFT_LIGHTS and texture_now in HARD_TEXTURES:
        if "光线质地" not in fixed:
            _repair(fields, "光线质地", SOFT_TEXTURES, rng, fixed)
        elif "主光来源" not in fixed:
            _repair(fields, "主光来源", HARD_LIGHTS, rng, fixed)
    elif light_now in HARD_LIGHTS and texture_now in SOFT_TEXTURES:
        if "光线质地" not in fixed:
            _repair(fields, "光线质地", HARD_TEXTURES, rng, fixed)
        elif "主光来源" not in fixed:
            _repair(fields, "主光来源", SOFT_LIGHTS, rng, fixed)

    # 柔和光源不可能打出落日长影
    if fields.get("主光来源") in SOFT_LIGHTS and fields.get("阴影表现") in SUN_SHADOWS:
        if "阴影表现" not in fixed:
            _repair(fields, "阴影表现",
                    [v for v in FIELD_OPTIONS.get("阴影表现", ()) if v not in SUN_SHADOWS],
                    rng, fixed)
        else:
            _repair(fields, "主光来源", HARD_LIGHTS, rng, fixed)

    # ---------------- 从属项冲突：改非手选的那一侧
    mat_ok = OUTER_MATERIAL.get(fields.get("外套类型") or "")
    if mat_ok and fields.get("外套材质"):
        if not _repair(fields, "外套材质", mat_ok, rng, fixed):
            _swap_partner(fields, "外套类型",
                          OUTER_OF_MATERIAL.get(fields.get("外套材质") or "", ()), rng, fixed)

    color_ok = PANTS_COLOR.get(fields.get("裤装类型") or "")
    if color_ok and fields.get("裤装颜色"):
        if not _repair(fields, "裤装颜色", color_ok, rng, fixed):
            _swap_partner(fields, "裤装类型",
                          PANTS_OF_COLOR.get(fields.get("裤装颜色") or "", ()), rng, fixed)

    socks_ok = SOCKS_OF_SHOE.get(fields.get("鞋履") or "")
    if socks_ok and fields.get("袜装"):
        if not _repair(fields, "袜装", socks_ok, rng, fixed):
            _swap_partner(fields, "鞋履",
                          SHOE_OF_SOCKS.get(fields.get("袜装") or "", ()), rng, fixed)

    muscle_ok = MUSCLE_OF_SHAPE.get(fields.get("基础身形") or "")
    if muscle_ok and fields.get("肌肉线条"):
        if not _repair(fields, "肌肉线条", muscle_ok, rng, fixed):
            _swap_partner(fields, "基础身形",
                          SHAPE_OF_MUSCLE.get(fields.get("肌肉线条") or "", ()), rng, fixed)

    # 内搭类型 ↔ 内搭材质：衬衫不该是抓绒
    inner_ok = INNER_MATERIAL.get(fields.get("内搭类型") or "")
    if inner_ok and fields.get("内搭材质"):
        if not _repair(fields, "内搭材质", inner_ok, rng, fixed):
            _swap_partner(fields, "内搭类型",
                          INNER_OF_MATERIAL.get(fields.get("内搭材质") or "", ()), rng, fixed)

    # 裤装类型 ↔ 裤装材质：西装裤不该是防撕裂尼龙
    pants_ok = PANTS_MATERIAL.get(fields.get("裤装类型") or "")
    if pants_ok and fields.get("裤装材质"):
        if not _repair(fields, "裤装材质", pants_ok, rng, fixed):
            _swap_partner(fields, "裤装类型",
                          PANTS_OF_MATERIAL.get(fields.get("裤装材质") or "", ()), rng, fixed)

    # 等效焦段 ↔ 景深：广角做不出极浅景深
    if (fields.get("等效焦段") in NO_ULTRA_SHALLOW
            and (fields.get("景深") or "").startswith("极浅")):
        if not _repair(fields, "景深", [v for v in FIELD_OPTIONS.get("景深", ())
                                        if not v.startswith("极浅")], rng, fixed):
            _repair(fields, "等效焦段", TELE_LENS, rng, fixed)

    # 画面瞬间 → 头部方向与视线
    moment = fields.get("画面瞬间") or ""
    head = fields.get("头部方向") or ""
    gaze = fields.get("视线") or ""
    if "抬头" in moment:
        if "头部方向" not in fixed:
            put("头部方向", "头部上扬")
            head = "头部上扬"
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "整理袖口")
    elif "低头" in moment:
        if "头部方向" not in fixed:
            put("头部方向", "头部轻微低下")
            head = "头部轻微低下"
        elif "画面瞬间" not in fixed:
            put("画面瞬间", "整理袖口")

    # 头部方向 ↔ 视线：手选视线时反过来定头
    head = fields.get("头部方向") or ""
    gaze = fields.get("视线") or ""
    if head and gaze and head in GAZE_OF_HEAD and gaze not in GAZE_OF_HEAD[head]:
        if "视线" in fixed and "头部方向" in fixed:
            pass  # 两个都手选了，照用户写的，一个字都不动
        elif "视线" in fixed:
            heads = [h for h in HEAD_OF_GAZE.get(gaze, ()) if h in FIELD_OPTIONS.get("头部方向", ())]
            if heads:
                put("头部方向", rng.choice(heads) if rng else heads[0])
        else:
            _repair(fields, "视线", GAZE_OF_HEAD[head], rng, fixed)

    # 阴雨雾霾天气 ↔ 高饱和配色
    if fields.get("天气状态") in MUTED_WEATHER and fields.get("主配色") in BOLD_PALETTES:
        if "主配色" in fixed:
            if "天气状态" not in fixed:
                put("天气状态", rng.choice(BRIGHT_WEATHER) if rng else BRIGHT_WEATHER[0])
        elif "天气状态" in fixed:
            _repair(fields, "主配色", MUTED_PALETTES, rng, fixed)
        else:
            _repair(fields, "主配色", MUTED_PALETTES, rng, fixed)

    # 景别 ↔ 主光落点：腰部以上构图不该照亮腿部
    if (fields.get("景别") in NO_LEG_LIGHT_FRAMING
            and fields.get("照明落点") == "腿部与鞋子"):
        if "照明落点" in fixed:
            if "景别" not in fixed:
                put("景别", rng.choice(FULL_BODY_FRAMING) if rng else FULL_BODY_FRAMING[0])
        elif "景别" in fixed:
            _repair(fields, "照明落点",
                    ["面部与肩颈", "上半身", "服装材质", "面部与双眼"], rng, fixed)
        else:
            _repair(fields, "照明落点",
                    ["面部与肩颈", "上半身", "服装材质", "面部与双眼"], rng, fixed)

    # 发色模式＝整体发色：色调与染色方式由发色统一推导
    hair_color = fields.get("发色") or ""
    if fields.get("发色模式") == "整体发色":
        if hair_color in HAIR_DYE_MODE and "染色方式" not in fixed:
            put("染色方式", HAIR_DYE_MODE[hair_color])
        if hair_color in HAIR_TONE_OF and "发色色调" not in fixed:
            put("发色色调", HAIR_TONE_OF[hair_color])

    # 发色 ↔ 染色方式：非本色发色不能说「保持原生」
    hair_color = fields.get("发色") or ""
    if hair_color and hair_color not in NATURAL_HAIR:
        if fields.get("染色方式") == "本色":
            if "发色" in fixed:
                if "染色方式" not in fixed:
                    put("染色方式", HAIR_DYE_MODE.get(hair_color) or
                        (rng.choice(DYE_MODES) if rng else DYE_MODES[0]))
            else:
                _repair(fields, "发色", NATURAL_HAIR, rng, fixed)

    # 「自然黑」的文案已经写死「自然」，不能再配漂后上色 / 一次性喷雾
    if hair_color in UNDYED_HAIR and fields.get("染色方式") in DYE_OPS:
        if "染色方式" in fixed:
            if "发色" not in fixed:
                dyed = [v for v in FIELD_OPTIONS.get("发色", ())
                        if v not in NATURAL_HAIR and v != hair_color]
                if dyed:
                    put("发色", rng.choice(dyed) if rng else dyed[0])
        else:
            put("染色方式", HAIR_DYE_MODE.get(hair_color) or "本色")

    # 「未做染色」不搭「染后褪色 / 挑染 / 根深尾浅」这类染色痕迹
    if fields.get("染色方式") == "本色" and fields.get("发色色调") in DYE_TONES:
        if "发色色调" in fixed:
            if "染色方式" not in fixed:
                put("染色方式", "全头染")
        else:
            put("发色色调", "均匀单一")

    # 时间切片 ↔ 后期调色：大白天不套夜色调
    if fields.get("时间切片") in BRIGHT_TIMES and fields.get("后期调色") in NIGHT_GRADES:
        if "后期调色" in fixed:
            if "时间切片" not in fixed:
                put("时间切片", rng.choice(NIGHT_TIMES) if rng else NIGHT_TIMES[0])
        elif "时间切片" in fixed:
            _repair(fields, "后期调色", DAY_GRADES, rng, fixed)
        else:
            _repair(fields, "后期调色", DAY_GRADES, rng, fixed)

    # 收尾保险：最后一步可能又摘掉了外套，颜色/面料/图案不能留
    if fields.get("外套类型") == "无外套":
        for key in ("外套颜色", "外套材质", "外套图案"):
            if key not in fixed:
                fields.pop(key, None)
        if (fields.get("穿搭结构") in ("外套叠穿", "内搭加外套", "西装套装")
                and "穿搭结构" not in fixed):
            put("穿搭结构", "单件上装")

    # 室内场景不写天气
    place = fields.get("场景地点") or ""
    if place and not any(k in place for k in OUTDOOR_HINTS) and "天气状态" not in fixed:
        fields.pop("天气状态", None)
    return fields


def _align_categories(fields, fixed, rng):
    """大类与从属项对齐。

    从属项是手选的 → 大类跟着它走（大类进不了正文，改它没人看得出）；
    从属项没被手选 → 拉进大类范围里，实在对不上才改大类。
    """
    fixed = set(fixed or ())

    # ---- 族裔：族裔大类 ↔ 地域族裔分支
    cat = fields.get("族裔大类") or ""
    branch = fields.get("地域族裔分支") or ""
    group = [v for v in BRANCH_OF_ETHNICITY.get(cat, ())
             if v in FIELD_OPTIONS.get("地域族裔分支", ())]
    if branch and "地域族裔分支" in fixed:
        parent = BRANCH_PARENT.get(branch)
        if (parent and "族裔大类" not in fixed
                and parent in FIELD_OPTIONS.get("族裔大类", ())):
            fields["族裔大类"] = parent
    elif group and branch and branch not in group:
        if "族裔大类" in fixed and "地域族裔分支" in fixed:
            pass  # 两个都手选了，照用户写的
        elif "族裔大类" in fixed:
            fields["地域族裔分支"] = rng.choice(group) if rng is not None else group[0]
        else:
            parent = BRANCH_PARENT.get(branch)
            if parent:
                fields["族裔大类"] = parent

    # ---- 场景：场景大类 ↔ 场景地点
    place = fields.get("场景地点") or ""
    scene_cat = fields.get("场景大类") or ""
    places = [v for v in LOCATIONS_OF_SCENE.get(scene_cat, ())
              if v in FIELD_OPTIONS.get("场景地点", ())]
    if place and "场景地点" in fixed:
        parent = SCENE_OF_LOCATION.get(place)
        if parent and "场景大类" not in fixed:
            fields["场景大类"] = parent
    elif places and place and place not in places:
        if "场景大类" in fixed and "场景地点" in fixed:
            pass  # 两个都手选了，照用户写的
        elif "场景大类" in fixed:
            fields["场景地点"] = rng.choice(places) if rng is not None else places[0]
            _reapply_package(fields, fixed, fields["场景地点"], rng)
        else:
            parent = SCENE_OF_LOCATION.get(place)
            if parent:
                fields["场景大类"] = parent
    elif place and not scene_cat:
        parent = SCENE_OF_LOCATION.get(place)
        if parent:
            fields["场景大类"] = parent
    return fields


def _reapply_package(fields, fixed, place, rng=None):
    """换了场景地点，配套的前景/背景/细节也跟着换，避免场景与背景两张皮。"""
    package = SCENE_PACKAGE.get(place or "") or {}
    scene_cat = SCENE_OF_LOCATION.get(place or "") or (fields.get("场景大类") or "")
    for key in SCENE_PACKAGE_FIELDS:
        if key not in fields or key in fixed:
            continue
        value = package.get(key)
        if value in FIELD_OPTIONS.get(key, ()) and value != place:
            fields[key] = value
            continue
        if not scene_cat or rng is None:
            continue
        # 新场景没有现成配套，就在它所属类别里挑与场景名最贴的，别留上一个场景的背景
        pool = _package_pool(key, place, scene_cat)
        if pool:
            fields[key] = rng.choice(pool)
        else:
            fields.pop(key, None)


def resolve_fields(preset, scope, seed, values):
    """三态字段 + 随机范围的落值。

    跟随预设   → 用预设值；随机范围决定这一项要不要跳出预设（局部微调只动细节…
    随机抽取   → 真的从整个词库里抽，只会被大类从属和场景配套收窄
    不使用     → 该字段整条不出现
    手选具体值 → 原样保留，任何一致性规则都绕开它
    """
    preset_values = PRESET_TABLE.get(preset) or {}
    rng = random.Random(int(seed) & MAX_SEED)
    out, explicit = {}, set()
    for name in FIELD_ORDER:
        if name not in FIELD_OPTIONS:
            continue
        choice = values.get(name, RANDOM_CHOICE)
        if choice == EMPTY_CHOICE:
            continue
        if choice == FOLLOW_PRESET:
            keep = _follows_preset(scope, name)
            if keep and preset_values.get(name) in FIELD_OPTIONS.get(name, ()):
                out[name] = preset_values[name]
            else:
                out[name] = _pick_for(name, preset, scope, out, rng)
            continue
        if choice in FIELD_TEXT.get(name, {}):
            out[name] = choice
            explicit.add(name)
        else:
            # 随机抽取（以及词库里已不存在的旧值）都走抽取
            out[name] = _pick_for(name, preset, scope, out, rng)
    _align_categories(out, explicit, rng)
    # 场景换了地方，配套的前景/背景/细节不能还留在上一个场景
    preset_place = preset_values.get("场景地点")
    if out.get("场景地点") and out["场景地点"] != preset_place:
        _reapply_package(out, explicit, out["场景地点"], rng)
    return _harmonize(out, rng, explicit)


# ---------------------------------------------------------------- 成句
def _text(fields, name):
    value = fields.get(name)
    if not value:
        return ""
    return FIELD_TEXT.get(name, {}).get(value, "")


def _en(fields, name):
    value = fields.get(name)
    if not value:
        return ""
    text = FIELD_EN.get(name, {}).get(value, "") or ""
    # 材质和颜色都用 in 开头会连成 "in white, in suede"，材质换一种说法
    if name.endswith("材质") and text.startswith("in "):
        text = "made of " + text[3:]
    return text


def _brief(fields, name):
    value = fields.get(name)
    if not value:
        return ""
    return FIELD_BRIEF.get(name, {}).get(value, "")


def _want(level_cap, name, explicit=()):
    """这个字段要不要进正文。

    手选的字段一律进（密度只裁自动填充的细节，不裁用户点的东西），
    其余按字段等级跟密度比。
    """
    return name in explicit or FIELD_LEVEL.get(name, 2) <= level_cap


LEVEL_CAP = {"精简": 1, "标准": 2, "详细": 3}


def _join_zh(parts):
    clean = [str(p).strip().strip("，。；、,.;") for p in parts if p and str(p).strip()]
    return "，".join(clean) + "。" if clean else ""


def _join_en(parts):
    clean = [str(p).strip().strip(".,;") for p in parts if p and str(p).strip()]
    return ", ".join(clean) + "." if clean else ""


def _identity_zh(fields):
    age = _text(fields, "年龄阶段")
    branch = fields.get("地域族裔分支") or ""
    cat = fields.get("族裔大类") or ""
    if age and branch and branch != "大类通用外观":
        adj = _text(fields, "地域族裔分支").replace("成年男性", "").strip()
        if adj:
            return "一位%s、具有%s的成年男性" % (age, adj)
    if age and cat:
        return "一位%s的%s" % (age, _text(fields, "族裔大类"))
    if age:
        return "一位%s的成年男性" % age
    return "一位成年男性"


def _identity_en(fields):
    age = _text(fields, "年龄阶段")
    number = re.search(r"\d+", age)
    base = "an adult man"
    if number:
        base = "an adult man around %s years old" % number.group(0)
    branch_en = (_en(fields, "地域族裔分支") or "").strip()
    if not branch_en:
        branch_en = (_en(fields, "族裔大类") or "").strip()
    if branch_en:
        base += " of %s appearance" % branch_en
    return base


def _aspect_zh(value):
    match = re.match(r"^(\d+:\d+)(竖|横|方形)构图$", value or "")
    return "%s %s构图" % (match.group(1), match.group(2)) if match else (value or "")


def _aspect_en(value):
    width, height = ASPECT_RESOLUTIONS.get(value or "", (0, 0))
    match = re.match(r"^(\d+:\d+)", value or "")
    ratio = match.group(1) if match else "portrait"
    if width and height:
        orient = "square" if width == height else ("landscape" if width > height else "portrait")
    else:
        orient = "portrait"
    return "%s %s composition" % (ratio, orient)


def _module_theme(fields, cap, explicit=()):
    parts = []
    if _want(cap, "画面比例", explicit):
        parts.append(_aspect_zh(fields.get("画面比例") or ""))
    for name in ("成像媒介", "写真主题", "写真大类", "气质类型", "场合氛围"):
        if _want(cap, name, explicit):
            parts.append(_text(fields, name))
    return _join_zh(parts)


def _module_person(fields, cap, explicit=()):
    parts = [_identity_zh(fields)]
    for name in MODULES[1][1]:
        if name in CONTROL_ONLY or not _want(cap, name, explicit):
            continue
        parts.append(_text(fields, name))
    return _join_zh(parts)


def _module_cloth(fields, cap, explicit=()):
    """服装模块：版型细节里混着上装和裤装的说法，按选项内容插到正确位置。"""
    def piece(name):
        if name in CONTROL_ONLY or not _want(cap, name, explicit):
            return ""
        return _text(fields, name)

    fit_name = fields.get("版型细节") or ""
    fit = piece("版型细节")
    fit_top = fit if fit_name in FIT_TOP else ""
    fit_bottom = fit if fit_name in FIT_BOTTOM else ""
    fit_neutral = fit if fit and not (fit_top or fit_bottom) else ""
    parts = [piece("穿搭结构"), piece("外套类型"), piece("外套颜色"), piece("外套材质"),
             piece("外套图案"), piece("内搭类型"), piece("内搭颜色"), piece("内搭材质"),
             fit_top, piece("裤装类型"), piece("裤装颜色"), piece("裤装材质"), fit_bottom,
             piece("袜装"), piece("鞋履"), piece("服装配件"), piece("腕表配饰"),
             fit_neutral]
    return _join_zh(parts)


def _module_cloth_en(fields, cap, explicit=()):
    def piece(name):
        if name in CONTROL_ONLY or not _want(cap, name, explicit):
            return ""
        return _en(fields, name)

    fit_name = fields.get("版型细节") or ""
    fit = piece("版型细节")
    fit_top = fit if fit_name in FIT_TOP else ""
    fit_bottom = fit if fit_name in FIT_BOTTOM else ""
    fit_neutral = fit if fit and not (fit_top or fit_bottom) else ""
    parts = [piece("穿搭结构"), piece("外套类型"), piece("外套颜色"), piece("外套材质"),
             piece("外套图案"), piece("内搭类型"), piece("内搭颜色"), piece("内搭材质"),
             fit_top, piece("裤装类型"), piece("裤装颜色"), piece("裤装材质"), fit_bottom,
             piece("袜装"), piece("鞋履"), piece("服装配件"), piece("腕表配饰"),
             fit_neutral]
    return _join_en(parts)


def _module_simple(fields, cap, module, explicit=()):
    """发型 / 服装 / 姿态 / 场景 / 光影 / 镜头 / 收尾 都是同一套串接规则。"""
    names = next(n for m, n in MODULES if m == module)
    parts = []
    for name in names:
        if name in CONTROL_ONLY or not _want(cap, name, explicit):
            continue
        parts.append(_text(fields, name))
    return _join_zh(parts)


def compose_prompt_text(fields, density, separate_modules=False, explicit=()):
    cap = LEVEL_CAP.get(density, 2)
    blocks = []
    for module, _names in MODULES:
        if module == "主题":
            text = _module_theme(fields, cap, explicit)
        elif module == "人物":
            text = _module_person(fields, cap, explicit)
        elif module == "服装":
            text = _module_cloth(fields, cap, explicit)
        else:
            text = _module_simple(fields, cap, module, explicit)
        if text:
            blocks.append(text)
    if not blocks:
        return ""
    if separate_modules:
        return "\n\n".join(blocks)
    return "".join(blocks)


def _module_theme_en(fields, cap, explicit=()):
    parts = [_aspect_en(fields.get("画面比例") or "")]
    for name in ("成像媒介", "写真主题", "写真大类", "气质类型"):
        if _want(cap, name, explicit):
            parts.append(_en(fields, name))
    return _join_en(parts)


def _module_person_en(fields, cap, explicit=()):
    parts = [_identity_en(fields)]
    for name in MODULES[1][1]:
        if name in CONTROL_ONLY or not _want(cap, name, explicit):
            continue
        parts.append(_en(fields, name))
    return _join_en(parts)


def compose_english_prompt_text(fields, density, separate_modules=False, explicit=()):
    cap = LEVEL_CAP.get(density, 2)
    blocks = []
    for module, names in MODULES:
        if module == "主题":
            text = _module_theme_en(fields, cap, explicit)
        elif module == "人物":
            text = _module_person_en(fields, cap, explicit)
        elif module == "服装":
            text = _module_cloth_en(fields, cap, explicit)
        else:
            parts = [_en(fields, name) for name in names
                     if name not in CONTROL_ONLY and _want(cap, name, explicit)]
            text = _join_en(parts)
        if text:
            blocks.append(text)
    if not blocks:
        return ""
    if separate_modules:
        return "\n\n".join(blocks)
    return " ".join(blocks)


def join_prompt_text(free, structured, position):
    free = (free or "").strip()
    structured = (structured or "").strip()
    if not free:
        return structured
    if not structured:
        return free
    if position == PROMPT_JOIN_POSITIONS[1]:
        head, tail = structured, free
    else:
        head, tail = free, structured
    sep = " " if head.endswith(("。", "，", "；", ",", ".", ";")) else "。"
    return head + sep + tail


def join_prompt_paragraphs(first, second):
    return "\n\n".join(p for p in (first, second) if p and p.strip())


# ---------------------------------------------------------------- 分辨率
def calculate_pixel_resolution(aspect, pixels_wan=100.0, multiple=8):
    if aspect not in ASPECT_RESOLUTIONS:
        aspect = list(ASPECT_RESOLUTIONS)[3]
    base_w, base_h = ASPECT_RESOLUTIONS[aspect]
    ratio = base_w / float(base_h)
    target = float(pixels_wan) * 10000.0
    step = max(8, int(multiple))
    height = (target / ratio) ** 0.5
    width = height * ratio
    w = max(step, int(round(width / step)) * step)
    h = max(step, int(round(height / step)) * step)
    return int(w), int(h)


def resolution_from_options(aspect, options):
    mode = options.get("分辨率模式", PIXEL_BUDGET_MODE)
    if mode == "原推荐尺寸":
        return ASPECT_RESOLUTIONS.get(aspect, (832, 1248))
    if mode == "按总像素计算":
        return calculate_pixel_resolution(aspect, float(options.get("目标总像素", 1.0)) * 100.0,
                                          options.get("尺寸对齐倍数", 8))
    return calculate_pixel_resolution(aspect, options.get("目标总像素（万）", 100.0),
                                      options.get("尺寸对齐倍数", 8))


# ---------------------------------------------------------------- 节点本体
class SunsetMalePromptBuilder:

    CATEGORY = "TaiYang"
    SEARCH_ALIASES = ["taiyang", "tai yang", "太阳", "男性人像", "男性摄影", "男性角色", "男性", "男装", "male", "cosplay"]

    FUNCTION = "build_prompt"
    RETURN_TYPES = ("STRING", "INT", "INT", "STRING")
    RETURN_NAMES = ("中文提示词", "推荐宽度", "推荐高度", "英文提示词")
    OUTPUT_NODE = False
    DESCRIPTION = (
        "男性人像摄影师模板：92 项字段（人物 / 发型 / 男装 / 姿态 / 场景 / 光影 / 镜头 / 收尾），"
        "中英双语自然语句输出，附推荐分辨率。"
    )

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "预设": (PRESET_OPTIONS,),
            "提示词密度": (
                PROMPT_DENSITIES,
                {"default": "标准",
                 "tooltip": "精简只留核心项，标准保留主要摄影信息，详细保留全部字段细节。"
                            "手选过的字段不受密度影响，一定会写进去。"},
            ),
            "随机范围": (
                RANDOM_SCOPES,
                {"tooltip": "只管「跟随预设」的字段：局部微调只动细节，同主题重拍保留主题与人物，"
                            "跨风格混搭连主题一起换。字段自己选了「随机抽取」就一律全库随机。"},
            ),
            "随机种子": (
                "INT",
                {"default": 0, "min": 0, "max": MAX_SEED,
                 "control_after_generate": True,
                 "tooltip": "相同选项和相同种子会生成相同提示词。"},
            ),
        }
        for name in FIELD_ORDER:
            options = FIELD_OPTIONS.get(name) or []
            if not options:
                continue
            inputs[name] = (
                [FOLLOW_PRESET, RANDOM_CHOICE, EMPTY_CHOICE, *options],
                {"default": FOLLOW_PRESET},
            )
        optional = {}
        optional["自由提示词"] = (
            "STRING",
            {"default": "", "multiline": True, "dynamicPrompts": False,
             "tooltip": "自写正向提示词，中英文输出都会原样保留，按拼接位置组合。"},
        )
        optional["拼接位置"] = (
            PROMPT_JOIN_POSITIONS,
            {"default": "自由提示词在前",
             "tooltip": "决定自由提示词与结构化模块的先后顺序。"},
        )
        optional["输出排版"] = (
            LAYOUT_OPTIONS,
            {"default": "按模块分段",
             "tooltip": "按模块分段用空行分隔；连续拼接合成一整段。"},
        )
        for module_name, input_name in USER_MODULE_INPUTS.items():
            optional[input_name] = (
                "STRING",
                {"default": "", "multiline": True, "dynamicPrompts": False,
                 "tooltip": "外部模块词库写入的%s描述。" % module_name},
            )
        optional.update(RESOLUTION_INPUTS)
        return {"required": inputs, "optional": optional}

    def build_prompt(self, **kwargs):
        preset = kwargs.pop("预设", PRESET_OPTIONS[0])
        density = kwargs.pop("提示词密度", "标准")
        scope = kwargs.pop("随机范围", RANDOM_SCOPES[0])
        seed = kwargs.pop("随机种子", 0)
        free_prompt = kwargs.pop("自由提示词", "")
        join_position = kwargs.pop("拼接位置", PROMPT_JOIN_POSITIONS[0])
        separate = kwargs.pop("输出排版", LAYOUT_OPTIONS[0]) == "按模块分段"
        resolution_options = {name: kwargs.pop(name) for name in RESOLUTION_INPUTS
                              if name in kwargs}
        user_fragments = {module: kwargs.pop(input_name, "")
                          for module, input_name in USER_MODULE_INPUTS.items()}

        # 用户手选的字段：密度不能把它们裁掉
        explicit = {n for n in FIELD_ORDER
                    if isinstance(kwargs.get(n), str) and kwargs.get(n) in FIELD_TEXT.get(n, {})}
        fields = resolve_fields(preset, scope, seed, kwargs)

        def supplied(module):
            value = user_fragments.get(module, "")
            return value.strip().strip("，。；,.;") if isinstance(value, str) else ""

        blocks = []
        for module, _names in MODULES:
            if module == "主题":
                text = supplied("画面基础") or _module_theme(fields, LEVEL_CAP.get(density, 2), explicit)
            elif module == "人物":
                text = supplied("人物") or _module_person(fields, LEVEL_CAP.get(density, 2), explicit)
            elif module == "发型":
                text = supplied("发型") or _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            elif module == "服装":
                text = supplied("服装") or _module_cloth(fields, LEVEL_CAP.get(density, 2), explicit)
            elif module == "姿态":
                text = supplied("姿态动作") or _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            elif module == "场景":
                text = supplied("场景") or _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            elif module == "光影":
                text = _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            elif module == "镜头":
                text = supplied("摄影") or _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            else:
                text = supplied("视觉表现") or _module_simple(fields, LEVEL_CAP.get(density, 2), module, explicit)
            if text:
                blocks.append(text if text.endswith("。") else text + "。")
        custom = supplied("自定义")
        if custom:
            blocks.append(custom + "。" if not custom.endswith("。") else custom)

        structured = ("\n\n" if separate else "").join(blocks)
        if separate:
            prompt = (join_prompt_paragraphs(free_prompt, structured)
                      if join_position == PROMPT_JOIN_POSITIONS[0]
                      else join_prompt_paragraphs(structured, free_prompt))
        else:
            prompt = join_prompt_text(free_prompt, structured, join_position)

        english_blocks = []
        for module, _names in MODULES:
            if module == "主题":
                text = _module_theme_en(fields, LEVEL_CAP.get(density, 2), explicit)
            elif module == "人物":
                text = _module_person_en(fields, LEVEL_CAP.get(density, 2), explicit)
            else:
                names = next(n for m, n in MODULES if m == module)
                text = _join_en([_en(fields, name) for name in names
                                 if name not in CONTROL_ONLY
                                 and _want(LEVEL_CAP.get(density, 2), name, explicit)])
            if text:
                english_blocks.append(text)
        english_structured = ("\n\n" if separate else " ").join(english_blocks)
        if separate:
            english_prompt = (join_prompt_paragraphs(free_prompt, english_structured)
                              if join_position == PROMPT_JOIN_POSITIONS[0]
                              else join_prompt_paragraphs(english_structured, free_prompt))
        else:
            english_prompt = join_prompt_text(free_prompt, english_structured, join_position)

        aspect = fields.get("画面比例")
        if aspect not in ASPECT_RESOLUTIONS:
            aspect = list(ASPECT_RESOLUTIONS)[3]
        width, height = resolution_from_options(aspect, resolution_options)
        return {
            "ui": {
                "中文提示词": [prompt],
                "推荐宽度": [width],
                "推荐高度": [height],
                "英文提示词": [english_prompt],
            },
            "result": (prompt, width, height, english_prompt),
        }


NODE_CLASS_MAPPINGS = {
    "SunsetMalePromptBuilder": SunsetMalePromptBuilder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SunsetMalePromptBuilder": "⚡提示词男性人像",
}

# ---------------------------------------------------------------- 我的预设（存盘）
MALE_PRESETS_FILE = LIB_ROOT / "user_presets.json"


def _read_presets():
    if not MALE_PRESETS_FILE.exists():
        return {}
    try:
        text = MALE_PRESETS_FILE.read_text(encoding="utf-8-sig")
        data = json.loads(text) if text.strip() else {}
    except Exception as exc:
        logging.debug("[SunsetMale] 预设文件解析失败（未改动）：%s" % exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_presets(data):
    MALE_PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = MALE_PRESETS_FILE.with_name("user_presets.tmp.json")
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(MALE_PRESETS_FILE)


def _register_routes():
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception:
        return False
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return False
    routes = server.routes

    @routes.get("/luori/male_presets")
    async def male_presets_get(request):
        return web.json_response(_read_presets())

    @routes.post("/luori/male_presets")
    async def male_presets_post(request):
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return web.json_response({"error": "bad request"}, status=400)
        data = _read_presets()
        action = body.get("action")
        if action == "save":
            name = str(body.get("name") or "").strip()
            values = body.get("values")
            if not name or not isinstance(values, dict):
                return web.json_response({"error": "bad request"}, status=400)
            data[name] = values
        elif action == "delete":
            data.pop(str(body.get("name") or ""), None)
        else:
            return web.json_response({"error": "bad request"}, status=400)
        try:
            _write_presets(data)
        except OSError:
            return web.json_response({"error": "preset_write_failed"}, status=500)
        return web.json_response(data)

    logging.debug("[SunsetMale] 预设接口就绪：/luori/male_presets")
    return True


try:
    _register_routes()
except Exception as _exc:
    logging.debug("[SunsetMale] 预设接口未注册：%s" % _exc)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "SunsetMalePromptBuilder",
    "FIELD_ORDER",
    "FIELD_OPTIONS",
    "PRESET_OPTIONS",
    "library_stats",
    "resolve_fields",
    "compose_prompt_text",
]
