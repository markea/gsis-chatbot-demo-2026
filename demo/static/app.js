// GSIS Gabay AI Omnichannel Executive Demo — Frontend Controller

let currentAccessToken = null;
let currentMemberClaims = null;
let currentMemberBundle = null;
let pendingOtpSessionId = null;
let currentChannel = "gwaps_web";

const ROTATING_NUDGES = [
  "First time here? Compute your MPL Flex Loan or RA 8291 Pension in 5 seconds!",
  "Need to check unposted agency ERF contributions? Sign in with 1 click!",
  "Compare RA 8291 Option 1 (5-Yr Lump Sum) vs Option 2 (18-Mo Cash) instantly!",
  "Protected by Google Cloud Model Armor & Identity-Bound MCP Guardrails 🛡️"
];
let nudgeIdx = 0;

let pillWasDragged = false;

document.addEventListener("DOMContentLoaded", () => {
  refreshStatusAndQuota();
  initDraggableFloatingPill();
  if (localStorage.getItem("gsis_hide_demo_disclaimer") === "1") {
    toggleDemoDisclaimer(true);
  }
  document.addEventListener("click", (e) => {
    const popover = document.getElementById("googleAccountPopover");
    const wrapper = document.getElementById("googleProfileWrapper");
    const chatChip = document.getElementById("chatDrawerUserChip");
    if (!popover || popover.style.display === "none") return;
    if (
      !popover.contains(e.target) &&
      (!wrapper || !wrapper.contains(e.target)) &&
      (!chatChip || !chatChip.contains(e.target))
    ) {
      closeUserAccountMenu();
    }
  });
  setInterval(() => {
    nudgeIdx = (nudgeIdx + 1) % ROTATING_NUDGES.length;
    const el = document.getElementById("rotatingNudgeText");
    if (el) el.textContent = ROTATING_NUDGES[nudgeIdx];
  }, 5500);
});

function initDraggableFloatingPill() {
  const pill = document.getElementById("floatingDemoPill");
  if (!pill) return;

  // Restore saved position if valid
  try {
    const saved = JSON.parse(localStorage.getItem("gsis_floating_pill_pos") || "null");
    if (saved && typeof saved.left === "number" && typeof saved.top === "number") {
      const clampedLeft = Math.max(12, Math.min(window.innerWidth - 260, saved.left));
      const clampedTop = Math.max(12, Math.min(window.innerHeight - 54, saved.top));
      pill.style.left = `${clampedLeft}px`;
      pill.style.top = `${clampedTop}px`;
      pill.style.bottom = "auto";
      pill.style.right = "auto";
    }
  } catch (_) {}

  let isDragging = false;
  let startX = 0;
  let startY = 0;
  let initialLeft = 0;
  let initialTop = 0;

  function onPointerDown(clientX, clientY, target) {
    if (target && target.classList && target.classList.contains("floating-demo-expand-btn")) {
      return;
    }
    isDragging = true;
    pillWasDragged = false;
    const rect = pill.getBoundingClientRect();
    startX = clientX;
    startY = clientY;
    initialLeft = rect.left;
    initialTop = rect.top;
    pill.classList.add("dragging");
  }

  function onPointerMove(clientX, clientY) {
    if (!isDragging) return;
    const dx = clientX - startX;
    const dy = clientY - startY;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
      pillWasDragged = true;
    }
    const maxLeft = Math.max(12, window.innerWidth - pill.offsetWidth - 12);
    const maxTop = Math.max(12, window.innerHeight - pill.offsetHeight - 12);
    const nextLeft = Math.max(12, Math.min(maxLeft, initialLeft + dx));
    const nextTop = Math.max(12, Math.min(maxTop, initialTop + dy));

    pill.style.left = `${nextLeft}px`;
    pill.style.top = `${nextTop}px`;
    pill.style.bottom = "auto";
    pill.style.right = "auto";
  }

  function onPointerUp() {
    if (!isDragging) return;
    isDragging = false;
    pill.classList.remove("dragging");
    const rect = pill.getBoundingClientRect();
    localStorage.setItem(
      "gsis_floating_pill_pos",
      JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) })
    );
  }

  pill.addEventListener("mousedown", (e) => onPointerDown(e.clientX, e.clientY, e.target));
  window.addEventListener("mousemove", (e) => onPointerMove(e.clientX, e.clientY));
  window.addEventListener("mouseup", onPointerUp);

  pill.addEventListener(
    "touchstart",
    (e) => {
      if (e.touches.length === 1) {
        onPointerDown(e.touches[0].clientX, e.touches[0].clientY, e.target);
      }
    },
    { passive: true }
  );
  window.addEventListener(
    "touchmove",
    (e) => {
      if (isDragging && e.touches.length === 1) {
        onPointerMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    },
    { passive: true }
  );
  window.addEventListener("touchend", onPointerUp);
}

