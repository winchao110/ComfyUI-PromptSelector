/* 落日提示词 · 右侧即时提示词框
 *
 * 给本包原来的 6 个节点各加一栏：
 *   左边 = 原面板（一点没动）
 *   右边 = 提示词框 + 下面那排按钮（⚡抽取 / ↺复位 / 复制 / 清空）
 *
 * 抽取规则完全走原节点自己的那套：这里只把当前面板的值发给
 * /hub/render（后端直通原节点的生成函数），把结果贴进框里。
 * 框里的字会同步到隐藏控件「即时提示词」，入队时节点优先用它。
 *
 * 改动即换为常开状态：改任意控件约 0.3 秒后自动重抽，没有开关。
 */

import { app } from "../../scripts/app.js";

const VERSION = "1.6.1";
const RIGHT_W = 340;
const INLINE_WIDGET = "即时提示词";
const RUN_WIDGET = "运行重抽";
const HIST_MAX = 80;

const MODE_OF = {
  ZImagePromptLoaderNode: "Z",
  Krea2PromptPicker: "K",
  ZImagePromptGeneratorNode: "G",
  ZImageFashionPresetLoaderNode: "F",
  SunsetLRPromptBuilder: "L",
  SunsetMalePromptBuilder: "M",
  SunsetNSPromptSelector: "N",
};

const LEFT_MIN = {
  ZImagePromptLoaderNode: 352,
  ZImagePromptGeneratorNode: 352,
  Krea2PromptPicker: 352,
  ZImageFashionPresetLoaderNode: 400,
  SunsetNSPromptSelector: 520,
  SunsetLRPromptBuilder: 480,
  SunsetMalePromptBuilder: 480,
};

