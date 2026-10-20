
// ================= BASIC ELEMENTS =================

const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const messages = document.getElementById("messages");
const sendButton = form ? form.querySelector("button") : null;

const conversationHistory = [];
let currentChatId = null;

const welcomeMessage =
    "Hello! 👋 I'm CyberSafe AI, your cybersecurity assistant. Ask me about phishing, OTP scams, passwords, or online safety.";


// ================= HTML ESCAPING =================

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, (character) => {
        const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        };

        return entities[character];
    });
}


// ================= MARKDOWN FORMATTING =================

function formatInline(text) {
    let safe = escapeHTML(text);

    safe = safe.replace(/`([^`]+)`/g, "<code>$1</code>");

    safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    safe = safe.replace(/__(.+?)__/g, "<strong>$1</strong>");

    safe = safe.replace(
        /(^|[^*])\*([^*\n]+)\*(?!\*)/g,
        "$1<em>$2</em>"
    );

    safe = safe.replace(
        /(^|[^_])_([^_\n]+)_(?!_)/g,
        "$1<em>$2</em>"
    );

    return safe;
}


function renderMarkdown(text) {
    const lines = String(text)
        .replace(/\r\n/g, "\n")
        .split("\n");

    const output = [];

    let paragraph = [];
    let listType = null;

    function flushParagraph() {
        if (!paragraph.length) return;

        output.push(
            `<p>${paragraph.map(formatInline).join(" ")}</p>`
        );

        paragraph = [];
    }

    function closeList() {
        if (listType) {
            output.push(`</${listType}>`);
            listType = null;
        }
    }

    function startList(type) {
        if (listType === type) return;

        closeList();
        flushParagraph();

        listType = type;
        output.push(`<${type}>`);
    }

    for (const originalLine of lines) {
        const line = originalLine.trim();

        if (!line) {
            flushParagraph();
            closeList();
            continue;
        }

        // Markdown headings
        const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);

        if (headingMatch) {
            flushParagraph();
            closeList();

            const level = headingMatch[1].length;

            output.push(
                `<h${level}>${formatInline(headingMatch[2])}</h${level}>`
            );

            continue;
        }

        // Numbered lists
        const numberedMatch = line.match(/^\d+[.)]\s+(.+)$/);

        if (numberedMatch) {
            startList("ol");
            output.push(`<li>${formatInline(numberedMatch[1])}</li>`);
            continue;
        }

        // Bulleted lists
        const bulletMatch = line.match(/^[-*•]\s+(.+)$/);

        if (bulletMatch) {
            startList("ul");
            output.push(`<li>${formatInline(bulletMatch[1])}</li>`);
            continue;
        }

        closeList();

        // Plain-text section headings
        const plainHeading = line.match(
            /^(Overview|How It Works|Warning Signs|How to Stay Safe|What to Do If It Already Happened|How to Report)\s*:?\s*$/i
        );

        if (plainHeading) {
            flushParagraph();

            output.push(
                `<h3>${formatInline(plainHeading[1])}</h3>`
            );

            continue;
        }

        // Heading followed by text
        const labelledParagraph = line.match(
            /^(Overview|How It Works|Warning Signs|How to Stay Safe|What to Do If It Already Happened|How to Report)\s*:\s*(.+)$/i
        );

        if (labelledParagraph) {
            flushParagraph();

            output.push(
                `<h3>${formatInline(labelledParagraph[1])}</h3>`
            );

            output.push(
                `<p>${formatInline(labelledParagraph[2])}</p>`
            );

            continue;
        }

        paragraph.push(line);
    }

    flushParagraph();
    closeList();

    return output.join("");
}


// ================= DISPLAY MESSAGES =================

function addMessage(text, type) {
    const message = document.createElement("div");
    message.className = `message ${type}`;

    if (type === "bot") {
        message.innerHTML = renderMarkdown(text);
    } else {
        message.textContent = text;
    }

    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;

    return message;
}


function showWelcomeMessage() {
    if (!messages) return;

    messages.replaceChildren();
    addMessage(welcomeMessage, "bot");
}


// ================= CHAT API =================

if (form && input && messages && sendButton) {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const userMessage = input.value.trim();

        if (!userMessage || sendButton.disabled) return;

        addMessage(userMessage, "user");

        input.value = "";
        sendButton.disabled = true;

        const loading = addMessage("Thinking...", "bot");

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: userMessage,
                    history: conversationHistory.slice(-8),
                    chat_id: currentChatId
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Chat request failed.");
            }

            if (data.chat_id) {
                currentChatId = data.chat_id;
            }

            const answer = data.answer || "No answer received.";

            loading.innerHTML = renderMarkdown(answer);

            conversationHistory.push(
                { role: "user", content: userMessage },
                { role: "assistant", content: answer }
            );

            if (conversationHistory.length > 12) {
                conversationHistory.splice(
                    0,
                    conversationHistory.length - 12
                );
            }

            // Refresh history after saving the conversation.
            loadChatHistory();
            loadAnalytics();


        } catch (error) {
            loading.textContent =
                error.message || "Unable to connect to the chatbot.";

            console.error("Chatbot error:", error);

        } finally {
            sendButton.disabled = false;
            input.focus();
            messages.scrollTop = messages.scrollHeight;
        }
    });
}


// ================= QUICK QUESTIONS =================

document.querySelectorAll(".prompt-button").forEach((button) => {
    button.addEventListener("click", () => {
        if (!input || !form) return;

        input.value = button.dataset.prompt || "";
        form.requestSubmit();
    });
});


// ================= CLEAR CHAT =================

const clearChatButton = document.getElementById("clear-chat");

if (clearChatButton) {
    clearChatButton.addEventListener("click", () => {
        currentChatId = null;
        conversationHistory.length = 0;

        showWelcomeMessage();
        input.focus();
    });
}


// ================= MOBILE SIDEBAR =================

const menuButton = document.getElementById("menu-button");
const sidebar = document.getElementById("sidebar");

if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
        sidebar.classList.toggle("open");
    });

    document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            sidebar.classList.remove("open");
        });
    });
}


// ================= CHAT HISTORY ELEMENTS =================

const historyList = document.getElementById("chat-history-list");
const historyMessage = document.getElementById("chat-history-message");

const newHistoryChatButton = document.getElementById(
    "new-chat-history-btn"
);


function showHistoryMessage(message) {
    if (historyMessage) {
        historyMessage.textContent = message;
    }
}


function formatChatDate(value) {
    if (!value) return "";

    // MySQL timestamps may be returned as strings.
    const normalizedValue = value.includes("T")
        ? value
        : value.replace(" ", "T") + "Z";

    const date = new Date(normalizedValue);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short"
    });
}


// ================= LOAD CHAT HISTORY =================

async function loadChatHistory() {
    if (!historyList) return;

    historyList.replaceChildren();

    const loading = document.createElement("p");
    loading.className = "history-empty";
    loading.textContent = "Loading conversations...";
    historyList.appendChild(loading);

    try {
        const response = await fetch("/api/chats");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Could not load chat history."
            );
        }

        historyList.replaceChildren();

        if (!data.chats || data.chats.length === 0) {
            const empty = document.createElement("p");
            empty.className = "history-empty";
            empty.textContent =
                "No conversations yet. Start a new chat!";

            historyList.appendChild(empty);
            return;
        }

        data.chats.forEach((chat) => {
            const item = document.createElement("div");
            item.className = "history-item";

            const content = document.createElement("div");
            content.className = "history-item-content";
            content.tabIndex = 0;
            content.setAttribute("role", "button");

            const title = document.createElement("h4");
            title.textContent = chat.chat_title || "New Chat";

            const date = document.createElement("p");
            date.textContent = formatChatDate(chat.updated_at);

            content.append(title, date);

            content.setAttribute(
                "aria-label",
                `Open ${chat.chat_title || "conversation"}`
            );

            content.addEventListener("click", () => {
                openChatHistory(chat.chat_id);
            });

            content.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openChatHistory(chat.chat_id);
                }
            });

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "history-delete-btn";
            deleteButton.textContent = "Delete";
            deleteButton.setAttribute(
                "aria-label",
                "Delete conversation"
            );

            deleteButton.addEventListener("click", () => {
                deleteChatHistory(chat.chat_id, item);
            });

            item.append(content, deleteButton);
            historyList.appendChild(item);
        });

    } catch (error) {
        historyList.replaceChildren();

        const errorElement = document.createElement("p");
        errorElement.className = "history-empty";
        errorElement.textContent = error.message;

        historyList.appendChild(errorElement);
    }
}


// ================= OPEN PREVIOUS CHAT =================

function showChatbotPanel() {
    const chatbotLink = document.querySelector(
        '.sidebar .nav-link[href="#chatbot"]'
    );

    if (chatbotLink) {
        chatbotLink.click();
    }

    if (messages) {
        messages.scrollTop = messages.scrollHeight;
    }
}


async function openChatHistory(chatId) {
    showHistoryMessage("");

    try {
        const response = await fetch(`/api/chats/${chatId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Could not open conversation."
            );
        }

        currentChatId = data.chat.chat_id;
        conversationHistory.length = 0;

        messages.replaceChildren();

        for (const savedMessage of data.messages || []) {
            const sender =
                savedMessage.sender === "user" ? "user" : "bot";

            addMessage(savedMessage.message, sender);

            conversationHistory.push({
                role: sender === "user" ? "user" : "assistant",
                content: savedMessage.message
            });
        }

        // Keep only recent messages for the next Gemini request.
        if (conversationHistory.length > 12) {
            conversationHistory.splice(
                0,
                conversationHistory.length - 12
            );
        }

        showChatbotPanel();
        input.focus();

    } catch (error) {
        showHistoryMessage(error.message);
    }
}


