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
const myStoreForm = document.getElementById("my-store-form");
const myZipCodeInput = document.getElementById("my-zip-code");
const myStoreStatus = document.getElementById("my-store-status");
const myStoreMapElement = document.getElementById("my-store-map");
const myStoreResults = document.getElementById("my-store-results");
const selectedStoreList = document.getElementById("selected-store-list");
const myStoreSource = document.getElementById("my-store-source");
const pantryForm = document.getElementById("pantry-form");
const pantryNameInput = document.getElementById("pantry-name");
const pantryQuantityInput = document.getElementById("pantry-quantity");
const pantryStatus = document.getElementById("pantry-status");
const pantryList = document.getElementById("pantry-list");
const dishForm = document.getElementById("dish-form");
const dishInput = document.getElementById("dish-input");
const dishStatus = document.getElementById("dish-status");
const dishResults = document.getElementById("dish-results");
const dishSource = document.getElementById("dish-source");
const dishEmptyState = document.getElementById("dish-empty-state");
const profileNameInput = document.getElementById("profile-name");
const householdSizeInput = document.getElementById("household-size");
const profileZipCodeInput = document.getElementById("profile-zip-code");
const dietaryRestrictionsInput = document.getElementById("dietary-restrictions");
const budgetInput = document.getElementById("budget-input");
const currentBudget = document.getElementById("current-budget");
const remainingBudget = document.getElementById("remaining-budget");
const budgetMealCount = document.getElementById("budget-meal-count");
const scheduledMealCost = document.getElementById("scheduled-meal-cost");
const settingsStatus = document.getElementById("settings-status");
const accountStatus = document.querySelector(".account-status");
const accountUsername = document.getElementById("account-username");
const signOutButton = document.getElementById("sign-out-button");
const authStatus = document.getElementById("auth-status");
const signInForm = document.getElementById("sign-in-form");
const signUpForm = document.getElementById("sign-up-form");
const authTabs = document.querySelector(".auth-tabs");
const showSignInButton = document.getElementById("show-sign-in");
const showSignUpButton = document.getElementById("show-sign-up");
const signInUsernameInput = document.getElementById("sign-in-username");
const signInPasswordInput = document.getElementById("sign-in-password");
const signUpUsernameInput = document.getElementById("sign-up-username");
const signUpPasswordInput = document.getElementById("sign-up-password");

const scheduledMeals = [];
let currentUser = null;
let currentUserInfo = null;
let settingsSaveTimer = null;
let myStoreMap = null;
let myStoreMarkers = [];
let pantryItems = [];
let savedMyStores = [];
const selectedMyStoreIds = new Set();

const API_BASE_URL = (
  document.querySelector('meta[name="snapp-api-base-url"]')?.content || ""
)
  .trim()
  .replace(/\/+$/, "");
const SUPABASE_URL = (
  document.querySelector('meta[name="snapp-supabase-url"]')?.content || ""
).trim();
const SUPABASE_KEY = (
  document.querySelector('meta[name="snapp-supabase-key"]')?.content || ""
).trim();
const supabaseClient =
  window.supabase && SUPABASE_URL && SUPABASE_KEY
    ? window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY)
    : null;
const USERNAME_EMAIL_DOMAIN = "snapp.local";

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
const SIGNED_OUT_PANEL_IDS = new Set(["home", "account"]);
const SIGNED_IN_DEFAULT_PANEL_ID = "dishes";
const SIGNED_OUT_DEFAULT_PANEL_ID = "home";
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const RESTRICTION_WARNING_RULES = [
  {
    restrictionPattern: /\b(lactose|dairy|milk|cheese|cream|yogurt|butter)\b/i,
    ingredientPattern: /\b(milk|cheese|cheddar|mozzarella|feta|parmesan|cream|yogurt|butter|whey|lactose|dairy)\b/i,
    message: "Warning: contains lactose or dairy.",
  },
  {
    restrictionPattern: /\b(gluten|wheat|celiac|coeliac)\b/i,
    ingredientPattern: /\b(wheat|flour|bread|pasta|noodle|noodles|tortilla|breadcrumbs|gluten)\b/i,
    message: "Warning: contains gluten or wheat.",
  },
  {
    restrictionPattern: /\b(peanut|peanuts)\b/i,
    ingredientPattern: /\b(peanut|peanuts|peanut butter)\b/i,
    message: "Warning: contains peanuts.",
  },
  {
    restrictionPattern: /\b(tree nuts?|nuts?|almond|cashew|walnut|pecan)\b/i,
    ingredientPattern: /\b(almond|cashew|walnut|pecan|pistachio|hazelnut|nut butter|nuts?)\b/i,
    message: "Warning: contains tree nuts.",
  },
  {
    restrictionPattern: /\b(shellfish|shrimp|crab|lobster)\b/i,
    ingredientPattern: /\b(shellfish|shrimp|crab|lobster)\b/i,
    message: "Warning: contains shellfish.",
  },
  {
    restrictionPattern: /\b(egg|eggs)\b/i,
    ingredientPattern: /\b(egg|eggs|mayonnaise|mayo)\b/i,
    message: "Warning: contains egg.",
  },
  {
    restrictionPattern: /\b(soy|soya)\b/i,
    ingredientPattern: /\b(soy|soya|tofu|tempeh|edamame|soy sauce)\b/i,
    message: "Warning: contains soy.",
  },
];

