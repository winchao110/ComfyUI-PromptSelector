/* 提示词抽取 · 前端面板
 *
 * 六个模式各自走原节点自己的词库与成句规则（后端一对一调用，没有合并、没有改写）。
 * 左边是当前模式的控件，右边是提示词框：改任何一项立刻 POST /hub/render，
 * 把文本写进框里 —— 这就是「即时抽取」。
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "PromptPuller";
const TITLE_H = 42;        // 节点标题条占的高度
const MIN_H = 420;
const PANEL_H0 = 780;      // 面板默认高度（表单内部滚动，不靠拉高节点）
const PANEL_W = 1120;
const H_STEPS = [620, 780, 940, 1080];

let SCHEMA = null;
let SCHEMA_LOADING = null;

/* ------------------------------------------------------------------ 样式 */
const CSS = `
.pp-root{box-sizing:border-box;display:flex;gap:10px;width:100%;height:100%;padding:8px;
  background:radial-gradient(120% 140% at 0% 0%,#1d2030 0%,#141620 55%,#101119 100%);
  border:1px solid rgba(255,255,255,.07);border-radius:12px;color:#e8eaf2;
  font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;font-size:12px;overflow:hidden;}
.pp-l{display:flex;flex-direction:column;gap:7px;width:57%;min-width:0;}
.pp-r{display:flex;flex-direction:column;gap:6px;flex:1;min-width:0;}

/* 顶部：模式 + 搜索 */
.pp-top{display:flex;gap:6px;align-items:center;}
.pp-mode{flex:0 0 auto;max-width:170px;background:linear-gradient(180deg,rgba(255,182,72,.16),rgba(255,138,61,.10));
  border:1px solid rgba(255,182,72,.45);border-radius:7px;color:#ffd9a1;padding:5px 7px;
  font-size:12px;font-weight:700;outline:none;cursor:pointer;}
.pp-mode option{background:#1b1e2b;color:#e8eaf2;}
.pp-search{flex:1;min-width:0;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  border-radius:7px;color:#e8eaf2;padding:5px 8px;font-size:11.5px;outline:none;}
.pp-search:focus{border-color:rgba(255,190,90,.55);}
.pp-note{font-size:10.5px;color:#8890a6;line-height:1.45;padding:0 2px;min-height:15px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* 表单 */
.pp-form{flex:1;min-height:0;overflow-y:auto;overflow-x:hidden;padding-right:4px;
  display:flex;flex-direction:column;gap:6px;}
.pp-form::-webkit-scrollbar{width:7px;}
.pp-form::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:4px;}
.pp-g{border:1px solid rgba(255,255,255,.07);border-radius:8px;background:rgba(255,255,255,.022);}
.pp-g>summary{cursor:pointer;padding:5px 8px;font-weight:700;color:#c9cfe2;list-style:none;
  display:flex;align-items:center;gap:6px;font-size:11.5px;}
.pp-g>summary::-webkit-details-marker{display:none;}
.pp-g>summary::before{content:"▸";color:#ffb648;font-size:10px;transition:.15s;}
.pp-g[open]>summary::before{transform:rotate(90deg);}
.pp-g>summary .cnt{margin-left:auto;color:#6f7691;font-weight:400;font-size:10.5px;}
.pp-body{display:flex;flex-direction:column;gap:4px;padding:2px 8px 8px;}
.pp-row{display:flex;align-items:center;gap:8px;min-height:22px;}
.pp-row.off{display:none;}
.pp-lb{flex:0 0 42%;max-width:42%;color:#aab1c6;font-size:11.5px;line-height:1.3;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:help;}
.pp-ctl{flex:1;min-width:0;}
.pp-ctl select,.pp-ctl input[type=text],.pp-ctl input[type=number]{
  width:100%;box-sizing:border-box;background:rgba(255,255,255,.055);
  border:1px solid rgba(255,255,255,.11);border-radius:6px;color:#e8eaf2;
  padding:3.5px 6px;font-size:11.5px;outline:none;}
.pp-ctl select:focus,.pp-ctl input:focus{border-color:rgba(255,190,90,.6);}
.pp-ctl select option{background:#1b1e2b;color:#e8eaf2;}
.pp-ctl textarea{width:100%;box-sizing:border-box;min-height:44px;resize:vertical;
  background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.11);border-radius:6px;
  color:#e8eaf2;padding:4px 6px;font-size:11.5px;font-family:inherit;outline:none;}
.pp-sw{position:relative;display:inline-block;width:34px;height:18px;flex:0 0 auto;}
.pp-sw input{opacity:0;width:0;height:0;position:absolute;}
.pp-sw i{position:absolute;inset:0;background:rgba(255,255,255,.14);border-radius:9px;
  transition:.15s;cursor:pointer;}
.pp-sw i::after{content:"";position:absolute;left:2px;top:2px;width:14px;height:14px;
  border-radius:50%;background:#cfd4e4;transition:.15s;}
.pp-sw input:checked+i{background:linear-gradient(90deg,#ffb648,#ff8a3d);}
.pp-sw input:checked+i::after{transform:translateX(16px);background:#231708;}

/* 左栏底部 */
.pp-foot{display:flex;gap:6px;align-items:center;}
.pp-btn{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
  border-radius:7px;color:#cfd5e6;padding:4px 10px;font-size:11.5px;cursor:pointer;
  font-family:inherit;}
.pp-btn:hover{background:rgba(255,255,255,.11);color:#fff;}
.pp-btn.go{background:linear-gradient(90deg,#ffb648,#ff8a3d);border-color:transparent;
  color:#241708;font-weight:700;}
.pp-btn.go:hover{filter:brightness(1.08);}
.pp-tip{font-size:10.5px;color:#6f7691;margin-left:auto;}

/* 右栏 */
.pp-rhead{display:flex;align-items:center;gap:6px;}
.pp-rtitle{font-weight:700;color:#ffd9a1;font-size:12px;}
.pp-count{font-size:10.5px;color:#7d8499;}
.pp-rhead .pp-btn{padding:3px 8px;}
.pp-rhead .pp-btn:first-of-type{margin-left:auto;}
.pp-box{flex:1;min-height:0;resize:none;box-sizing:border-box;width:100%;
  background:rgba(10,12,18,.62);border:1px solid rgba(255,255,255,.1);border-radius:8px;
  color:#f0f2f8;padding:8px 9px;font-size:12px;line-height:1.6;outline:none;
  font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;}
.pp-box:focus{border-color:rgba(255,190,90,.55);}
.pp-sub{border:1px solid rgba(255,255,255,.08);border-radius:8px;background:rgba(255,255,255,.022);
  padding:4px 6px;display:flex;flex-direction:column;gap:3px;max-height:200px;}
.pp-sub.hide{display:none;}
.pp-subhead{font-size:10.5px;color:#8890a6;display:flex;gap:6px;align-items:center;}
.pp-sub textarea{min-height:70px;max-height:150px;resize:none;box-sizing:border-box;width:100%;
  background:rgba(10,12,18,.5);border:1px solid rgba(255,255,255,.07);border-radius:6px;
  color:#b9c0d4;padding:4px 6px;font-size:11px;line-height:1.5;font-family:inherit;outline:none;}
.pp-extra{display:flex;align-items:center;gap:6px;}
.pp-extra span{font-size:11px;color:#aab1c6;flex:0 0 auto;}
.pp-extra input{flex:1;min-width:0;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.1);border-radius:6px;color:#e8eaf2;
  padding:4px 7px;font-size:11.5px;outline:none;}
.pp-meta{font-size:10.5px;color:#7d8499;line-height:1.4;min-height:14px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.pp-empty{color:#8b91a6;font-size:11.5px;padding:10px;text-align:center;}
.pp-busy{color:#ffb648;}
`;

