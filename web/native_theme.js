/*
 * 原生风格（ComfyUI 普通节点样式）
 * ------------------------------------------------------------------
 * 七个节点原本带一整套霓虹皮肤：节点框渐变描边、发光标题、动画扫光、
 * 彩色磁贴。这里只把「外观」压回 ComfyUI 默认观感，面板功能原样保留。
 * 颜色全部取自前端自带的主题变量，切换 ComfyUI 明暗主题时会自动跟随。
 *
 * 默认开启。想回到原来的霓虹皮肤：
 *   浏览器控制台执行 localStorage.setItem("sunset_skin", "neon") 后刷新页面。
 */
import { app } from "../../scripts/app.js";

const NODE_CLASSES = [
  "Krea2PromptPicker",
  "ZImagePromptGeneratorNode",
  "ZImagePromptLoaderNode",
  "ZImageFashionPresetLoaderNode",
  "SunsetNSPromptSelector",
  "SunsetLRPromptBuilder",
  "SunsetMalePromptBuilder",
];

let neon = false;
try { neon = localStorage.getItem("sunset_skin") === "neon"; } catch (e) { /* ignore */ }

/* 两个皮肤脚本在 installPainting() 里读这个开关；未加载本模块时也为普通样式 */
globalThis.__SUNSET_PLAIN__ = !neon;

const CSS = `
/* ---------- 颜色全部借用 ComfyUI 自己的主题变量 ---------- */
.zs-root, .k2-root, .sun-right, .sun-hp {
  --sun-bg:     var(--component-node-background, #353535);
  --sun-panel:  var(--comfy-menu-bg, #2b2b2b);
  --sun-widget: var(--component-node-widget-background, var(--comfy-input-bg, #353535));
  --sun-border: var(--component-node-border, var(--border-color, #4a4a4a));
  --sun-fg:     var(--component-node-foreground, var(--fg-color, #d4d4d4));
  --sun-dim:    var(--component-node-foreground-secondary, #a0a0a0);
  --sun-mute:   var(--component-node-widget-background-disabled, #8a8a8a);
  --sun-sel:    var(--component-node-widget-background-selected, #3f5b78);
}
.zs-root, .k2-root {
  --o:var(--sun-mute) !important;  --p:var(--sun-mute) !important;
  --v:var(--sun-mute) !important;  --cy:var(--sun-mute) !important;
  --dg:var(--sun-mute) !important; --gd:var(--sun-mute) !important;
  --c1:var(--sun-mute) !important; --c2:var(--sun-mute) !important;
  --c3:var(--sun-mute) !important; --gc:var(--sun-mute) !important;
  --bg1:transparent !important; --bg2:transparent !important;
  --g1:transparent !important; --g2:transparent !important;
  --bgtop:transparent !important; --bgbtm:transparent !important;
  --ln:var(--sun-border) !important;
  --tx:var(--sun-fg) !important;
  --dim:var(--sun-dim) !important;
  background:var(--sun-bg) !important;
  background-image:none !important;
  border:1px solid var(--sun-border) !important;
  border-radius:4px !important;
  box-shadow:none !important;
  color:var(--sun-fg) !important;
}
.zs-root::after, .k2-root::after { display:none !important; }
.zs-root *, .k2-root *, .zs-root::before, .zs-root::after,
.k2-root::before, .k2-root::after,
.sun-right, .sun-right *, .sun-hp, .sun-hp * {
  background-image:none !important;
  box-shadow:none !important;
  text-shadow:none !important;
  animation:none !important;
  filter:none !important;
  transition:none !important;
  color:var(--sun-fg, #d4d4d4) !important;
}
.zs-root .zs-title, .k2-root .k2-title {
  color:var(--sun-fg) !important;
  -webkit-text-fill-color:var(--sun-fg, #d4d4d4) !important;
  background:none !important;
}
.zs-root .zs-gh::after, .k2-root .k2-sech::after {
  background-color:var(--sun-border) !important;
}

/* ---------- 控件表面：普通节点的深灰控件 + 细边框 ---------- */
.zs-root .zs-grp, .zs-root .zs-field, .zs-root .zs-cat, .zs-root .zs-btn,
.zs-root .zs-tab, .zs-root .zs-mega, .zs-root .zs-chip, .zs-root .zs-chipx,
.zs-root .zs-opt, .zs-root .zs-sw, .zs-root .zs-tagx, .zs-root .zs-seg b,
.zs-root .zs-out textarea, .zs-root .zs-seedin, .zs-root .zs-mini,
.k2-root .k2-card, .k2-root .k2-f, .k2-root .k2-big, .k2-root .k2-tile,
.k2-root .k2-tgl, .k2-root .k2-src, .k2-root .k2-btn, .k2-root .k2-chip,
.k2-root .k2-sub, .k2-root .k2-count, .k2-root .k2-dbtn,
.sun-right, .sun-right .sun-b, .sun-right .sun-mini, .sun-right .sun-run,
.sun-right .sun-ta, .sun-right .sun-sub textarea,
.sun-hp, .sun-hp-hd, .sun-hp-row, .sun-hp-hd .x, .sun-hp-hd .clr,
.sun-hp-row .del, .sun-tip {
  background-color:var(--sun-widget, #353535) !important;
  border:1px solid var(--sun-border, #4a4a4a) !important;
  border-radius:4px !important;
  color:var(--sun-fg, #d4d4d4) !important;
}
.zs-root input, .zs-root select, .zs-root textarea,
.k2-root input, .k2-root select, .k2-root textarea,
.sun-right textarea, .sun-hp input {
  background-color:var(--sun-panel, #2b2b2b) !important;
  color:var(--sun-fg, #d4d4d4) !important;
  border:1px solid var(--sun-border, #4a4a4a) !important;
  border-radius:4px !important;
}
.zs-root select option, .k2-root select option {
  background:var(--sun-panel, #2b2b2b) !important;
  color:var(--sun-fg, #d4d4d4) !important;
}
.zs-root .zs-dot, .k2-root .k2-dot, .sun-hd .sun-dot, .sun-hp-hd .dw {
  background-color:var(--sun-mute, #8a8a8a) !important;
}

/* ---------- 选中态：用主题自带的 selected 色，不用彩色渐变 ---------- */
.zs-root .zs-tab.on, .zs-root .zs-seg b.on, .zs-root .zs-cat.on,
.zs-root .zs-aurora.on, .zs-root .zs-danger.on, .zs-root .zs-mega.on,
.zs-root .zs-opt.on, .zs-root .zs-sw.on, .zs-root .zs-chipx.on,
.zs-root .zs-tagx.on, .zs-root .zs-chip.hot, .zs-root .zs-chip.zero,
.k2-root .k2-big.on, .k2-root .k2-tile.on, .k2-root .k2-tgl.on,
.k2-root .k2-src.on, .sun-run.on {
  background-color:var(--sun-sel, #3f5b78) !important;
  border-color:var(--sun-mute, #79a0c8) !important;
  color:#ffffff !important;
}
.zs-root .zs-field:hover, .k2-root .k2-tile:hover,
.sun-right .sun-b:hover, .sun-right .sun-mini:hover {
  border-color:var(--sun-mute, #6a6a6a) !important;
}
`;