function showPanel(id) {
  const isSignedIn = Boolean(currentUser);
  let targetId = id;

  if (isSignedIn && SIGNED_OUT_PANEL_IDS.has(targetId)) {
    targetId = SIGNED_IN_DEFAULT_PANEL_ID;
  }

  if (!isSignedIn && !SIGNED_OUT_PANEL_IDS.has(targetId)) {
    targetId = SIGNED_OUT_DEFAULT_PANEL_ID;
  }

  panels.forEach((panel) =>
    panel.classList.toggle("visible", panel.id === targetId)
  );
  navButtons.forEach((button) =>
    button.classList.toggle("active", button.dataset.target === targetId)
  );

  if (targetId === "my" && myStoreMap) {
    window.setTimeout(() => myStoreMap.invalidateSize(), 0);
  }
}

function renderNavigationForAuthState() {
  const isSignedIn = Boolean(currentUser);
  navButtons.forEach((button) => {
    const authView = button.dataset.authView;
    button.hidden =
      (authView === "signed-in" && !isSignedIn) ||
      (authView === "signed-out" && isSignedIn);
  });
  accountStatus.hidden = !isSignedIn;
}

function setAuthStatus(message, type = "neutral") {
  authStatus.textContent = message;
  authStatus.dataset.type = type;
}

function setSettingsStatus(message, type = "neutral") {
  settingsStatus.textContent = message;
  settingsStatus.dataset.type = type;
}

function normalizeUsername(username) {
  return username.trim().toLowerCase();
}

function getUsernameError(username) {
  if (!/^[a-z0-9._-]{3,24}$/.test(username)) {
    return "Use 3-24 letters, numbers, dots, underscores, or hyphens.";
  }

  return "";
}

function usernameToEmail(username) {
  return `${username}@${USERNAME_EMAIL_DOMAIN}`;
}

function getDisplayUsername(user) {
  if (!user) return "Signed out";
  return (
    currentUserInfo?.username ||
    user.user_metadata?.username ||
    user.email?.replace(/@snapp\.local$/, "") ||
    user.email
  );
}

function getDefaultUserInfo(user) {
  return {
    id: user.id,
    username: getDisplayUsername(user),
    zip_code: "",
    household_size: 2,
    budget: null,
    dietary_preference: "balanced",
    dietary_restrictions: "",
    notifications_enabled: true,
  };
}

function syncSettingsFromUserInfo(user, userInfo) {
  const info = userInfo || (user ? getDefaultUserInfo(user) : null);
  profileNameInput.value = getDisplayUsername(user);
  householdSizeInput.value = info?.household_size || "2";
  profileZipCodeInput.value = info?.zip_code || "";
  if (!myZipCodeInput.value) {
    myZipCodeInput.value = info?.zip_code || "";
  }
  if (info?.budget != null) {
    budgetInput.value = info.budget;
  } else {
    budgetInput.value = "";
  }
  if (info?.dietary_preference) {
    dietSelect.value = info.dietary_preference;
  }
  dietaryRestrictionsInput.value = info?.dietary_restrictions || "";
  if (info?.notifications_enabled != null) {
    notificationsToggle.checked = Boolean(info.notifications_enabled);
  }
  renderBudget();

  if (!user) {
    setSettingsStatus("");
  }
}

async function fetchUserInfo(user) {
  if (!supabaseClient || !user) return null;

  const { data, error } = await supabaseClient
    .from("user_info")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (error) {
    setSettingsStatus(error.message, "error");
    return null;
  }

  return data;
}