function injectCSS() {
  if (document.getElementById("pp-style")) return;
  const s = document.createElement("style");
  s.id = "pp-style";
  s.textContent = CSS;
  document.head.append(s);
}

/* ------------------------------------------------------------------ 小工具 */
function el(tag, cls, text) {
  const d = document.createElement(tag);
  if (cls) d.className = cls;
  if (text !== undefined) d.textContent = text;
  return d;
}

function wByName(node, name) {
  return (node.widgets || []).find((w) => w.name === name);
}

function setNative(node, name, value) {
  const w = wByName(node, name);
  if (w && w.value !== value) w.value = value;
}

function randSeed() {
  return Math.floor(Math.random() * 1e12);
}

function loadSchema() {
  if (SCHEMA) return Promise.resolve(SCHEMA);
  if (!SCHEMA_LOADING) {
    SCHEMA_LOADING = api
      .fetchApi("/hub/schema")
      .then((r) => r.json())
      .then((j) => {
        SCHEMA = j;
        SCHEMA_LOADING = null;
        return j;
      })
      .catch((e) => {
        SCHEMA_LOADING = null;
        throw e;
      });
  }
  return SCHEMA_LOADING;
}

function modeDef(key) {
  return (SCHEMA?.modes || []).find((m) => m.key === key) || null;
}

