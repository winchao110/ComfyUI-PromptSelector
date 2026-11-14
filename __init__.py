from .nodes_krea2 import Krea2PromptPicker, startup_check
from .nodes_zimage import (
    ZImagePromptGeneratorNode,
    ZImagePromptLoaderNode,
    ZImageFashionPresetLoaderNode,
)
from .nodes_nsfw import SunsetNSPromptSelector
from .nodes_lr import SunsetLRPromptBuilder
from .nodes_male import SunsetMalePromptBuilder
from . import nodes_override
from .nodes_hub import PromptPuller  # 只为挂上 /hub/render 路由（右侧即时框要用），节点本身不注册

__version__ = "1.8.4"

# 给 7 个节点补一个隐藏输入「即时提示词」：右侧框里的字入队时直接当当条输出
nodes_override.install([
    Krea2PromptPicker,
    ZImagePromptGeneratorNode,
    ZImagePromptLoaderNode,
    ZImageFashionPresetLoaderNode,
    SunsetNSPromptSelector,
    SunsetLRPromptBuilder,
    SunsetMalePromptBuilder,
])

NODE_CLASS_MAPPINGS = {
    "Krea2PromptPicker": Krea2PromptPicker,
    "ZImagePromptGeneratorNode": ZImagePromptGeneratorNode,
    "ZImagePromptLoaderNode": ZImagePromptLoaderNode,
    "ZImageFashionPresetLoaderNode": ZImageFashionPresetLoaderNode,
    "SunsetNSPromptSelector": SunsetNSPromptSelector,
    "SunsetLRPromptBuilder": SunsetLRPromptBuilder,
    "SunsetMalePromptBuilder": SunsetMalePromptBuilder,
}

# 显示名统一用「⚡提示词」开头，名字里不带分类名（例如 ⚡提示词抽取、⚡提示词男性角色）。
# 搜 taiyang / 太阳 靠各节点类里的 SEARCH_ALIASES 命中，分类保持 TaiYang 不变。
# 注意：前端搜索排序只认 name / display_name，别名只保证「搜得到」、不参与排序，
# 所以去掉前缀后本包节点会排在类名以 TaiYang 开头的第三方节点后面。
NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2PromptPicker": "⚡提示词最强文生图",
    "ZImagePromptGeneratorNode": "⚡提示词倾向摄影",
    "ZImagePromptLoaderNode": "⚡提示词抽取",
    "ZImageFashionPresetLoaderNode": "⚡提示词穿搭预设",
    "SunsetNSPromptSelector": "⚡提示词19+自选",
    "SunsetLRPromptBuilder": "⚡提示词权威摄影",
    "SunsetMalePromptBuilder": "⚡提示词男性角色",
}

WEB_DIRECTORY = "./web"

try:
    startup_check()
except Exception as _e:
    print("[Sunset] 词库自检跳过了：%s" % _e)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "__version__",
]
