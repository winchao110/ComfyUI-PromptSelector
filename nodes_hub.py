# -*- coding: utf-8 -*-
"""✨ 提示词抽取（PromptPuller）

一颗节点装下本包的 7 个抽词节点：

    整句词库 · Krea2卡池 · 摄影搭配 · 穿搭预设 · 权威摄影 · 19+自选

**抽取规则一律不动。** 每个模式拿的就是原节点自己的 INPUT_TYPES 和它自己的成句函数，
参数一对一喂进去、结果一对一贴到右侧提示词框，中间没有任何合并、改写或二次拼装。
这里只做三件事：

    1. 把原节点那些 hidden 的控件换成能看能点的面板（分组可折叠、可搜索）；
    2. 改任何一项立即 POST 回后端重算，把文本写进右侧框（「即时抽取」）；
    3. 入队时优先用框里的字，框是空的才按参数回算，跟以前那 6 颗节点的输出完全一致。
"""

import re
import json
import logging

LOG = logging.getLogger("Sunset.Hub")

try:
    from .nodes_krea2 import Krea2PromptPicker
    from .nodes_zimage import (
        ZImagePromptGeneratorNode,
        ZImagePromptLoaderNode,
        ZImageFashionPresetLoaderNode,
    )
    from .nodes_nsfw import SunsetNSPromptSelector
    from .nodes_lr import SunsetLRPromptBuilder
    from .nodes_male import SunsetMalePromptBuilder, MODULES as MALE_MODULES
except ImportError:  # 允许脱离包独立调试
    from nodes_krea2 import Krea2PromptPicker
    from nodes_zimage import (
        ZImagePromptGeneratorNode,
        ZImagePromptLoaderNode,
        ZImageFashionPresetLoaderNode,
    )
    from nodes_nsfw import SunsetNSPromptSelector
    from nodes_lr import SunsetLRPromptBuilder
    from nodes_male import SunsetMalePromptBuilder, MODULES as MALE_MODULES


NODE_TITLE = "✨ 提示词抽取"
SCHEMA_VERSION = 5

# ---------------------------------------------------------------- 七个模式
# key, 节点类, 显示名, 图标
SOURCES = [
    ("Z", ZImagePromptLoaderNode, "整句词库", "📜"),
    ("K", Krea2PromptPicker, "Krea2卡池", "🎴"),
    ("G", ZImagePromptGeneratorNode, "摄影搭配", "🧩"),
    ("F", ZImageFashionPresetLoaderNode, "穿搭预设", "👗"),
    ("L", SunsetLRPromptBuilder, "权威摄影", "🎬"),
    ("M", SunsetMalePromptBuilder, "男性摄影", "🕴"),
    ("N", SunsetNSPromptSelector, "19+自选", "🔞"),
]
MODE_CLS = {k: c for k, c, _n, _i in SOURCES}
MODE_NAME = {k: n for k, _c, n, _i in SOURCES}
MODE_ICON = {k: i for k, _c, _n, i in SOURCES}
MODE_LABEL = {k: "%s %s" % (MODE_ICON[k], MODE_NAME[k]) for k in MODE_CLS}
KEY_BY_LABEL = {v: k for k, v in MODE_LABEL.items()}
KEY_ORDER = [k for k, _c, _n, _i in SOURCES]
DEFAULT_KEY = "G"

# 各模式一句话说明（面板顶部提示）
MODE_HINT = {
    "Z": "从整句词库抽一整条，成句方式与原「整句词库」节点完全一致。",
    "K": "Krea2 抽卡器，单个词池抽一条或按分隔符拼合，规则同原节点。",
    "G": "按风格/人物/装扮/画面拼句，规则同原「摄影搭配」节点。",
    "F": "从穿搭预设里取一整套描述，规则同原「穿搭预设」节点。",
    "L": "权威摄影模板，112 项可调，输出中文/英文/推荐分辨率。",
    "M": "男性摄影模板，92 项可调（人物/男装/姿态/场景/光影/镜头），输出中文/英文/推荐分辨率。",
    "N": "19+ 自选，逐项挑，输出正面 + 负面提示词。",
}