const TAG_OF = {
  Z: "整句词库", K: "Krea2 卡池", G: "摄影搭配",
  F: "穿搭预设", L: "权威摄影", M: "男性摄影", N: "19+ 自选",
};

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/* ------------------------------------------------------------------ 样式 */
let cssDone = false;
function injectCSS() {
  if (cssDone) return;
  cssDone = true;
  const s = document.createElement("style");
  s.id = "sun-inline-css";
  s.textContent = `
.sun-split{display:flex;gap:8px;align-items:stretch;}
/* 左栏给足宽度时按原样显示；节点被拖窄时不外溢到右框，宁可自己裁掉 */
.sun-left{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;overflow:hidden;}
.sun-left>*{width:100%;max-width:100%;box-sizing:border-box;}

.sun-right{
  flex:0 0 ${RIGHT_W}px;width:${RIGHT_W}px;min-width:0;min-height:0;
  display:flex;flex-direction:column;gap:6px;overflow:hidden;
  padding:8px;border-radius:10px;
  border:1px solid rgba(255,255,255,.09);
  background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.012));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.06);
}
.sun-right *{box-sizing:border-box;}

.sun-hd{display:flex;align-items:center;gap:6px;flex:0 0 auto;}
.sun-dot{width:6px;height:6px;border-radius:50%;flex:0 0 auto;
  background:#FFB020;box-shadow:0 0 8px #FFB020;}
.sun-hd b{font:700 11px/1 "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  letter-spacing:.06em;color:#EDE9FE;white-space:nowrap;}
.sun-tag{font:700 9px/1 inherit;letter-spacing:.08em;color:#9A90C4;padding:3px 6px;
  border-radius:99px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);
  white-space:nowrap;}
.sun-cnt{margin-left:auto;font:600 9.5px/1.3 inherit;color:#8E86B5;white-space:nowrap;}

.sun-ta{
  flex:1 1 58%;min-height:0;width:100%;resize:none;border-radius:8px;outline:none;
  padding:7px 8px;font:11px/1.55 "Segoe UI","PingFang SC","Microsoft YaHei",monospace;
  color:#E4DFFB;background:rgba(11,7,26,.62);border:1px solid rgba(255,255,255,.1);
  overflow:auto;scrollbar-width:thin;
}
.sun-ta:focus{border-color:rgba(255,176,32,.5);}
.sun-ta::placeholder{color:#5F5880;}

.sun-sub{flex:1 1 38%;min-height:64px;display:flex;flex-direction:column;gap:3px;}
.sun-sub.hide{display:none;}
.sun-sub span{flex:0 0 auto;font:600 9px/1.2 inherit;letter-spacing:.08em;color:#8E86B5;}
.sun-sub textarea{flex:1 1 auto;width:100%;min-height:0;resize:none;border-radius:7px;outline:none;
  padding:5px 7px;font:10px/1.5 inherit;color:#C9C0EA;background:rgba(255,255,255,.035);
  border:1px solid rgba(255,255,255,.08);overflow:auto;}

.sun-meta{flex:0 0 auto;display:flex;align-items:center;gap:6px;flex-wrap:wrap;
  font:600 9px/1.3 inherit;color:#7E76A6;min-height:12px;}
.sun-meta .sun-warn{color:#FF9BAE;}
.sun-meta .sun-size{color:#9FE1CB;}

.sun-ft{flex:0 0 auto;display:flex;align-items:center;gap:5px;flex-wrap:wrap;row-gap:5px;}
.sun-b{height:28px;padding:0 9px;border-radius:8px;cursor:pointer;white-space:nowrap;
  font:700 10.5px/1 inherit;color:#D8D2F5;border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);transition:.16s;}
.sun-b:hover{color:#fff;border-color:rgba(255,255,255,.26);background:rgba(255,255,255,.08);}
.sun-b:active{transform:translateY(1px);}
.sun-go{color:#2A1400;border-color:transparent;
  background:linear-gradient(150deg,#FFC24D,#FF8A3D);
  box-shadow:0 2px 10px rgba(255,138,61,.38);}
.sun-go:hover{color:#2A1400;background:linear-gradient(150deg,#FFD06B,#FF9A52);}
.sun-b[disabled]{opacity:.45;cursor:default;filter:saturate(.4);}

/* 运行重抽开关 */
.sun-run{display:flex;align-items:center;gap:5px;height:28px;padding:0 8px;border-radius:8px;
  cursor:pointer;user-select:none;white-space:nowrap;font:600 10px/1 inherit;color:#8E86B5;
  border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.028);transition:.16s;}
.sun-run:hover{color:#D8D2F5;border-color:rgba(255,255,255,.2);}
.sun-run i{width:20px;height:11px;border-radius:99px;position:relative;flex:0 0 auto;
  background:rgba(255,255,255,.14);transition:background .18s;}
.sun-run i::after{content:"";position:absolute;left:1.5px;top:1.5px;width:8px;height:8px;
  border-radius:50%;background:#8b83a8;transition:transform .18s,background .18s;}
.sun-run.on{color:#FFD8A8;border-color:rgba(255,176,32,.42);background:rgba(255,176,32,.1);}
.sun-run.on i{background:rgba(255,176,32,.5);}
.sun-run.on i::after{transform:translateX(9px);background:#FFD8A8;}

.sun-mini{height:22px;padding:0 7px;border-radius:6px;cursor:pointer;
  font:600 9px/1 inherit;color:#8E86B5;border:1px solid rgba(255,255,255,.08);
  background:transparent;transition:.16s;}
.sun-mini:hover{color:#fff;border-color:rgba(255,255,255,.22);}

.sun-busy{animation:sunblink .9s ease-in-out infinite;}
@keyframes sunblink{0%,100%{opacity:1}50%{opacity:.45}}

/* ---------------- 历史弹窗（挂在 body 上，独立配色，跟节点同一套主题） */
.sun-hm{position:fixed;inset:0;z-index:120000;display:flex;align-items:center;justify-content:center;
  background:rgba(6,4,14,.66);
  font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
.sun-hm.hide{display:none;}
.sun-hp{width:min(1300px,95vw);height:auto;max-height:min(620px,84vh);min-height:260px;
  display:flex;flex-direction:column;
  border-radius:14px;overflow:hidden;border:1px solid rgba(255,255,255,.12);
  background:linear-gradient(180deg,#1C1830,#141122);
  box-shadow:0 26px 80px rgba(0,0,0,.62),inset 0 1px 0 rgba(255,255,255,.07);}
.sun-hp-hd{flex:0 0 auto;display:flex;align-items:center;gap:8px;padding:12px 14px;
  border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.018);}
.sun-hp-hd .dw{width:6px;height:6px;border-radius:50%;background:#FFB020;box-shadow:0 0 8px #FFB020;}
.sun-hp-hd b{font:700 13px/1 inherit;letter-spacing:.05em;color:#EDE9FE;}
.sun-hp-hd .tag{font:700 9px/1 inherit;letter-spacing:.08em;color:#9A90C4;padding:4px 7px;
  border-radius:99px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);}
.sun-hp-hd .sub{font:600 10px/1 inherit;color:#7E76A6;}
.sun-hp-hd .x{margin-left:0;width:26px;height:26px;border-radius:7px;cursor:pointer;
  font:700 14px/1 inherit;color:#B6AEDC;border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);transition:.16s;}
.sun-hp-hd .x:hover{color:#fff;border-color:rgba(255,255,255,.28);background:rgba(255,255,255,.09);}
.sun-hp-hd .clr{margin-left:auto;height:26px;padding:0 10px;border-radius:7px;cursor:pointer;
  font:700 10.5px/1 inherit;color:#B6AEDC;border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);transition:.16s;}
.sun-hp-hd .clr:hover{color:#fff;border-color:rgba(255,255,255,.28);background:rgba(255,255,255,.09);}
.sun-hp-list{flex:1 1 auto;min-height:0;overflow:auto;padding:6px;scrollbar-width:thin;}
.sun-hp-row{display:grid;grid-template-columns:34px 52px 56px 1fr 24px;gap:10px;align-items:center;
  padding:8px 10px;border-radius:8px;cursor:pointer;border:1px solid transparent;transition:.12s;}
.sun-hp-row:hover{background:rgba(255,176,32,.09);border-color:rgba(255,176,32,.34);}
.sun-hp-row .no{font:700 10px/1 inherit;color:#6E6690;text-align:right;}
.sun-hp-row .tm{font:600 10px/1 inherit;color:#8E86B5;}
.sun-hp-row .ln{font:600 10px/1 inherit;color:#9FE1CB;text-align:right;}
.sun-hp-row .tx{font:11.5px/1.55 inherit;color:#D8D2F5;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;}
.sun-hp-row .del{width:20px;height:20px;border-radius:6px;cursor:pointer;opacity:.55;
  font:700 13px/1 inherit;color:#E3B9C9;border:1px solid rgba(255,255,255,.16);
  background:rgba(255,255,255,.06);transition:.14s;}
.sun-hp-row:hover .del{opacity:1;}
.sun-hp-row .del:hover{color:#fff;border-color:rgba(255,90,80,.6);background:rgba(255,70,60,.24);}
.sun-hp-empty{padding:52px 0;text-align:center;color:#6E6690;font:600 11px/1.7 inherit;}
.sun-tip{position:fixed;z-index:120001;max-width:540px;max-height:54vh;overflow:auto;
  padding:9px 11px;border-radius:10px;pointer-events:none;white-space:pre-wrap;
  border:1px solid rgba(255,176,32,.32);background:#131021;
  box-shadow:0 14px 40px rgba(0,0,0,.62);
  font:11px/1.6 "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#E4DFFB;
  scrollbar-width:thin;}
.sun-tip.hide{display:none;}
.sun-tip .k{color:#9A90C4;font-weight:700;}
.sun-tip .n{margin-top:7px;padding-top:7px;border-top:1px solid rgba(255,255,255,.09);color:#C9C0EA;}
`;
  document.head.appendChild(s);
}

