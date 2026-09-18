/* ============================================================
   MODEWEAR · AI 客服工作台 前端逻辑
   会话列表 / SSE 流式对话 / 客户上下文面板 / 页面视图
   ============================================================ */

// ========== 全局状态 ==========
const state = {
  sessionId: null,          // 当前会话
  conversations: [],        // 会话列表缓存
  filter: "all",            // all / pending / closed
  context: null,            // 右侧面板数据
  recOffset: 0,             // 推荐换一批偏移
  isSending: false,
  uploadedImageUrl: null,
  selectedColor: "",
  selectedSize: "",
};

const DEMO_CUSTOMER_ID = "U10001";

// ========== DOM ==========
const $ = (id) => document.getElementById(id);
const messagesEl = $("messages");
const convListEl = $("convList");
const inputEl = $("messageInput");
const composerEl = $("composer");
const sendBtn = $("sendBtn");

// ========== 工具函数 ==========
function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[c]));
}
const escapeAttr = (v) => escapeHtml(v).replace(/`/g, "&#96;");

// Markdown 渲染（marked + DOMPurify 消毒）
function renderMarkdown(content) {
  if (typeof marked !== "undefined" && marked.parse) {
    const html = marked.parse(content);
    return typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(html) : escapeHtml(content);
  }
  return escapeHtml(content).replace(/\n/g, "<br>");
}

function timeLabel(ts) {
  const d = new Date(ts * 1000);
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return "昨天";
  const diffDays = (now - d) / 86400000;
  if (diffDays < 7) return "周" + "日一二三四五六"[d.getDay()];
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function followLabel(registeredAt) {
  const t = new Date(registeredAt.replace(/-/g, "/")).getTime();
  if (isNaN(t)) return "";
  const months = Math.max(1, Math.round((Date.now() - t) / (30 * 86400000)));
  return `关注 ${months} 个月`;
}

function money(v) {
  const n = Number(v) || 0;
  return Number.isInteger(n) ? `¥${n}` : `¥${n.toFixed(2)}`;
}

function friendlyEta(eta) {
  if (!eta) return "";
  const d = new Date(String(eta).replace(/-/g, "/"));
  if (isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `预计 ${d.getMonth() + 1}月${d.getDate()}日 送达`;
}

// ========== 左侧导航切换 ==========
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    const nav = btn.dataset.nav;
    if (nav === "analytics") { window.open("/admin", "_blank"); return; }
    if (nav === "settings") { window.open("/knowledge", "_blank"); return; }
    switchView(nav);
  });
});

function switchView(nav) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.nav === nav));
  document.querySelectorAll(".chats-view, .page-view").forEach((v) => v.classList.add("hidden"));
  if (nav === "chats") {
    $("view-chats").classList.remove("hidden");
  } else {
    $("view-" + nav)?.classList.remove("hidden");
    if (nav === "dashboard") loadDashboard();
    if (nav === "orders") loadOrdersPage();
    if (nav === "products") loadProductsPage();
    if (nav === "customers") loadCustomersPage();
  }
}

// ========== 会话列表 ==========
async function loadConversations() {
  try {
    const res = await fetch("/admin/sessions");
    const data = await res.json();
    state.conversations = data.sessions || [];
    renderConversations();
  } catch (e) {
    console.warn("会话列表加载失败:", e);
  }
}

function convCustomerName(session) {
  // 演示环境统一展示绑定客户
  return state.context?.customer?.nickname || "客户";
}

function renderConversations() {
  const now = Date.now() / 1000;
  const all = state.conversations;
  const pending = all.filter((s) => now - (s.last_active || 0) < 86400);
  const closed = all.filter((s) => now - (s.last_active || 0) >= 86400);
  $("cntAll").textContent = all.length;
  $("cntPending").textContent = pending.length;
  $("cntClosed").textContent = closed.length;

  const badge = $("navChatBadge");
  if (pending.length > 0) {
    badge.textContent = pending.length;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }

  const shown = state.filter === "pending" ? pending : state.filter === "closed" ? closed : all;
  shown.sort((a, b) => (b.last_active || 0) - (a.last_active || 0));

  convListEl.innerHTML = "";
  if (!shown.length) {
    convListEl.innerHTML = `<div style="text-align:center;color:var(--text-3);padding:30px 10px;font-size:13px;">暂无会话<br/>点击下方「新的会话」开始</div>`;
    return;
  }

  for (const s of shown) {
    const item = document.createElement("div");
    item.className = "conv-item" + (s.session_id === state.sessionId ? " active" : "");
    const name = convCustomerName(s);
    const initial = name.charAt(0) || "客";
    const unread = state.filter === "pending" && s.message_count > 0 && now - (s.last_active || 0) < 3600
      ? `<span class="unread">1</span>` : "";
    item.innerHTML = `
      <div class="avatar-wrap">
        <div class="avatar">${escapeHtml(initial)}</div>
        <span class="presence"></span>
      </div>
      <div class="preview">
        <div class="conv-name">${escapeHtml(name)} <span class="conv-time">${timeLabel(s.last_active || 0)}</span></div>
        <div class="conv-preview">${escapeHtml(s.first_message || "新会话")}</div>
      </div>
      ${unread}
    `;
    item.addEventListener("click", () => selectConversation(s.session_id));
    convListEl.appendChild(item);
  }
}

document.querySelectorAll(".conv-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".conv-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.filter = tab.dataset.filter;
    renderConversations();
  });
});

async function selectConversation(sessionId) {
  if (state.isSending) return;
  state.sessionId = sessionId;
  localStorage.setItem("zhice-session-id", sessionId);
  renderConversations();
  await loadSessionMessages(sessionId);
  loadContext(sessionId);
}

async function loadSessionMessages(sessionId) {
  clearMessages();
  try {
    const res = await fetch(`/admin/sessions/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    const history = (data.chat_history || []).filter((m) => m.role === "human" || m.role === "ai");
    for (const m of history) {
      appendMessage(m.role === "human" ? "user" : "ai", m.content, m.tools_used || []);
    }
  } catch (e) {
    console.warn("会话历史加载失败:", e);
  }
}