if (!neon) {
  const style = document.createElement("style");
  style.id = "sunset-native-theme-css";
  style.textContent = CSS;
  document.head.appendChild(style);

  const stripColors = (node) => {
    if (!node || !NODE_CLASSES.includes(node.comfyClass || node.type)) return;
    try {
      node.color = undefined;
      node.bgcolor = undefined;
    } catch (e) { /* ignore */ }
  };

  app.registerExtension({
    name: "luori.SunsetNativeTheme",
    nodeCreated: stripColors,
    loadedGraphNode: stripColors,
  });
}

/* ==================================================================
 * 1.8.2：提示词框纯黑底 + 按钮立体
 * 独立注入，排在原生主题 CSS 之后；两套皮肤下都生效。
 * 想关掉：localStorage.setItem("sunset_3d", "off") 后刷新。
 * ================================================================== */
const CSS_3D = `
/* ---------- 提示词框：纯黑底 ---------- */
html body .zs-root.zs-root textarea,
html body .k2-root.k2-root textarea,
html body .sun-right.sun-right textarea,
html body .sun-ta,
html body .sun-sub textarea,
html body .sun-hp.sun-hp textarea,
html body .pp-root.pp-root textarea,
html body textarea.comfy-multiline-input,
html body textarea[data-testid="dom-widget-textarea"] {
  background-color:#000000 !important;
  background-image:none !important;
  color:#eaeaea !important;
  caret-color:#eaeaea !important;
  border:1px solid #3b3b3b !important;
  box-shadow:inset 0 2px 6px rgba(0,0,0,.9) !important;
  scrollbar-color:#4a4a4a #000000 !important;
}
html body .zs-root.zs-root textarea::placeholder,
html body .k2-root.k2-root textarea::placeholder,
html body .sun-right.sun-right textarea::placeholder,
html body .pp-root.pp-root textarea::placeholder { color:#6a6a6a !important; }
html body .zs-root.zs-root textarea:focus,
html body .k2-root.k2-root textarea:focus,
html body .sun-right.sun-right textarea:focus,
html body .pp-root.pp-root textarea:focus {
  border-color:#6b6b6b !important;
  outline:none !important;
}

/* ---------- 按钮：立体（亮顶边 + 暗底边 + 投影 + 按下位移） ---------- */
html body .zs-root.zs-root button,
html body .k2-root.k2-root button,
html body .sun-right.sun-right button,
html body .sun-hp.sun-hp button,
html body .pp-root.pp-root button,
html body .zs-root.zs-root .zs-seg b,
html body .sun-right.sun-right .sun-run {
  background-image:linear-gradient(180deg,rgba(255,255,255,.20) 0%,rgba(255,255,255,.07) 45%,rgba(0,0,0,.20) 100%) !important;
  border:1px solid #4d4d4d !important;
  border-top-color:#7d7d7d !important;
  border-left-color:#696969 !important;
  border-bottom-color:#202020 !important;
  border-right-color:#202020 !important;
  box-shadow:0 2px 0 #171717,0 3px 7px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.22) !important;
  color:#f2f2f2 !important;
  text-shadow:0 1px 0 rgba(0,0,0,.7) !important;
  transform:translateY(0) !important;
  transition:transform .12s ease,box-shadow .12s ease !important;
}
html body .zs-root.zs-root button:hover:not([disabled]),
html body .k2-root.k2-root button:hover:not([disabled]),
html body .sun-right.sun-right button:hover:not([disabled]),
html body .sun-hp.sun-hp button:hover:not([disabled]),
html body .pp-root.pp-root button:hover:not([disabled]),
html body .zs-root.zs-root .zs-seg b:hover,
html body .sun-right.sun-right .sun-run:hover {
  background-image:linear-gradient(180deg,rgba(255,255,255,.27) 0%,rgba(255,255,255,.11) 45%,rgba(0,0,0,.17) 100%) !important;
  box-shadow:0 3px 0 #171717,0 5px 11px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.3) !important;
  transform:translateY(-1px) !important;
}
html body .zs-root.zs-root button:active:not([disabled]),
html body .k2-root.k2-root button:active:not([disabled]),
html body .sun-right.sun-right button:active:not([disabled]),
html body .sun-hp.sun-hp button:active:not([disabled]),
html body .pp-root.pp-root button:active:not([disabled]),
html body .zs-root.zs-root .zs-seg b:active,
html body .sun-right.sun-right .sun-run:active {
  transform:translateY(2px) !important;
  box-shadow:0 0 0 #171717,inset 0 2px 5px rgba(0,0,0,.65) !important;
}
/* 选中态做成「按下去」的内凹 */
html body .zs-root.zs-root button.on,
html body .k2-root.k2-root button.on,
html body .sun-right.sun-right button.on,
html body .zs-root.zs-root .zs-seg b.on,
html body .sun-right.sun-right .sun-run.on {
  transform:translateY(1px) !important;
  box-shadow:0 0 0 #171717,inset 0 2px 6px rgba(0,0,0,.72) !important;
}
html body .zs-root.zs-root button[disabled],
html body .k2-root.k2-root button[disabled],
html body .sun-right.sun-right button[disabled],
html body .pp-root.pp-root button[disabled] { opacity:.5 !important; }
`;

