const authPanel = document.querySelector("#auth-panel");
const authForm = document.querySelector("#auth-form");
const authEmail = document.querySelector("#auth-email");
const authPassword = document.querySelector("#auth-password");
const authTitle = document.querySelector("#auth-title");
const authDescription = document.querySelector("#auth-description");
const authSubmit = document.querySelector("#auth-submit");
const authMode = document.querySelector("#auth-mode");
const authMessage = document.querySelector("#auth-message");
const chatView = document.querySelector("#chat-view");
const conversationElement = document.querySelector(".conversation");
const accountEmail = document.querySelector("#account-email");
const logoutButton = document.querySelector("#logout-button");
const statusElement = document.querySelector("#status");
const conversationList = document.querySelector("#conversation-list");
const newChatButton = document.querySelector("#new-chat");
const chatForm = document.querySelector("#chat-form");
const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send-button");
const messagesElement = document.querySelector("#messages");
const welcome = document.querySelector("#welcome");

let registering = false;
let sending = false;
let conversationId = null;

function syncAppViewportHeight() {
  const viewport = window.visualViewport;
  const shouldFollowConversation = isConversationNearBottom();
  if (viewport && window.innerWidth <= 600) {
    document.documentElement.style.setProperty("--app-height", `${viewport.height}px`);
  } else {
    document.documentElement.style.removeProperty("--app-height");
  }
  if (shouldFollowConversation) scrollConversationToBottom();
}

function isConversationNearBottom() {
  return (
    conversationElement.scrollHeight -
      conversationElement.scrollTop -
      conversationElement.clientHeight <
    96
  );
}

function scrollConversationToBottom(behavior = "auto") {
  requestAnimationFrame(() => {
    conversationElement.scrollTo({
      top: conversationElement.scrollHeight,
      behavior,
    });
  });
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const body = await response.text();
  let result = null;
  if (body) {
    try {
      result = JSON.parse(body);
    } catch {
      throw new Error(`The server returned an invalid response (HTTP ${response.status}).`);
    }
  }
  if (!response.ok) {
    const error = new Error(
      (typeof result?.detail === "string" && result.detail) ||
        `Request failed (HTTP ${response.status}).`,
    );
    error.status = response.status;
    throw error;
  }
  return result;
}

function showAuth(message = "") {
  authPanel.hidden = false;
  chatView.hidden = true;
  accountEmail.hidden = true;
  logoutButton.hidden = true;
  authMessage.textContent = message;
  authEmail.focus();
}

function showChat(user) {
  authPanel.hidden = true;
  chatView.hidden = false;
  accountEmail.textContent = user.email;
  accountEmail.hidden = false;
  logoutButton.hidden = false;
}