// ================= DELETE CHAT =================

async function deleteChatHistory(chatId, item) {
    if (!window.confirm(
        "Delete this conversation permanently?"
    )) {
        return;
    }

    try {
        const response = await fetch(`/api/chats/${chatId}`, {
            method: "DELETE"
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Could not delete conversation."
            );
        }

        if (Number(currentChatId) === Number(chatId)) {
            currentChatId = null;
            conversationHistory.length = 0;
            showWelcomeMessage();
        }

        item.remove();
        showHistoryMessage("Conversation deleted.");

        if (
            historyList &&
            !historyList.querySelector(".history-item")
        ) {
            const empty = document.createElement("p");
            empty.className = "history-empty";
            empty.textContent =
                "No conversations yet. Start a new chat!";

            historyList.appendChild(empty);
        }

    } catch (error) {
        showHistoryMessage(error.message);
    }
}


// ================= CREATE NEW CHAT =================

if (newHistoryChatButton) {
    newHistoryChatButton.addEventListener("click", async () => {
        try {
            const response = await fetch("/api/chats", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Could not create a new chat."
                );
            }

            currentChatId = data.chat_id;
            conversationHistory.length = 0;

            showWelcomeMessage();
            showChatbotPanel();
            input.focus();

            await loadChatHistory();

        } catch (error) {
            showHistoryMessage(error.message);
        }
    });
}