function newConversation() {
  state.sessionId = null;
  localStorage.removeItem("zhice-session-id");
  clearMessages();
  ensureEmptyHint();
  renderConversations();
  $("peerName").textContent = "新的会话";
  $("peerSub").textContent = "发送消息后自动创建";
  $("peerBadge").classList.add("hidden");
  inputEl.focus();
}

$("newConvBtn").addEventListener("click", newConversation);

// ========== 消息渲染 ==========
function clearMessages() {
  messagesEl.innerHTML = "";
  $("emptyHint")?.remove();
}

function ensureEmptyHint() {
  if (!messagesEl.children.length) {
    messagesEl.innerHTML = `
      <div class="empty-hint" id="emptyHint">
        <div class="empty-icon">💬</div>
        <p>选择左侧会话，或点击「新的会话」开始服务</p>
      </div>`;
  }
}

function createMessageRow(role) {
  $("emptyHint")?.remove();
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  const avatar = document.createElement(role === "user" ? "div" : "div");
  avatar.className = role === "user" ? "avatar" : "avatar-ai";
  avatar.textContent = role === "user" ? (state.context?.customer?.nickname || "客").charAt(0) : "AI";
  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";
  const sender = document.createElement("div");
  sender.className = "msg-sender";
  sender.textContent = role === "user"
    ? (state.context?.customer?.nickname || "客户")
    : "MODEWEAR AI 客服";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  wrap.append(sender, bubble);
  row.append(avatar, wrap);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { row, wrap, bubble };
}