function addMessage(role, content, isError = false) {
  const shouldFollow = isConversationNearBottom();
  const message = document.createElement("article");
  message.className = `message ${role}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : isError ? "Notice" : "Assistant";

  const body = document.createElement("div");
  body.className = `message-content${isError ? " error" : ""}`;
  body.textContent = content;

  message.append(label, body);
  messagesElement.append(message);
  if (shouldFollow) scrollConversationToBottom();
}

function showLoading() {
  const loading = document.createElement("article");
  loading.className = "message assistant loading-message";
  loading.id = "loading-message";
  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = "Assistant";
  const body = document.createElement("div");
  body.className = "message-content";
  body.textContent = "Thinking…";
  loading.append(label, body);
  messagesElement.append(loading);
}

async function refreshConversations() {
  const conversations = await request("/api/conversations");
  conversationList.replaceChildren();

  for (const conversation of conversations) {
    const row = document.createElement("div");
    row.className = "conversation-row";

    const openButton = document.createElement("button");
    openButton.className = "conversation-link";
    openButton.type = "button";
    openButton.textContent = conversation.title || "New conversation";
    openButton.setAttribute("aria-current", conversation.id === conversationId ? "true" : "false");
    openButton.addEventListener("click", () => openConversation(conversation.id));

    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-conversation";
    deleteButton.type = "button";
    deleteButton.textContent = "×";
    deleteButton.setAttribute("aria-label", `Delete ${conversation.title || "conversation"}`);
    deleteButton.addEventListener("click", () => removeConversation(conversation.id));

    row.append(openButton, deleteButton);
    conversationList.append(row);
  }
}

async function openConversation(id) {
  try {
    const conversation = await request(`/api/conversations/${encodeURIComponent(id)}`);
    conversationId = conversation.id;
    messagesElement.replaceChildren();
    welcome.hidden = true;
    for (const message of conversation.messages) {
      addMessage(message.role, message.content);
    }
    await refreshConversations();
    scrollConversationToBottom();
  } catch (error) {
    if (error.status === 401) showAuth("Your session expired. Please sign in again.");
    else addMessage("assistant", error.message, true);
  }
}

async function removeConversation(id) {
  try {
    await request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (conversationId === id) startNewChat();
    await refreshConversations();
  } catch (error) {
    if (error.status === 401) showAuth("Your session expired. Please sign in again.");
    else addMessage("assistant", error.message, true);
  }
}

function startNewChat() {
  if (sending) return;
  conversationId = null;
  messagesElement.replaceChildren();
  welcome.hidden = false;
  promptInput.value = "";
  promptInput.focus();
  refreshConversations().catch((error) => addMessage("assistant", error.message, true));
}

async function checkModelStatus() {
  try {
    const result = await request("/api/models");
    statusElement.innerHTML = '<span class="status-dot"></span> Local model ready';
    statusElement.setAttribute("aria-label", `Local model ready: ${result.model}`);
  } catch {
    statusElement.innerHTML = '<span class="status-dot status-dot-offline"></span> Model unavailable';
    statusElement.setAttribute("aria-label", "Local model unavailable");
  }
}

async function submitMessage(text) {
  const content = text.trim();
  if (!content || sending) return;

  sending = true;
  newChatButton.disabled = true;
  welcome.hidden = true;
  addMessage("user", content);
  promptInput.value = "";
  promptInput.style.height = "auto";
  sendButton.disabled = true;
  showLoading();
  scrollConversationToBottom();

  try {
    const payload = {
      messages: [{ role: "user", content }],
      ...(conversationId ? { conversation_id: conversationId } : {}),
    };
    const result = await request("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    document.querySelector("#loading-message")?.remove();
    if (typeof result?.reply !== "string" || !result.reply.trim()) {
      throw new Error("The server response did not contain an assistant reply.");
    }
    conversationId = result.conversation_id;
    addMessage("assistant", result.reply);
    await refreshConversations();
    if (isConversationNearBottom()) scrollConversationToBottom();
  } catch (error) {
    document.querySelector("#loading-message")?.remove();
    if (error.status === 401) showAuth("Your session expired. Please sign in again.");
    else addMessage("assistant", error.message || "Something went wrong. Please try again.", true);
  } finally {
    sending = false;
    newChatButton.disabled = false;
    sendButton.disabled = false;
    promptInput.focus();
  }
}

authMode.addEventListener("click", () => {
  registering = !registering;
  authTitle.textContent = registering ? "Create your account" : "Welcome back";
  authDescription.textContent = registering
    ? "Register to save your private conversations."
    : "Sign in to continue to Max-AI.";
  authSubmit.textContent = registering ? "Create account" : "Sign in";
  authMode.textContent = registering
    ? "Already have an account? Sign in"
    : "Need an account? Register";
  authPassword.autocomplete = registering ? "new-password" : "current-password";
  authMessage.textContent = "";
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  authSubmit.disabled = true;
  authMessage.textContent = registering ? "Creating your account…" : "Signing in…";
  try {
    const result = await request(registering ? "/api/auth/register" : "/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: authEmail.value.trim(),
        password: authPassword.value,
      }),
    });
    authPassword.value = "";
    showChat(result.user);
    startNewChat();
    await checkModelStatus();
  } catch (error) {
    authMessage.textContent = error.message || "Unable to authenticate. Please try again.";
  } finally {
    authSubmit.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await request("/api/auth/logout", { method: "POST" });
    conversationId = null;
    messagesElement.replaceChildren();
    showAuth("You have signed out.");
  } catch (error) {
    authMessage.textContent = `Unable to sign out: ${error.message}`;
  }
});

newChatButton.addEventListener("click", startNewChat);
chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessage(promptInput.value);
});

promptInput.addEventListener("input", () => {
  promptInput.style.height = "auto";
  promptInput.style.height = `${Math.min(promptInput.scrollHeight, 180)}px`;
});

promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => submitMessage(button.textContent));
});

syncAppViewportHeight();
window.addEventListener("resize", syncAppViewportHeight);
window.visualViewport?.addEventListener("resize", syncAppViewportHeight);
new ResizeObserver(() => {
  if (isConversationNearBottom()) scrollConversationToBottom();
}).observe(conversationElement);

async function initialize() {
  try {
    const result = await request("/api/auth/me");
    showChat(result);
    await refreshConversations();
    await checkModelStatus();
  } catch {
    showAuth();
  }
}

initialize();