function handleFloatingPillClick() {
  if (pillWasDragged) {
    pillWasDragged = false;
    return;
  }
  toggleDemoDisclaimer(false);
}

function toggleDemoDisclaimer(hide) {
  const banner = document.getElementById("demoDisclaimerBanner");
  const floatingPill = document.getElementById("floatingDemoPill");
  if (hide) {
    if (banner) banner.style.display = "none";
    if (floatingPill) floatingPill.style.display = "inline-flex";
    document.body.classList.add("disclaimer-hidden");
    localStorage.setItem("gsis_hide_demo_disclaimer", "1");
  } else {
    if (banner) banner.style.display = "block";
    if (floatingPill) floatingPill.style.display = "none";
    document.body.classList.remove("disclaimer-hidden");
    localStorage.setItem("gsis_hide_demo_disclaimer", "0");
  }
}

function toggleUserAccountMenu(e) {
  if (e) e.stopPropagation();
  const popover = document.getElementById("googleAccountPopover");
  if (!popover) return;
  if (popover.style.display === "block") {
    closeUserAccountMenu();
  } else {
    popover.style.display = "block";
  }
}

function closeUserAccountMenu() {
  const popover = document.getElementById("googleAccountPopover");
  if (popover) popover.style.display = "none";
}

async function switchPersonaFromMenu(username) {
  closeUserAccountMenu();
  await quickPersonaLogin(username);
}

function getInitials(fullName) {
  if (!fullName) return "👤";
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

async function refreshStatusAndQuota() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateQuotaUI(data.quota);
  } catch (err) {
    console.error("Failed to fetch status:", err);
  }
}

function updateQuotaUI(quota) {
  if (!quota) return;
  const used = quota.custom_mock_users_count || 0;
  const max = quota.max_custom_mock_users || 25;
  const pct = Math.min(100, Math.round((used / max) * 100));

  const headerText = document.getElementById("headerQuotaText");
  if (headerText) headerText.textContent = `${used} / ${max}`;

  const heroInline = document.getElementById("heroQuotaInline");
  if (heroInline) heroInline.textContent = `${used}/${max}`;

  const popoverQuota = document.getElementById("popoverQuotaInline");
  if (popoverQuota) popoverQuota.textContent = `${used}/${max}`;

  const modalLabel = document.getElementById("modalQuotaCountLabel");
  if (modalLabel) modalLabel.textContent = `${used} / ${max} Used`;

  const barFill = document.getElementById("modalQuotaBarFill");
  if (barFill) {
    barFill.style.width = `${pct}%`;
    if (used >= max) {
      barFill.classList.add("limit-reached");
    } else {
      barFill.classList.remove("limit-reached");
    }
  }

  const errorBanner = document.getElementById("quotaExceededErrorBanner");
  const regBtn = document.getElementById("registerSubmitBtn");
  if (used >= max) {
    if (errorBanner) errorBanner.style.display = "flex";
    if (regBtn) {
      regBtn.disabled = true;
      regBtn.textContent = "🚫 Maximum of 25 Custom Mock Users Reached (Quota Full)";
      regBtn.style.background = "#94A3B8";
    }
  }
}

