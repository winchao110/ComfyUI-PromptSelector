/* ------------------------------------------------------------------ 高度驱动
 *
 * 为什么要单独抽这一层：
 *
 * 之前每套皮肤各自按「面板元素实测高度 → node.setSize」贴高度，而 DOM 面板元素的
 * 高度又是由前端按「节点高度 / 控件高度」分配的，于是形成
 *
 *      节点高  →  面板元素高  →  节点高
 *
 * 的正反馈：每 300~700ms 涨一截（正好是 panelPad + edgeGap 那些常数），
 * 一路拉到几千像素且永不收敛，表现就是「节点自动无限向下延伸、拉得老长」。
 *
 * 现在改成单向流，任何环节都不再读「会随节点高度变化的量」：
 *
 *      面板内容高度(body.scrollHeight)
 *          → node.__sunPanelH        （唯一来源，只在内容真变时更新）
 *          → computeSize / getHeight （只读上面那个数）
 *          → setSize([w, panelH + 控件偏移])
 *
 * 另外两道保险：
 *   1) 硬上限 maxPanelH，任何情况下都不会把节点撑成几千像素；
 *   2) 熔断：短时间内连续同向改高度太多次，就暂停 5 秒并打一次 warn，
 *      临时停用自动撑高（节点仍可正常使用，用户手动拉也行）。
 */

export const LAYOUT = {
  chrome: 22,        // 面板根元素的 padding(10*2) + border(1*2)
  titleH: 30,        // LiteGraph 默认标题栏高度，取不到控件 y 时兜底
  edgeGap: 4,        // 面板底边留白（前端 computeSize 会 +4，这里对齐）
  minPanelH: 160,
  maxPanelH: 1520,   // 硬上限：再高也不会自动撑
  brakeStreak: 12,   // 连续同向改高度次数上限
  brakeWindow: 900,  // 判定「连续」的时间窗
  brakePause: 5000,  // 熔断后暂停自动撑高的时长
};

const titleH = () => {
  try {
    const h = globalThis.LiteGraph?.NODE_TITLE_HEIGHT;
    return Number.isFinite(h) && h > 0 ? h : LAYOUT.titleH;
  } catch (e) { return LAYOUT.titleH; }
};

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/* 只认内容高度：主面板 body 自身的滚动高度（它不受节点高度影响，这是关键）。
   右侧即时框按「有上限的补充项」处理：它是 flex 列，被拉伸时 scrollHeight 会跟着
   容器长，所以这里 clamp 一个上限 —— 既能盖住「负面/英文副框出现后右栏变高」的
   情况，又不会让右栏反过来把节点撑起来。
   绝不读 root.offsetHeight —— 它可能被前端按节点高度撑开，读它就把环闭合了。 */
export function measurePanelH(root, body, chrome = LAYOUT.chrome) {
  let h = 0;
  try { if (body) h = body.scrollHeight || 0; } catch (e) { /* ignore */ }
  try {
    const right = root?.querySelector?.(".sun-right");
    if (right) h = Math.max(h, Math.min(right.scrollHeight || 0, LAYOUT.maxPanelH / 3));
  } catch (e) { /* ignore */ }
  return h > 0 ? Math.round(h + chrome) : 0;
}

/* 第一帧的估值：面板还没进 document 时量不到内容高度，
   而 computeSize/getHeight 又必须给个数（给 0 会让节点先塌一下再弹开）。
   只用来撑过最初一帧，第一次量到内容后就被真值替换。 */
export function bootPanelH(node, def = 620) {
  const s = Math.round(node?.size?.[1] || 0);
  if (s > 280) return clamp(s - 40, LAYOUT.minPanelH, LAYOUT.maxPanelH);
  return clamp(def, LAYOUT.minPanelH, LAYOUT.maxPanelH);
}

/* 面板顶边在节点坐标系里的偏移。
   优先用前端自己算好的 DOM 控件 y（它只跟前面的控件有关，与节点高度无关），
   其次用标题栏高度常量。不要用 node.pos + 画布 rect 反推：
   那条路在缩放、分组、Vue 节点渲染下都会带误差，误差再被 setSize 吃掉就变成了缓慢生长。 */
export function widgetOffset(node, dom, fallback) {
  try {
    if (dom && Number.isFinite(dom.y) && dom.y > 0 && dom.y < 400) {
      return Math.round(dom.y);
    }
  } catch (e) { /* ignore */ }
  return Math.round(fallback || titleH());
}

