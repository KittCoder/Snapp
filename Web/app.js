const panels = document.querySelectorAll(".panel");
const navButtons = document.querySelectorAll(".nav-button");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatLog = document.getElementById("chat-log");
const scheduleTableBody = document.querySelector("#schedule-table tbody");
const themeSelect = document.getElementById("theme-select");
const notificationsToggle = document.getElementById("notifications-toggle");
const dietSelect = document.getElementById("diet-select");
const storeSearchForm = document.getElementById("store-search-form");
const zipCodeInput = document.getElementById("zip-code");
const storeSearchStatus = document.getElementById("store-search-status");
const storeResults = document.getElementById("store-results");
const storeSource = document.getElementById("store-source");

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

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "")
  .trim()
  .replace(/\/+$/, "");

function getApiEndpoints(path) {
  if (API_BASE_URL) {
    return [`${API_BASE_URL}${path}`];
  }

  if (["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return [
      `http://localhost:5000${path}`,
      `http://127.0.0.1:5000${path}`,
    ];
  }

  return [];
}

const CHAT_ENDPOINTS = getApiEndpoints("/chat");

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
  let lastError = API_BASE_URL
    ? "Unable to reach chat backend."
    : "Backend URL is not configured. Set VITE_API_BASE_URL in Vercel.";

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

  throw new Error(lastError);
}

async function fetchStores(zipCode) {
  let lastError = API_BASE_URL
    ? "Unable to reach the grocery store backend."
    : "Backend URL is not configured. Set VITE_API_BASE_URL in Vercel.";

  for (const endpoint of getApiEndpoints("/grocery-stores")) {
    try {
      const response = await fetch(`${endpoint}?zip=${encodeURIComponent(zipCode)}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const responseError = data.error || `Store search failed (${response.status}).`;
        if (response.status !== 404 || data.error) {
          return Promise.reject(new Error(responseError));
        }
        lastError = responseError;
        continue;
      }
      return data;
    } catch (error) {
      lastError = error.message || "Network error while searching for stores.";
    }
  }

  throw new Error(lastError);
}

function renderStores(stores) {
  storeResults.replaceChildren();
  stores.forEach((store) => {
    const item = document.createElement("li");
    const name = document.createElement("h3");
    const address = document.createElement("p");
    name.textContent = store.name;
    address.textContent = store.address;
    item.append(name, address);

    const links = document.createElement("div");
    links.className = "store-links";
    if (store.latitude != null && store.longitude != null) {
      const mapLink = document.createElement("a");
      mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(store.latitude)}&mlon=${encodeURIComponent(store.longitude)}#map=17/${encodeURIComponent(store.latitude)}/${encodeURIComponent(store.longitude)}`;
      mapLink.target = "_blank";
      mapLink.rel = "noopener noreferrer";
      mapLink.textContent = "View on map";
      links.appendChild(mapLink);
    }

    if (store.website) {
      const websiteLink = document.createElement("a");
      websiteLink.href = store.website;
      websiteLink.target = "_blank";
      websiteLink.rel = "noopener noreferrer";
      websiteLink.textContent = "Visit website";
      links.appendChild(websiteLink);
    }

    item.appendChild(links);
    storeResults.appendChild(item);
  });
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

storeSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = zipCodeInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    storeSearchStatus.textContent = "Enter a valid 5-digit US ZIP code.";
    storeResults.replaceChildren();
    storeSource.hidden = true;
    return;
  }

  const submitButton = storeSearchForm.querySelector("button");
  submitButton.disabled = true;
  storeSearchStatus.textContent = "Searching for grocery stores...";
  storeResults.replaceChildren();
  storeSource.hidden = true;

  try {
    const data = await fetchStores(zipCode);
    renderStores(data.stores);
    storeSearchStatus.textContent = data.stores.length
      ? `${data.stores.length} grocery store${data.stores.length === 1 ? "" : "s"} found near ${data.location}.`
      : `No grocery stores were found in ${data.location}.`;
    storeSource.hidden = false;
  } catch (error) {
    storeSearchStatus.textContent = `Store search error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
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