/* ------------------------------------------------------------------ 取值 */
function collect(node) {
  const out = {};
  for (const w of node.widgets || []) {
    if (!w || !w.name) continue;
    if (w.element) continue;                 // DOM 面板自己
    if (w.type === "button") continue;
    if (w.name === INLINE_WIDGET) continue;
    if (w.name === RUN_WIDGET) continue;     // 开关不参与参数比对
    if (typeof w.value === "function") continue;
    out[w.name] = w.value;
  }
  return out;
}

/* ------------------------------------------------------------------ 历史 */
/* 只放内存（WeakMap 挂在节点上），不写 node.properties —— 不随工作流存盘，
   关掉 ComfyUI 刷新页面就没了，不占磁盘。 */
const HIST_STORE = new WeakMap();

function readHist(node) {
  try {
    let a = HIST_STORE.get(node);
    if (!Array.isArray(a)) { a = []; HIST_STORE.set(node, a); }
    return a;
  } catch (e) { return []; }
}

/* 老版本把历史写进了节点属性，这里顺手清掉，别继续塞进工作流文件 */
function purgeHistProp(node) {
  try {
    if (node?.properties && "sunHistory" in node.properties) delete node.properties.sunHistory;
  } catch (e) { /* ignore */ }
}

function pushHist(node, rec) {
  const arr = readHist(node);
  const text = String(rec.text || "");
  if (!text.trim()) return arr;
  rec.text = text;
  rec.t = rec.t || Date.now();

  /* 同一段提示词全局只留一条：已经存在就把它提到最前、刷新时间，
     不再新增（以前只比对第 1 条，A→B→A 会记两条） */
  const i = arr.findIndex((x) => x && x.text === text);
  if (i === 0) {
    Object.assign(arr[0], rec);
    return arr;
  }
  if (i > 0) {
    const [old] = arr.splice(i, 1);
    Object.assign(old, rec);
    arr.unshift(old);
    return arr;
  }

  arr.unshift(rec);
  if (arr.length > HIST_MAX) arr.length = HIST_MAX;
  return arr;
}

function dropHist(node, rec) {
  const arr = readHist(node);
  const i = arr.indexOf(rec);
  if (i >= 0) arr.splice(i, 1);
  return arr;
}

function clearHist(node) {
  const arr = readHist(node);
  arr.length = 0;
  return arr;
}

function hhmm(ts) {
  const d = new Date(ts || Date.now());
  const p = (n) => String(n).padStart(2, "0");
  return p(d.getHours()) + ":" + p(d.getMinutes());
}

function fullTime(ts) {
  const d = new Date(ts || Date.now());
  const p = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
    " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
}

