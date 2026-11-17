import logging

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

__version__ = "1.8.8"

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

# 显示名统一用「⚡提示词」开头，名字里不带分类名（例如 ⚡提示词抽取、⚡提示词男性人像）。
# 搜 taiyang / 太阳 靠各节点类里的 SEARCH_ALIASES 命中，分类保持 TaiYang 不变。
# 注意：前端搜索排序只认 name / display_name，别名只保证「搜得到」、不参与排序，
# 所以去掉前缀后本包节点会排在类名以 TaiYang 开头的第三方节点后面。
NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2PromptPicker": "⚡提示词最强文生图",
    "ZImagePromptGeneratorNode": "⚡提示词倾向摄影",
    "ZImagePromptLoaderNode": "⚡提示词抽取",
    "ZImageFashionPresetLoaderNode": "⚡提示词穿搭预设",
    "SunsetNSPromptSelector": "⚡提示词19+自选",
    "SunsetLRPromptBuilder": "⚡提示词女性人像",
    "SunsetMalePromptBuilder": "⚡提示词男性人像",
}

# ComfyUI 核心读完 pyproject.toml 的 [tool.comfy].web 之后会打印
#   [INFO] Automatically register web folder web for ComfyUI-PromptSelector
# 前端目录本来也由下面的 WEB_DIRECTORY 注册（key 完全一致），这条纯属噪音。
# 只精确屏蔽这一条文本：不改 ComfyUI 主程序、不影响其它任何日志。
class _QuietWebFolderLog(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return not (msg.startswith("Automatically register web folder")
                    and "ComfyUI-PromptSelector" in msg)


_ROOT_LOG = logging.getLogger()
if not any(isinstance(f, _QuietWebFolderLog) for f in _ROOT_LOG.filters):
    _ROOT_LOG.addFilter(_QuietWebFolderLog())

WEB_DIRECTORY = "./web"

try:
    startup_check()
except Exception as _e:
    logging.debug("[Sunset] 词库自检跳过了：%s", _e)

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
    "__version__",
]