# ---------------------------------------------------------------- 哪些字段不进面板
# 只挡「纯技术项」：外部词库目录、拼合方式、分隔符、词库文件路径、只读提示；
# 以及 Krea2 的 12 个分卷词池开关（用户明确说没用，后台按需补默认值）。
BLOCK_FIELDS = {
    ("K", "prompt_dir"), ("K", "mode"), ("K", "separator"), ("K", "使用提示"),
    ("Z", "文件路径"),
    ("L", "文件路径"),
    # 右侧即时框回写用的隐藏控件，本身不是选项
    ("Z", "即时提示词"), ("K", "即时提示词"), ("G", "即时提示词"),
    ("F", "即时提示词"), ("L", "即时提示词"), ("M", "即时提示词"),
    ("N", "即时提示词"),
    ("Z", "运行重抽"), ("K", "运行重抽"), ("G", "运行重抽"),
    ("F", "运行重抽"), ("L", "运行重抽"), ("M", "运行重抽"),
    ("N", "运行重抽"),
}
BLOCK_NAME_RE = re.compile(r"^(提示词|part)\d+$")

# Krea2 那些分卷词池不进面板：统一按 False 传，用户用下面的套装开关即可
K_HIDDEN_POOLS = ["提示词%d" % i for i in range(1, 13)]

# 字段改名，避免同一个中文名在几个模式下含义不同
RELABEL = {
    ("N", "触发词"): "主体构成",
    ("N", "预设配置"): "场景预设",
    ("L", "预设"): "模板预设",
    ("L", "自由提示词"): "自由提示词（权威）",
    ("L", "目标总像素（万）"): "目标总像素(万)",
    ("M", "预设"): "模板预设",
    ("M", "自由提示词"): "自由提示词（男性）",
    ("M", "目标总像素（万）"): "目标总像素(万)",
    ("K", "超强中文模式"): "超强中文词池",
    ("G", "细节级别"): "细节级别",
}

# 英文键名统一中文
COMMON_LABELS = {
    "seed": "随机种子",
    "NSFW": "NSFW 内容",
    "prompt_input": "外部提示词",
}


def _dropped(mode, name):
    if (mode, name) in BLOCK_FIELDS:
        return True
    if mode == "K" and name in K_HIDDEN_POOLS:
        return True
    if BLOCK_NAME_RE.match(name) and mode != "L":
        return True
    return False


# ---------------------------------------------------------------- 分组（纯展示用）
LR_GROUP_ORDER = [
    "模板与密度", "画面基调", "人物", "发型与头部", "服装", "姿态与表情",
    "场景", "光照", "色彩", "镜头构图", "收尾质感", "自定义", "其它",
]

G_FIELD_GROUP = {
    "风格主题": "风格与主题", "拍摄风格": "风格与主题", "拍摄类型": "风格与主题",
    "细节级别": "风格与主题", "细節级别": "风格与主题",
    "年龄": "人物", "身材": "人物", "种族选择": "人物", "美瞳选择": "人物",
    "动作": "姿态与动作", "包含姿势描述": "姿态与动作",
    "情趣衣服": "装扮", "丝袜类型": "装扮", "头部配饰": "装扮", "鞋子类型": "装扮",
    "景别": "画面与收尾", "包含高级细节": "画面与收尾", "包含画质参数": "画面与收尾",
    "包含后缀参数": "画面与收尾", "启用前景特效": "画面与收尾",
    "触发词开关": "触发词", "触发词内容": "触发词",
    "seed": "抽取控制", "NSFW": "抽取控制",
}
G_GROUP_ORDER = ["风格与主题", "人物", "装扮", "姿态与动作", "画面与收尾", "触发词", "抽取控制"]