function showQuotaExceededAlertPreview() {
  const banner = document.getElementById("quotaExceededErrorBanner");
  if (banner) {
    banner.style.display = "flex";
    banner.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function switchOmnichannelMode(mode) {
  const webView = document.getElementById("webPortalView");
  const mobileView = document.getElementById("mobileSimulatorView");
  const webBtn = document.getElementById("modeWebBtn");
  const mobileBtn = document.getElementById("modeMobileBtn");

  if (mode === "mobile") {
    currentChannel = "gsis_touch_mobile";
    webView.style.display = "none";
    mobileView.style.display = "block";
    webBtn.classList.remove("active");
    mobileBtn.classList.add("active");
  } else {
    currentChannel = "gwaps_web";
    webView.style.display = "block";
    mobileView.style.display = "none";
    mobileBtn.classList.remove("active");
    webBtn.classList.add("active");
  }
}

function dismissWelcomeBubble(e) {
  if (e) e.stopPropagation();
  const card = document.getElementById("launcherWelcomeCard");
  if (card) card.style.display = "none";
}

function openChatDrawer() {
  const drawer = document.getElementById("chatDrawer");
  if (drawer) drawer.classList.add("open");
  const welcome = document.getElementById("launcherWelcomeCard");
  if (welcome) welcome.style.display = "none";
}

function closeChatDrawer() {
  const drawer = document.getElementById("chatDrawer");
  if (drawer) drawer.classList.remove("open");
}

function toggleChatDrawer() {
  const drawer = document.getElementById("chatDrawer");
  if (drawer.classList.contains("open")) {
    closeChatDrawer();
  } else {
    openChatDrawer();
  }
}

function openChatAndSend(promptText) {
  openChatDrawer();
  sendChatMessage(promptText);
}

function sendQuickPrompt(promptText) {
  openChatDrawer();
  sendChatMessage(promptText);
}

function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendChatMessage(text);
}

function formatMarkdownToHtml(md) {
  if (!md) return "";
  let html = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Headers
  html = html.replace(/^#### (.*$)/gim, "<h4>$1</h4>");
  html = html.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  // Blockquotes
  html = html.replace(/^&gt; (.*$)/gim, "<blockquote>$1</blockquote>");
  // Bold & Code
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Bullets
  html = html.replace(/^\s*-\s+(.*$)/gim, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  // Line breaks
  html = html.replace(/\n\n/g, "<br><br>");
  html = html.replace(/\n/g, "<br>");
  return html;
}

function appendUserBubble(text) {
  const container = document.getElementById("chatMessages");
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `<div class="message-bubble">${text.replace(/</g, "&lt;")}</div>`;
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
}

function appendAssistantBubble(data) {
  const container = document.getElementById("chatMessages");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const trace = data.agent_trace || {};
  const specialist = trace.specialist_agent || "GSIS_Policy_FAQ_Agent (gemini-3.7-flash)";
  const blocked = specialist === "BLOCKED_BY_MODEL_ARMOR";

  const armorBadge = blocked
    ? `<span class="armor-block-tag">🛡️ Blocked by Model Armor</span>`
    : `<span class="armor-pass-tag">🛡️ Model Armor Verified</span>`;

  let toolsHtml = "";
  if (trace.mcp_tools_called && trace.mcp_tools_called.length > 0) {
    const chips = trace.mcp_tools_called
      .map((t) => `<span class="mcp-chip">🔧 MCP: ${t.tool}${t.bp_number ? ` (BP ${t.bp_number})` : ""}</span>`)
      .join("");
    toolsHtml = `<div class="mcp-tools-trace">${chips}</div>`;
  }

  let actionsHtml = "";
  if (data.phase3_actions && data.phase3_actions.length > 0) {
    const btns = data.phase3_actions
      .map(
        (act) =>
          `<button class="btn-phase3-cta" onclick='openComingSoonModal(${JSON.stringify(act.label)}, ${JSON.stringify(
            act.description
          )})'>🚀 ${act.label} (${act.badge})</button>`
      )
      .join("");
    actionsHtml = `<div class="phase3-cta-box">${btns}</div>`;
  }

  let loginPromptBtnHtml = "";
  if (data.requires_login_modal) {
    loginPromptBtnHtml = `
      <div class="phase3-cta-box">
        <button class="btn-primary-auth" onclick="openAuthModal('login')">🔐 Sign In or Register Mock Member Now</button>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="message-bubble">
      <div class="bubble-meta">
        <span>🤖 <strong>${specialist}</strong></span>
        ${armorBadge}
      </div>
      <div class="bubble-content">${formatMarkdownToHtml(data.reply)}</div>
      ${toolsHtml}
      ${actionsHtml}
      ${loginPromptBtnHtml}
    </div>
  `;
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;

  const badgeEl = document.getElementById("lastAgentBadge");
  if (badgeEl) {
    badgeEl.innerHTML = `🤖 Active: <code>${specialist}</code>`;
  }
}

async function sendChatMessage(promptText) {
  appendUserBubble(promptText);
  const headers = { "Content-Type": "application/json" };
  if (currentAccessToken) {
    headers["Authorization"] = `Bearer ${currentAccessToken}`;
  }

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers,
      body: JSON.stringify({ prompt: promptText, channel: currentChannel })
    });
    const data = await res.json();
    appendAssistantBubble(data);
  } catch (err) {
    appendAssistantBubble({
      reply: "⚠️ Connection error while contacting GSIS Gabay AI backend.",
      agent_trace: { specialist_agent: "System" }
    });
  }
}

// =====================================================================
// AUTHENTICATION, CUSTOM SEEDER & SIMULATED 6-DIGIT OTP FLOW
// =====================================================================

function openAuthModal(defaultTab = "login") {
  refreshStatusAndQuota();
  document.getElementById("authModalBackdrop").style.display = "flex";
  switchAuthTab(defaultTab);
}

function closeAuthModal() {
  document.getElementById("authModalBackdrop").style.display = "none";
}

function switchAuthTab(tab) {
  const loginTab = document.getElementById("authTabLogin");
  const regTab = document.getElementById("authTabRegister");
  const loginBtn = document.getElementById("tabLoginBtn");
  const regBtn = document.getElementById("tabRegisterBtn");

  if (tab === "register") {
    loginTab.style.display = "none";
    regTab.style.display = "block";
    loginBtn.classList.remove("active");
    regBtn.classList.add("active");
    if (!document.getElementById("regFullName").value) {
      randomFillMockRegistration();
    }
  } else {
    loginTab.style.display = "block";
    regTab.style.display = "none";
    regBtn.classList.remove("active");
    loginBtn.classList.add("active");
  }
}

function fillLoginCredentials(username, password) {
  document.getElementById("loginUsername").value = username;
  document.getElementById("loginPassword").value = password;
}

async function submitLoginForm(e) {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value;
  const errEl = document.getElementById("loginErrorMsg");
  errEl.style.display = "none";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = data.detail || "Login failed.";
      errEl.style.display = "block";
      return;
    }
    closeAuthModal();
    showSimulatedOtpToast(data);
  } catch (err) {
    errEl.textContent = "Network error during login.";
    errEl.style.display = "block";
  }
}