// ================= HISTORY NAVIGATION =================

document.querySelectorAll(
    '.sidebar .nav-link[href="#history"]'
).forEach((link) => {
    link.addEventListener("click", loadChatHistory);
});


// Load history if the History section is initially visible.
// if (
//     historyList &&
//     document.getElementById("history")?.classList.contains("active")
// ) {
//     loadChatHistory();

// }

// Load chat history automatically when the dashboard opens.
document.addEventListener("DOMContentLoaded", () => {
    loadChatHistory();
});

// ================= ANALYTICS =================

async function loadAnalytics() {
    const conversationsElement = document.getElementById(
        "analytics-conversations"
    );

    const responsesElement = document.getElementById(
        "analytics-responses"
    );

    const statusElement = document.getElementById("analytics-status");

    if (!conversationsElement || !responsesElement) return;

    try {
        const response = await fetch("/api/analytics");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not load analytics.");
        }

        conversationsElement.textContent = data.conversations;
        responsesElement.textContent = data.responses;

        if (statusElement) {
            statusElement.textContent = "Your account activity at a glance.";
        }

    } catch (error) {
        conversationsElement.textContent = "—";
        responsesElement.textContent = "—";

        if (statusElement) {
            statusElement.textContent = error.message;
        }

        console.error("Analytics error:", error);
    }
}

// Load statistics when the dashboard opens.
document.addEventListener("DOMContentLoaded", loadAnalytics);

// Refresh statistics when the user opens Analytics.
document.querySelectorAll(
    '.sidebar .nav-link[href="#analytics"]'
).forEach((link) => {
    link.addEventListener("click", loadAnalytics);
});

/* =============== SETTINGS FUNCTIONALITY =============== */

const settingsStatus = document.getElementById("settings-status");
const themeSetting = document.getElementById("theme-setting");
const enterToSendSetting = document.getElementById("enter-to-send");
const settingsClearChat = document.getElementById("settings-clear-chat");