function defaultParams(key) {
  return Object.assign({}, SCHEMA?.defaults?.[key] || {});
}

/* ------------------------------------------------------------------ 状态 */
function readState(node) {
  const raw = wByName(node, "参数")?.value || "{}";
  let data = {};
  try {
    data = JSON.parse(raw);
  } catch (e) {
    data = {};
  }
  let mode = data.mode;
  if (!modeDef(mode)) mode = SCHEMA?.defaultMode || "G";
  const all = data.all && typeof data.all === "object" ? data.all : {};
  if (data.params && typeof data.params === "object") all[mode] = data.params;
  return { mode, all, extra: wByName(node, "附加提示词")?.value || "" };
}

function paramsOf(st, key) {
  if (!st.all[key] || typeof st.all[key] !== "object") st.all[key] = defaultParams(key);
  return st.all[key];
}

function writeState(node, st) {
  const payload = { mode: st.mode, params: paramsOf(st, st.mode), all: st.all };
  const txt = JSON.stringify(payload);
  const w = wByName(node, "参数");
  if (w && w.value !== txt) w.value = txt;
  const def = modeDef(st.mode);
  if (def) setNative(node, "模式", def.label);
}

/* ------------------------------------------------------------------ 面板骨架 */
function buildPanel() {
  const root = el("div", "pp-root");

  /* 左栏 */
  const left = el("div", "pp-l");
  const top = el("div", "pp-top");
  const modeSel = el("select", "pp-mode");
  const search = el("input", "pp-search");
  search.type = "text";
  search.placeholder = "搜索选项…（如 场景 / 光 / 姿态 / 丝袜）";
  top.append(modeSel, search);
  const note = el("div", "pp-note");
  const form = el("div", "pp-form");
  const foot = el("div", "pp-foot");
  const btnGo = el("button", "pp-btn go", "⚡ 抽取");
  const btnReset = el("button", "pp-btn", "↺ 复位");
  const tip = el("span", "pp-tip", "改任意一项即时出词");
  foot.append(btnGo, btnReset, tip);
  left.append(top, note, form, foot);

  /* 右栏 */
  const right = el("div", "pp-r");
  const rhead = el("div", "pp-rhead");
  const rtitle = el("div", "pp-rtitle", "即时提示词");
  const count = el("div", "pp-count", "0 字");
  const status = el("div", "pp-count");
  const btnSize = el("button", "pp-btn", "高度");
  const btnCopy = el("button", "pp-btn", "复制");
  const btnClear = el("button", "pp-btn", "清空");
  rhead.append(rtitle, count, status, btnSize, btnCopy, btnClear);

  const box = el("textarea", "pp-box");
  box.spellcheck = false;
  box.placeholder = "选好左边的选项，这里会即时出现提示词；也可以直接改写。";

  const sub = el("div", "pp-sub hide");
  const subhead = el("div", "pp-subhead");
  const box2 = el("textarea", "");
  box2.readOnly = true;
  sub.append(subhead, box2);

  const extraRow = el("div", "pp-extra");
  extraRow.append(el("span", null, "附加提示词"));
  const extraInp = el("input", "");
  extraInp.type = "text";
  extraInp.placeholder = "追加在末尾（可留空），会一起写进节点";
  extraRow.append(extraInp);

  const meta = el("div", "pp-meta");
  right.append(rhead, box, sub, extraRow, meta);
  root.append(left, right);

  return {
    root, modeSel, search, note, form, foot, status,
    box, box2, sub, subhead, meta, count, extraInp,
    btnGo, btnReset, btnCopy, btnClear, btnSize,
    seedInputs: {},
    commit: null,
  };
}

