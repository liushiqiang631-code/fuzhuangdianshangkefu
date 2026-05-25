const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const clearBtn = document.querySelector("#clearBtn");
const exportBtn = document.querySelector("#exportBtn");
const toolsCountEl = document.querySelector("#toolsCount");
const modelNameEl = document.querySelector("#modelName");
const agentStatusEl = document.querySelector("#agentStatus span:nth-child(2)");
const tokenUsageEl = document.querySelector("#tokenUsage");

let sessionId = localStorage.getItem("zhice-session-id") || `web-${Date.now().toString(36)}`;
let transcript = [];
let totalTokens = 0;
localStorage.setItem("zhice-session-id", sessionId);

function timeLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return entities[char];
  });
}

// 渲染内容（优先 Markdown，降级为纯文本）
function renderContent(content) {
  if (typeof marked !== "undefined" && marked.parse) {
    return marked.parse(content);
  }
  return escapeHtml(content).replace(/\n/g, "<br>");
}

// 设置所有快捷按钮的可用状态
function setQuickButtonsDisabled(disabled) {
  document.querySelectorAll("[data-prompt], .quick-item").forEach((btn) => {
    btn.disabled = disabled;
    btn.style.opacity = disabled ? "0.5" : "";
    btn.style.pointerEvents = disabled ? "none" : "";
  });
}

// 创建反馈按钮
function createFeedbackButtons(msgIndex) {
  const wrapper = document.createElement("div");
  wrapper.className = "feedback-bar";
  wrapper.innerHTML = `
    <button class="feedback-btn" data-rating="positive" data-index="${msgIndex}" title="有帮助">👍</button>
    <button class="feedback-btn" data-rating="negative" data-index="${msgIndex}" title="没帮助">👎</button>
  `;
  wrapper.querySelectorAll(".feedback-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const rating = btn.dataset.rating;
      const index = parseInt(btn.dataset.index);
      sendFeedback(index, rating);
      // 高亮选中
      wrapper.querySelectorAll(".feedback-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
    });
  });
  return wrapper;
}

// 发送反馈到后端
async function sendFeedback(messageIndex, rating) {
  try {
    await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message_index: messageIndex, rating }),
    });
  } catch (e) {
    console.warn("反馈发送失败:", e);
  }
}

// 完整消息追加（用于用户消息和非流式回复）
function appendMessage(role, content, tools = []) {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "bot-message"}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "你" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "bot") {
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `<strong>服装电商客服</strong><span>${timeLabel()}</span>`;
    bubble.appendChild(meta);
  }

  const text = document.createElement("p");
  text.innerHTML = renderContent(content);
  bubble.appendChild(text);

  if (tools.length) {
    const container = document.createElement("div");
    container.className = "tool-calls-container collapsed";
    container.innerHTML = `<div class="tool-calls-toggle"><span class="tool-calls-icon">▶</span><span class="tool-calls-summary">调用了 ${tools.length} 个工具</span></div><div class="tool-calls-list" style="display:none;">${tools.map(t => `<div class="tool-status done"><span>✓</span><span>${t}</span></div>`).join("")}</div>`;
    container.querySelector(".tool-calls-toggle").addEventListener("click", () => {
      const list = container.querySelector(".tool-calls-list");
      const icon = container.querySelector(".tool-calls-icon");
      const isOpen = list.style.display !== "none";
      list.style.display = isOpen ? "none" : "block";
      icon.textContent = isOpen ? "▶" : "▼";
    });
    bubble.appendChild(container);
  }

  // bot 消息添加反馈按钮
  if (role === "bot") {
    const feedbackEl = createFeedbackButtons(transcript.length);
    bubble.appendChild(feedbackEl);
  }

  article.append(avatar, bubble);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  transcript.push({ role, content, tools, time: new Date().toISOString() });
}

// 创建流式消息容器（返回 bubble 和 textEl 供后续填充）
function createStreamingBubble() {
  const article = document.createElement("article");
  article.className = "message bot-message";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = "🤖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML = `<strong>服装电商客服</strong><span>${timeLabel()}</span>`;
  bubble.appendChild(meta);

  const text = document.createElement("p");
  text.className = "streaming-cursor";
  bubble.appendChild(text);

  article.append(avatar, bubble);
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  return { article, bubble, textEl: text };
}