N_FIELD_GROUP = {
    "触发词": "主体",
    "预设配置": "主体", "质量等级": "主体", "视觉风格": "主体",
    "场景类型": "场景", "光源类型": "光照", "光线类型": "光照", "色调": "色彩",
    "动作姿态": "动作与情绪", "情绪氛围": "动作与情绪",
    "服饰": "服饰",
    "运镜方式": "镜头", "机位角度": "镜头", "镜头类型": "镜头",
    "焦距": "镜头", "特效镜头": "镜头", "镜头滤镜": "镜头",
    "随机选择": "抽取控制", "权重_场景": "权重", "权重_动作": "权重",
    "权重_服饰": "权重", "权重_情绪": "权重",
    "自定义前缀": "自定义", "自定义后缀": "自定义", "前置提示词": "自定义",
    "负面提示词类型": "负面", "自定义负面提示词": "负面",
}
N_GROUP_ORDER = ["主体", "场景", "光照", "色彩", "动作与情绪", "服饰",
                 "镜头", "权重", "负面", "自定义", "抽取控制"]

K_GROUP = {
    "seed": "抽取控制", "超强中文模式": "抽取控制", "NSFW": "抽取控制",
    "触发词开关": "触发词", "触发词内容": "触发词",
    "大呲花词库": "词池", "KOOK词库": "词池", "SFW词库": "词池", "19+词库": "词池",
}
K_GROUP_ORDER = ["抽取控制", "词池", "触发词"]


_LR_SETS = None


def _lr_sets():
    """权威摄影的字段按它自己的常量表归组。"""
    global _LR_SETS
    if _LR_SETS is None:
        try:
            from . import nodes_lr as LR
        except ImportError:
            import nodes_lr as LR

        def const(n):
            v = getattr(LR, n, ())
            return set(v) if isinstance(v, (list, tuple)) else set()

        mods = getattr(LR, "USER_MODULE_INPUTS", {})
        _LR_SETS = [
            ("模板与密度", {"预设", "提示词密度", "随机范围", "随机种子",
                            "拼接位置", "输出排版"}),
            ("画面基调", {"画面比例", "成像媒介", "写真大类", "写真主题",
                          "分辨率模式", "目标总像素", "尺寸对齐倍数"}),
            ("人物", {"年龄阶段", "族裔大类", "地域族裔分支"} | const("PERSON_OUTPUT_FIELDS")),
            ("发型与头部", {"发色模式", "发色", "发色色调", "染色方式", "头发长度",
                            "发质与卷度", "发型造型", "刘海", "头部配饰"}),
            ("服装", const("CLOTHING_OUTPUT_FIELDS")),
            ("姿态与表情", const("POSE_OUTPUT_FIELDS")),
            ("场景", const("SCENE_GROUP_FIELDS")),
            ("光照", const("LIGHTING_OUTPUT_FIELDS")),
            ("色彩", const("COLOR_OUTPUT_FIELDS")),
            ("镜头构图", {"景别", "画面布局", "等效焦段", "拍摄距离", "机位",
                          "景深", "对焦位置"} | const("CAMERA_OUTPUT_FIELDS")),
            ("收尾质感", const("FINISH_OUTPUT_FIELDS")),
            ("自定义", set(mods.values()) if isinstance(mods, dict) else set()),
        ]
    return _LR_SETS


Z_CTRL = {"超强模式", "随机模式", "seed"}
TRIGGER_FIELDS = {"触发词开关", "触发词内容"}
F_CTRL = {"seed", "润色模式"}


MALE_MODULE_TITLES = [title for title, _names in MALE_MODULES]


def _group_of(mode, name, fallback):
    if mode == "Z":
        if name in Z_CTRL:
            return "抽取控制"
        if name in TRIGGER_FIELDS:
            return "触发词"
        return "词库分类"
    if mode == "F":
        return "抽取控制" if name in F_CTRL else "选项"
    if mode == "L":
        for title, keys in _lr_sets():
            if name in keys:
                return title
        return "其它"
    if mode == "M":
        if name in ("预设", "提示词密度", "随机范围", "随机种子",
                    "拼接位置", "输出排版", "分辨率模式", "目标总像素",
                    "目标总像素（万）", "尺寸对齐倍数"):
            return "模板与密度"
        for title, names in MALE_MODULES:
            if name in names:
                return title
        return "自定义"
    if mode == "G":
        return G_FIELD_GROUP.get(name, fallback)
    if mode == "N":
        return N_FIELD_GROUP.get(name, fallback)
    if mode == "K":
        return K_GROUP.get(name, "词池")
    return "选项"