/* ------------------------------------------------------------------ 表单渲染 */
function makeControl(node, ui, f, value, onChange) {
  const row = el("div", "pp-row");
  row.dataset.key = f.name;
  const lb = el("div", "pp-lb", f.label);
  if (f.tooltip) lb.title = f.tooltip;
  const wrap = el("div", "pp-ctl");
  row.append(lb, wrap);

  if (f.type === "bool") {
    const sw = el("label", "pp-sw");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !!value;
    const knob = document.createElement("i");
    sw.append(cb, knob);
    wrap.append(sw);
    cb.addEventListener("change", () => onChange(cb.checked));
  } else if (f.type === "combo") {
    const sel = document.createElement("select");
    let opts = (f.options || []).slice();
    let val = value === undefined || value === null ? "" : String(value);
    if (val && !opts.includes(val)) opts.unshift(val);
    for (const o of opts) {
      const op = document.createElement("option");
      op.value = o;
      const t = o.length > 60 ? o.slice(0, 60) + "…" : o;
      op.textContent = t;
      op.title = o;
      sel.append(op);
    }
    sel.value = val;
    if (f.multi) sel.title = (sel.title ? sel.title + " · " : "") + "原节点支持多选，这里按单选送";
    wrap.append(sel);
    sel.addEventListener("change", () => onChange(sel.value));
  } else if (f.type === "int" || f.type === "float") {
    const inp = document.createElement("input");
    inp.type = "number";
    inp.value = value ?? 0;
    if (f.type === "int") {
      inp.step = String(f.step || 1);
    } else {
      inp.step = String(f.step || 0.01);
    }
    if (f.min !== undefined) inp.min = String(f.min);
    if (f.max !== undefined) inp.max = String(f.max);
    wrap.append(inp);
    if (f.name === "seed" || f.name === "随机种子") ui.seedInputs[f.name] = inp;
    inp.addEventListener("change", () => onChange(f.type === "int" ? parseInt(inp.value || "0", 10) : parseFloat(inp.value || "0")));
  } else if (f.type === "text") {
    const ta = document.createElement("textarea");
    ta.value = value ?? "";
    ta.rows = 2;
    wrap.append(ta);
    ta.addEventListener("change", () => onChange(ta.value));
  } else {
    const inp = document.createElement("input");
    inp.type = "text";
    inp.value = value ?? "";
    wrap.append(inp);
    inp.addEventListener("change", () => onChange(inp.value));
  }

  // 布尔行的开关贴右，标签留白小些
  if (f.type === "bool") {
    lb.style.flex = "1";
    lb.style.maxWidth = "none";
    wrap.style.flex = "0 0 auto";
  }
  return row;
}

function renderModeSelect(node, ui) {
  const st = node.__ppState;
  ui.modeSel.innerHTML = "";
  for (const m of SCHEMA.modes) {
    const op = document.createElement("option");
    op.value = m.key;
    op.textContent = m.label;
    ui.modeSel.append(op);
  }
  ui.modeSel.value = st.mode;
}