/* 历史弹窗：整个页面只有一个，切换节点时重画 */
let histUI = null;

function ensureHistUI() {
  if (histUI) return histUI;

  const mask = el("div", "sun-hm hide");
  const panel = el("div", "sun-hp");
  const hd = el("div", "sun-hp-hd");
  const tag = el("span", "tag", "");
  const sub = el("span", "sub", "");
  const clr = el("button", "clr", "清空");
  const x = el("button", "x", "×");
  hd.append(el("i", "dw"), el("b", null, "提示词历史"), tag, sub, clr, x);
  const list = el("div", "sun-hp-list");
  panel.append(hd, list);
  mask.append(panel);
  document.body.appendChild(mask);

  const tip = el("div", "sun-tip hide");
  document.body.appendChild(tip);

  mask.addEventListener("pointerdown", (e) => {
    e.stopPropagation();
    if (e.target === mask) closeHist();
  });
  mask.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
  x.addEventListener("click", closeHist);

  /* 清空：点一下直接清干净（不弹确认） */
  clr.addEventListener("click", () => {
    const node = histUI?.node;
    if (!node) return;
    clearHist(node);
    histUI.tip.classList.add("hide");
    paintHist(histUI, node);
  });

  document.addEventListener("keydown", (e) => {
    if (mask.classList.contains("hide")) return;
    if (e.key === "Escape") { closeHist(); return; }
    e.stopPropagation();        // 弹窗开着时别让画布吃到 Delete / Ctrl+Z 之类
  }, true);

  histUI = { mask, panel, list, tag, sub, tip, clr, node: null, apply: null };
  return histUI;
}

function closeHist() {
  if (!histUI) return;
  histUI.mask.classList.add("hide");
  histUI.tip.classList.add("hide");
}

function placeTip(tip, ev) {
  const pad = 12;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 18, y = ev.clientY + 14;
  if (x + w > window.innerWidth - pad) x = ev.clientX - w - 18;
  if (x < pad) x = pad;
  if (y + h > window.innerHeight - pad) y = window.innerHeight - pad - h;
  if (y < pad) y = pad;
  tip.style.left = Math.round(x) + "px";
  tip.style.top = Math.round(y) + "px";
}

function openHist(node, st, apply) {
  const ui = ensureHistUI();
  ui.node = node;
  ui.apply = apply;
  ui.tag.textContent = TAG_OF[st.mode] || st.mode;
  ui.tip.classList.add("hide");
  paintHist(ui, node);
  ui.mask.classList.remove("hide");
}

/* 重画列表（删除一条 / 清空后复用，不关弹窗） */
function paintHist(ui, node) {
  const arr = readHist(node);
  ui.sub.textContent = arr.length ? "共 " + arr.length + " 条 · 新的在上 · 不存盘" : "还没有记录";
  ui.clr.disabled = !arr.length;
  ui.clr.style.opacity = arr.length ? "" : ".4";
  ui.list.innerHTML = "";
  ui.tip.classList.add("hide");

  if (!arr.length) {
    ui.list.appendChild(el("div", "sun-hp-empty",
      "还没有历史。点「⚡ 抽取」或跑一次工作流，记录会出现在这里。（只在本次会话内，不写盘）"));
    return;
  }

  arr.forEach((rec, i) => {
    const row = el("div", "sun-hp-row");
    const del = el("button", "del", "×");
    del.title = "删除这一条";
    row.append(
      el("span", "no", String(i + 1)),
      el("span", "tm", hhmm(rec.t)),
      el("span", "ln", (String(rec.text || "").length) + " 字"),
      el("span", "tx", String(rec.text || "").replace(/\s+/g, " ").slice(0, 200)),
      del
    );

    const show = (ev) => {
      const tip = ui.tip;
      tip.innerHTML = "";
      const head = el("div");
      head.appendChild(el("span", "k", fullTime(rec.t) + " · " + (rec.text || "").length + " 字"));
      const body = el("div");
      body.textContent = rec.text || "";
      tip.append(head, body);
      if (rec.neg) {
        const n = el("div", "n");
        n.textContent = "负面提示词：\n" + rec.neg;
        tip.appendChild(n);
      }
      if (rec.en) {
        const n = el("div", "n");
        n.textContent = "英文提示词：\n" + rec.en;
        tip.appendChild(n);
      }
      if (rec.w && rec.h) {
        const n = el("div", "n");
        n.textContent = "推荐尺寸：" + rec.w + " × " + rec.h;
        tip.appendChild(n);
      }
      tip.classList.remove("hide");
      placeTip(tip, ev);
    };

    row.addEventListener("pointerenter", show);
    row.addEventListener("pointermove", show);
    row.addEventListener("pointerleave", () => ui.tip.classList.add("hide"));
    row.addEventListener("click", () => {
      ui.apply?.(rec);
      closeHist();
    });

    /* 行内删除：直接删这一条，不关弹窗、不弹确认 */
    del.addEventListener("pointerdown", (e) => e.stopPropagation());
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      ui.tip.classList.add("hide");
      dropHist(node, rec);
      paintHist(ui, node);
    });

    ui.list.appendChild(row);
  });
}

