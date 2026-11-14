# -*- coding: utf-8 -*-
"""给本包 6 个抽词节点补两个可选输入。

1) 「即时提示词」（隐藏 STRING）
   节点面板右侧那个即时提示词框，内容会同步进这个隐藏控件里；
   入队时只要它不是空的，就用它顶替节点原来的第一条输出
   （prompt / 中文提示词 / 正面提示词）。

2) 「运行重抽」（隐藏 BOOLEAN）
   打开后 IS_CHANGED 返回 NaN，ComfyUI 每次跑工作流都会真正执行这个节点，
   于是按节点面板上的设置重新抽一次词；结果连同 ui.sun_pack 一起回传前端，
   由右侧的框实时换上新词。此时不再用「即时提示词」里的旧字覆盖输出。

抽取规则、词库、成句方式一点没动。
"""

import hashlib

INLINE_FIELD = "即时提示词"
RUN_FIELD = "运行重抽"
SEED_FIELD = "随机种子"
SEED_MAX = 0xFFFFFFFFFFFFFFFF
GOLDEN = 2654435761          # Knuth 乘法散列常数，用来把 n 打散成互不重复的偏移

# 每个节点类各存一个自增计数，「运行重抽」靠它派生新种子。
# 按类分开存，所以男、女两个节点各数各的，绝不会互相带动。
_RUN_COUNTER = {}
_CLASS_OFFSET = {}


def _class_offset(cls):
    """每个节点类一个固定的偏移，男、女两颗种子连轨迹都不一样。"""
    key = getattr(cls, "__name__", "") or ""
    if key not in _CLASS_OFFSET:
        _CLASS_OFFSET[key] = int(hashlib.md5(key.encode("utf-8")).hexdigest()[:8], 16)
    return _CLASS_OFFSET[key]


def _next_seed(cls, seed):
    """运行重抽时给这个类派一个新的种子（同一次运行内多次也各不相同）。"""
    try:
        base = int(seed)
    except (TypeError, ValueError):
        base = 0
    n = _RUN_COUNTER.get(cls.__name__, 0) + 1
    _RUN_COUNTER[cls.__name__] = n
    return (base + _class_offset(cls) + n * GOLDEN) % SEED_MAX


def _patch_input_types(cls):
    bound = cls.INPUT_TYPES          # 旧 classmethod 的绑定版本，调用时不带 cls

    def patched(cls=None):          # classmethod 会把类作为第一个参数传进来
        spec = bound() or {}
        out = {}
        for key, val in spec.items():
            out[key] = dict(val) if isinstance(val, dict) else val
        opt = dict(out.get("optional") or {})
        if INLINE_FIELD not in opt:
            opt[INLINE_FIELD] = ("STRING", {
                "default": "",
                "multiline": True,
                "hidden": True,
            })
        if RUN_FIELD not in opt:
            opt[RUN_FIELD] = ("BOOLEAN", {
                "default": False,
                "hidden": True,
            })
        out["optional"] = opt
        return out

    cls.INPUT_TYPES = classmethod(patched)


def _sig(kwargs):
    """没有自带 IS_CHANGED 的节点：按输入算一个稳定签名，行为等同于默认缓存规则。"""
    items = "|".join("%s=%r" % (k, v) for k, v in sorted(kwargs.items()))
    digest = hashlib.md5(items.encode("utf-8", "replace")).hexdigest()[:12]
    return float(int(digest, 16))


def _patch_is_changed(cls):
    """运行重抽开着 → NaN，ComfyUI 认为每次都变了，节点必跑。"""
    orig = getattr(cls, "IS_CHANGED", None)

    def is_changed(*args, **kwargs):
        if kwargs.get(RUN_FIELD):
            return float("nan")
        if orig is not None:
            try:
                return orig(**kwargs)
            except TypeError:
                pass
            except Exception:
                pass
        return _sig(kwargs)

    cls.IS_CHANGED = classmethod(is_changed)