async function quickPersonaLogin(username) {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password: "gsis2026" })
    });
    const data = await res.json();
    if (!res.ok) return;
    closeAuthModal();
    // Automatically verify the simulated OTP for 1-click executive convenience
    pendingOtpSessionId = data.otp_session_id;
    document.getElementById("otpSimulatedCodeDisplay").textContent = data.simulated_otp_code;
    document.getElementById("otpInputBox").value = data.simulated_otp_code;
    await verifySimulatedOtp();
    openChatDrawer();
  } catch (err) {
    console.error(err);
  }
}

function randomFillMockRegistration() {
  const firstNamesF = ["Elena", "Carmela", "Patricia", "Maricel", "Lorna", "Grace", "Teresita"];
  const firstNamesM = ["Roberto", "Antonio", "Marco", "Ferdinand", "Danilo", "Ramon", "noel"];
  const lastNames = ["Villanueva", "Mendoza", "Bautista", "Ramos", "Aquino", "Castillo", "Soriano", "Salazar"];
  const isFemale = Math.random() > 0.45;
  const fn = isFemale
    ? firstNamesF[Math.floor(Math.random() * firstNamesF.length)]
    : firstNamesM[Math.floor(Math.random() * firstNamesM.length)];
  const ln = lastNames[Math.floor(Math.random() * lastNames.length)];
  const randSuffix = Math.floor(100 + Math.random() * 899);
  const year = Math.floor(1966 + Math.random() * 31); // Ages 29 to 60
  const month = String(Math.floor(1 + Math.random() * 12)).padStart(2, "0");
  const day = String(Math.floor(1 + Math.random() * 28)).padStart(2, "0");
  const civilChoices = ["Married", "Single", "Widowed", "Legally Separated"];

  document.getElementById("regFullName").value = `${fn} ${ln}`;
  document.getElementById("regUsername").value = `${fn.toLowerCase()}.${ln.toLowerCase()}${randSuffix}`;
  document.getElementById("regPassword").value = "gsis2026";
  document.getElementById("regBirthDate").value = `${year}-${month}-${day}`;
  document.getElementById("regGender").value = isFemale ? "Female" : "Male";
  document.getElementById("regCivilStatus").value = civilChoices[Math.floor(Math.random() * civilChoices.length)];
  document.getElementById("regEmail").value = `${fn.toLowerCase()}.${ln.toLowerCase()}${randSuffix}@gov.ph`;
  document.getElementById("regMobile").value = `0917-${Math.floor(100 + Math.random() * 899)}-${Math.floor(1000 + Math.random() * 8999)}`;
}

