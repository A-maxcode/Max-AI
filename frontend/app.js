const form = document.querySelector("#chat-form");
const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send-button");
const messagesElement = document.querySelector("#messages");
const welcome = document.querySelector("#welcome");
const history = [];

function addMessage(role, content, isError = false) {
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
  message.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function submitMessage(text) {
  const content = text.trim();
  if (!content || sendButton.disabled) return;

  welcome.hidden = true;
  history.push({ role: "user", content });
  addMessage("user", content);
  promptInput.value = "";
  promptInput.style.height = "auto";
  sendButton.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const responseBody = await response.text();
    let result;
    try {
      result = JSON.parse(responseBody);
    } catch {
      if (!response.ok) {
        throw new Error(`The server returned HTTP ${response.status} with an invalid response.`);
      }
      throw new Error("The server returned an invalid response. Check the backend terminal for errors.");
    }
    if (!response.ok) {
      throw new Error(
        (typeof result.detail === "string" && result.detail) ||
          `The assistant could not respond (HTTP ${response.status}).`,
      );
    }
    if (typeof result.reply !== "string" || !result.reply.trim()) {
      throw new Error("The server response did not contain an assistant reply.");
    }
    history.push({ role: "assistant", content: result.reply });
    addMessage("assistant", result.reply);
  } catch (error) {
    history.pop();
    addMessage("assistant", error.message || "Something went wrong. Please try again.", true);
  } finally {
    sendButton.disabled = false;
    promptInput.focus();
  }
}

form.addEventListener("submit", (event) => {
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
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => submitMessage(button.textContent));
});