async function ensureUserInfo(user) {
  if (!supabaseClient || !user) return null;

  const existingUserInfo = await fetchUserInfo(user);
  if (existingUserInfo) return existingUserInfo;

  const newUserInfo = getDefaultUserInfo(user);
  const { data, error } = await supabaseClient
    .from("user_info")
    .insert(newUserInfo)
    .select()
    .single();

  if (error) {
    setSettingsStatus(error.message, "error");
    return null;
  }

  return data;
}

function getSettingsError() {
  const householdSize = Number.parseInt(householdSizeInput.value, 10);
  const zipCode = profileZipCodeInput.value.trim();

  if (!Number.isFinite(householdSize) || householdSize < 1) {
    return "Household size must be at least 1.";
  }

  if (zipCode && !/^\d{5}$/.test(zipCode)) {
    return "ZIP code must be 5 digits.";
  }

  return "";
}

async function saveSettingsToUser() {
  if (!supabaseClient || !currentUser) return;

  const settingsError = getSettingsError();
  if (settingsError) {
    setSettingsStatus(settingsError, "error");
    return;
  }

  const householdSize = Number.parseInt(householdSizeInput.value, 10);
  const zipCode = profileZipCodeInput.value.trim();
  setSettingsStatus("Saving settings...");

  const { data, error } = await supabaseClient
    .from("user_info")
    .upsert({
      id: currentUser.id,
      username: getDisplayUsername(currentUser),
      household_size: householdSize,
      zip_code: zipCode,
      budget: budgetInput.value ? Number(budgetInput.value) : null,
      dietary_preference: dietSelect.value,
      dietary_restrictions: dietaryRestrictionsInput.value.trim(),
      notifications_enabled: notificationsToggle.checked,
    })
    .select()
    .single();

  if (error) {
    setSettingsStatus(error.message, "error");
    return;
  }

  currentUserInfo = data;
  setSettingsStatus("Settings saved.", "success");
}

function queueSettingsSave() {
  if (!currentUser) return;
  window.clearTimeout(settingsSaveTimer);
  settingsSaveTimer = window.setTimeout(saveSettingsToUser, 450);
}

function setPantryStatus(message, type = "neutral") {
  pantryStatus.textContent = message;
  pantryStatus.dataset.type = type;
}

function getPantryErrorMessage(error) {
  const message = error?.message || "";
  if (
    message.includes("user_pantry_items") &&
    message.includes("schema cache")
  ) {
    return "Pantry setup is missing. Run the user_pantry_items SQL table setup in Supabase, then refresh.";
  }

  return message || "Pantry request failed.";
}

function getStoreErrorMessage(error) {
  const message = error?.message || "";
  if (message.includes("user_stores") && message.includes("schema cache")) {
    return "Store setup is missing. Run the user_stores SQL table setup in Supabase, then refresh.";
  }

  if (message.includes("permission denied")) {
    return "Store permissions are missing. Run the user_stores grant and policy SQL in Supabase, then refresh.";
  }

  return message || "Store request failed.";
}

function getStoreKey(store) {
  return [
    store.name || "store",
    store.address || "address",
    store.latitude ?? "lat",
    store.longitude ?? "lon",
  ].join("|");
}

function normalizeSavedStore(store) {
  return {
    id: store.store_key || getStoreKey(store),
    store_key: store.store_key || getStoreKey(store),
    name: store.name,
    address: store.address,
    latitude: store.latitude,
    longitude: store.longitude,
    website: store.website,
    distance_miles: store.distance_miles,
  };
}

function storeRecordForSave(store) {
  return {
    user_id: currentUser.id,
    store_key: store.id || getStoreKey(store),
    name: store.name,
    address: store.address,
    latitude: store.latitude != null ? Number(store.latitude) : null,
    longitude: store.longitude != null ? Number(store.longitude) : null,
    website: store.website || null,
    distance_miles:
      store.distance_miles != null ? Number(store.distance_miles) : null,
  };
}

function upsertSavedStoreState(store) {
  const savedStore = normalizeSavedStore(store);
  savedMyStores = [
    savedStore,
    ...savedMyStores.filter((existing) => existing.store_key !== savedStore.store_key),
  ];
  selectedMyStoreIds.add(savedStore.store_key);
}