// 显示工具调用状态
function showToolStatus(bubble, toolName) {
  const toolNames = {
    knowledge_search: "查询知识库",
    get_product_info: "查询商品信息",
    search_products: "搜索商品",
    list_categories: "查询分类",
    query_order: "查询订单",
    query_user_orders: "查询用户订单",
    query_active_users: "查询业务数据",
    calculate_price: "计算价格",
    calculate_full_reduction: "计算满减",
    calculate_member_discount: "计算会员折扣",
    activate_user: "激活用户",
    get_user_info: "查询用户信息",
    recommend_for_user: "生成推荐",
  };

  // 确保有工具调用容器
  let container = bubble.querySelector(".tool-calls-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "tool-calls-container";
    container.innerHTML = `<div class="tool-calls-toggle"><span class="tool-calls-icon">▶</span><span class="tool-calls-summary">正在调用工具...</span></div><div class="tool-calls-list" style="display:none;"></div>`;
    bubble.appendChild(container);
    // 绑定展开/收起事件
    const toggle = container.querySelector(".tool-calls-toggle");
    toggle.addEventListener("click", () => {
      const list = container.querySelector(".tool-calls-list");
      const icon = container.querySelector(".tool-calls-icon");
      const isOpen = list.style.display !== "none";
      list.style.display = isOpen ? "none" : "block";
      icon.textContent = isOpen ? "▶" : "▼";
    });
  }

  const list = container.querySelector(".tool-calls-list");
  const el = document.createElement("div");
  el.className = "tool-status";
  el.innerHTML = `<span class="spinner"></span><span>正在${toolNames[toolName] || toolName}...</span>`;
  el.dataset.toolName = toolName;
  list.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// 标记工具完成
function markToolDone(bubble, toolName) {
  const els = bubble.querySelectorAll(".tool-status");
  for (const el of els) {
    if (el.dataset.toolName === toolName && !el.classList.contains("done")) {
      el.classList.add("done");
      const label = el.querySelector("span:last-child");
      if (label) label.textContent += " ✓";
      break;
    }
  }
  // 更新摘要
  const container = bubble.querySelector(".tool-calls-container");
  if (container) {
    const total = container.querySelectorAll(".tool-status").length;
    const done = container.querySelectorAll(".tool-status.done").length;
    const summary = container.querySelector(".tool-calls-summary");
    if (summary) summary.textContent = `工具调用 (${done}/${total})`;
  }
}

// 核心：SSE 流式发送消息
async function sendMessage(message) {
  // 如果有上传的图片，附加到消息中
  let fullMessage = message;
  if (uploadedImageUrl) {
    fullMessage = `${message}\n\n[用户上传了图片：${uploadedImageUrl}]`;
    uploadedImageUrl = null;
    imagePreview.style.display = "none";
    previewImg.src = "";
  }

  appendMessage("user", fullMessage);
  inputEl.value = "";
  inputEl.focus();

  const submitBtn = formEl.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "回复中...";
  agentStatusEl.textContent = "正在思考...";
  setQuickButtonsDisabled(true);

  const { article, bubble, textEl } = createStreamingBubble();
  let fullReply = "";
  let toolsUsed = [];
  let hasError = false;

  try {
    const response = await fetch("/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: fullMessage, session_id: sessionId, use_agent: true }),
    });

    if (!response.ok) {
      throw new Error(`请求失败：${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop(); // 保留未完成的事件

      for (const evt of events) {
        const lines = evt.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          let data;
          try {
            data = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          switch (data.type) {
            case "session":
              sessionId = data.session_id;
              localStorage.setItem("zhice-session-id", sessionId);
              break;

            case "token":
              fullReply += data.content;
              textEl.innerHTML = renderContent(fullReply);
              messagesEl.scrollTop = messagesEl.scrollHeight;
              break;

            case "tool_start":
              showToolStatus(bubble, data.tool);
              if (!toolsUsed.includes(data.tool)) toolsUsed.push(data.tool);
              break;

            case "tool_end":
              markToolDone(bubble, data.tool);
              break;

            case "done":
              fullReply = data.reply || fullReply;
              toolsUsed = data.tools_used || toolsUsed;
              if (data.token_usage) {
                totalTokens += data.token_usage.total_tokens || 0;
                tokenUsageEl.textContent = `${totalTokens} tokens`;
              }
              break;

            case "error":
              hasError = true;
              textEl.innerHTML = renderContent(data.message || "抱歉，处理遇到问题。");
              article.classList.add("error-message");
              break;

            case "escalate":
              // 显示转人工提示（防止重复）
              if (!bubble.querySelector(".escalate-banner")) {
                const escalateEl = document.createElement("div");
                escalateEl.className = "escalate-banner";
                escalateEl.textContent = "正在为您转接人工客服，请稍候...";
                bubble.appendChild(escalateEl);
              }
              // 记录转人工请求
              fetch("/escalate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: sessionId, reason: "用户情绪不满" }),
              }).catch(() => {});
              break;
          }
        }
      }
    }
  } catch (error) {
    hasError = true;
    textEl.innerHTML = `抱歉，服务暂时不可用。${escapeHtml(error.message)}`;
    article.classList.add("error-message");
  }

  // 移除流式光标
  textEl.classList.remove("streaming-cursor");

  // 更新工具调用容器的摘要
  const toolContainer = bubble.querySelector(".tool-calls-container");
  if (toolContainer && toolsUsed.length && !hasError) {
    const summary = toolContainer.querySelector(".tool-calls-summary");
    if (summary) summary.textContent = `调用了 ${toolsUsed.length} 个工具`;
  }

  // 添加反馈按钮
  if (!hasError) {
    const feedbackEl = createFeedbackButtons(transcript.length);
    bubble.appendChild(feedbackEl);
  }

  // 记录到 transcript
  transcript.push({ role: "bot", content: fullReply, tools: toolsUsed, time: new Date().toISOString() });

  submitBtn.disabled = false;
  submitBtn.textContent = "发送 📩";
  agentStatusEl.textContent = "客服在线 | 商品知识库已同步";
  setQuickButtonsDisabled(false);
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (message) {
    sendMessage(message);
  }
});

document.querySelectorAll("[data-prompt], .quick-item").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.disabled) return;
    const prompt = button.dataset.prompt || button.textContent.trim();
    sendMessage(prompt);
  });
});

clearBtn.addEventListener("click", async () => {
  await fetch(`/chat/${sessionId}`, { method: "DELETE" }).catch(() => {});
  document.querySelectorAll(".message:not(:first-child)").forEach((node) => node.remove());
  transcript = [];
});

exportBtn.addEventListener("click", () => {
  const content = transcript
    .map((item) => `[${item.time}] ${item.role === "user" ? "用户" : "客服"}：${item.content}`)
    .join("\n\n");
  const blob = new Blob([content || "暂无对话记录"], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `zhice-chat-${Date.now()}.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
});

// ========== 图片上传 ==========
const imageInput = document.querySelector("#imageInput");
const uploadBtn = document.querySelector("#uploadBtn");
const imagePreview = document.querySelector("#imagePreview");
const previewImg = document.querySelector("#previewImg");
const removeImg = document.querySelector("#removeImg");
let uploadedImageUrl = null;

uploadBtn.addEventListener("click", () => imageInput.click());

imageInput.addEventListener("change", async () => {
  const file = imageInput.files[0];
  if (!file) return;

  // 上传
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || "上传失败，请重试");
      imageInput.value = "";
      return;
    }
    const data = await res.json();
    if (data.url) {
      uploadedImageUrl = data.url;
      // 预览
      const reader = new FileReader();
      reader.onload = () => {
        previewImg.src = reader.result;
        imagePreview.style.display = "flex";
      };
      reader.readAsDataURL(file);
    }
  } catch (e) {
    console.warn("图片上传失败:", e);
    alert("图片上传失败，请重试");
  }
  imageInput.value = "";
});

removeImg.addEventListener("click", () => {
  uploadedImageUrl = null;
  imagePreview.style.display = "none";
  previewImg.src = "";
});

async function loadStatus() {
  try {
    const [healthRes, toolsRes] = await Promise.all([fetch("/health"), fetch("/tools")]);
    const health = await healthRes.json();
    const tools = await toolsRes.json();
    toolsCountEl.textContent = `${tools.count ?? "-"} 个`;
    modelNameEl.textContent = health.model === "deepseek-chat" ? "deepseek" : health.model || "-";
    agentStatusEl.textContent = health.chroma_db_exists
      ? "客服在线 | 商品知识库已同步"
      : "客服在线 | 等待同步商品知识库";
  } catch {
    toolsCountEl.textContent = "-";
    modelNameEl.textContent = "-";
    agentStatusEl.textContent = "客服状态待确认";
  }
}

loadStatus();