function renderForm(node, ui) {
  const st = node.__ppState;
  const def = modeDef(st.mode);
  ui.form.innerHTML = "";
  ui.seedInputs = {};
  if (!def) {
    ui.form.append(el("div", "pp-empty", "词库结构里没有这个模式"));
    return;
  }
  const params = paramsOf(st, st.mode);
  ui.note.textContent = def.hint || "";
  ui.note.title = def.hint || "";

  const commit = (name, value) => {
    params[name] = value;
    writeState(node, st);
    scheduleExtract(node, 60);      // 下拉/开关一下就出词，别拖到入队还没算完
  };

  let idx = 0;
  const openAll = def.count <= 30;          // 字段不多就全展开，省得一堆空的折叠条
  for (const g of def.groups) {
    const det = el("details", "pp-g");
    det.open = openAll || idx === 0;
    const sum = el("summary");
    sum.append(el("span", null, g.title), el("span", "cnt", "· " + g.fields.length));
    det.append(sum);
    const body = el("div", "pp-body");
    for (const f of g.fields) {
      body.append(makeControl(node, ui, f, params[f.name], (v) => commit(f.name, v)));
    }
    det.append(body);
    ui.form.append(det);
    idx++;
  }
  applySearch(ui);
}

function applySearch(ui) {
  const q = (ui.search.value || "").trim().toLowerCase();
  let total = 0;
  for (const det of ui.form.querySelectorAll(".pp-g")) {
    let hit = 0;
    for (const row of det.querySelectorAll(".pp-row")) {
      const key = (row.dataset.key || "").toLowerCase();
      const lb = (row.querySelector(".pp-lb")?.textContent || "").toLowerCase();
      const ok = !q || key.includes(q) || lb.includes(q);
      row.classList.toggle("off", !ok);
      if (ok) hit++;
    }
    det.style.display = hit ? "" : "none";
    if (q && hit) det.open = true;
    total += hit;
  }
  const old = ui.form.querySelector(".pp-nomatch");
  if (q && !total) {
    if (!old) ui.form.append(el("div", "pp-empty pp-nomatch", "没有匹配「" + q + "」的选项"));
    else old.textContent = "没有匹配「" + q + "」的选项";
  } else if (old) {
    old.remove();
  }
}

/* ------------------------------------------------------------------ 抽取 */
let EXTRACT_TOKEN = 0;

function scheduleExtract(node, delay) {
  clearTimeout(node.__ppTimer);
  node.__ppTimer = setTimeout(() => doExtract(node), delay ?? 240);
}

async function doExtract(node) {
  const ui = node.__ppUI;
  const st = node.__ppState;
  if (!ui || !st) return;
  const token = ++EXTRACT_TOKEN;
  ui.status.textContent = "…";
  ui.status.classList.add("pp-busy");
  let res = null;
  let err = "";
  try {
    const r = await api.fetchApi("/hub/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: st.mode,
        params: paramsOf(st, st.mode),
        extra: ui.extraInp.value || "",
      }),
    });
    res = await r.json();
  } catch (e) {
    err = String(e?.message || e);
  }
  if (token !== EXTRACT_TOKEN) return;   // 后面的请求已经发出，这次结果作废
  ui.status.classList.remove("pp-busy");

  if (!res || res.error) {
    ui.status.textContent = "抽取失败";
    ui.meta.textContent = (res?.error || err || "接口没响应").slice(0, 120);
    if (res?.prompt) ui.box.value = res.prompt;
    syncBox(node, ui);
    return;
  }
  ui.status.textContent = "";

  ui.box.value = res.prompt || "";
  syncBox(node, ui);

  // 副框：19+ 显示负面，权威摄影显示英文
  const neg = res.negative || "";
  const eng = res.english || "";
  if (neg) {
    ui.sub.classList.remove("hide");
    ui.subhead.textContent = "负面提示词 · " + neg.length + " 字";
    ui.box2.value = neg;
  } else if (eng) {
    ui.sub.classList.remove("hide");
    ui.subhead.textContent = "英文提示词 · " + eng.length + " 字";
    ui.box2.value = eng;
  } else {
    ui.sub.classList.add("hide");
    ui.box2.value = "";
  }

  const bits = [];
  if (res.label) bits.push(res.label);
  bits.push((res.prompt || "").length + " 字");
  const m = res.meta || {};
  for (const k of Object.keys(m)) {
    if (k === "字符数") continue;
    bits.push(k + "：" + m[k]);
  }
  ui.meta.textContent = bits.join(" · ");
  ui.meta.title = ui.meta.textContent;
}