/**
 * 给一个节点建/取高度驱动。
 * @param {object} node  LGraphNode
 * @param {object} opts  { root, body, chrome, minWidth, width, tag }
 * @returns 驱动对象：{ root, panelH, measure(), apply(), refresh(), schedule(ms), destroy() }
 */
export function createHeightDriver(node, opts = {}) {
  if (!node) return null;
  if (node.__sunHDrv && node.__sunHDrv.root === opts.root) return node.__sunHDrv;

  const st = {
    root: opts.root || null,
    body: opts.body || null,
    tag: opts.tag || "Sunset",
    panelH: Math.round(node.__sunPanelH || 0),
    timer: 0,
    streak: 0,
    dir: 0,
    lastAt: 0,
    warned: false,
    frozenUntil: 0,
    pending: false,
    gone: false,
  };

  const domOf = () => node.__zsDm || node.__k2dm || node.__sunDm || null;

  const measure = () => {
    if (st.gone) return 0;
    if (!st.body) {
      st.body = st.root?.querySelector?.(".zs-body, .k2-body, .sun-left > *") || null;
    }
    const h = measurePanelH(st.root, st.body);
    if (h > 0) {
      st.panelH = clamp(h, LAYOUT.minPanelH, LAYOUT.maxPanelH);
      node.__sunPanelH = st.panelH;
    }
    return st.panelH;
  };

  const apply = () => {
    if (st.gone || node.__sunGone) return false;
    if (node.__sunSizing) { st.pending = true; return false; }   // 自己触发的 onResize，别套娃
    const now = Date.now();
    if (now < st.frozenUntil) return false;

    const panelH = st.panelH || 0;
    if (!panelH) return false;

    const off = widgetOffset(node, domOf(), titleH());
    const goal = Math.round(panelH + off + LAYOUT.edgeGap);
    const cur = Math.round(node.size?.[1] || 0);
    const curW = Math.round(node.size?.[0] || 0);
    const want = Math.max(curW, Math.round(opts.width?.() || 0), Math.round(opts.minWidth || 0));

    if (Math.abs(goal - cur) <= 2 && Math.abs(want - curW) <= 1) {
      st.streak = 0;
      return false;
    }

    // 熔断：短时间内连续同向推太多次，说明还有地方在反馈，先停手
    const dir = goal > cur ? 1 : -1;
    if (dir !== st.dir || now - st.lastAt > LAYOUT.brakeWindow) st.streak = 0;
    st.streak++;
    st.dir = dir;
    st.lastAt = now;
    if (st.streak > LAYOUT.brakeStreak) {
      st.frozenUntil = now + LAYOUT.brakePause;
      st.streak = 0;
      if (!st.warned) {
        st.warned = true;
        console.warn(
          `[${st.tag}] 面板高度连续单向变化超过 ${LAYOUT.brakeStreak} 次，已暂停自动撑高 ${LAYOUT.brakePause / 1000}s。` +
          `节点照常可用；如仍异常请反馈：前端版本、浏览器缩放比例、是否开启 Vue Nodes。`
        );
      }
      return false;
    }

    node.__sunSizing = true;
    try { node.setSize?.([want, goal]); } catch (e) { /* ignore */ }
    try {
      node.graph?.setDirtyCanvas?.(true, true);
      node.setDirtyCanvas?.(true, true);
    } catch (e) { /* ignore */ }
    /* 闸门要一帧后放开；但标签页不可见时 rAF 不触发，再加个定时兜底，
       否则闸门卡死会让这个节点再也长不高（还会被 scheduleFit 反复重试）。 */
    const release = () => {
      if (!node.__sunSizing) return;
      node.__sunSizing = false;
      if (st.pending) { st.pending = false; drv.schedule(0); }
    };
    requestAnimationFrame(release);
    setTimeout(release, 120);
    return true;
  };

  const drv = {
    root: st.root,
    get panelH() { return st.panelH; },
    measure,
    apply,
    refresh() { measure(); return apply(); },
    schedule(ms = 0) {
      if (st.gone) return;
      clearTimeout(st.timer);
      st.timer = setTimeout(() => { if (!st.gone) drv.refresh(); }, ms);
    },
    reset() { st.warned = false; st.frozenUntil = 0; st.streak = 0; },
    destroy() { st.gone = true; clearTimeout(st.timer); },
  };

  node.__sunHDrv = drv;
  return drv;
}