function writeWidget(node, name, value) {
  const w = (node.widgets || []).find((x) => x.name === name);
  if (!w) return false;
  if (Object.is(w.value, value)) return true;
  w.value = value;
  try { w.callback?.(value, app.canvas, node); } catch (e) { /* ignore */ }
  try { node.setDirtyCanvas?.(true, true); } catch (e) { /* ignore */ }
  return true;
}

function randSeed() {
  return Math.floor(Math.random() * 0x7fffffff);
}

function reroll(node) {
  let hit = false;
  for (const w of node.widgets || []) {
    if (!w || !w.name || w.element) continue;
    if (!/^(seed|随机种子|种子)$/i.test(w.name) && !/seed|种子/i.test(w.name)) continue;
    if (w.type === "button") continue;
    writeWidget(node, w.name, randSeed());
    hit = true;
  }
  return hit;
}

/* ------------------------------------------------------------------ 网络 */
let defaultsCache = null;
let defaultsPending = null;

async function loadDefaults() {
  if (defaultsCache) return defaultsCache;
  if (defaultsPending) return defaultsPending;
  defaultsPending = (async () => {
    try {
      const r = await fetch("/hub/schema");
      const j = await r.json();
      defaultsCache = j?.defaults || {};
    } catch (e) {
      console.warn("[SunInline] 结构表没取到", e);
      defaultsCache = {};
    }
    return defaultsCache;
  })();
  return defaultsPending;
}

async function postRender(mode, params) {
  const r = await fetch("/hub/render", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, params }),
  });
  if (!r.ok) throw new Error("HTTP " + r.status);
  return await r.json();
}

/* ------------------------------------------------------------------ 量偏移 */
/* 皮肤算节点高度时用的是控件自身的 y（dm.y），但前端真正把面板摆下去的位置
   比它多一个标题栏高度，结果节点总是矮一截、面板底边露在节点外。
   这里直接从画面坐标量一次真实偏移（画布元素自身有 16px 顶边，别漏掉）。 */
function measureY(node, root) {
  try {
    const cv = app?.canvas || app?.canvas;
    const ds = cv?.ds;
    const el = root?.parentElement || root;
    if (!ds || !el || !cv?.canvas) return null;
    const scale = ds.scale || 1;
    const cr = cv.canvas.getBoundingClientRect();
    const nodeTop = cr.top + ((Number(node.pos?.[1]) || 0) + Number(ds.offset?.[1] || 0)) * scale;
    const v = (el.getBoundingClientRect().top - nodeTop) / scale;
    return (isFinite(v) && v > 0 && v < 240) ? v : null;
  } catch (e) { return null; }
}

