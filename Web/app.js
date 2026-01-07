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

const cannedResponses = [
  { keywords: ["breakfast", "morning"], reply: "Start the day with protein and fiber—how about Greek yogurt with berries?" },
  { keywords: ["lunch", "midday"], reply: "Need something quick? Try a grain bowl with roasted veggies." },
  { keywords: ["dinner", "evening"], reply: "A lean protein with greens will keep dinner light but satisfying." },
  { keywords: ["swap", "change"], reply: "Sure! Pick a meal you want to swap, and I'll suggest an alternative." },
  { keywords: ["schedule", "plan"], reply: "Your weekly schedule shows three meals per day—check the Schedule tab for details." },
];

const fallbackReply = "I'm here to help with meals, schedules, or settings. Try asking about breakfast ideas!";

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
  const response = await fetch("http://localhost:5000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error("Chat request failed");
  }
  const data = await response.json();
  return data.reply;
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
    const normalized = message.toLowerCase();
    const match = cannedResponses.find(({ keywords }) =>
      keywords.some((keyword) => normalized.includes(keyword))
    );
    pendingMessage.textContent = match ? match.reply : fallbackReply;
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