function showSettingsStatus(message) {
    if (settingsStatus) {
        settingsStatus.textContent = message;
    }
}

// 1. Appearance: save and apply the theme
function applyTheme(theme) {
    document.body.classList.toggle("light-theme", theme === "light");

    if (themeSetting) {
        themeSetting.value = theme;
    }
}

const savedTheme = localStorage.getItem("cybersafe-theme") || "dark";
applyTheme(savedTheme);

if (themeSetting) {
    themeSetting.addEventListener("change", () => {
        const theme = themeSetting.value;
        localStorage.setItem("cybersafe-theme", theme);
        applyTheme(theme);
        showSettingsStatus("Theme updated.");
    });
}

// 2. Chat settings: save Enter-to-Send preference
if (enterToSendSetting) {
    enterToSendSetting.checked =
        localStorage.getItem("cybersafe-enter-to-send") !== "false";

    enterToSendSetting.addEventListener("change", () => {
        localStorage.setItem(
            "cybersafe-enter-to-send",
            String(enterToSendSetting.checked)
        );
        showSettingsStatus("Chat preference saved.");
    });
}

// Press Enter to send, or Shift+Enter for a new line.
// Applies only when the preference is enabled.
if (input && form) {
    input.addEventListener("keydown", (event) => {
        if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.isComposing &&
            enterToSendSetting?.checked
        ) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
}

// Clear the current chat using your existing Clear Chat button.

if (settingsClearChat) {
    settingsClearChat.addEventListener("click", () => {
        const confirmed = window.confirm(
            "Return to the dashboard and clear the current chat?"
        );

        if (!confirmed) return;

        window.location.href = "/?clear_chat=1";
    });
}

// 3. Security: change password through the existing Flask API.
const passwordForm = document.getElementById("settings-password-form");
const passwordStatus = document.getElementById("password-status");

if (passwordForm) {
    passwordForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const currentPassword =
            document.getElementById("current-password").value;
        const newPassword =
            document.getElementById("new-password").value;
        const confirmPassword =
            document.getElementById("confirm-password").value;

        passwordStatus.textContent = "";

        if (newPassword.length < 8) {
            passwordStatus.textContent =
                "New password must contain at least 8 characters.";
            return;
        }

        if (newPassword !== confirmPassword) {
            passwordStatus.textContent =
                "New password and confirmation do not match.";
            return;
        }

        if (currentPassword === newPassword) {
            passwordStatus.textContent =
                "Choose a password different from your current password.";
            return;
        }

        const submitButton = passwordForm.querySelector(
            'button[type="submit"]'
        );
        submitButton.disabled = true;

        try {
            const response = await fetch("/api/change-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Could not change password.");
            }

            passwordStatus.textContent =
                data.message || "Password changed successfully.";
            passwordForm.reset();
        } catch (error) {
            passwordStatus.textContent = error.message;
        } finally {
            submitButton.disabled = false;
        }
    });
}

// 4. Account: load and save profile through the existing Flask API.
const profileForm = document.getElementById("settings-profile-form");
const profileStatus = document.getElementById("profile-status");
const profileNameInput = document.getElementById("settings-name");
const profileEmailInput = document.getElementById("settings-email");

async function loadSettingsProfile() {
    if (!profileForm) return;

    try {
        const response = await fetch("/api/profile");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not load profile.");
        }

        // Supports either {name, email} or {user: {name, email}}.
        const profile = data.user || data;

        profileNameInput.value = profile.name || "";
        profileEmailInput.value = profile.email || "";
    } catch (error) {
        profileStatus.textContent = error.message;
    }
}

if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        profileStatus.textContent = "";

        const submitButton = profileForm.querySelector(
            'button[type="submit"]'
        );
        submitButton.disabled = true;

        try {
            const response = await fetch("/api/profile", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: profileNameInput.value.trim(),
                    email: profileEmailInput.value.trim()
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Could not update profile.");
            }

            profileStatus.textContent =
                data.message || "Profile updated successfully.";

            // Update visible account details if those elements exist.
            const nameDisplay = document.getElementById("profile-name");
            const emailDisplay = document.getElementById("profile-email");

            if (nameDisplay) {
                nameDisplay.textContent = profileNameInput.value.trim();
            }

            if (emailDisplay) {
                emailDisplay.textContent = profileEmailInput.value.trim();
            }
        } catch (error) {
            profileStatus.textContent = error.message;
        } finally {
            submitButton.disabled = false;
        }
    });

    loadSettingsProfile();
}