function syncBox(node, ui) {
  setNative(node, "提示词", ui.box.value);
  ui.count.textContent = ui.box.value.length + " 字";
}

function rerollSeeds(node) {
  const ui = node.__ppUI;
  const st = node.__ppState;
  const params = paramsOf(st, st.mode);
  let touched = false;
  for (const k of Object.keys(ui.seedInputs)) {
    const v = randSeed();
    params[k] = v;
    ui.seedInputs[k].value = v;
    touched = true;
  }
  if (!touched) {
    // 没有种子控件也要能换一批：把随机种子类字段翻新
    for (const k of ["随机种子", "seed"]) {
      if (params[k] !== undefined) params[k] = randSeed();
    }
  }
  writeState(node, st);
}

/* ------------------------------------------------------------------ 尺寸 */
function applyPanel(node, ui) {
  const h = Math.round(node.__ppPanelH || PANEL_H0);
  ui.root.style.height = h + "px";
  ui.root.style.width = "100%";
  if (ui.dom) ui.dom.computeSize = () => [PANEL_W, h];
}

/* 面板高度是唯一依据：节点高度 = 面板高 + 标题高，绝不反过来从节点高度推面板高度
   （那样会正反馈，节点一路涨到几千像素） */
function lockHeight(node) {
  const want = Math.round((node.__ppPanelH || PANEL_H0) + TITLE_H);
  const w = Math.max(360, Math.round(node.size?.[0] || PANEL_W));
  if (Math.abs(Math.round(node.size?.[1] || 0) - want) <= 1) return;
  node.__ppSelfSizing = true;
  try {
    node.setSize([w, want]);
  } catch (e) { /* ignore */ }
  node.__ppSelfSizing = false;
}

function hideNative(node) {
  for (const w of node.widgets || []) {
    if (w.__ppOwn) continue;
    w.__ppOrigin = { computeSize: w.computeSize, type: w.type };
    w.computeSize = () => [0, -4];
    w.type = "hidden";
    w.hidden = true;
    w.options = Object.assign({}, w.options, { hidden: true, showLabel: false });
  }
}