let flat3d = false;
try { flat3d = localStorage.getItem("sunset_3d") === "off"; } catch (e) { /* ignore */ }
if (!flat3d) {
  const st = document.createElement("style");
  st.id = "sunset-black3d-css";
  st.textContent = CSS_3D;
  document.head.appendChild(st);
}

console.debug("[SunsetNativeTheme] " + (neon ? "霓虹皮肤（已关闭原生风格）" : "ComfyUI 普通节点样式"));
console.debug("[SunsetBlack3D] " + (flat3d ? "已关闭" : "提示词框纯黑底 / 按钮立体"));

/* ------------------------------------------------------------------
 * 字号归一：三套皮肤里原本混着 8.5 / 9 / 9.5 / 10 / 10.5 / 11 /
 * 11.5 / 12.5 / 13 / 14px 等自定义缩放，这里一律清掉，
 * 让七个节点上的字全部回到 ComfyUI 默认文字大小。
 * 默认取前端基础控件字号 var(--text-xs) = .75rem = 12px，
 * 与 litegraph 画布上普通节点标签的字号一致；跟随主题缩放。
 * 想自定义：localStorage.setItem("sunset_font_size", "14") 后刷新（px）。
 * 想彻底关掉：localStorage.setItem("sunset_font_size", "off") 后刷新。
 * ------------------------------------------------------------------ */
const FONT_ROOTS = [
  ".zs-root", ".k2-root", ".pp-root", ".sun-split", ".sun-right",
  ".sun-hm", ".sun-hp", ".sun-tip", ".k2-roll",
];
const FONT_SELECTORS = FONT_ROOTS.map((r) =>
  `html body ${r}${r}, html body ${r}${r} *, ` +
  `html body ${r}${r} *::before, html body ${r}${r} *::after`
).join(",\n");
const CSS_FONT = `
:root { --sun-font-size: var(--text-xs, 12px); }
${FONT_SELECTORS} {
  font-size: var(--sun-font-size) !important;
  line-height: 1.4 !important;
}
`;

let fsOverride = "";
try { fsOverride = localStorage.getItem("sunset_font_size") || ""; } catch (e) { /* ignore */ }
const fsEnabled = fsOverride !== "off";
const fsPx = Number.parseFloat(fsOverride);
const fsCustom = fsEnabled && Number.isFinite(fsPx) && fsPx >= 6 && fsPx <= 40;
if (fsEnabled) {
  const sf = document.createElement("style");
  sf.id = "sunset-font-css";
  sf.textContent =
    (fsCustom ? `:root { --sun-font-size: ${fsPx}px !important; }\n` : "") + CSS_FONT;
  document.head.appendChild(sf);
}
console.debug("[SunsetFont] " + (!fsEnabled
  ? "已关闭（保留皮肤原字号）"
  : (fsCustom ? `全部文字统一为 ${fsPx}px` : "全部文字统一为 ComfyUI 默认字号（12px）")));