def _simple(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _pack_result(cls, result):
    """把头几个输出按 RETURN_NAMES 打包，前端据此找负面/英文。"""
    names = getattr(cls, "RETURN_NAMES", None) or ()
    pack = {}
    if isinstance(result, (tuple, list)):
        for i, v in enumerate(result):
            key = names[i] if i < len(names) else ("out%d" % i)
            pack[str(key)] = _simple(v)
    return pack


def _as_dict(res, cls):
    if isinstance(res, dict):
        out = dict(res)
        out.setdefault("ui", {})
        return out
    if isinstance(res, (tuple, list)):
        return {"ui": {}, "result": tuple(res)}
    return {"ui": {}, "result": (res,)}


def _patch_function(cls):
    name = getattr(cls, "FUNCTION", None)
    if not name:
        return
    orig = getattr(cls, name, None)
    if orig is None:
        return

    def wrapped(self, *args, **kwargs):
        run = bool(kwargs.pop(RUN_FIELD, False))
        text = kwargs.pop(INLINE_FIELD, "")

        # ---- 运行重抽：忽略框里的旧字，换一颗只属于本节点的新种子再重算，
        #      结果连同实际用的种子一起回传前端（前端会写回「随机种子」控件）。
        if run:
            new_seed = None
            if SEED_FIELD in kwargs:
                new_seed = _next_seed(cls, kwargs[SEED_FIELD])
                kwargs[SEED_FIELD] = new_seed
            res = orig(self, *args, **kwargs)
            out = _as_dict(res, cls)
            result = out.get("result")
            first = ""
            if isinstance(result, (tuple, list)) and result:
                first = _simple(result[0])
            ui = dict(out.get("ui") or {})
            ui["sun_prompt"] = ["" if first is None else str(first)]
            ui["sun_pack"] = [_pack_result(cls, result)]
            if new_seed is not None:
                ui["sun_seed"] = [new_seed]
            out["ui"] = ui
            return out

        # ---- 平时：框里有字就用它顶替第一条输出
        res = orig(self, *args, **kwargs)
        text = "" if text is None else str(text).strip()
        if not text:
            return res

        # Krea2 / 19+ / 权威摄影 返回 {"ui": {...}, "result": (...)}，
        # 剩下的返回裸元组；两种都要让第一条输出变成框里的字。
        if isinstance(res, dict):
            out = dict(res)
            old = None
            result = out.get("result")
            if isinstance(result, (tuple, list)) and result:
                old = result[0]
                rows = list(result)
                rows[0] = text
                out["result"] = tuple(rows)
            ui = out.get("ui")
            if isinstance(ui, dict) and old is not None:
                olds = str(old)
                new_ui = {}
                for key, val in ui.items():
                    if isinstance(val, (list, tuple)) and val:
                        cur = str(val[0])
                        if cur == olds:
                            repl = text
                        elif olds and olds in cur:
                            # Krea2 的 ui.text 是「正文 + 词池 + 稀有度」三行、
                            # 19+ 的 ui.full 是「POSITIVE: …」，只换正文那一段
                            repl = cur.replace(olds, text, 1)
                        else:
                            repl = None
                        if repl is not None:
                            rows = list(val)
                            rows[0] = repl
                            val = rows
                    new_ui[key] = val
                out["ui"] = new_ui
            return out

        if not isinstance(res, (tuple, list)):
            return (text,)
        rows = list(res)
        if rows:
            rows[0] = text
        return tuple(rows)

    wrapped.__name__ = name
    wrapped.__doc__ = getattr(orig, "__doc__", None)
    setattr(cls, name, wrapped)


PATCHED = []


def install(classes):
    for cls in classes:
        if getattr(cls, "__sun_inline_patched__", False):
            continue
        try:
            _patch_input_types(cls)
            _patch_is_changed(cls)
            _patch_function(cls)
            cls.__sun_inline_patched__ = True
            PATCHED.append(cls.__name__)
        except Exception as exc:      # 单个失败不影响其它节点
            print("[Sunset] 即时提示词补丁失败 %s: %s" % (cls.__name__, exc))
    return PATCHED