function syncVisibleStoreSelection(storeKey, isSelected) {
  myStoreResults.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
    if (checkbox.value !== storeKey) return;
    checkbox.checked = isSelected;
    checkbox.closest("li")?.classList.toggle("selected", isSelected);
  });
}

async function loadSavedStores() {
  selectedMyStoreIds.clear();

  if (!supabaseClient || !currentUser) {
    savedMyStores = [];
    renderSelectedMyStores();
    return;
  }

  const { data, error } = await supabaseClient
    .from("user_stores")
    .select("store_key,name,address,latitude,longitude,website,distance_miles,created_at")
    .eq("user_id", currentUser.id)
    .order("created_at", { ascending: false });

  if (error) {
    savedMyStores = [];
    renderSelectedMyStores();
    myStoreStatus.textContent = getStoreErrorMessage(error);
    return;
  }

  savedMyStores = (data || []).map(normalizeSavedStore);
  savedMyStores.forEach((store) => selectedMyStoreIds.add(store.store_key));
  renderSelectedMyStores();
}

async function saveMyStore(store) {
  if (!supabaseClient || !currentUser) return false;

  const { data, error } = await supabaseClient
    .from("user_stores")
    .upsert(storeRecordForSave(store), { onConflict: "user_id,store_key" })
    .select("store_key,name,address,latitude,longitude,website,distance_miles,created_at")
    .single();

  if (error) {
    myStoreStatus.textContent = getStoreErrorMessage(error);
    return false;
  }

  upsertSavedStoreState(data);
  renderSelectedMyStores();
  myStoreStatus.textContent = `${data.name} saved to My stores.`;
  return true;
}

async function deleteMyStore(storeKey) {
  if (!supabaseClient || !currentUser) return false;

  const { error } = await supabaseClient
    .from("user_stores")
    .delete()
    .eq("user_id", currentUser.id)
    .eq("store_key", storeKey);

  if (error) {
    myStoreStatus.textContent = getStoreErrorMessage(error);
    return false;
  }

  savedMyStores = savedMyStores.filter((store) => store.store_key !== storeKey);
  selectedMyStoreIds.delete(storeKey);
  syncVisibleStoreSelection(storeKey, false);
  renderSelectedMyStores();
  myStoreStatus.textContent = "Store removed from My stores.";
  return true;
}

function renderPantryItems() {
  pantryList.replaceChildren();

  if (!currentUser) {
    setPantryStatus("");
    return;
  }

  if (!pantryItems.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "pantry-empty";
    emptyItem.textContent = "No pantry items added yet.";
    pantryList.appendChild(emptyItem);
    return;
  }

  pantryItems.forEach((item) => {
    const listItem = document.createElement("li");
    const itemText = document.createElement("span");
    const removeButton = document.createElement("button");

    itemText.textContent = `${item.name} - ${item.quantity}`;
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => deletePantryItem(item.id));

    listItem.append(itemText, removeButton);
    pantryList.appendChild(listItem);
  });
}

async function loadPantryItems() {
  if (!supabaseClient || !currentUser) {
    pantryItems = [];
    renderPantryItems();
    return;
  }

  const { data, error } = await supabaseClient
    .from("user_pantry_items")
    .select("id,name,quantity,created_at")
    .eq("user_id", currentUser.id)
    .order("created_at", { ascending: false });

  if (error) {
    pantryItems = [];
    renderPantryItems();
    setPantryStatus(getPantryErrorMessage(error), "error");
    return;
  }

  pantryItems = data || [];
  renderPantryItems();
  setPantryStatus("");
}

async function addPantryItem(name, quantity) {
  if (!supabaseClient || !currentUser) return false;

  setPantryStatus("Adding pantry item...");
  const { data, error } = await supabaseClient
    .from("user_pantry_items")
    .insert({
      user_id: currentUser.id,
      name,
      quantity,
    })
    .select("id,name,quantity,created_at")
    .single();

  if (error) {
    setPantryStatus(getPantryErrorMessage(error), "error");
    return false;
  }

  pantryItems = [data, ...pantryItems];
  renderPantryItems();
  setPantryStatus("Pantry item added.", "success");
  return true;
}

async function deletePantryItem(itemId) {
  if (!supabaseClient || !currentUser) return;

  const { error } = await supabaseClient
    .from("user_pantry_items")
    .delete()
    .eq("id", itemId)
    .eq("user_id", currentUser.id);

  if (error) {
    setPantryStatus(getPantryErrorMessage(error), "error");
    return;
  }

  pantryItems = pantryItems.filter((item) => item.id !== itemId);
  renderPantryItems();
  setPantryStatus("Pantry item removed.", "success");
}