/* ------------------------------------------------------------------ 主挂载 */
export function mountInlineBox(node, root) {
  const mode = MODE_OF[node?.comfyClass];
  if (!mode || !root) return null;
  if (node.__sunBox) return node.__sunBox;

  injectCSS();

  /* 1) 原面板整体包进左栏 */
  let left = root.querySelector(":scope > .sun-left");
  if (!left) {
    left = el("div", "sun-left");
    const kids = Array.from(root.childNodes);
    for (const k of kids) left.appendChild(k);
    root.appendChild(left);
  }
  root.classList.add("sun-split");

  /* 2) 右栏 */
  const right = el("div", "sun-right");

  const hd = el("div", "sun-hd");
  hd.append(el("div", "sun-dot"), el("b", null, "即时提示词"),
    el("span", "sun-tag", TAG_OF[mode] || mode), el("span", "sun-cnt", "—"));
  const cnt = hd.querySelector(".sun-cnt");

  const ta = el("textarea", "sun-ta");
  ta.placeholder = "点下面的「⚡抽取」，这里就会出现提示词；也可以直接改，改完跟着节点走。";
  ta.spellcheck = false;

  const sub = el("div", "sun-sub hide");
  const subLbl = el("span", null, "负面提示词");
  const subTa = el("textarea");
  subTa.spellcheck = false;
  sub.append(subLbl, subTa);

  const meta = el("div", "sun-meta");

  const ft = el("div", "sun-ft");
  const btnGo = el("button", "sun-b sun-go", "⚡ 抽取");
  const btnReset = el("button", "sun-b", "↺ 复位");
  const runWrap = el("div", "sun-run", "运行重抽");
  runWrap.prepend(el("i"));
  runWrap.title = "打开后，每次跑工作流都会按节点上的设置重新抽取一次";
  const btnHist = el("button", "sun-b", "历史");
  const btnCopy = el("button", "sun-mini", "复制");
  const btnClear = el("button", "sun-mini", "清空");
  ft.append(btnGo, btnReset, runWrap, btnHist);
  const ft2 = el("div", "sun-ft");
  ft2.append(btnCopy, btnClear);
  ft2.style.justifyContent = "flex-end";

  right.append(hd, ta, sub, meta, ft, ft2);
  root.appendChild(right);

  const st = {
    mode, root, right, ta, sub, subTa, cnt, meta,
    busy: false, queued: false, manual: false, mute: false,
    runOn: false,                 // 老后端还没有「运行重抽」控件时，先用本地状态
    lastSnap: "", pending: null, failures: 0,
  };
  node.__sunBox = st;

  /* 3) 宽度：给右栏腾位置，并守住一个最小宽度
     （节点被拖到比"原面板 + 右栏"还窄时，左栏会被挤到右框上，看起来像两个窗口重合） */
  const minW = Math.round((LEFT_MIN[node.comfyClass] || 352) + RIGHT_W + 28);
  const clampW = () => {
    try {
      if (!node.size) return;
      const w = Math.round(node.size[0]);
      if (w >= minW) return;
      node.setSize?.([minW, Math.round(node.size[1] || 300)]);
      node.graph?.setDirtyCanvas?.(true, true);
      node.setDirtyCanvas?.(true, true);
    } catch (e) { /* ignore */ }
  };
  try {
    if (Math.round(node.size?.[0] || 0) < minW) {
      node.setSize?.([minW, Math.round(node.size?.[1] || 300)]);
      node.graph?.setDirtyCanvas?.(true, true);
    }
  } catch (e) { /* ignore */ }

  const prevResize = node.onResize;
  node.onResize = function (...a) {
    try { prevResize?.apply(this, a); } catch (e) { /* ignore */ }
    clampW();
  };

  /* 高度兜底：副框出现 / 元信息多一行时面板会长高，
     一旦探出节点底边就把节点撑高。口径和皮肤一致（面板底边留 2px），
     所以正常情况这里什么都不做，只在皮肤没跟上时才补一刀。 */
  const fitH = () => {
    try {
      if (!node.size || !root.offsetHeight) return;
      const wY = measureY(node, root);
      if (wY == null) return;                              // 面板还没摆好位置
      const need = Math.round(wY + root.offsetHeight + 2);
      if (Math.round(node.size[1]) >= need) return;
      node.setSize?.([Math.round(node.size[0]), need]);
      node.graph?.setDirtyCanvas?.(true, true);
      node.setDirtyCanvas?.(true, true);
    } catch (e) { /* ignore */ }
  };

  /* 4) 状态渲染（旧画布里存过的开关/历史字段清掉） */
  try {
    if (node.properties && "sunAuto" in node.properties) delete node.properties.sunAuto;
  } catch (e) { /* ignore */ }
  purgeHistProp(node);

  const runWidget = () => (node.widgets || []).find((w) => w.name === RUN_WIDGET);
  const isRunOn = () => {
    const w = runWidget();
    return w ? !!w.value : !!st.runOn;
  };
  const paintRun = () => runWrap.classList.toggle("on", isRunOn());
  paintRun();

  const setMeta = (bits) => {
    meta.innerHTML = "";
    for (const b of bits) if (b) meta.appendChild(b);
  };

  const showSub = (label, text) => {
    const v = String(text || "").trim();
    if (!v) { sub.classList.add("hide"); subTa.value = ""; return; }
    subLbl.textContent = label;
    subTa.value = v;
    sub.classList.remove("hide");
  };

  const pushToNode = (text) => {
    writeWidget(node, INLINE_WIDGET, text || "");
  };

  const applyResult = (res, force) => {
    const text = String(res?.prompt || "");
    if (force || !st.manual) {
      ta.value = text;
      st.manual = false;
      pushToNode(text);
      if (text.trim()) {
        pushHist(node, {
          t: Date.now(),
          text: text,
          neg: String(res?.negative || "").slice(0, 4000),
          en: String(res?.english || "").slice(0, 8000),
          w: res?.width || 0,
          h: res?.height || 0,
        });
      }
    }
    cnt.textContent = (ta.value.length || 0) + " 字";
    const bits = [];
    if (res?.width && res?.height) {
      const s = el("span", "sun-size", "推荐 " + res.width + "×" + res.height);
      bits.push(s);
    }
    if (res?.meta?.词池) bits.push(el("span", null, String(res.meta.词池)));
    if (res?.meta?.稀有度) bits.push(el("span", null, String(res.meta.稀有度)));
    if (res?.error) bits.push(el("span", "sun-warn", "抽取失败：" + res.error));
    setMeta(bits);

    if (mode === "N") showSub("负面提示词", res?.negative);
    else if (mode === "L" || mode === "M") showSub("英文提示词", res?.english);
    else showSub("", "");
    setTimeout(fitH, 60);
    setTimeout(fitH, 260);
  };

  /* 5) 抽取 */
  const extract = async (force) => {
    if (st.busy) { st.queued = true; return; }
    st.busy = true;
    btnGo.classList.add("sun-busy");
    try {
      const res = await postRender(st.mode, collect(node));
      st.failures = 0;
      applyResult(res, force !== false ? true : false);
    } catch (e) {
      st.failures++;
      var lastErr = String(e?.message || e);
      console.warn("[SunInline] 抽取失败", e);
      setMeta([el("span", "sun-warn", "服务没响应：" + lastErr)]);
    } finally {
      st.busy = false;
      btnGo.classList.remove("sun-busy");
      if (st.queued) { st.queued = false; setTimeout(() => extract(force), 60); }
    }
  };
  st.extract = extract;

  /* 5.5) 工作流开始跑：这一刻框里的词（含手改过的）就是实际要用的，记进历史 */
  const prevStart = node.onExecutionStart;
  node.onExecutionStart = function () {
    try { prevStart?.apply(this, arguments); } catch (e) { /* ignore */ }
    try {
      const m = Number(node.mode ?? 0);
      if (m === 2 || m === 4) return;          // 静音 / 旁路的节点，这次并没有真跑
      if (isRunOn()) return;                   // 开了运行重抽：跑的是新抽的，等回传再记
      const text = String(ta.value || "");
      if (!text.trim()) return;
      const rec = { t: Date.now(), text: text };
      if (mode === "N") rec.neg = String(subTa.value || "");
      else if (mode === "L" || mode === "M") rec.en = String(subTa.value || "");
      pushHist(node, rec);
    } catch (e) { /* ignore */ }
  };

  /* 5.6) 工作流跑完：节点把重抽结果回传，框里跟着换 */
  const prevExec = node.onExecuted;
  node.onExecuted = function (msg) {
    try { prevExec?.apply(this, arguments); } catch (e) { /* ignore */ }
    try {
      // 有的前端版本直接给 ui 字典，有的给 {node, output}
      const ui = (msg && (msg.sun_prompt || msg.sun_pack)) ? msg : (msg?.output || msg);
      const pack = ui?.sun_pack?.[0];
      let text = ui?.sun_prompt?.[0];
      if (!text && pack) {
        text = Object.values(pack).find((v) => typeof v === "string" && v.length > 0);
      }
      if (!text) return;
      const pick = (re) => {
        const hit = pack ? Object.entries(pack).find(([k]) => re.test(k)) : null;
        return hit ? hit[1] : "";
      };
      // 运行重抽时后端会派生一颗只属于本节点的新种子，写回控件才好复现，
      // 顺便把快照对齐掉，免得 700ms 的巡检把它当成「参数变了」再抽一次。
      const seed = ui?.sun_seed?.[0];
      if (seed != null && seed !== "") {
        const sw = (node.widgets || []).find((x) => x.name === "随机种子");
        if (sw && String(sw.value) !== String(seed)) {
          st.mute = true;
          writeWidget(node, "随机种子", seed);
          st.mute = false;
          st.lastSnap = JSON.stringify(collect(node));
        }
      }
      st.manual = false;
      applyResult({
        prompt: text,
        negative: pick(/负面/),
        english: pick(/英文/),
        width: Number(pick(/宽度/)) || 0,
        height: Number(pick(/高度/)) || 0,
      }, true);
    } catch (e) { /* ignore */ }
  };

  /* 6) 参数变动监听：给每个控件加一层 callback + 定时兜底比对 */
  const watchWidgets = () => {
    for (const w of node.widgets || []) {
      if (!w || !w.name || w.element || w.__sunHooked) continue;
      if (w.type === "button") continue;
      w.__sunHooked = true;
      const prev = w.callback;
      w.callback = function (...args) {
        let out;
        try { out = prev?.apply(this, args); } catch (e) { /* ignore */ }
        onChanged();
        return out;
      };
    }
  };

  let changeTimer = null;
  const onChanged = () => {
    if (st.mute) return;
    clearTimeout(changeTimer);
    changeTimer = setTimeout(() => extract(true), 320);
  };

  watchWidgets();
  const tick = setInterval(() => {
    if (node.__sunBox !== st) { clearInterval(tick); return; }
    watchWidgets();
    paintRun();                      // 从工作流恢复过来的开关状态
    clampW();                        // 载入旧工作流时可能带回过窄的宽度
    fitH();                          // 副框出现后别让面板探出节点底边
    if (st.busy) return;
    const snap = JSON.stringify(collect(node));
    if (snap === st.lastSnap) return;
    st.lastSnap = snap;
    onChanged();
  }, 700);

  /* 7) 按钮 */
  btnGo.addEventListener("click", () => {
    st.manual = false;
    reroll(node);
    st.lastSnap = JSON.stringify(collect(node));
    extract(true);
  });

  btnReset.addEventListener("click", async () => {
    btnReset.disabled = true;
    try {
      const all = await loadDefaults();
      const d = all?.[st.mode] || {};
      let n = 0;
      for (const k of Object.keys(d)) {
        if (k === INLINE_WIDGET) continue;
        if (writeWidget(node, k, d[k])) n++;
      }
      st.manual = false;
      st.lastSnap = JSON.stringify(collect(node));
      await extract(true);
      cnt.textContent = (ta.value.length || 0) + " 字";
      if (!n) setMeta([el("span", "sun-warn", "没找到可复位的项，已按当前参数重抽")]);
    } finally {
      btnReset.disabled = false;
    }
  });

  runWrap.addEventListener("click", () => {
    const nv = !isRunOn();
    st.runOn = nv;
    if (runWidget()) {
      st.mute = true;
      writeWidget(node, RUN_WIDGET, nv);
      st.mute = false;
    }
    paintRun();
  });

  btnHist.addEventListener("click", () => {
    openHist(node, st, (rec) => {
      ta.value = rec.text || "";
      st.manual = false;
      pushToNode(ta.value);
      cnt.textContent = (ta.value.length || 0) + " 字";
      if (mode === "N") showSub("负面提示词", rec.neg);
      else if (mode === "L" || mode === "M") showSub("英文提示词", rec.en);
      else showSub("", "");
      const bits = [];
      bits.push(el("span", "sun-size", "来自历史 " + hhmm(rec.t)));
      if (rec.w && rec.h) bits.push(el("span", null, "推荐 " + rec.w + "×" + rec.h));
      setMeta(bits);
    });
  });

  btnCopy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(ta.value || "");
      btnCopy.textContent = "已复制";
      setTimeout(() => (btnCopy.textContent = "复制"), 900);
    } catch (e) { /* ignore */ }
  });

  btnClear.addEventListener("click", () => {
    ta.value = "";
    st.manual = false;
    pushToNode("");
    cnt.textContent = "0 字";
    showSub("", "");
  });

  ta.addEventListener("input", () => {
    st.manual = true;
    cnt.textContent = (ta.value.length || 0) + " 字";
    pushToNode(ta.value);
  });

  /* 别让框里的拖动把节点拖走 */
  const stop = (e) => e.stopPropagation();
  for (const t of [ta, subTa]) {
    t.addEventListener("pointerdown", stop);
    t.addEventListener("wheel", stop, { passive: true });
  }
  runWrap.addEventListener("pointerdown", stop);
  right.addEventListener("pointerdown", stop);

  /* 8) 首抽（第一次强制，后两次只在没手改时补一下，防止服务刚起来没响应） */
  st.lastSnap = JSON.stringify(collect(node));
  setTimeout(() => extract(true), 60);
  setTimeout(() => extract(false), 900);
  setTimeout(() => extract(false), 2200);

  console.log("[SunInline] 即时框已挂到 " + (node.title || node.comfyClass) + " (" + mode + ")");
  return st;
}

