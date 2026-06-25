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
const dishForm = document.getElementById("dish-form");
const dishInput = document.getElementById("dish-input");
const dishStatus = document.getElementById("dish-status");
const dishResults = document.getElementById("dish-results");
const dishSource = document.getElementById("dish-source");
const dishEmptyState = document.getElementById("dish-empty-state");
const householdSizeInput = document.getElementById("household-size");
const budgetInput = document.getElementById("budget-input");
const currentBudget = document.getElementById("current-budget");
const remainingBudget = document.getElementById("remaining-budget");
const budgetMealCount = document.getElementById("budget-meal-count");
const scheduledMealCost = document.getElementById("scheduled-meal-cost");

const scheduledMeals = [];

const API_BASE_URL = (
  document.querySelector('meta[name="snapp-api-base-url"]')?.content || ""
)
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
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

function showPanel(id) {
  panels.forEach((panel) => panel.classList.toggle("visible", panel.id === id));
  navButtons.forEach((button) =>
    button.classList.toggle("active", button.dataset.target === id)
  );
}

function getScheduledMealTotal() {
  return scheduledMeals.reduce(
    (total, meal) => total + Number(meal.estimated_price_total || 0),
    0
  );
}

function getHouseholdSize() {
  const householdSize = Number.parseInt(householdSizeInput.value, 10);
  return Number.isFinite(householdSize) && householdSize > 0 ? householdSize : 1;
}

function renderBudget() {
  const budget = Number(budgetInput.value || 0);
  const scheduledTotal = getScheduledMealTotal();
  const remaining = budget - scheduledTotal;

  currentBudget.textContent = currencyFormatter.format(budget);
  remainingBudget.textContent = currencyFormatter.format(remaining);
  remainingBudget.classList.toggle("over-budget", remaining < 0);
  budgetMealCount.textContent = scheduledMeals.length;
  scheduledMealCost.textContent = currencyFormatter.format(scheduledTotal);
}

function renderSchedule() {
  scheduleTableBody.replaceChildren();

  scheduledMeals.forEach((meal, index) => {
    const row = document.createElement("tr");
    const orderCell = document.createElement("td");
    const mealCell = document.createElement("td");
    const caloriesCell = document.createElement("td");
    const priceCell = document.createElement("td");

    orderCell.textContent = index + 1;
    mealCell.textContent = meal.name;
    caloriesCell.textContent = `${meal.calories_total || meal.calories_per_person} total`;
    priceCell.textContent = currencyFormatter.format(meal.estimated_price_total);

    row.append(orderCell, mealCell, caloriesCell, priceCell);
    scheduleTableBody.appendChild(row);
  });

  renderBudget();
}

function addMealToSchedule(dish) {
  const isAlreadyScheduled = scheduledMeals.some((meal) => meal.name === dish.name);
  if (!isAlreadyScheduled) {
    scheduledMeals.push(dish);
    renderSchedule();
  }

  showPanel("schedule");
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
    : "Backend URL is not configured.";

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
    : "Backend URL is not configured.";

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

async function fetchDishes(ingredients, householdSize) {
  let lastError = API_BASE_URL
    ? "Unable to reach the dishes backend."
    : "Backend URL is not configured.";

  for (const endpoint of getApiEndpoints("/dishes")) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ingredients, household_size: householdSize }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        lastError = data.error || `Dish request failed (${response.status}).`;
        continue;
      }
      return data;
    } catch (error) {
      lastError = error.message || "Network error while finding dishes.";
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

function renderDishes(data) {
  dishResults.replaceChildren();
  dishEmptyState.hidden = true;

  data.dishes.forEach((dish) => {
    const nutritionTotal = dish.nutrition_total || {};
    const nutritionPerPerson = dish.nutrition_per_person || {};
    const ingredientsToBuy = dish.ingredients_to_buy || dish.ingredients || [];
    const item = document.createElement("li");
    const title = document.createElement("h3");
    const calories = document.createElement("p");
    const price = document.createElement("p");
    const method = document.createElement("p");
    const totalNutrition = document.createElement("div");
    const perPersonNutrition = document.createElement("div");
    const ingredientsHeading = document.createElement("h4");
    const ingredientList = document.createElement("ul");
    const scheduleButton = document.createElement("button");

    title.textContent = dish.name;
    calories.className = "dish-calories";
    calories.textContent = `${dish.calories_total || dish.calories_per_person} total calories | ${dish.calories_per_person} per person`;
    price.className = "dish-price";
    price.textContent = `${currencyFormatter.format(dish.estimated_price_total)} total | ${currencyFormatter.format(dish.estimated_price_per_serving)} per person`;
    method.textContent = dish.method;
    totalNutrition.className = "dish-nutrition";
    totalNutrition.textContent = [
      "Total nutrition:",
      `${nutritionTotal.protein_g || 0}g protein`,
      `${nutritionTotal.carbohydrates_g || 0}g carbs`,
      `${nutritionTotal.fat_g || 0}g fat`,
      `${nutritionTotal.fiber_g || 0}g fiber`,
    ].join(" | ");
    perPersonNutrition.className = "dish-nutrition";
    perPersonNutrition.textContent = [
      "Per person:",
      `${nutritionPerPerson.protein_g || 0}g protein`,
      `${nutritionPerPerson.carbohydrates_g || 0}g carbs`,
      `${nutritionPerPerson.fat_g || 0}g fat`,
      `${nutritionPerPerson.fiber_g || 0}g fiber`,
    ].join(" | ");
    ingredientsHeading.className = "dish-ingredients-heading";
    ingredientsHeading.textContent = "Ingredients to buy";
    ingredientList.className = "dish-ingredients";
    scheduleButton.type = "button";
    scheduleButton.className = "add-to-schedule-button";
    scheduleButton.textContent = "Add to schedule";
    scheduleButton.addEventListener("click", () => addMealToSchedule(dish));

    ingredientsToBuy.forEach((ingredient) => {
      const ingredientItem = document.createElement("li");
      ingredientItem.textContent = `${ingredient.grams_total}g ${ingredient.name} - ${currencyFormatter.format(ingredient.estimated_price_total)}`;
      ingredientList.appendChild(ingredientItem);
    });

    item.append(
      title,
      calories,
      price,
      totalNutrition,
      perPersonNutrition,
      method,
      ingredientsHeading,
      ingredientList,
      scheduleButton
    );
    dishResults.appendChild(item);
  });

  if (data.missing_ingredients.length) {
    const missing = document.createElement("li");
    missing.className = "dish-missing";
    missing.textContent = `No USDA match found for: ${data.missing_ingredients.join(", ")}.`;
    dishResults.appendChild(missing);
  }
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

dishForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ingredients = dishInput.value.trim();
  if (!ingredients) return;

  const submitButton = dishForm.querySelector("button");
  submitButton.disabled = true;
  dishStatus.textContent = "Checking USDA FoodData Central...";
  dishResults.replaceChildren();
  dishSource.hidden = true;
  dishEmptyState.hidden = false;

  try {
    const householdSize = getHouseholdSize();
    const data = await fetchDishes(ingredients, householdSize);
    renderDishes(data);
    dishStatus.textContent = `Built 3 dishes for ${data.household_size} ${data.household_size === 1 ? "person" : "people"} from ${data.matched_ingredients.length} USDA food match${data.matched_ingredients.length === 1 ? "" : "es"}.`;
    dishSource.hidden = false;
  } catch (error) {
    dishStatus.textContent = `Dish search error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

budgetInput.addEventListener("input", renderBudget);

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