function createFeedbackButtons(bubbleWrap) {
  const bar = document.createElement("div");
  bar.className = "feedback-bar";
  bar.innerHTML = `
    <button class="feedback-btn" data-rating="positive" title="有帮助">👍</button>
    <button class="feedback-btn" data-rating="negative" title="没帮助">👎</button>`;
  bar.querySelectorAll(".feedback-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      bar.querySelectorAll(".feedback-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId || "anonymous",
          message_index: 0,
          rating: btn.dataset.rating,
        }),
      }).catch(() => {});
    });
  });
  bubbleWrap.appendChild(bar);
}

function appendMessage(role, content, tools = []) {
  const { wrap, bubble } = createMessageRow(role);
  bubble.innerHTML = renderMarkdown(content);
  if (role === "ai" && tools?.length) {
    const line = document.createElement("div");
    line.className = "tool-status-line";
    line.innerHTML = tools.map((t) => `<span class="ts-item done">${escapeHtml(t)}</span>`).join("");
    wrap.appendChild(line);
  }
  if (role === "ai") createFeedbackButtons(wrap);
  return { wrap, bubble };
}

// ========== 发送消息（SSE 流式） ==========
composerEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (text) sendMessage(text);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (text) sendMessage(text);
  }
});

// 自适应高度
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + "px";
});