/* Clear chat after returning from the separate Settings page */
const pageParams = new URLSearchParams(window.location.search);

if (pageParams.get("clear_chat") === "1" && clearChatButton) {
    clearChatButton.click();

    window.history.replaceState(
        {},
        document.title,
        window.location.pathname
    );
}

// ================= PHISHING URL SCANNER =================
// Render API content using textContent only; never inject server data as HTML.
const urlScanForm = document.getElementById("url-scan-form");
const urlScanInput = document.getElementById("url-scan-input");
const urlScanButton = document.getElementById("url-scan-button");
const urlScanResult = document.getElementById("url-scan-result");
const urlScanResultTitle = document.getElementById("url-scan-result-title");
const urlScanResultDetail = document.getElementById("url-scan-result-detail");
const urlScanResultWarning = document.getElementById("url-scan-result-warning");

function showUrlScanMessage(kind, title, detail = "", warning = "") {
    if (!urlScanResult) return;
    urlScanResult.hidden = false;
    urlScanResult.className = `url-scan-result ${kind}`;
    urlScanResultTitle.textContent = title;
    urlScanResultDetail.textContent = detail;
    urlScanResultWarning.textContent = warning;
    urlScanResultWarning.hidden = !warning;
}

if (urlScanForm && urlScanInput && urlScanButton) {
    urlScanForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submittedUrl = urlScanInput.value.trim();

        if (!submittedUrl) {
            showUrlScanMessage("error", "Enter a URL", "Paste a website address to scan.");
            urlScanInput.focus();
            return;
        }
        if (submittedUrl.length > 2048) {
            showUrlScanMessage("error", "URL is too long", "Use a URL no longer than 2048 characters.");
            return;
        }
        if (/\s/.test(submittedUrl)) {
            showUrlScanMessage("error", "Invalid URL", "Enter one URL without spaces.");
            return;
        }

        // Permit a bare domain by normalizing it to HTTPS for browser-side validation.
        const candidateForValidation = /^[a-zA-Z][a-zA-Z\d+.-]*:\/\//.test(submittedUrl)
            ? submittedUrl
            : `https://${submittedUrl}`;
        let parsedUrl;
        try {
            parsedUrl = new URL(candidateForValidation);
        } catch (_) {
            showUrlScanMessage("error", "Invalid URL", "Enter a valid website address, such as https://example.com.");
            return;
        }
        if (!['http:', 'https:'].includes(parsedUrl.protocol) || !parsedUrl.hostname || !parsedUrl.hostname.includes('.')) {
            showUrlScanMessage("error", "Unsupported URL", "Only web URLs with a valid domain using HTTP or HTTPS can be scanned.");
            return;
        }

        urlScanButton.disabled = true;
        urlScanButton.querySelector(".url-scan-button-label").textContent = "Scanning…";
        showUrlScanMessage("loading", "Checking URL…", "The trained model is analyzing URL features.");

        try {
            const response = await fetch("/api/check-url", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify({ url: submittedUrl })
            });

            let data;
            try {
                data = await response.json();
            } catch (_) {
                throw new Error("The server returned an unreadable response. Please try again.");
            }
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "The URL could not be scanned.");
            }

            const isPhishing = data.label === "likely_phishing";
            const probability = Number(data.phishing_probability);
            const hasProbability = Number.isFinite(probability) && probability >= 0 && probability <= 1;
            const probabilityText = hasProbability
                ? `Estimated phishing probability: ${(probability * 100).toFixed(1)}%.`
                : "The model did not return a usable probability.";
            const confidence = Number(data.confidence_percent);
            const confidenceText = Number.isFinite(confidence)
                ? ` Model confidence estimate: ${confidence.toFixed(1)}%.`
                : "";

            showUrlScanMessage(
                isPhishing ? "danger" : "caution",
                isPhishing ? "⚠ Likely suspicious / phishing" : "No obvious phishing signal detected",
                `${probabilityText}${confidenceText}`,
                // data.warning || "This model estimate is not proof that a website is malicious or safe. Verify the domain independently before entering sensitive information."
            );
        } catch (error) {
            showUrlScanMessage("error", "Scan failed", error.message || "Could not contact the scanner. Check that you are logged in and the server is running.");
        } finally {
            urlScanButton.disabled = false;
            urlScanButton.querySelector(".url-scan-button-label").textContent = "Scan URL";
        }
    });
}