async function submitRegisterForm(e) {
  e.preventDefault();
  const errEl = document.getElementById("registerErrorMsg");
  errEl.style.display = "none";

  const payload = {
    full_name: document.getElementById("regFullName").value.trim(),
    username: document.getElementById("regUsername").value.trim(),
    password: document.getElementById("regPassword").value,
    birth_date: document.getElementById("regBirthDate").value,
    gender: document.getElementById("regGender").value,
    civil_status: document.getElementById("regCivilStatus").value,
    email: document.getElementById("regEmail").value.trim(),
    mobile_number: document.getElementById("regMobile").value.trim(),
    agency_name: document.getElementById("regAgency").value
  };

  try {
    const res = await fetch("/api/auth/register-mock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.status === 429) {
      // Hard limit of 25 custom mock users reached! Show prominent error notification banner
      const banner = document.getElementById("quotaExceededErrorBanner");
      const txt = document.getElementById("quotaExceededErrorText");
      if (txt && data.message) txt.textContent = data.message;
      if (banner) {
        banner.style.display = "flex";
        banner.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      await refreshStatusAndQuota();
      return;
    }

    if (!res.ok) {
      errEl.textContent = data.detail || "Registration failed.";
      errEl.style.display = "block";
      return;
    }

    await refreshStatusAndQuota();
    closeAuthModal();
    showSimulatedOtpToast(data);
  } catch (err) {
    errEl.textContent = "Error communicating with registration endpoint.";
    errEl.style.display = "block";
  }
}

function showSimulatedOtpToast(data) {
  pendingOtpSessionId = data.otp_session_id;
  document.getElementById("otpToastMessage").textContent = data.message;
  document.getElementById("otpSimulatedCodeDisplay").textContent = data.simulated_otp_code;
  document.getElementById("otpInputBox").value = data.simulated_otp_code;
  document.getElementById("otpToastModal").style.display = "block";
}

function closeOtpToast() {
  document.getElementById("otpToastModal").style.display = "none";
}

async function verifySimulatedOtp() {
  const otpCode = document.getElementById("otpInputBox").value.trim();
  if (!pendingOtpSessionId || !otpCode) return;

  try {
    const res = await fetch("/api/auth/verify-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ otp_session_id: pendingOtpSessionId, otp_code: otpCode })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Invalid OTP");
      return;
    }

    currentAccessToken = data.access_token;
    currentMemberClaims = data.claims;
    currentMemberBundle = data.member_bundle;
    closeOtpToast();
    applyAuthenticatedState();
  } catch (err) {
    console.error("OTP verification error:", err);
  }
}