/* 兜底：如果皮肤那头没调用，自己补挂一次 */
app.registerExtension({
  name: "luori.SunsetInlineBox",
  beforeRegisterNodeDef(nodeType, nodeData) {
    if (!MODE_OF[nodeData?.name]) return;
    try {
      const opt = nodeData?.input?.optional;
      for (const f of [INLINE_WIDGET, RUN_WIDGET]) {
        if (opt && opt[f] && typeof opt[f][1] === "object") opt[f][1].hidden = true;
      }
    } catch (e) { /* ignore */ }
  },
  nodeCreated(node) {
    if (!MODE_OF[node.comfyClass]) return;
    const find = (n) => n.__zsCtx?.root || n.__k2ctx?.root || null;
    let tries = 0;
    const iv = setInterval(() => {
      tries++;
      const root = find(node);
      if (root && !node.__sunBox) {
        try { mountInlineBox(node, root); } catch (e) { console.warn("[SunInline] 补挂失败", e); }
      }
      if (node.__sunBox || tries > 40) clearInterval(iv);
    }, 250);
  },
  loadedGraphNode(node) {
    if (!MODE_OF[node.comfyClass]) return;
    const find = (n) => n.__zsCtx?.root || n.__k2ctx?.root || null;
    let tries = 0;
    const iv = setInterval(() => {
      tries++;
      const root = find(node);
      if (root && !node.__sunBox) {
        try { mountInlineBox(node, root); } catch (e) { /* ignore */ }
      }
      if (node.__sunBox || tries > 40) clearInterval(iv);
    }, 250);
  },
});

console.log("[SunInline] 即时提示词框 v" + VERSION + " 已加载");
