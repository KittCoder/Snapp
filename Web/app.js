const panels = document.querySelectorAll(".panel");
const navButtons = document.querySelectorAll(".nav-button");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatLog = document.getElementById("chat-log");
const scheduleTableBody = document.querySelector("#schedule-table tbody");
const themeSelect = document.getElementById("theme-select");
const notificationsToggle = document.getElementById("notifications-toggle");
const dietSelect = document.getElementById("diet-select");

const scheduleData = [
  {
    day: "Monday",
    meals: {
      breakfast: "Greek yogurt parfait with berries",
      lunch: "Quinoa bowl with roasted veggies",
      dinner: "Lemon herb salmon with asparagus",
    },
  },
  {
    day: "Tuesday",
    meals: {
      breakfast: "Avocado toast with poached egg",
      lunch: "Chickpea salad wrap",
      dinner: "Turkey meatballs with zucchini noodles",
    },
  },
  {
    day: "Wednesday",
    meals: {
      breakfast: "Overnight oats with chia and banana",
      lunch: "Miso soup and sesame soba",
      dinner: "Grilled tofu with stir-fried greens",
    },
  },
  {
    day: "Thursday",
    meals: {
      breakfast: "Spinach smoothie with almond butter",
      lunch: "Mediterranean farro bowl",
      dinner: "Curry cauliflower with basmati rice",
    },
  },
  {
    day: "Friday",
    meals: {
      breakfast: "Veggie omelet with feta",
      lunch: "Teriyaki salmon lettuce cups",
      dinner: "Garlic shrimp with quinoa pilaf",
    },
  },
  {
    day: "Saturday",
    meals: {
      breakfast: "Pancakes with fresh fruit",
      lunch: "Caprese sandwich on sourdough",
      dinner: "BBQ chicken with roasted sweet potatoes",
    },
  },
  {
    day: "Sunday",
    meals: {
      breakfast: "Breakfast burrito with black beans",
      lunch: "Sun-dried tomato pasta salad",
      dinner: "Mushroom risotto with arugula",
    },
  },
];

function getChatEndpoints() {
  const endpoints = [];
  const { origin, protocol } = window.location;

  // Prefer same-origin /chat when served by Flask on localhost:5000.
  if (origin && origin !== "null") {
    endpoints.push(`${origin}/chat`);
  }

  // Fallback to local Flask endpoint for file:// and other local static hosts.
  if (protocol === "http:" || protocol === "file:") {
    endpoints.push("http://localhost:5000/chat");
    endpoints.push("http://127.0.0.1:5000/chat");
  }

  return [...new Set(endpoints)];
}

const CHAT_ENDPOINTS = getChatEndpoints();

function showPanel(id) {
  panels.forEach((panel) => panel.classList.toggle("visible", panel.id === id));
  navButtons.forEach((button) =>
    button.classList.toggle("active", button.dataset.target === id)
  );
}

function renderSchedule() {
  const rows = scheduleData
    .map(
      ({ day, meals }) => `
      <tr>
        <td>${day}</td>
        <td>${meals.breakfast}</td>
        <td>${meals.lunch}</td>
        <td>${meals.dinner}</td>
      </tr>`
    )
    .join("");
  scheduleTableBody.innerHTML = rows;
}

function appendMessage(type, text) {
  const li = document.createElement("li");
  li.className = type;
  li.textContent = text;
  chatLog.appendChild(li);
  chatLog.scrollTop = chatLog.scrollHeight;
  return li;
}

async function fetchBotReply(message) {
  let lastError = "Unable to reach chat backend.";

  for (const endpoint of CHAT_ENDPOINTS) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        lastError =
          data.details || data.error || `Chat request failed (${response.status}).`;
        continue;
      }

      if (!data.reply) {
        lastError = "Chat backend returned an invalid response.";
        continue;
      }

      return data.reply;
    } catch (error) {
      lastError = error.message || "Network error while contacting chat backend.";
    }
  }

  if (/Failed to fetch/i.test(lastError)) {
    const { origin, protocol } = window.location;
    if (protocol === "file:") {
      throw new Error(
        "Failed to fetch. Run `python Model/model.py` and open http://localhost:5000 (not the file directly)."
      );
    }
    if (protocol === "https:") {
      throw new Error(
        "Failed to fetch. HTTPS pages cannot call an HTTP backend; open the app at http://localhost:5000."
      );
    }
    throw new Error(
      `Failed to fetch from chat backend. Ensure Flask is running at http://localhost:5000 and try reloading ${origin}.`
    );
  }

  throw new Error(lastError);
}

navButtons.forEach((button) =>
  button.addEventListener("click", () => showPanel(button.dataset.target))
);

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  appendMessage("user", message);
  const pendingMessage = appendMessage("bot", "Thinking...");
  try {
    const reply = await fetchBotReply(message);
    pendingMessage.textContent = reply;
  } catch (error) {
    pendingMessage.textContent = `Chat backend error: ${error.message}`;
  }
  chatInput.value = "";
});

themeSelect.addEventListener("change", () => {
  document.body.classList.toggle("dark-theme", themeSelect.value === "dark");
});

notificationsToggle.addEventListener("change", () => {
  const status = notificationsToggle.checked ? "enabled" : "disabled";
  appendMessage("bot", `Daily reminders ${status}.`);
});

dietSelect.addEventListener("change", () => {
  appendMessage("bot", `Dietary preference set to ${dietSelect.value}.`);
});

renderSchedule();