function updateAccountSwitcherRows(activeUsername) {
  const personas = [
    { key: "maria", username: "maria.santos" },
    { key: "juan", username: "juan.delacruz" },
    { key: "rosa", username: "rosa.reyes" }
  ];
  personas.forEach((p) => {
    const row = document.getElementById(`switcherRow_${p.key}`);
    const badge = document.getElementById(`switcherBadge_${p.key}`);
    if (!row || !badge) return;
    if (activeUsername && activeUsername.toLowerCase() === p.username) {
      row.classList.add("active-persona");
      badge.textContent = "✓ ACTIVE";
    } else {
      row.classList.remove("active-persona");
      badge.textContent = "Switch";
    }
  });
}

function applyAuthenticatedState() {
  if (!currentMemberClaims || !currentMemberBundle) return;
  const prof = currentMemberBundle.profile;
  const initials = getInitials(prof.full_name);
  const firstName = prof.full_name.split(" ")[0];

  // 1. Update Top-Right Google-Style Profile Pill
  const triggerBtn = document.getElementById("userProfileTriggerBtn");
  if (triggerBtn) triggerBtn.className = "google-profile-pill auth";

  const avatarCircle = document.getElementById("headerAvatarCircle");
  if (avatarCircle) avatarCircle.className = "profile-avatar-circle auth";

  const avatarInitials = document.getElementById("headerAvatarInitials");
  if (avatarInitials) avatarInitials.textContent = initials;

  const statusDot = document.getElementById("sessionStatusDot");
  if (statusDot) statusDot.className = "avatar-status-dot auth";

  document.getElementById("sessionPhaseLabel").textContent = `🟢 MFA VERIFIED • BP ${prof.bp_number}`;
  document.getElementById("sessionUserName").textContent = `${prof.full_name} (${prof.agency_code})`;

  const inspectBtn = document.getElementById("inspectRecordsBtn");
  if (inspectBtn) inspectBtn.style.display = "inline-block";

  // 2. Update Chat Drawer Header User Profile Chip
  const chatChip = document.getElementById("chatDrawerUserChip");
  if (chatChip) chatChip.className = "chat-user-chip auth";
  const chatChipAvatar = document.getElementById("chatChipAvatar");
  if (chatChipAvatar) chatChipAvatar.textContent = initials;
  const chatChipName = document.getElementById("chatChipName");
  if (chatChipName) chatChipName.textContent = `${firstName} (BP ${prof.bp_number.slice(-4)}) ▾`;

  // 3. Update Google Account Switcher Popover Card
  const popEmail = document.getElementById("popoverTopEmail");
  if (popEmail) popEmail.textContent = `${prof.email} • GSIS Phase 2 MFA Session`;

  const popAvatar = document.getElementById("popoverLargeAvatar");
  if (popAvatar) {
    popAvatar.className = "popover-large-avatar auth";
    popAvatar.textContent = initials;
  }

  const popName = document.getElementById("popoverUserFullName");
  if (popName) popName.textContent = prof.full_name;

  const popBp = document.getElementById("popoverUserBpBadge");
  if (popBp) popBp.textContent = `🟢 BP ${prof.bp_number} • ${prof.position_title} (${prof.agency_code})`;

  const popMeta = document.getElementById("popoverUserMeta");
  if (popMeta) {
    popMeta.textContent = `Age ${prof.age} • ${prof.civil_status} • PPP ${prof.total_ppp_years} yrs • Salary ₱${Number(prof.basic_monthly_salary).toLocaleString()}`;
  }

  const popInspect = document.getElementById("popoverInspectDbBtn");
  if (popInspect) popInspect.style.display = "block";

  const popSignOut = document.getElementById("popoverSignOutBtn");
  if (popSignOut) popSignOut.style.display = "inline-block";

  updateAccountSwitcherRows(prof.username);

  // 4. Update Mobile App Simulator eCard
  document.getElementById("touchGreeting").textContent = `Mabuhay, ${firstName}!`;
  document.getElementById("touchSub").textContent = `${prof.position_title} • ${prof.agency_name}`;
  document.getElementById("touchBpNum").textContent = `BP: ${prof.bp_number}`;
  document.getElementById("touchMemberName").textContent = prof.full_name.toUpperCase();
  document.getElementById("touchAgency").textContent = `Civil: ${prof.civil_status} (Age ${prof.age})`;
  document.getElementById("touchPpp").textContent = `PPP: ${prof.total_ppp_years} yrs`;

  // 5. Update Chat Drawer Subtitle
  document.getElementById("chatAuthSubtitle").textContent = `Phase 2 Active: ${prof.full_name} (BP ${prof.bp_number} • JWT Bound)`;

  appendAssistantBubble({
    reply: `✅ **Phase 2 MFA Session Activated for ${prof.full_name} (\`BP ${prof.bp_number}\`)**\n\nYour JWT is now cryptographically bound to **BP \`${prof.bp_number}\`** (${prof.position_title}, ${prof.agency_code} • Age ${prof.age} • ${prof.civil_status} • PPP ${prof.total_ppp_years} yrs).\n\n💡 *Tip: Click your **User Profile Badge** in the top-right corner anytime to switch personas in 1 click or sign out!*\n\nTry asking:\n- *"Simulate my MPL Flex reloan and show my exact net proceeds"*\n- *"Show my last 12 months GSIS contributions and unposted ERF status"*\n- *"Compute my RA 8291 Option 1 vs Option 2 retirement benefits"*`,
    agent_trace: {
      specialist_agent: "GSIS_Concierge_Router (gemini-3.7-flash)",
      mcp_tools_called: [{ tool: "jwt_identity_binding", bp_number: prof.bp_number }]
    }
  });
}