/* ------------------------------------------------------------------ 挂载 */
async function mount(node) {
  if (node.__ppUI) return;
  injectCSS();

  const ui = buildPanel();
  node.__ppUI = ui;
  node.__ppPanelH = PANEL_H0;
  hideNative(node);

  if (typeof node.addDOMWidget === "function") {
    const dm = node.addDOMWidget("prompt_puller_ui", "pullui", ui.root, {
      serialize: false,
      hideOnZoom: false,
      getHeight: () => Math.round(node.__ppPanelH || PANEL_H0),
    });
    if (dm) {
      dm.__ppOwn = true;
      dm.computeSize = () => [PANEL_W, Math.round(node.__ppPanelH || PANEL_H0)];
      ui.dom = dm;
    }
  } else {
    ui.form.append(el("div", "pp-empty", "当前前端不支持 DOM 控件，无法显示面板"));
  }

  try {
    SCHEMA = await loadSchema();
  } catch (e) {
    ui.form.innerHTML = "";
    ui.form.append(el("div", "pp-empty", "词库结构没取到：" + (e?.message || e)));
    return;
  }

  const st = readState(node);
  node.__ppState = st;
  renderModeSelect(node, ui);
  renderForm(node, ui);
  writeState(node, st);
  ui.extraInp.value = st.extra || "";

  node.__ppPanelH = Math.max(MIN_H, node.__ppPanelH || PANEL_H0);
  try {
    node.__ppSelfSizing = true;
    node.setSize([Math.max(PANEL_W, Math.round(node.size?.[0] || 0)),
                  Math.round(node.__ppPanelH + TITLE_H)]);
  } catch (e) { /* ignore */ }
  node.__ppSelfSizing = false;
  applyPanel(node, ui);
  lockHeight(node);
  requestAnimationFrame(() => {
    applyPanel(node, ui);
    lockHeight(node);
  });

  /* ---- 交互（任何一步出错都不影响出词） ---- */
  try {
    ui.modeSel.addEventListener("change", () => {
      const st2 = node.__ppState;
      if (!modeDef(ui.modeSel.value)) return;
      st2.mode = ui.modeSel.value;
      writeState(node, st2);
      renderForm(node, ui);
      doExtract(node);
    });

    ui.search.addEventListener("input", () => applySearch(ui));

    ui.btnGo.addEventListener("click", () => {
      rerollSeeds(node);
      doExtract(node);
    });
    ui.btnReset.addEventListener("click", () => {
      const st2 = node.__ppState;
      st2.all[st2.mode] = defaultParams(st2.mode);
      writeState(node, st2);
      renderForm(node, ui);
      doExtract(node);
    });
    ui.btnCopy.addEventListener("click", () => {
      try {
        navigator.clipboard?.writeText(ui.box.value);
        ui.status.textContent = "已复制";
        setTimeout(() => (ui.status.textContent = ""), 900);
      } catch (e) { /* ignore */ }
    });
    ui.btnClear.addEventListener("click", () => {
      ui.box.value = "";
      ui.box2.value = "";
      ui.sub.classList.add("hide");
      syncBox(node, ui);
    });
    ui.btnSize.addEventListener("click", () => {
      const cur = Math.round(node.__ppPanelH || PANEL_H0);
      let i = H_STEPS.findIndex((h) => h > cur);
      if (i < 0) i = 0;
      node.__ppPanelH = H_STEPS[i];
      applyPanel(node, ui);
      lockHeight(node);
      ui.btnSize.textContent = node.__ppPanelH;
      setTimeout(() => (ui.btnSize.textContent = "高度"), 1200);
    });

    const syncBoxL = () => syncBox(node, ui);
    ui.box.addEventListener("input", syncBoxL);
    ui.box.addEventListener("change", syncBoxL);

    ui.extraInp.addEventListener("input", () => {
      setNative(node, "附加提示词", ui.extraInp.value);
      node.__ppState.extra = ui.extraInp.value;
      scheduleExtract(node, 200);
    });
  } catch (e) {
    console.error("[PromptPuller] 控件绑定失败", e);
  }

  // 首次抽取排在绑定之后单独跑，前面任何异常都不挡它
  scheduleExtract(node, 40);

  const prevResize = node.onResize;
  node.onResize = function (size) {
    const r = prevResize?.apply(this, arguments);
    if (this.__ppSelfSizing) return r;
    const want = Math.round((this.__ppPanelH || PANEL_H0) + TITLE_H);
    const cur = Math.round(this.size?.[1] || 0);
    if (Math.abs(cur - want) > 1) lockHeight(this);   // 拉高拉低都弹回固定高度
    return r;
  };

  const prevConfig = node.onConfigure;
  node.onConfigure = function () {
    const r = prevConfig?.apply(this, arguments);
    const st2 = readState(this);
    this.__ppState = st2;
    ui.modeSel.value = st2.mode;
    renderForm(this, ui);
    ui.extraInp.value = st2.extra || "";
    this.__ppPanelH = Math.max(MIN_H, Math.min(this.__ppPanelH || PANEL_H0, 1080));
    setTimeout(() => {
      applyPanel(this, ui);
      lockHeight(this);
      scheduleExtract(this, 60);
    }, 16);
    return r;
  };
}

/* ------------------------------------------------------------------ 注册 */
app.registerExtension({
  name: "sunset.promptPuller",
  async nodeCreated(node) {
    const cls = node?.comfyClass ?? node?.type;
    if (cls !== NODE_CLASS) return;
    try {
      await mount(node);
    } catch (e) {
      console.error("[PromptPuller] 面板挂载失败", e);
    }
  },
});

console.log("[PromptPuller] 提示词抽取面板已加载");
