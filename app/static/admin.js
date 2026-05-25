/**
 * 管理后台 JS
 * 加载会话列表、反馈统计、会话详情
 */

const sessionListEl = document.querySelector("#sessionList");
const sessionCountEl = document.querySelector("#sessionCount");
const detailPanel = document.querySelector("#detailPanel");
const feedbackStatsEl = document.querySelector("#feedbackStats");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return entities[char];
  });
}

// 加载反馈统计
async function loadFeedback() {
  try {
    const res = await fetch("/admin/feedback");
    const data = await res.json();
    const s = data.stats || {};
    feedbackStatsEl.innerHTML = `
      <div class="stat-item"><div class="num">${s.total || 0}</div><div class="label">总反馈</div></div>
      <div class="stat-item"><div class="num">${s.rate || "N/A"}</div><div class="label">好评率</div></div>
      <div class="stat-item"><div class="num">${s.positive || 0}</div><div class="label">好评</div></div>
      <div class="stat-item"><div class="num">${s.negative || 0}</div><div class="label">差评</div></div>
    `;
  } catch (e) {
    console.warn("加载反馈统计失败:", e);
  }
}

// 加载会话列表
async function loadSessions() {
  try {
    const res = await fetch("/admin/sessions");
    const data = await res.json();
    const sessions = data.sessions || [];
    sessionCountEl.textContent = sessions.length;

    sessionListEl.innerHTML = sessions.map((s) => {
      const time = s.last_active ? new Date(s.last_active * 1000).toLocaleString("zh-CN") : "-";
      return `
        <li class="session-item" data-id="${escapeHtml(s.session_id)}">
          <div class="sid">${escapeHtml(s.session_id)}</div>
          <div class="preview">${escapeHtml(s.first_message) || "（空会话）"}</div>
          <div class="meta">${s.message_count} 条消息 · ${time}</div>
        </li>
      `;
    }).join("");

    // 点击事件
    sessionListEl.querySelectorAll(".session-item").forEach((item) => {
      item.addEventListener("click", () => {
        loadSessionDetail(item.dataset.id);
        sessionListEl.querySelectorAll(".session-item").forEach((i) => i.style.background = "");
        item.style.background = "#e3f2fd";
      });
    });
  } catch (e) {
    console.warn("加载会话列表失败:", e);
  }
}

// 加载会话详情
async function loadSessionDetail(sessionId) {
  detailPanel.innerHTML = '<div class="detail-empty">加载中...</div>';
  try {
    const res = await fetch(`/admin/sessions/${sessionId}`);
    const data = await res.json();
    const history = data.chat_history || [];

    if (history.length === 0) {
      detailPanel.innerHTML = '<div class="detail-empty">该会话暂无对话记录</div>';
      return;
    }

    const messages = history.map((msg) => {
      const role = msg.role === "human" ? "用户" : "客服";
      const cls = msg.role === "human" ? "human" : "ai";
      const content = escapeHtml(msg.content || "").replace(/\n/g, "<br>");
      return `<div class="chat-msg ${cls}"><div class="role">${role}</div>${content}</div>`;
    }).join("");

    const created = data.created_at ? new Date(data.created_at * 1000).toLocaleString("zh-CN") : "-";
    const lastActive = data.last_active ? new Date(data.last_active * 1000).toLocaleString("zh-CN") : "-";

    detailPanel.innerHTML = `
      <h2 style="margin-bottom:16px; font-size:16px;">会话 ${sessionId}</h2>
      <div style="font-size:13px; color:#888; margin-bottom:16px;">
        创建时间: ${created} · 最后活跃: ${lastActive} · 消息数: ${history.length}
      </div>
      <div class="chat-log">${messages}</div>
    `;
  } catch (e) {
    detailPanel.innerHTML = '<div class="detail-empty">加载失败</div>';
    console.warn("加载会话详情失败:", e);
  }
}

// ========== 日志查看 ==========
const logContainerEl = document.querySelector("#logContainer");
const refreshLogsBtn = document.querySelector("#refreshLogs");
const logLinesSelect = document.querySelector("#logLines");

async function loadLogs() {
  const lines = parseInt(logLinesSelect.value) || 200;
  logContainerEl.innerHTML = '<div class="detail-empty">加载中...</div>';
  try {
    const res = await fetch(`/admin/logs?lines=${lines}`);
    const data = await res.json();
    const logs = data.logs || [];

    if (logs.length === 0) {
      logContainerEl.innerHTML = '<div class="detail-empty">暂无日志</div>';
      return;
    }

    logContainerEl.innerHTML = logs.map((line) => {
      // 解析日志格式: 2026-05-25 10:30:00,123 [INFO] zhice-platform.xxx: message
      const match = line.match(/^(\d{4}-\d{2}-\d{2}\s[\d:,]+)\s+\[(\w+)\]\s+(.*)$/);
      if (match) {
        const [, time, level, rest] = match;
        const levelClass = `log-level-${level}`;
        return `<p class="log-line"><span class="log-time">${escapeHtml(time)}</span> <span class="${levelClass}">[${escapeHtml(level)}]</span> ${escapeHtml(rest)}</p>`;
      }
      return `<p class="log-line">${escapeHtml(line)}</p>`;
    }).join("");

    // 滚动到底部
    logContainerEl.scrollTop = logContainerEl.scrollHeight;
  } catch (e) {
    logContainerEl.innerHTML = '<div class="detail-empty">加载日志失败</div>';
    console.warn("加载日志失败:", e);
  }
}

// ========== Tab 切换 ==========
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".tab-content").forEach((c) => c.style.display = "none");
    const panel = document.querySelector(`#tab-${target}`);
    if (panel) panel.style.display = "flex";

    // 切到日志 tab 时自动加载
    if (target === "logs") loadLogs();
  });
});

refreshLogsBtn.addEventListener("click", loadLogs);
logLinesSelect.addEventListener("change", loadLogs);

// 初始化
loadFeedback();
loadSessions();