function logoutMember() {
  currentAccessToken = null;
  currentMemberClaims = null;
  currentMemberBundle = null;

  // Reset Top-Right Google Profile Pill
  const triggerBtn = document.getElementById("userProfileTriggerBtn");
  if (triggerBtn) triggerBtn.className = "google-profile-pill unauth";

  const avatarCircle = document.getElementById("headerAvatarCircle");
  if (avatarCircle) avatarCircle.className = "profile-avatar-circle unauth";

  const avatarInitials = document.getElementById("headerAvatarInitials");
  if (avatarInitials) avatarInitials.textContent = "👤";

  const statusDot = document.getElementById("sessionStatusDot");
  if (statusDot) statusDot.className = "avatar-status-dot unauth";

  document.getElementById("sessionPhaseLabel").textContent = "PHASE 1: PUBLIC GUEST";
  document.getElementById("sessionUserName").textContent = "Not Signed In • Click to Sign In";

  const inspectBtn = document.getElementById("inspectRecordsBtn");
  if (inspectBtn) inspectBtn.style.display = "none";

  // Reset Chat Drawer User Chip
  const chatChip = document.getElementById("chatDrawerUserChip");
  if (chatChip) chatChip.className = "chat-user-chip unauth";
  const chatChipAvatar = document.getElementById("chatChipAvatar");
  if (chatChipAvatar) chatChipAvatar.textContent = "👤";
  const chatChipName = document.getElementById("chatChipName");
  if (chatChipName) chatChipName.textContent = "Guest ▾";

  // Reset Google Account Switcher Popover
  const popEmail = document.getElementById("popoverTopEmail");
  if (popEmail) popEmail.textContent = "unauthenticated.guest@gsis.gov.ph (Phase 1 Public Mode)";

  const popAvatar = document.getElementById("popoverLargeAvatar");
  if (popAvatar) {
    popAvatar.className = "popover-large-avatar unauth";
    popAvatar.textContent = "👤";
  }

  const popName = document.getElementById("popoverUserFullName");
  if (popName) popName.textContent = "Hi, Guest Visitor!";

  const popBp = document.getElementById("popoverUserBpBadge");
  if (popBp) popBp.textContent = "🟠 Unauthenticated Mode — FAQ & Sample Calculators Only";

  const popMeta = document.getElementById("popoverUserMeta");
  if (popMeta) popMeta.textContent = "Sign in below to bind your JWT and access personal GSIS records.";

  const popInspect = document.getElementById("popoverInspectDbBtn");
  if (popInspect) popInspect.style.display = "none";

  const popSignOut = document.getElementById("popoverSignOutBtn");
  if (popSignOut) popSignOut.style.display = "none";

  updateAccountSwitcherRows(null);

  // Reset Mobile Simulator eCard
  document.getElementById("touchGreeting").textContent = "Magandang Araw, Member!";
  document.getElementById("touchSub").textContent = "Sign in to view your Digital eCard & Loans";
  document.getElementById("touchBpNum").textContent = "BP: 2016-XXXX-XX";
  document.getElementById("touchMemberName").textContent = "GUEST VISITOR (PHASE 1)";
  document.getElementById("touchAgency").textContent = "Agency: Public Guest";
  document.getElementById("touchPpp").textContent = "PPP: -- yrs";

  document.getElementById("chatAuthSubtitle").textContent = "Phase 1: Unauthenticated FAQ & Sample Calculator";

  appendAssistantBubble({
    reply: "🚪 **Signed Out to Phase 1 (Public Guest Mode)**\n\nYour MFA JWT session has been cleared. You can still ask general GSIS policy questions or click the **top-right User Profile Badge** to sign back in or switch personas.",
    agent_trace: { specialist_agent: "GSIS_Concierge_Router (gemini-3.7-flash)" }
  });
}

function toggleRecordsDrawer() {
  const modal = document.getElementById("recordsModalBackdrop");
  if (modal.style.display === "flex") {
    modal.style.display = "none";
    return;
  }
  if (currentMemberBundle) {
    document.getElementById("recordsDrawerTitle").textContent = `Seeded 5-Table Relational Records — ${currentMemberBundle.profile.full_name} (BP ${currentMemberBundle.profile.bp_number})`;
    document.getElementById("recordsDrawerContent").innerHTML = `<pre>${JSON.stringify(currentMemberBundle, null, 2)}</pre>`;
  }
  modal.style.display = "flex";
}

function openComingSoonModal(title, description) {
  document.getElementById("comingSoonTitle").textContent = `🚀 ${title} — Coming Soon!`;
  document.getElementById("comingSoonDescription").textContent = description;
  document.getElementById("comingSoonModalBackdrop").style.display = "flex";
}

function closeComingSoonModal() {
  document.getElementById("comingSoonModalBackdrop").style.display = "none";
}