function showAuthMode(mode) {
  const isSignUp = mode === "sign-up";
  authTabs.hidden = false;
  signInForm.hidden = isSignUp;
  signUpForm.hidden = !isSignUp;
  showSignInButton.classList.toggle("active", !isSignUp);
  showSignUpButton.classList.toggle("active", isSignUp);
  setAuthStatus("");
}

async function renderAuthState(user) {
  const wasSignedIn = Boolean(currentUser);
  currentUser = user;
  currentUserInfo = null;
  document.body.classList.toggle("signed-in", Boolean(user));
  renderNavigationForAuthState();
  accountUsername.textContent = getDisplayUsername(user);
  signOutButton.hidden = !user;

  if (user) {
    currentUserInfo = await ensureUserInfo(user);
  }

  accountUsername.textContent = getDisplayUsername(user);
  syncSettingsFromUserInfo(user, currentUserInfo);
  await loadSavedStores();
  await loadPantryItems();

  if (user) {
    authTabs.hidden = true;
    signInForm.hidden = true;
    signUpForm.hidden = true;
    setAuthStatus(`Signed in as ${getDisplayUsername(user)}.`, "success");
    if (SIGNED_OUT_PANEL_IDS.has(document.querySelector(".panel.visible")?.id)) {
      showPanel(SIGNED_IN_DEFAULT_PANEL_ID);
    }
    return;
  }

  if (wasSignedIn) {
    showAuthMode("sign-in");
    setAuthStatus("Signed out.", "success");
  }
  showPanel(SIGNED_OUT_DEFAULT_PANEL_ID);
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

function dishIngredientText(dish) {
  const ingredients = dish.ingredients_to_buy || dish.ingredients || [];
  const recipeIngredients = dish.recipe?.ingredients || [];
  return [...ingredients, ...recipeIngredients]
    .map((ingredient) =>
      [
        ingredient.product_name,
        ingredient.name,
        ingredient.ingredient,
        ingredient.package_size,
        ingredient.display,
        ingredient.measure,
      ]
        .filter(Boolean)
        .join(" ")
    )
    .join(" ");
}

function getRestrictionWarnings(dish) {
  const restrictions = dietaryRestrictionsInput.value.trim();
  if (!restrictions) return [];

  const dishText = `${dish.name || ""} ${dishIngredientText(dish)}`;
  return RESTRICTION_WARNING_RULES.filter(
    (rule) =>
      rule.restrictionPattern.test(restrictions) &&
      rule.ingredientPattern.test(dishText)
  ).map((rule) => rule.message);
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

async function fetchStores(zipCode, options = {}) {
  let lastError = API_BASE_URL
    ? "Unable to reach the grocery store backend."
    : "Backend URL is not configured.";

  for (const endpoint of getApiEndpoints("/grocery-stores")) {
    try {
      const params = new URLSearchParams({ zip: zipCode });
      if (options.radiusMiles) {
        params.set("radius_miles", options.radiusMiles);
      }
      const response = await fetch(`${endpoint}?${params.toString()}`);
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

function getStoreId(store) {
  return getStoreKey(store);
}

function clearMyStoreMap() {
  myStoreMarkers.forEach((marker) => marker.remove());
  myStoreMarkers = [];
}

function ensureMyStoreMap(center) {
  if (!window.L || !myStoreMapElement) return null;

  const mapCenter = [
    Number(center?.latitude) || 39.8283,
    Number(center?.longitude) || -98.5795,
  ];

  if (!myStoreMap) {
    myStoreMap = window.L.map(myStoreMapElement).setView(mapCenter, 14);
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors",
    }).addTo(myStoreMap);
  } else {
    myStoreMap.setView(mapCenter, 14);
    myStoreMap.invalidateSize();
  }

  return myStoreMap;
}

function renderSelectedMyStores() {
  selectedStoreList.replaceChildren();

  if (!savedMyStores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = "No stores selected.";
    selectedStoreList.appendChild(emptyItem);
    return;
  }

  savedMyStores.forEach((store) => {
    const item = document.createElement("li");
    const itemText = document.createElement("span");
    const removeButton = document.createElement("button");

    itemText.textContent = store.name;
    removeButton.type = "button";
    removeButton.textContent = "Remove";
    removeButton.addEventListener("click", () => deleteMyStore(store.store_key));

    item.append(itemText, removeButton);
    selectedStoreList.appendChild(item);
  });
}

function renderMyStores(data) {
  const stores = (data.stores || []).map((store) => ({
    ...store,
    id: getStoreId(store),
  }));
  myStoreResults.replaceChildren();
  clearMyStoreMap();

  const map = ensureMyStoreMap(data.center);
  if (!window.L || !map) {
    myStoreStatus.textContent = "Map library could not load. Store list is still available.";
  }

  stores.forEach((store) => {
    const item = document.createElement("li");
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    const text = document.createElement("span");
    const distanceText =
      store.distance_miles != null ? ` (${store.distance_miles} mi)` : "";

    checkbox.type = "checkbox";
    checkbox.value = store.id;
    text.textContent = `${store.name}${distanceText} - ${store.address}`;
    label.append(checkbox, text);
    item.appendChild(label);
    myStoreResults.appendChild(item);

    const marker =
      window.L && store.latitude != null && store.longitude != null
        ? window.L.marker([Number(store.latitude), Number(store.longitude)]).addTo(map)
        : null;

    async function setSelected(isSelected) {
      const previousSelected = selectedMyStoreIds.has(store.id);
      checkbox.disabled = true;

      const didPersist = isSelected
        ? await saveMyStore(store)
        : await deleteMyStore(store.id);

      checkbox.disabled = false;
      if (!didPersist) {
        checkbox.checked = previousSelected;
        item.classList.toggle("selected", previousSelected);
        return;
      }

      checkbox.checked = isSelected;
      item.classList.toggle("selected", isSelected);
      if (marker) {
        marker.setOpacity(isSelected ? 1 : 0.72);
      }
    }

    checkbox.addEventListener("change", () => setSelected(checkbox.checked));

    if (marker) {
      const popup = document.createElement("div");
      const popupName = document.createElement("strong");
      const popupAddress = document.createElement("div");
      popupName.textContent = store.name;
      popupAddress.textContent = store.address;
      popup.append(popupName, popupAddress);
      marker
        .bindPopup(popup)
        .on("click", () => setSelected(!selectedMyStoreIds.has(store.id)));
      myStoreMarkers.push(marker);
    }

    const isSelected = selectedMyStoreIds.has(store.id);
    checkbox.checked = isSelected;
    item.classList.toggle("selected", isSelected);
    if (marker) {
      marker.setOpacity(isSelected ? 1 : 0.72);
    }
  });

  if (map && myStoreMarkers.length) {
    const group = window.L.featureGroup(myStoreMarkers);
    map.fitBounds(group.getBounds().pad(0.22));
  }

  renderSelectedMyStores();
  myStoreSource.hidden = false;
}

async function fetchDishes(mealPrompt, householdSize, dietaryRestrictions) {
  let lastError = API_BASE_URL
    ? "Unable to reach the dishes backend."
    : "Backend URL is not configured.";

  for (const endpoint of getApiEndpoints("/dishes")) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meal_prompt: mealPrompt,
          household_size: householdSize,
          dietary_restrictions: dietaryRestrictions,
          pantry_items: pantryItems.map((item) => ({
            name: item.name,
            quantity: item.quantity,
          })),
        }),
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
    const restrictionWarnings = getRestrictionWarnings(dish);
    const ingredientsHeading = document.createElement("h4");
    const ingredientList = document.createElement("ul");
    const recipeIngredientsHeading = document.createElement("h4");
    const recipeIngredientList = document.createElement("ul");
    const recipeLinks = document.createElement("p");
    const scheduleButton = document.createElement("button");
    const recipe = dish.recipe || {};

    title.textContent = dish.name;
    calories.className = "dish-calories";
    calories.textContent = dish.calories_total
      ? `${dish.calories_total} matched grocery calories | ${dish.calories_per_person} per person`
      : "No demo grocery calorie match";
    price.className = "dish-price";
    price.textContent = dish.estimated_price_total
      ? `${currencyFormatter.format(dish.estimated_price_total)} matched grocery total | ${currencyFormatter.format(dish.estimated_price_per_serving)} per person`
      : "No demo grocery price match";
    method.className = "dish-method";
    method.textContent = recipe.instructions || dish.method;
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
    recipeIngredientsHeading.className = "dish-ingredients-heading";
    recipeIngredientsHeading.textContent = "MealDB recipe ingredients";
    recipeIngredientList.className = "dish-ingredients";
    recipeLinks.className = "dish-recipe-links";
    scheduleButton.type = "button";
    scheduleButton.className = "add-to-schedule-button";
    scheduleButton.textContent = "Add to schedule";
    scheduleButton.addEventListener("click", () => addMealToSchedule(dish));

    ingredientsToBuy.forEach((ingredient) => {
      const ingredientItem = document.createElement("li");
      const storeText = ingredient.store_name ? ` at ${ingredient.store_name}` : "";
      ingredientItem.textContent = `${ingredient.product_name || ingredient.name} (${ingredient.package_size})${storeText} - ${currencyFormatter.format(ingredient.estimated_price_total)}`;
      ingredientList.appendChild(ingredientItem);
    });
    if (!ingredientsToBuy.length) {
      const ingredientItem = document.createElement("li");
      ingredientItem.textContent = "No matching item in the SNAPP demo grocery database.";
      ingredientList.appendChild(ingredientItem);
    }

    (recipe.ingredients || []).forEach((ingredient) => {
      const ingredientItem = document.createElement("li");
      ingredientItem.textContent = ingredient.display || ingredient.name;
      recipeIngredientList.appendChild(ingredientItem);
    });

    if (recipe.source || recipe.youtube) {
      const links = [];
      if (recipe.source) {
        const sourceLink = document.createElement("a");
        sourceLink.href = recipe.source;
        sourceLink.target = "_blank";
        sourceLink.rel = "noopener noreferrer";
        sourceLink.textContent = "Recipe source";
        links.push(sourceLink);
      }
      if (recipe.youtube) {
        const youtubeLink = document.createElement("a");
        youtubeLink.href = recipe.youtube;
        youtubeLink.target = "_blank";
        youtubeLink.rel = "noopener noreferrer";
        youtubeLink.textContent = "Video";
        links.push(youtubeLink);
      }
      links.forEach((link, index) => {
        if (index) recipeLinks.append(" | ");
        recipeLinks.appendChild(link);
      });
    }

    item.appendChild(title);

    if (recipe.thumbnail) {
      const image = document.createElement("img");
      image.className = "dish-recipe-image";
      image.src = recipe.thumbnail;
      image.alt = `${dish.name} recipe photo`;
      item.appendChild(image);
    }

    item.append(
      calories,
      price,
      totalNutrition,
      perPersonNutrition,
      method
    );

    restrictionWarnings.forEach((warning) => {
      const warningMessage = document.createElement("p");
      warningMessage.className = "dish-warning";
      warningMessage.textContent = warning;
      item.appendChild(warningMessage);
    });

    item.append(
      recipeIngredientsHeading,
      recipeIngredientList,
      recipeLinks,
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

async function initializeAuth() {
  if (!supabaseClient) {
    setAuthStatus("Supabase is not configured. Check the project URL and publishable key.", "error");
    await renderAuthState(null);
    return;
  }

  const { data, error } = await supabaseClient.auth.getSession();
  if (error) {
    setAuthStatus(error.message, "error");
  }
  await renderAuthState(data.session?.user || null);

  supabaseClient.auth.onAuthStateChange(async (_event, session) => {
    await renderAuthState(session?.user || null);
  });
}

navButtons.forEach((button) =>
  button.addEventListener("click", () => showPanel(button.dataset.target))
);

showSignInButton.addEventListener("click", () => showAuthMode("sign-in"));
showSignUpButton.addEventListener("click", () => showAuthMode("sign-up"));

signInForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabaseClient) return;

  const submitButton = signInForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setAuthStatus("Signing in...");
  const username = normalizeUsername(signInUsernameInput.value);
  const usernameError = getUsernameError(username);

  if (usernameError) {
    setAuthStatus(usernameError, "error");
    submitButton.disabled = false;
    return;
  }

  const { error } = await supabaseClient.auth.signInWithPassword({
    email: usernameToEmail(username),
    password: signInPasswordInput.value,
  });

  if (error) {
    setAuthStatus(error.message, "error");
  } else {
    signInForm.reset();
    setAuthStatus("Signed in.", "success");
  }

  submitButton.disabled = false;
});

signUpForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabaseClient) return;

  const submitButton = signUpForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setAuthStatus("Creating account...");
  const username = normalizeUsername(signUpUsernameInput.value);
  const usernameError = getUsernameError(username);

  if (usernameError) {
    setAuthStatus(usernameError, "error");
    submitButton.disabled = false;
    return;
  }

  const { data, error } = await supabaseClient.auth.signUp({
    email: usernameToEmail(username),
    password: signUpPasswordInput.value,
    options: {
      data: {
        username,
      },
    },
  });

  if (error) {
    setAuthStatus(error.message, "error");
  } else if (data.session) {
    signUpForm.reset();
    setAuthStatus("Account created. You are signed in.", "success");
  } else {
    signUpForm.reset();
    showAuthMode("sign-in");
    setAuthStatus("Account created. Sign in with your username and password.", "success");
  }

  submitButton.disabled = false;
});

signOutButton.addEventListener("click", async () => {
  if (!supabaseClient) return;

  signOutButton.disabled = true;
  const { error } = await supabaseClient.auth.signOut();
  if (error) {
    setAuthStatus(error.message, "error");
  }
  signOutButton.disabled = false;
});

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

myStoreForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = myZipCodeInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    myStoreStatus.textContent = "Enter a valid 5-digit US ZIP code.";
    myStoreResults.replaceChildren();
    selectedStoreList.replaceChildren();
    myStoreSource.hidden = true;
    clearMyStoreMap();
    return;
  }

  const submitButton = myStoreForm.querySelector("button");
  submitButton.disabled = true;
  myStoreStatus.textContent = "Searching within 1 mile...";
  myStoreResults.replaceChildren();
  selectedStoreList.replaceChildren();
  myStoreSource.hidden = true;
  clearMyStoreMap();

  try {
    const data = await fetchStores(zipCode, { radiusMiles: "1" });
    renderMyStores(data);
    myStoreStatus.textContent = data.stores.length
      ? `${data.stores.length} grocery store${data.stores.length === 1 ? "" : "s"} found within 1 mile of ${data.location}.`
      : `No grocery stores were found within 1 mile of ${data.location}.`;
  } catch (error) {
    myStoreStatus.textContent = `Store search error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

pantryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = pantryNameInput.value.trim();
  const quantity = pantryQuantityInput.value.trim();

  if (!name || !quantity) {
    setPantryStatus("Enter both a food name and quantity.", "error");
    return;
  }

  const submitButton = pantryForm.querySelector("button");
  submitButton.disabled = true;

  try {
    const wasAdded = await addPantryItem(name, quantity);
    if (wasAdded) {
      pantryForm.reset();
    }
  } finally {
    submitButton.disabled = false;
  }
});

dishForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mealPrompt = dishInput.value.trim();
  if (!mealPrompt) return;

  const submitButton = dishForm.querySelector("button");
  submitButton.disabled = true;
  dishStatus.textContent = "Building grocery-backed meal ideas...";
  dishResults.replaceChildren();
  dishSource.hidden = true;
  dishEmptyState.hidden = false;

  try {
    const householdSize = getHouseholdSize();
    const dietaryRestrictions = dietaryRestrictionsInput.value.trim();
    const data = await fetchDishes(mealPrompt, householdSize, dietaryRestrictions);
    renderDishes(data);
    dishStatus.textContent = `Built 3 grocery-backed ideas for ${data.household_size} ${data.household_size === 1 ? "person" : "people"}.`;
    dishSource.hidden = false;
  } catch (error) {
    dishStatus.textContent = `Dish search error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

householdSizeInput.addEventListener("input", () => {
  renderBudget();
  queueSettingsSave();
});

profileZipCodeInput.addEventListener("input", queueSettingsSave);

dietaryRestrictionsInput.addEventListener("input", queueSettingsSave);

budgetInput.addEventListener("input", () => {
  renderBudget();
  queueSettingsSave();
});

themeSelect.addEventListener("change", () => {
  document.body.classList.toggle("dark-theme", themeSelect.value === "dark");
});

notificationsToggle.addEventListener("change", () => {
  const status = notificationsToggle.checked ? "enabled" : "disabled";
  appendMessage("bot", `Daily reminders ${status}.`);
  queueSettingsSave();
});

dietSelect.addEventListener("change", () => {
  appendMessage("bot", `Dietary preference set to ${dietSelect.value}.`);
  queueSettingsSave();
});

renderSchedule();
showAuthMode("sign-in");
initializeAuth();