def _group_order(mode):
    if mode == "Z":
        return ["抽取控制", "词库分类", "触发词"]
    if mode == "F":
        return ["选项", "抽取控制"]
    if mode == "L":
        return LR_GROUP_ORDER
    if mode == "M":
        return ["模板与密度", *MALE_MODULE_TITLES, "自定义"]
    if mode == "G":
        return G_GROUP_ORDER
    if mode == "N":
        return N_GROUP_ORDER
    if mode == "K":
        return K_GROUP_ORDER
    return ["选项"]


# ---------------------------------------------------------------- 取值助手
def _s(v, default=""):
    return default if v is None else str(v)


def _b(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on", "是", "开")
    return bool(v)


def _i(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 字段采集
_SPEC_CACHE = {}


def _spec_of(mode, for_form=True):
    """原节点自己的 INPUT_TYPES，按 required→optional 顺序摊平。

    for_form=False 时连「面板里不显示」的技术项也一并收进来：
    浏览器发来的参数是节点上真实的控件值（含词库文件、拼合方式这些），
    要原样喂给原节点，不能因为面板不画它们就把值丢掉。
    """
    cache_key = (mode, bool(for_form))
    if cache_key in _SPEC_CACHE:
        return _SPEC_CACHE[cache_key]
    rows = []
    try:
        spec = MODE_CLS[mode].INPUT_TYPES() or {}
    except Exception as exc:
        LOG.warning("[Hub] %s 输入定义读取失败：%s", mode, exc)
        spec = {}
    for section in ("required", "optional"):
        for name, t in (spec.get(section) or {}).items():
            if not isinstance(t, (list, tuple)) or not t:
                continue
            opt = t[1] if len(t) > 1 and isinstance(t[1], dict) else {}
            if opt.get("forceInput"):      # 连线口，面板里没法画
                continue
            if opt.get("readonly"):        # 只读提示文字
                continue
            if for_form and _dropped(mode, name):
                continue
            rows.append((name, t[0], opt))
    _SPEC_CACHE[cache_key] = rows
    return rows


def _default_of(mode, name, t, opt):
    """该字段在「原节点」里的默认值。"""
    if isinstance(t, (list, tuple)):
        d = opt.get("default", t[0] if t else "")
        if isinstance(d, (list, tuple)):
            return d[0] if d else (t[0] if t else "")
        return _s(d, _s(t[0] if t else ""))
    if t == "BOOLEAN":
        return bool(opt.get("default", False))
    if t == "INT":
        return int(opt.get("default", 0) or 0)
    if t == "FLOAT":
        return float(opt.get("default", 0.0) or 0.0)
    return _s(opt.get("default", ""))


def _field_of(mode, name, t, opt):
    f = {
        "name": name,
        "label": RELABEL.get((mode, name)) or COMMON_LABELS.get(name) or name,
    }
    if isinstance(t, (list, tuple)):
        options = []
        for x in t:
            s = _s(x)
            if s not in options:
                options.append(s)
        if not options:
            return None
        f.update(type="combo", options=options, default=_default_of(mode, name, t, opt))
        if opt.get("multi_select"):
            f["multi"] = True
    elif t == "BOOLEAN":
        f.update(type="bool", default=bool(opt.get("default", False)))
    elif t == "INT":
        f.update(type="int", default=int(opt.get("default", 0) or 0),
                 min=opt.get("min", 0), max=opt.get("max", 0x7FFFFFFF),
                 step=opt.get("step", 1))
    elif t == "FLOAT":
        f.update(type="float", default=float(opt.get("default", 0.0) or 0.0),
                 min=opt.get("min", 0.0), max=opt.get("max", 1.0),
                 step=opt.get("step", 0.01))
    elif t == "STRING":
        f.update(type="text" if opt.get("multiline") else "str",
                 default=_s(opt.get("default", "")))
    else:
        return None
    if opt.get("tooltip"):
        f["tooltip"] = _s(opt["tooltip"])
    if name == "seed":
        f["field"] = "seed"
    return f


def _mode_fields(mode):
    """该模式的字段（已分组排序）。"""
    rows = []
    for name, t, opt in _spec_of(mode):
        f = _field_of(mode, name, t, opt)
        if not f:
            continue
        f["group"] = _group_of(mode, name, "选项")
        rows.append(f)
    order = _group_order(mode)
    rows.sort(key=lambda f: order.index(f["group"]) if f["group"] in order else 999)
    return rows


def mode_defaults(mode):
    """该模式的一份完整默认参数（原节点喊得动的那一套）。"""
    out = {}
    for name, t, opt in _spec_of(mode):
        out[name] = _default_of(mode, name, t, opt)
    if mode == "K":
        # 12 个分卷词池没有面板控件，统一关掉（用户开着别的池就够用了）
        for name in K_HIDDEN_POOLS:
            out[name] = False
        # 这两个是 Krea2 内部必填，节点签名里要
        out["prompt_dir"] = "./part"
        out["mode"] = "single"
        out["separator"] = ", "
    if mode == "Z":
        out["文件路径"] = "prompt_library.json"
    return out


# ---------------------------------------------------------------- schema
def build_schema():
    modes = []
    defaults = {}
    for key in KEY_ORDER:
        fields = _mode_fields(key)
        groups = []
        for f in fields:
            title = f["group"]
            g = next((x for x in groups if x["title"] == title), None)
            if g is None:
                g = {"title": title, "fields": []}
                groups.append(g)
            g["fields"].append({k: v for k, v in f.items() if k != "group"})
        modes.append({
            "key": key,
            "label": MODE_LABEL[key],
            "name": MODE_NAME[key],
            "icon": MODE_ICON[key],
            "hint": MODE_HINT.get(key, ""),
            "groups": groups,
            "count": len(fields),
        })
        defaults[key] = mode_defaults(key)
    return {
        "version": SCHEMA_VERSION,
        "title": NODE_TITLE,
        "defaultMode": DEFAULT_KEY,
        "modes": modes,
        "defaults": defaults,
    }


_SCHEMA_CACHE = {}


def get_schema(refresh=False):
    if refresh or "v" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE.clear()
        _SCHEMA_CACHE["v"] = build_schema()
    return _SCHEMA_CACHE["v"]


def all_fields():
    out = []
    for key in KEY_ORDER:
        out.extend(_mode_fields(key))
    return out


# ---------------------------------------------------------------- 参数整理
FIELD_CACHE = {}


def _field_index(mode):
    """参数白名单：含面板不显示、但节点上真实存在的技术项。"""
    idx = FIELD_CACHE.get(mode)
    if idx is None:
        idx = {}
        for name, t, opt in _spec_of(mode, for_form=False):
            f = _field_of(mode, name, t, opt)
            if f:
                idx[name] = f
        FIELD_CACHE[mode] = idx
    return idx


def coerce_params(mode, params):
    """把面板来的值按原节点要求对齐类型；缺的用原节点默认值补齐。"""
    base = mode_defaults(mode)
    idx = _field_index(mode)
    params = params if isinstance(params, dict) else {}
    for name, v in params.items():
        f = idx.get(name)
        if not f:
            continue                      # 不在面板里的键（老画布残留）直接丢
        kind = f["type"]
        if kind == "combo":
            opts = f.get("options") or []
            value = _s(v)
            if value not in opts:
                value = f.get("default") or (opts[0] if opts else "")
            if f.get("multi"):
                base[name] = [value] if value else []
            else:
                base[name] = value
        elif kind == "bool":
            base[name] = _b(v)
        elif kind == "int":
            base[name] = _i(v, _i(f.get("default")))
        elif kind == "float":
            base[name] = _f(v, _f(f.get("default")))
        else:
            base[name] = _s(v)
    return base


# ---------------------------------------------------------------- 结果解包
def _unpack(mode, raw):
    """按各节点自己的返回声明取用，不做任何二次加工。"""
    out = {"prompt": "", "negative": "", "width": 0, "height": 0,
           "english": "", "meta": {}}
    res = raw
    if isinstance(raw, dict):
        ui = raw.get("ui") or {}
        for k, v in ui.items():
            if isinstance(v, (list, tuple)) and v:
                out["meta"][_s(k)] = _s(v[0])
            elif v is not None:
                out["meta"][_s(k)] = _s(v)
        res = raw.get("result") or ()
    if isinstance(res, str):
        res = (res,)
    if not isinstance(res, (list, tuple)):
        res = ()
    res = list(res)

    if mode in ("L", "M"):   # 中文, 宽, 高, 英文
        out["prompt"] = _s(res[0]) if len(res) > 0 else ""
        out["width"] = _i(res[1]) if len(res) > 1 else 0
        out["height"] = _i(res[2]) if len(res) > 2 else 0
        out["english"] = _s(res[3]) if len(res) > 3 else ""
    elif mode == "N":        # 正面, 负面, 完整
        out["prompt"] = _s(res[0]) if len(res) > 0 else ""
        out["negative"] = _s(res[1]) if len(res) > 1 else ""
        if len(res) > 2:
            out["meta"]["完整"] = _s(res[2])
    else:
        out["prompt"] = _s(res[0]) if len(res) > 0 else ""
    if mode == "K":
        # Krea2 的 ui.text 是三行：正文 / 词池来源 / 稀有度
        txt = out["meta"].get("text") or ""
        if txt:
            lines = txt.split("\n")
            out["prompt"] = lines[0] if lines else out["prompt"]
            if len(lines) > 1:
                out["meta"]["词池"] = lines[1]
            if len(lines) > 2:
                out["meta"]["稀有度"] = lines[2]
    return out


# ---------------------------------------------------------------- 抽取
META_KEEP = {"词池", "稀有度"}


def render(mode, params=None, extra=""):
    """调原节点生成提示词；出错也不抛，把错误写进框里让人看见。"""
    key = mode if mode in MODE_CLS else KEY_BY_LABEL.get(_s(mode), DEFAULT_KEY)
    out = {"mode": key, "label": MODE_LABEL.get(key, ""),
           "prompt": "", "negative": "", "width": 0, "height": 0,
           "english": "", "meta": {}, "error": ""}
    try:
        vals = coerce_params(key, params)
        node = MODE_CLS[key]()
        raw = getattr(node, MODE_CLS[key].FUNCTION)(**vals)
        packed = _unpack(key, raw)
        out.update(packed)
    except Exception as exc:
        LOG.exception("[Hub] %s 抽取失败", key)
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
        out["prompt"] = "［抽取失败］%s" % out["error"]

    extra = _s(extra).strip()
    if extra:
        base = out["prompt"].rstrip()
        if base.endswith(("。", "，", "；", "、", ",", ".")):
            base = base[:-1].rstrip()
        out["prompt"] = (base + " " + extra).strip()
    # 只留面板底部要显示的少量信息，别把整段正文再塞进 meta
    out["meta"] = {k: v for k, v in out["meta"].items() if k in META_KEEP}
    out["meta"]["字符数"] = len(out["prompt"])
    if out["width"] and out["height"]:
        out["meta"]["推荐尺寸"] = "%d×%d" % (out["width"], out["height"])
    return out


def render_state(state, extra=""):
    """入队时用：参数 JSON → 抽取结果。"""
    data = _load_state(state)
    return render(data.get("mode") or DEFAULT_KEY, data.get("params") or {}, extra)


# ---------------------------------------------------------------- 节点本体
class PromptPuller:

    DESCRIPTION = (
        "提示词抽取：一个节点装下整句词库 / Krea2卡池 / 摄影搭配 / 穿搭预设 / 权威摄影 / 男性摄影 / 19+ 七个抽词模式，"
        "每个模式走它自己原来的词库与成句规则（完全没改）。"
        "左侧选好了，右侧提示词框即时出词，不用入队也能看。"
    )
    CATEGORY = "落日/Sunset"
    FUNCTION = "run"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING", "STRING", "INT", "INT")
    RETURN_NAMES = ("prompt", "negative", "width", "height")
    OUTPUT_TOOLTIPS = (
        "抽好的正面提示词，接 CLIP 文本编码器",
        "负面提示词（仅 19+ 模式有内容）",
        "推荐宽度（仅权威摄影模式给出，其余为 0）",
        "推荐高度（仅权威摄影模式给出，其余为 0）",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "模式": (list(MODE_LABEL.values()), {"default": MODE_LABEL[DEFAULT_KEY]}),
                "参数": ("STRING", {"default": "{}", "multiline": True}),
                "提示词": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "附加提示词": ("STRING", {"default": "", "multiline": True}),
            },
        }

    def run(self, 模式, 参数, 提示词, 附加提示词="", **kw):
        text = _s(提示词).strip()
        extra = _s(附加提示词).strip()

        if text:
            # 面板一直在同步，框里的字（含手改）就是最终结果
            if extra and not text.endswith(extra):
                text = text.rstrip() + " " + extra
            return {"ui": {"text": [text]}, "result": (text, "", 0, 0)}

        data = _load_state(参数)
        key = data.get("mode") or KEY_BY_LABEL.get(_s(模式), DEFAULT_KEY)
        res = render(key, data.get("params") or {}, extra)
        return {
            "ui": {"text": [res["prompt"]]},
            "result": (res["prompt"], res["negative"], res["width"], res["height"]),
        }


def _load_state(raw):
    """参数 JSON：{mode, params}；老画布的 {values} 也认，退化成默认参数。"""
    if isinstance(raw, dict):
        data = raw
    else:
        txt = _s(raw).strip()
        data = {}
        if txt:
            try:
                data = json.loads(txt)
            except Exception:
                LOG.warning("[Hub] 参数不是合法 JSON，按默认值处理")
                data = {}
    if not isinstance(data, dict):
        data = {}
    mode = data.get("mode")
    if mode not in MODE_CLS:
        mode = KEY_BY_LABEL.get(_s(mode), DEFAULT_KEY)
    params = data.get("params")
    if not isinstance(params, dict):
        params = {}
    return {"mode": mode, "params": params}


# ---------------------------------------------------------------- HTTP 路由
def _register_routes():
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:
        return False

    server = getattr(PromptServer, "instance", None)
    if server is None:
        return False
    routes = server.routes

    @routes.get("/hub/schema")
    async def hub_schema(request):
        refresh = request.query.get("refresh") in ("1", "true", "yes")
        try:
            return web.json_response(get_schema(refresh=refresh))
        except Exception as exc:
            LOG.exception("[Hub] schema 生成失败")
            return web.json_response(
                {"error": "%s: %s" % (type(exc).__name__, exc)}, status=500)

    @routes.post("/hub/render")
    async def hub_render(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        mode = body.get("mode")
        params = body.get("params")
        if not isinstance(params, dict):
            params = {}
        return web.json_response(render(mode, params, body.get("extra") or ""))

    LOG.info("[Hub] 路由就绪：/hub/schema · /hub/render")
    return True


ROUTES_OK = False
try:
    ROUTES_OK = _register_routes()
except Exception as _exc:  # 只影响即时预览，节点仍可用
    LOG.warning("[Hub] 路由注册失败：%s", _exc)


NODE_CLASS_MAPPINGS = {"PromptPuller": PromptPuller}
NODE_DISPLAY_NAME_MAPPINGS = {"PromptPuller": NODE_TITLE}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS",
           "PromptPuller", "build_schema", "get_schema", "render", "render_state"]