async function sendMessage(message) {
  if (state.isSending) return;
  state.isSending = true;
  sendBtn.disabled = true;

  let fullMessage = message;
  if (state.uploadedImageUrl) {
    fullMessage = `${message}\n\n[用户上传了图片：${state.uploadedImageUrl}]`;
    clearUploadPreview();
  }

  inputEl.value = "";
  inputEl.style.height = "auto";

  // 用户消息上屏
  const { bubble: userBubble } = createMessageRow("user");
  userBubble.innerHTML = renderMarkdown(fullMessage);

  // 若无会话，先占位一个临时 id（SSE session 事件会返回真实 id）
  if (!state.sessionId) {
    $("peerName").textContent = state.context?.customer?.nickname || "客户";
    $("peerSub").textContent = "来自 MODEWEAR · 新会话";
  }

  // AI 流式气泡
  const { wrap: aiWrap, bubble: aiBubble, row: aiRow } = (() => {
    const r = createMessageRow("ai");
    r.bubble.classList.add("streaming-cursor");
    return r;
  })();
  const toolLine = document.createElement("div");
  toolLine.className = "tool-status-line hidden";
  aiWrap.appendChild(toolLine);
  const toolEls = new Map();

  let fullReply = "";
  let toolsUsed = [];

  try {
    const response = await fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: fullMessage, session_id: state.sessionId, use_agent: true }),
    });
    if (!response.ok) throw new Error(`请求失败：${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const evt of events) {
        for (const line of evt.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let data;
          try { data = JSON.parse(line.slice(6)); } catch { continue; }

          switch (data.type) {
            case "session":
              state.sessionId = data.session_id;
              localStorage.setItem("zhice-session-id", data.session_id);
              break;
            case "token":
              fullReply += data.content;
              aiBubble.innerHTML = renderMarkdown(fullReply);
              messagesEl.scrollTop = messagesEl.scrollHeight;
              break;
            case "tool_start": {
              toolLine.classList.remove("hidden");
              const el = document.createElement("span");
              el.className = "ts-item";
              el.innerHTML = `<span class="spinner"></span> ${escapeHtml(data.tool)}`;
              toolLine.appendChild(el);
              toolEls.set(data.tool, el);
              messagesEl.scrollTop = messagesEl.scrollHeight;
              break;
            }
            case "tool_end": {
              const el = toolEls.get(data.tool);
              if (el) {
                el.classList.add("done");
                el.querySelector(".spinner")?.remove();
                el.textContent = data.tool;
              }
              if (!toolsUsed.includes(data.tool)) toolsUsed.push(data.tool);
              break;
            }
            case "done":
              if (data.reply) fullReply = data.reply;
              if (data.tools_used?.length) toolsUsed = data.tools_used;
              if (data.escalate) {
                const banner = document.createElement("div");
                banner.className = "escalate-banner";
                banner.textContent = "检测到客户情绪波动，已创建人工工单，请及时跟进。";
                aiWrap.appendChild(banner);
              }
              break;
            case "error":
              aiBubble.innerHTML = renderMarkdown(data.message || "抱歉，处理遇到问题。");
              aiRow.classList.add("error-message");
              break;
          }
        }
      }
    }
  } catch (error) {
    aiBubble.innerHTML = `抱歉，服务暂时不可用。${escapeHtml(error.message)}`;
    aiRow.classList.add("error-message");
  }

  aiBubble.classList.remove("streaming-cursor");
  if (!fullReply) aiBubble.innerHTML = renderMarkdown("抱歉，我暂时无法回答这个问题。");

  // 补全工具标记
  toolLine.classList.remove("hidden");
  toolLine.innerHTML = toolsUsed.map((t) => `<span class="ts-item done">${escapeHtml(t)}</span>`).join("");
  if (!toolsUsed.length) toolLine.classList.add("hidden");

  createFeedbackButtons(aiWrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // 刷新会话列表与上下文
  await loadConversations();
  if (state.sessionId) loadContext(state.sessionId);

  sendBtn.disabled = false;
  state.isSending = false;
  inputEl.focus();
}

// ========== 快捷 chips ==========
document.querySelectorAll("#quickChips .chip[data-msg]").forEach((chip) => {
  chip.addEventListener("click", () => sendMessage(chip.dataset.msg));
});

const MORE_CHIPS = ["查物流", "优惠券", "洗护建议", "转人工"];
let moreShown = false;
$("moreChips").addEventListener("click", () => {
  if (moreShown) return;
  moreShown = true;
  const labels = { "查物流": "帮我查一下订单的物流信息", "优惠券": "我有什么可用的优惠券？", "洗护建议": "这条裙子应该怎么洗护保养？", "转人工": "我需要转人工客服" };
  const moreBtn = $("moreChips");
  for (const label of MORE_CHIPS) {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = label;
    chip.dataset.msg = labels[label];
    chip.addEventListener("click", () => sendMessage(labels[label]));
    moreBtn.before(chip);
  }
  moreBtn.remove();
});

// ========== 右侧上下文面板 ==========
document.querySelectorAll(".ctx-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".ctx-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".ctx-pane").forEach((p) => p.classList.remove("active"));
    $(`pane-${tab.dataset.ctx}`)?.classList.add("active");
  });
});

document.querySelectorAll("[data-goto]").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.goto));
});

async function loadContext(sessionId) {
  $("ctxSkeleton").classList.remove("hidden");
  $("customerContent").classList.add("hidden");
  try {
    const res = await fetch(`/api/workbench/context/${sessionId}?user_id=${DEMO_CUSTOMER_ID}`);
    if (!res.ok) throw new Error("context unavailable");
    state.context = await res.json();
    state.recOffset = 0;
    renderContext();
    renderConversations(); // 客户名加载后刷新会话列表显示
  } catch (e) {
    console.warn("上下文加载失败:", e);
    $("ctxSkeleton").classList.add("hidden");
  }
}

function renderContext() {
  const ctx = state.context;
  if (!ctx) return;
  const c = ctx.customer || {};
  $("cntOrders").textContent = (ctx.orders || []).length;
  $("cntProducts").textContent = ctx.current_product ? 1 : 0;

  // ----- 客户卡片 -----
  $("cAvatar").textContent = (c.nickname || "客").charAt(0);
  $("cName").textContent = c.nickname || "—";
  $("cGender").textContent = c.gender === "女" ? "♀" : c.gender === "男" ? "♂" : "";
  $("cVip").textContent = c.member_level || "普通";
  $("cFollow").textContent = followLabel(c.registered_at || "");
  $("cPhone").textContent = c.phone || "—";
  $("cLocation").textContent = c.location || "—";
  $("cStyles").textContent = (c.favorite_styles || []).join("、") || "—";
  $("cTags").innerHTML = (c.preference_tags || [])
    .map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");

  // ----- 聊天头部同步 -----
  $("peerAvatar").textContent = (c.nickname || "客").charAt(0);
  if (state.sessionId) {
    $("peerName").textContent = c.nickname || "客户";
    const shopTag = c.total_orders === 0 ? "新客" : "";
    $("peerBadge").textContent = shopTag || (c.member_level || "");
    $("peerBadge").classList.toggle("hidden", false);
    $("peerSub").textContent = `来自 MODEWEAR${c.location ? " · " + c.location : ""}`;
  }

  // ----- 最近订单 -----
  const orders = (ctx.orders || []).slice(0, 2);
  $("recentOrders").innerHTML = orders.map((o) => orderCardHtml(o, true)).join("") ||
    `<div class="order-eta">暂无订单</div>`;

  // ----- 当前咨询商品 -----
  renderCurrentProduct(ctx.current_product);

  // ----- 推荐 -----
  renderRecommendations();

  $("ctxSkeleton").classList.add("hidden");
  $("customerContent").classList.remove("hidden");
}

function orderCardHtml(o) {
  const first = (o.items && o.items[0]) || {};
  const statusClass = /已完成|已签收/.test(o.status) ? "badge-done"
    : /退款|退货/.test(o.status) ? "badge-pending" : "badge-status";
  const thumb = first.image_url || (state.context?.current_product?.image_url) || "";
  const eta = o.tracking?.estimated_delivery ? friendlyEta(o.tracking.estimated_delivery) : "";
  const itemsText = (o.items || []).map((i) => i.name).join("、");
  return `
    <div class="order-card">
      <div class="order-main">
        ${thumb ? `<img class="order-thumb" src="${escapeAttr(thumb)}" alt="" onerror="this.style.visibility='hidden'"/>` : ""}
        <div class="order-info">
          <div class="order-name">${escapeHtml(itemsText || o.order_id)}</div>
          <div class="order-sub">${escapeHtml(o.order_id)}</div>
        </div>
        <div style="text-align:right">
          <span class="badge ${statusClass}">${escapeHtml(o.status)}</span>
          <div class="order-price">${money(o.total)}<small>${escapeHtml(String(o.created_at).slice(0, 10))}</small></div>
        </div>
      </div>
      ${eta ? `<div class="order-eta">${escapeHtml(eta)} · ${escapeHtml(o.tracking?.carrier || "")} ${escapeHtml(o.tracking?.number || "")}</div>` : ""}
    </div>`;
}

const COLOR_HEX = {
  "米白": "#f3efe6", "白色": "#f7f7f7", "黑色": "#1c1c1e", "灰色": "#9a9aa0",
  "卡其": "#c8b28a", "深蓝": "#2c3a55", "藏青": "#2c3a55", "浅蓝": "#a8c3e0",
  "粉色": "#f2c4cd", "军绿": "#6b7047", "驼色": "#c19a6b", "红色": "#c0392b",
};
function colorHex(name) {
  for (const key of Object.keys(COLOR_HEX)) {
    if (name.includes(key)) return COLOR_HEX[key];
  }
  return "#d8d2c8";
}

function renderCurrentProduct(p) {
  const box = $("currentProduct");
  if (!p) {
    box.innerHTML = `<div class="order-eta">暂未识别到咨询商品</div>`;
    state.selectedColor = "";
    state.selectedSize = "";
    return;
  }
  state.selectedColor = p.colors?.[0] || "";
  state.selectedSize = p.sizes?.[Math.min(2, (p.sizes?.length || 1) - 1)] || "";
  const stars = "★".repeat(Math.round(p.rating || 0)) + "☆".repeat(5 - Math.round(p.rating || 0));
  box.innerHTML = `
    <div class="cp-top">
      ${p.image_url ? `<img class="cp-image" src="${escapeAttr(p.image_url)}" alt="${escapeAttr(p.name)}" onerror="this.style.visibility='hidden'"/>` : ""}
      <div class="cp-info">
        <div class="cp-name">${escapeHtml(p.name)}</div>
        <div class="cp-tags">${escapeHtml((p.tags || []).join(" · "))}</div>
        <div class="cp-price-row">
          <span class="cp-price">${money(p.price)}</span>
          ${p.original_price ? `<span class="cp-original">${money(p.original_price)}</span>` : ""}
        </div>
        ${p.rating ? `<div class="cp-rating"><span class="stars">${stars}</span> ${p.rating} <span class="count">(${p.rating_count || 0}条评价)</span></div>` : ""}
      </div>
    </div>
    <div class="cp-colors">
      ${(p.colors || []).map((c, i) => `
        <span class="color-dot ${i === 0 ? "selected" : ""}" data-color="${escapeAttr(c)}"
              title="${escapeAttr(c)}" style="background:${colorHex(c)}"></span>`).join("")}
    </div>
    <div class="cp-sizes">
      ${(p.sizes || []).map((s, i) => `
        <button class="size-chip ${i === 2 ? "selected" : ""}" data-size="${escapeAttr(s)}">${escapeHtml(s)}</button>`).join("")}
    </div>
    <div class="cp-actions">
      <button class="mini-cart-btn" id="quickAddCart" title="加入购物车">＋</button>
    </div>
  `;

  box.querySelectorAll(".color-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      box.querySelectorAll(".color-dot").forEach((d) => d.classList.remove("selected"));
      dot.classList.add("selected");
      state.selectedColor = dot.dataset.color;
    });
  });
  box.querySelectorAll(".size-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      box.querySelectorAll(".size-chip").forEach((c) => c.classList.remove("selected"));
      chip.classList.add("selected");
      state.selectedSize = chip.dataset.size;
    });
  });
  $("quickAddCart")?.addEventListener("click", () => {
    const sizePart = state.selectedSize ? `、尺码${state.selectedSize}` : "";
    sendMessage(`请帮我把「${p.name}」（颜色：${state.selectedColor || "默认"}${sizePart}）加入购物车`);
  });
}

function renderRecommendations() {
  const recs = state.context?.recommendations || [];
  const grid = $("recGrid");
  if (!recs.length) {
    grid.innerHTML = `<div class="order-eta">暂无推荐</div>`;
    return;
  }
  const start = state.recOffset % recs.length;
  const shown = [];
  for (let i = 0; i < Math.min(2, recs.length); i++) {
    shown.push(recs[(start + i) % recs.length]);
  }
  grid.innerHTML = shown.map((p) => `
    <div class="rec-card">
      ${p.image_url ? `<img src="${escapeAttr(p.image_url)}" alt="${escapeAttr(p.name)}" onerror="this.style.visibility='hidden'"/>` : `<div style="height:108px;background:#f4f4f6"></div>`}
      <div class="rec-info">
        <div class="rec-name" title="${escapeAttr(p.name)}">${escapeHtml(p.name)}</div>
        <div class="rec-price-row">
          <span class="rec-price">${money(p.price)}</span>
          <button class="rec-cart" data-pid="${escapeAttr(p.id)}" title="加入购物车">＋</button>
        </div>
      </div>
    </div>`).join("");

  grid.querySelectorAll(".rec-cart").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = recs.find((x) => x.id === btn.dataset.pid);
      if (p) sendMessage(`请帮我把「${p.name}」加入购物车`);
    });
  });
}

$("shuffleRec").addEventListener("click", () => {
  state.recOffset += 2;
  renderRecommendations();
});

// ========== 快捷回复（插入输入框） ==========
const CANNED_REPLIES = [
  ["您好呀～很高兴为你服务～", "开场问候"],
  ["这条连衣裙是标准版型，如果你在 S-M 之间，建议选 M 会更舒适～", "尺码建议"],
  ["现货商品一般 24 小时内发出，预计 2-3 天送达～", "发货时效"],
  ["支持 7 天无理由退换货，商品不影响二次销售即可哦～", "退换政策"],
  ["面料柔软亲肤，建议冷水手洗，阴凉处晾干～", "洗护建议"],
  ["您是我们的 VIP 会员，本次可享专属折扣～", "会员权益"],
  ["已经为您加急处理，预计明天就能发货啦～", "催单安抚"],
  ["如需人工客服，随时告诉我，马上为您转接～", "转人工"],
];
$("replyList").innerHTML = CANNED_REPLIES.map(([text, tag]) => `
  <button class="reply-item" data-text="${escapeAttr(text)}">${escapeHtml(text)}<small>${escapeHtml(tag)}</small></button>
`).join("");
document.querySelectorAll(".reply-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    inputEl.value = btn.dataset.text;
    inputEl.focus();
    inputEl.dispatchEvent(new Event("input"));
  });
});

// ========== 商品搜索（右侧面板） ==========
let productSearchTimer = null;
$("productSearch").addEventListener("input", () => {
  clearTimeout(productSearchTimer);
  productSearchTimer = setTimeout(() => loadProductMiniList($("productSearch").value.trim()), 250);
});

async function loadProductMiniList(query = "") {
  try {
    const res = await fetch(`/api/workbench/products?query=${encodeURIComponent(query)}&limit=15`);
    const data = await res.json();
    $("productList").innerHTML = (data.products || []).map((p) => `
      <div class="product-mini" data-name="${escapeAttr(p.name)}">
        ${p.image_url ? `<img src="${escapeAttr(p.image_url)}" alt="" onerror="this.style.visibility='hidden'"/>` : ""}
        <div class="pm-info">
          <div class="pm-name">${escapeHtml(p.name)}</div>
          <div class="pm-sub">${escapeHtml(p.category)} · 库存${escapeHtml(p.stock_status || "-")}</div>
        </div>
        <div class="pm-price">${money(p.price)}</div>
      </div>`).join("") || `<div class="order-eta">没有匹配的商品</div>`;

    document.querySelectorAll(".product-mini").forEach((el) => {
      el.addEventListener("click", () => sendMessage(`请介绍一下「${el.dataset.name}」的详细信息`));
    });
  } catch (e) {
    console.warn("商品列表加载失败:", e);
  }
}

// ========== 页面视图 ==========
async function loadDashboard() {
  try {
    const res = await fetch("/api/workbench/stats");
    const s = await res.json();
    const rate = s.feedback?.rate && s.feedback.rate !== "N/A" ? s.feedback.rate : "—";
    $("statCards").innerHTML = `
      <div class="stat-card"><div class="num">${s.active_sessions}</div><div class="label">24h 活跃会话</div></div>
      <div class="stat-card"><div class="num">${s.total_sessions}</div><div class="label">累计会话</div></div>
      <div class="stat-card"><div class="num">${rate}</div><div class="label">客户好评率</div></div>
      <div class="stat-card"><div class="num">${s.total_products}</div><div class="label">在售商品</div></div>
      <div class="stat-card"><div class="num">${s.total_customers}</div><div class="label">注册客户</div></div>`;
  } catch (e) {
    $("statCards").innerHTML = `<div class="tip">统计数据加载失败</div>`;
  }
}

async function loadOrdersPage() {
  try {
    const res = await fetch(`/api/workbench/orders`);
    const data = await res.json();
    const saved = state.context;
    state.context = state.context || { current_product: null };
    $("pageOrders").innerHTML = (data.orders || []).map((o) => orderCardHtml(o)).join("") ||
      `<div class="tip">暂无订单</div>`;
    state.context = saved;
  } catch (e) {
    $("pageOrders").innerHTML = `<div class="tip">订单加载失败</div>`;
  }
}

async function loadProductsPage() {
  try {
    const res = await fetch("/api/workbench/products?limit=40");
    const data = await res.json();
    $("pageProducts").innerHTML = (data.products || []).map((p) => `
      <div class="product-page-card">
        ${p.image_url ? `<img src="${escapeAttr(p.image_url)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'"/>` : ""}
        <div class="ppc-info">
          <div class="ppc-name">${escapeHtml(p.name)}</div>
          <div class="ppc-sub">${escapeHtml(p.category)}${p.rating ? ` · ★${p.rating}` : ""}</div>
          <div class="ppc-price-row">
            <span class="ppc-price">${money(p.price)}</span>
            ${p.original_price ? `<span class="ppc-original">${money(p.original_price)}</span>` : ""}
          </div>
        </div>
      </div>`).join("");
  } catch (e) {
    $("pageProducts").innerHTML = `<div class="tip">商品加载失败</div>`;
  }
}

async function loadCustomersPage() {
  try {
    const res = await fetch("/api/workbench/customers");
    const data = await res.json();
    $("pageCustomers").innerHTML = (data.customers || []).map((c) => `
      <div class="customer-page-card">
        <div class="cpc-head">
          <div class="avatar">${escapeHtml((c.nickname || "客").charAt(0))}</div>
          <div>
            <div class="cpc-name">${escapeHtml(c.nickname)} <span class="badge badge-vip">${escapeHtml(c.member_level)}</span></div>
            <div class="cpc-sub">${escapeHtml(c.phone)} · ${escapeHtml(c.total_orders)}笔订单 · ${money(c.total_spent)}</div>
          </div>
        </div>
        <div class="cpc-tags">
          ${(c.preference_tags || c.favorite_styles || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}
        </div>
      </div>`).join("");
  } catch (e) {
    $("pageCustomers").innerHTML = `<div class="tip">客户加载失败</div>`;
  }
}

// ========== 图片上传 ==========
$("uploadBtn").addEventListener("click", () => $("imageInput").click());
$("imageBtn").addEventListener("click", () => $("imageInput").click());

$("imageInput").addEventListener("change", async () => {
  const file = $("imageInput").files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || "上传失败，请重试");
      return;
    }
    const data = await res.json();
    if (data.url) {
      state.uploadedImageUrl = data.url;
      $("previewImg").src = URL.createObjectURL(file);
      $("imagePreview").classList.remove("hidden");
    }
  } catch (e) {
    alert("图片上传失败，请重试");
  } finally {
    $("imageInput").value = "";
  }
});

$("removeImg").addEventListener("click", clearUploadPreview);

function clearUploadPreview() {
  state.uploadedImageUrl = null;
  $("imagePreview").classList.add("hidden");
  $("previewImg").src = "";
}

// 商品按钮：把当前咨询商品名插入输入框
$("productBtn").addEventListener("click", () => {
  const p = state.context?.current_product;
  if (!p) {
    alert("当前会话尚未识别到咨询商品");
    return;
  }
  inputEl.value = `请介绍一下「${p.name}」`;
  inputEl.focus();
  inputEl.dispatchEvent(new Event("input"));
});

// ========== 初始化 ==========
(async function init() {
  // 恢复上次的会话
  const saved = localStorage.getItem("zhice-session-id");
  await loadConversations();
  if (saved && state.conversations.some((s) => s.session_id === saved)) {
    await selectConversation(saved);
  } else {
    newConversation();
    // 无会话时也渲染默认客户上下文（用当前时间生成临时上下文 id 无意义，直接取默认客户）
    loadDefaultContext();
  }
  loadProductMiniList();
})();

async function loadDefaultContext() {
  // 尚无会话时，用「临时会话 id」拉取默认客户上下文（服务端只校验格式）
  const tempId = "web-" + Date.now().toString(36);
  try {
    const res = await fetch(`/api/workbench/context/${tempId}?user_id=${DEMO_CUSTOMER_ID}`);
    if (res.ok) {
      state.context = await res.json();
      renderContext();
      renderConversations();
    }
  } catch (e) { /* 忽略 */ }
}
