const panels = document.querySelectorAll(".panel");
const navButtons = document.querySelectorAll(".nav-button");
const appSwitchButtons = document.querySelectorAll("[data-app-mode]");
const scheduleCalendar = document.getElementById("schedule-calendar");
const scheduleRecipeTray = document.getElementById("schedule-recipe-tray");
const scheduleRecipeList = document.getElementById("schedule-recipe-list");
const scheduleFavoriteRecipesButton = document.getElementById("schedule-favorite-recipes-button");
const scheduleFavoriteRecipesPanel = document.getElementById("schedule-favorite-recipes-panel");
const favoriteRecipesStatus = document.getElementById("favorite-recipes-status");
const favoriteRecipesList = document.getElementById("favorite-recipes-list");
const themeSelect = document.getElementById("theme-select");
const languageSelect = document.getElementById("language-select");
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
const pantryQuantityLabel = document.getElementById("pantry-quantity-label");
const pantrySpiceSuggestions = document.getElementById("pantry-spice-suggestions");
const pantryStatus = document.getElementById("pantry-status");
const pantryList = document.getElementById("pantry-list");
const dishForm = document.getElementById("dish-form");
const dishInput = document.getElementById("dish-input");
const dishStatus = document.getElementById("dish-status");
const dishResults = document.getElementById("dish-results");
const dishSource = document.getElementById("dish-source");
const dishEmptyState = document.getElementById("dish-empty-state");
const dishModal = document.getElementById("dish-modal");
const dishModalTitle = document.getElementById("dish-modal-title");
const dishModalContent = document.getElementById("dish-modal-content");
const dishModalClose = document.getElementById("dish-modal-close");
const shoppingAddPantryButton = document.getElementById("shopping-add-pantry-button");
const shoppingStatus = document.getElementById("shopping-status");
const shoppingList = document.getElementById("shopping-list");
const profileNameInput = document.getElementById("profile-name");
const householdSizeInput = document.getElementById("household-size");
const profileZipCodeInput = document.getElementById("profile-zip-code");
const dietaryRestrictionsInput = document.getElementById("dietary-restrictions");
const budgetInput = document.getElementById("budget-input");
const currentBudget = document.getElementById("current-budget");
const remainingBudget = document.getElementById("remaining-budget");
const budgetEmptyMessage = document.getElementById("budget-empty-message");
const budgetOpenSnap101Button = document.getElementById("budget-open-snap101");
const budgetMealCount = document.getElementById("budget-meal-count");
const scheduledMealCost = document.getElementById("scheduled-meal-cost");
const macroTrackerMealCount = document.getElementById("macro-tracker-meal-count");
const macroProteinTotal = document.getElementById("macro-protein-total");
const macroProteinGoal = document.getElementById("macro-protein-goal");
const macroProteinFill = document.getElementById("macro-protein-fill");
const macroCarbsTotal = document.getElementById("macro-carbs-total");
const macroCarbsGoal = document.getElementById("macro-carbs-goal");
const macroCarbsFill = document.getElementById("macro-carbs-fill");
const macroFatTotal = document.getElementById("macro-fat-total");
const macroFatGoal = document.getElementById("macro-fat-goal");
const macroFatFill = document.getElementById("macro-fat-fill");
const settingsStatus = document.getElementById("settings-status");
const accountStatus = document.querySelector(".account-status");
const accountUsername = document.getElementById("account-username");
const signOutButton = document.getElementById("sign-out-button");
const accountPanelSignOutButton = document.getElementById("account-panel-sign-out-button");
const signedInAccountPanel = document.getElementById("signed-in-account");
const signedInAccountName = document.getElementById("signed-in-account-name");
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
const saleIngredientsGrid = document.getElementById("sale-ingredients-grid");
const saleIngredientsStatus = document.getElementById("sale-ingredients-status");
const homeUsername = document.getElementById("home-username");
const onboardingForm = document.getElementById("onboarding-form");
const onboardingProgressLabel = document.getElementById("onboarding-progress-label");
const onboardingProgressBar = document.getElementById("onboarding-progress-bar");
const onboardingStatus = document.getElementById("onboarding-status");
const onboardingBackButton = document.getElementById("onboarding-back");
const onboardingContinueButton = document.getElementById("onboarding-continue");
const onboardingZipCodeInput = document.getElementById("onboarding-zip-code");
const onboardingHouseholdMinusButton = document.getElementById("onboarding-household-minus");
const onboardingHouseholdPlusButton = document.getElementById("onboarding-household-plus");
const onboardingHouseholdInput = document.getElementById("onboarding-household-size");
const onboardingHouseholdOutput = document.getElementById("onboarding-household-output");
const onboardingPreferenceChips = document.getElementById("onboarding-preference-chips");
const onboardingCustomPreferenceInput = document.getElementById("onboarding-custom-preference");
const onboardingAddPreferenceButton = document.getElementById("onboarding-add-preference");
const onboardingSelectedPreferences = document.getElementById("onboarding-selected-preferences");
const settingsPreferenceChips = document.getElementById("settings-preference-chips");
const settingsCustomPreferenceInput = document.getElementById("settings-custom-preference");
const settingsAddPreferenceButton = document.getElementById("settings-add-preference");
const settingsSelectedPreferences = document.getElementById("settings-selected-preferences");
const snapHouseholdSizeInput = document.getElementById("snap-household-size");
const snapIncomeInput = document.getElementById("snap-income");
const snapEstimateOutput = document.getElementById("snap-estimate-output");
const plateBalanceSlider = document.getElementById("plate-balance-slider");
const plateBalanceScore = document.getElementById("plate-balance-score");
const plateBalanceMessage = document.getElementById("plate-balance-message");
const plateProduceFill = document.getElementById("plate-produce-fill");
const plateGrainFill = document.getElementById("plate-grain-fill");
const snackOptionButtons = document.querySelectorAll(".snack-options button");
const snackScore = document.getElementById("snack-score");
const snackMeterFill = document.getElementById("snack-meter-fill");
const snackMessage = document.getElementById("snack-message");
const waterTapButton = document.getElementById("water-tap-button");
const waterResetButton = document.getElementById("water-reset-button");
const waterCount = document.getElementById("water-count");
const waterFill = document.getElementById("water-fill");
const waterMessage = document.getElementById("water-message");

const scheduledMeals = [];
let favoriteRecipes = [];
let currentUser = null;
let currentUserInfo = null;
let settingsSaveTimer = null;
let onboardingStepIndex = 0;
let onboardingForNewAccount = false;
let pendingNewAccountUsername = "";
let authLandingPending = false;
let selectedDietaryPreferences = [];
let myStoreMap = null;
let myStoreMarkers = [];
let pantryItems = [];
let savedMyStores = [];
let activeAuthUserId = null;
let dishProgressTimer = null;
let authRenderSequence = 0;
let activeAppMode = "snapp";
let hydrationTaps = 3;
const selectedMyStoreIds = new Set();
const selectedShoppingIngredientIds = new Set();
const pantryHandledShoppingIngredientIds = new Set();
const LANGUAGE_STORAGE_KEY = "snapp-language";
const ONBOARDING_COMPLETED_STORAGE_PREFIX = "snapp:onboarding-completed:";
const SHOPPING_CATEGORY_ORDER = [
  "Produce",
  "Bakery & Bread",
  "Deli & Prepared Foods",
  "Meat",
  "Poultry",
  "Seafood",
  "Dairy & Eggs",
  "Refrigerated",
  "Frozen",
  "Canned & Jarred Goods",
  "Pasta, Rice & Grains",
  "Beans & Legumes",
  "Baking",
  "Spices & Seasonings",
  "Oils, Vinegars & Condiments",
  "Sauces & Dressings",
  "Breakfast & Cereal",
  "Snacks",
  "Beverages",
  "International Foods",
  "Household",
  "Other",
];

function getLanguage() { return window.SNAPP_I18N.locale; }
function t(key, values = {}) { return window.SNAPP_I18N.t(key, values); }
function translateText(text) { return window.SNAPP_I18N.translate(text); }
function applyLanguage() { window.SNAPP_I18N.refresh(); }

const DISH_PROGRESS_MESSAGES = [
  "Finding meals...",
  "Checking recipes...",
  "Matching ingredients...",
  "Pricing groceries...",
];

const TRADITIONAL_SPICES = [
  "salt",
  "black pepper",
  "garlic powder",
  "onion powder",
  "paprika",
  "smoked paprika",
  "cayenne pepper",
  "crushed red pepper flakes",
  "chili powder",
  "ground cumin",
  "ground coriander",
  "ground cinnamon",
  "ground ginger",
  "ground nutmeg",
  "ground cloves",
  "allspice",
  "turmeric",
  "dried oregano",
  "dried basil",
  "dried thyme",
  "dried rosemary",
  "dried sage",
  "dried parsley",
  "dill weed",
  "bay leaves",
  "Italian seasoning",
  "herbes de Provence",
  "poultry seasoning",
  "celery seed",
  "mustard powder",
];

const SPICE_ALIASES = new Map([
  ["pepper", "black pepper"],
  ["cayenne", "cayenne pepper"],
  ["red pepper flakes", "crushed red pepper flakes"],
  ["crushed red pepper", "crushed red pepper flakes"],
  ["cumin", "ground cumin"],
  ["coriander", "ground coriander"],
  ["cinnamon", "ground cinnamon"],
  ["ginger", "ground ginger"],
  ["nutmeg", "ground nutmeg"],
  ["cloves", "ground cloves"],
  ["oregano", "dried oregano"],
  ["basil", "dried basil"],
  ["thyme", "dried thyme"],
  ["rosemary", "dried rosemary"],
  ["sage", "dried sage"],
  ["parsley", "dried parsley"],
  ["dill", "dill weed"],
  ["bay leaf", "bay leaves"],
  ["italian seasoning", "Italian seasoning"],
  ["herbs de provence", "herbes de Provence"],
  ["herbes de provence", "herbes de Provence"],
  ["mustard", "mustard powder"],
  ["dry mustard", "mustard powder"],
]);

function normalizeSpiceText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function canonicalSpiceName(value) {
  const normalized = normalizeSpiceText(value);
  if (!normalized) return "";
  const direct = TRADITIONAL_SPICES.find((spice) => normalizeSpiceText(spice) === normalized);
  if (direct) return direct;
  return SPICE_ALIASES.get(normalized) || "";
}

function isTraditionalSpice(value) {
  return Boolean(canonicalSpiceName(value));
}
const SCHEDULE_DAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];
const MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner"];
const DEFAULT_TRADER_JOES_STORE_NUMBER = "544";

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

const SIGNED_OUT_PANEL_IDS = new Set(["home", "account"]);
const ONBOARDING_PANEL_ID = "onboarding";
const SIGNED_IN_DEFAULT_PANEL_ID = "home";
const SIGNED_OUT_DEFAULT_PANEL_ID = "home";
const ONBOARDING_TOTAL_STEPS = 4;
const SNAP101_PANEL_IDS = new Set(["snap101-snap", "snap101-nutrition", "snap101-signup", "snap101-signup-options", "snap101-centers"]);
const SNAP101_DEFAULT_PANEL_ID = "snap101-snap";
const SNAPP_PANEL_IDS = new Set([
  "account",
  "onboarding",
  "home",
  "dishes",
  "recipe-chat",
  "schedule",
  "shopping",
  "my",
  "pantry",
  "budget",
  "settings",
]);
const WEEKLY_MACRO_GOALS = {
  protein: 350,
  carbs: 1925,
  fat: 546,
};
// USDA FY2027, effective 2026-10-01 through 2027-09-30 (48 states/DC).
// https://fns-prod.azureedge.us/snap/allotment/cola
const SNAP_MAX_ALLOTMENTS = {
  1: 306,
  2: 562,
  3: 808,
  4: 1023,
  5: 1217,
  6: 1463,
  7: 1616,
  8: 1841,
};
const SNAP_ADDITIONAL_MEMBER_ALLOTMENT = 225;
const SNAP_LARGE_HOUSEHOLD_ALLOTMENT = 3887;
const HOUSEHOLD_MIN = 1;
const HOUSEHOLD_MAX = 20;
const POPULAR_DIETARY_PREFERENCES = [
  "Vegetarian",
  "Vegan",
  "Pescatarian",
  "Gluten-free",
  "Dairy-free",
  "Nut-free",
  "Peanut-free",
  "Egg-free",
  "Soy-free",
  "Halal",
  "Kosher",
  "Low sodium",
  "Low sugar",
  "High protein",
];
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const gramFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

function formatServings(dish) {
  const recipe = dish?.recipe || {};
  const value = dish?.servings_display || recipe.servings_display || recipe.servings || dish?.servings;
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const text = String(value).trim();
  if (!text) {
    return "";
  }
  return `${text} serving${text === "1" ? "" : "s"}`;
}

function getServingCount(dish) {
  const recipe = dish?.recipe || {};
  const candidates = [
    dish?.nutrition_servings,
    dish?.servings,
    recipe.servings,
    dish?.servings_display,
    recipe.servings_display,
  ];

  for (const candidate of candidates) {
    if (candidate === null || candidate === undefined || candidate === "") continue;
    const numericValue = Number(candidate);
    if (Number.isFinite(numericValue) && numericValue > 0) {
      return numericValue;
    }
    const match = String(candidate).match(/\d+(?:\.\d+)?/);
    if (match) {
      const parsedValue = Number(match[0]);
      if (Number.isFinite(parsedValue) && parsedValue > 0) {
        return parsedValue;
      }
    }
  }

  return 1;
}

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
  let targetId = id === "information" ? "my" : id;
  const targetAppMode = SNAP101_PANEL_IDS.has(targetId) ? "snap101" : "snapp";

  activeAppMode = targetAppMode;
  renderAppMode();

  if (activeAppMode === "snapp" && !isSignedIn && !SIGNED_OUT_PANEL_IDS.has(targetId)) {
    targetId = SIGNED_OUT_DEFAULT_PANEL_ID;
  }

  if (
    activeAppMode === "snapp" &&
    isOnboardingRequired() &&
    targetId !== ONBOARDING_PANEL_ID &&
    targetId !== "account"
  ) {
    targetId = ONBOARDING_PANEL_ID;
  }

  panels.forEach((panel) =>
    panel.classList.toggle("visible", panel.id === targetId)
  );
  const navTargetId = ["snap101-signup-options", "snap101-centers"].includes(targetId) ? "snap101-signup" : targetId;
  navButtons.forEach((button) =>
    button.classList.toggle("active", button.dataset.target === navTargetId)
  );

  if (targetId === "snap101-centers") renderSnapSignupCenters();

  if (targetId === "my" && myStoreMap) {
    window.setTimeout(() => myStoreMap.invalidateSize(), 0);
  }

  if (targetId === ONBOARDING_PANEL_ID) {
    renderOnboardingStep();
  }

  if (targetId === SNAP101_DEFAULT_PANEL_ID) {
    syncSnapCalculatorHouseholdSize();
  }
}

function isOnboardingRequired() {
  return Boolean(onboardingForNewAccount && currentUser && currentUserInfo && !hasCompletedOnboarding(currentUserInfo, currentUser));
}

function onboardingCompletedStorageKey(user = currentUser) {
  return user?.id ? `${ONBOARDING_COMPLETED_STORAGE_PREFIX}${user.id}` : "";
}

function hasCompletedOnboarding(userInfo = currentUserInfo, user = currentUser) {
  if (!user) return false;
  if (userInfo?.onboarding_completed) return true;
  const storageKey = onboardingCompletedStorageKey(user);
  return Boolean(storageKey && window.localStorage.getItem(storageKey) === "true");
}

function rememberOnboardingCompleted(user = currentUser) {
  const storageKey = onboardingCompletedStorageKey(user);
  if (storageKey) {
    window.localStorage.setItem(storageKey, "true");
  }
}

async function repairOnboardingCompletionIfNeeded(user, userInfo) {
  if (!supabaseClient || !user || !userInfo || userInfo.onboarding_completed || !hasCompletedOnboarding(userInfo, user)) {
    return userInfo;
  }

  const { data, error } = await supabaseClient
    .from("user_info")
    .update({ onboarding_completed: true })
    .eq("id", user.id)
    .select()
    .single();

  if (error) {
    setSettingsStatus(error.message, "error");
    return { ...userInfo, onboarding_completed: true };
  }

  return data || { ...userInfo, onboarding_completed: true };
}

function renderNavigationForAuthState() {
  const isSignedIn = Boolean(currentUser);
  navButtons.forEach((button) => {
    const authView = button.dataset.authView;
    const appView = button.dataset.appView || "snapp";
    button.hidden =
      appView !== activeAppMode ||
      (authView === "signed-in" && !isSignedIn) ||
      (authView === "signed-out" && isSignedIn);
  });
  accountStatus.hidden = !isSignedIn;
}

function renderAppMode() {
  appSwitchButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.appMode === activeAppMode);
  });
  document.body.dataset.appMode = activeAppMode;
  renderNavigationForAuthState();
}

function renderAccountForAuthState() {
  const isSignedIn = Boolean(currentUser);
  const displayUsername = getDisplayUsername(currentUser);

  if (isSignedIn) {
    authTabs.hidden = true;
    signInForm.hidden = true;
    signUpForm.hidden = true;
  }
  if (signedInAccountPanel) {
    signedInAccountPanel.hidden = !isSignedIn;
  }
  if (signedInAccountName) {
    signedInAccountName.textContent = displayUsername;
  }
  accountUsername.textContent = displayUsername;
  signOutButton.hidden = !isSignedIn;
  if (accountPanelSignOutButton) {
    accountPanelSignOutButton.hidden = !isSignedIn;
  }
}

function renderHomeForAuthState() {
  const isSignedIn = Boolean(currentUser);
  document.querySelectorAll(".signed-in-home").forEach((element) => {
    element.hidden = !isSignedIn;
  });
  document.querySelectorAll(".signed-out-home").forEach((element) => {
    element.hidden = isSignedIn;
  });
  if (homeUsername) {
    homeUsername.textContent = getDisplayUsername(currentUser);
  }
  if (isSignedIn) {
    loadSaleIngredients();
  } else if (saleIngredientsGrid && saleIngredientsStatus) {
    saleIngredientsGrid.replaceChildren();
    saleIngredientsStatus.textContent = "";
  }
}

function setAuthStatus(message, type = "neutral") {
  authStatus.textContent = message;
  authStatus.dataset.type = type;
}

function clearDishProgress() {
  if (dishProgressTimer) {
    window.clearInterval(dishProgressTimer);
    dishProgressTimer = null;
  }
  delete dishStatus.dataset.loading;
}

function setDishStatus(message) {
  clearDishProgress();
  dishStatus.textContent = message;
}

function startDishProgress() {
  clearDishProgress();
  let messageIndex = 0;
  const spinner = document.createElement("span");
  spinner.className = "dish-status-spinner";
  spinner.setAttribute("aria-hidden", "true");
  const text = document.createElement("span");
  text.className = "dish-status-text";
  text.textContent = DISH_PROGRESS_MESSAGES[messageIndex];
  dishStatus.dataset.loading = "true";
  dishStatus.replaceChildren(spinner, text);
  dishProgressTimer = window.setInterval(() => {
    messageIndex = (messageIndex + 1) % DISH_PROGRESS_MESSAGES.length;
    text.textContent = DISH_PROGRESS_MESSAGES[messageIndex];
  }, 1200);
}

function clearDishSession() {
  dishResults.replaceChildren();
  dishEmptyState.hidden = false;
  dishInput.value = "";
  setDishStatus("");
  dishSource.hidden = true;
}

function clearUserScopedTransientState() {
  recipeChat.reset(false);
  selectedShoppingIngredientIds.clear();
  pantryHandledShoppingIngredientIds.clear();
  scheduledMeals.splice(0, scheduledMeals.length);
  favoriteRecipes = [];
  clearDishSession();
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
    household_size: 1,
    budget: null,
    dietary_preference: "balanced",
    dietary_preferences: [],
    dietary_restrictions: "",
    onboarding_completed: false,
    notifications_enabled: true,
    store_number: null,
    store_name: "",
    store_address: "",
    store_website: "",
    store_distance_miles: null,
  };
}

function normalizeDietaryPreference(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

function getDietaryPreferencesFromInfo(info) {
  if (Array.isArray(info?.dietary_preferences)) {
    return info.dietary_preferences.map(normalizeDietaryPreference).filter(Boolean);
  }

  if (typeof info?.dietary_restrictions === "string" && info.dietary_restrictions.trim()) {
    return info.dietary_restrictions
      .split(",")
      .map(normalizeDietaryPreference)
      .filter(Boolean);
  }

  return [];
}

function setDietaryPreferences(preferences, { syncTextarea = true } = {}) {
  const seen = new Set();
  selectedDietaryPreferences = preferences
    .map(normalizeDietaryPreference)
    .filter(Boolean)
    .filter((preference) => {
      const key = preference.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

  if (syncTextarea) {
    dietaryRestrictionsInput.value = selectedDietaryPreferences.join(", ");
  }

  renderDietaryPreferenceEditors();
}

function addDietaryPreference(preference, options = {}) {
  const normalizedPreference = normalizeDietaryPreference(preference);
  if (!normalizedPreference) return false;

  const exists = selectedDietaryPreferences.some(
    (item) => item.toLowerCase() === normalizedPreference.toLowerCase()
  );
  if (exists) return false;

  setDietaryPreferences([...selectedDietaryPreferences, normalizedPreference], options);
  return true;
}

function removeDietaryPreference(preference, options = {}) {
  const key = normalizeDietaryPreference(preference).toLowerCase();
  setDietaryPreferences(
    selectedDietaryPreferences.filter((item) => item.toLowerCase() !== key),
    options
  );
}

function renderPreferenceChips(container) {
  if (!container) return;
  container.replaceChildren(
    ...POPULAR_DIETARY_PREFERENCES.map((preference) => {
      const button = document.createElement("button");
      const isSelected = selectedDietaryPreferences.some(
        (item) => item.toLowerCase() === preference.toLowerCase()
      );
      button.type = "button";
      button.className = "preference-chip";
      button.textContent = preference;
      button.setAttribute("aria-pressed", String(isSelected));
      button.dataset.selected = String(isSelected);
      button.addEventListener("click", () => {
        if (isSelected) {
          removeDietaryPreference(preference);
        } else {
          addDietaryPreference(preference);
        }
        queueSettingsSave();
      });
      return button;
    })
  );
}

function renderSelectedPreferenceTags(container) {
  if (!container) return;
  container.replaceChildren(
    ...selectedDietaryPreferences.map((preference) => {
      const tag = document.createElement("span");
      tag.className = "selected-tag";
      const label = document.createElement("span");
      label.textContent = preference;
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.textContent = "×";
      removeButton.setAttribute("aria-label", t("copy.remove.arg0", {arg0: (preference)}));
      removeButton.addEventListener("click", () => {
        removeDietaryPreference(preference);
        queueSettingsSave();
      });
      tag.append(label, removeButton);
      return tag;
    })
  );
}

function renderDietaryPreferenceEditors() {
  renderPreferenceChips(onboardingPreferenceChips);
  renderSelectedPreferenceTags(onboardingSelectedPreferences);
  renderPreferenceChips(settingsPreferenceChips);
  renderSelectedPreferenceTags(settingsSelectedPreferences);
}

function syncSettingsFromUserInfo(user, userInfo) {
  const info = userInfo || (user ? getDefaultUserInfo(user) : null);
  profileNameInput.value = getDisplayUsername(user);
  householdSizeInput.value = info?.household_size || "1";
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
  setDietaryPreferences(getDietaryPreferencesFromInfo(info), {
    syncTextarea: !info?.dietary_restrictions,
  });
  if (info?.dietary_restrictions) {
    dietaryRestrictionsInput.value = info.dietary_restrictions;
  }
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

  if (!Number.isFinite(householdSize) || householdSize < 1 || householdSize > 20) {
    return "Household size must be between 1 and 20.";
  }

  if (zipCode && !/^\d{5}$/.test(zipCode)) {
    return "ZIP code must be 5 digits.";
  }

  return "";
}

async function saveSettingsToUser() {
  if (!supabaseClient || !currentUser) return false;

  const settingsError = getSettingsError();
  if (settingsError) {
    setSettingsStatus(settingsError, "error");
    return false;
  }

  const householdSize = Number.parseInt(householdSizeInput.value, 10);
  const zipCode = profileZipCodeInput.value.trim();
  setSettingsStatus(t("copy.saving.settings", {}));

  const { data, error } = await supabaseClient
    .from("user_info")
    .upsert({
      id: currentUser.id,
      username: getDisplayUsername(currentUser),
      household_size: householdSize,
      zip_code: zipCode,
      budget: budgetInput.value ? Number(budgetInput.value) : null,
      dietary_preference: dietSelect.value,
      dietary_preferences: selectedDietaryPreferences,
      dietary_restrictions: dietaryRestrictionsInput.value.trim(),
      onboarding_completed: hasCompletedOnboarding(currentUserInfo, currentUser),
      notifications_enabled: notificationsToggle.checked,
    })
    .select()
    .single();

  if (error) {
    setSettingsStatus(error.message, "error");
    return false;
  }

  currentUserInfo = data;
  if (currentUserInfo?.onboarding_completed) {
    rememberOnboardingCompleted(currentUser);
  }
  setSettingsStatus(t("copy.settings.saved", {}), "success");
  return true;
}

function queueSettingsSave() {
  if (!currentUser) return;
  window.clearTimeout(settingsSaveTimer);
  settingsSaveTimer = window.setTimeout(saveSettingsToUser, 450);
}

function setOnboardingStatus(message, type = "neutral") {
  if (!onboardingStatus) return;
  onboardingStatus.textContent = message;
  onboardingStatus.dataset.type = type;
}

function getClampedHouseholdSize(value) {
  const householdSize = Number.parseInt(value, 10);
  if (!Number.isFinite(householdSize)) return HOUSEHOLD_MIN;
  return Math.min(HOUSEHOLD_MAX, Math.max(HOUSEHOLD_MIN, householdSize));
}

function getSnapMaximumAllotment(householdSize) {
  const size = Math.max(1, Math.floor(Number(householdSize) || 1));
  if (size <= 8) {
    return SNAP_MAX_ALLOTMENTS[size];
  }
  if (size >= 18) return SNAP_LARGE_HOUSEHOLD_ALLOTMENT;
  return SNAP_MAX_ALLOTMENTS[8] + (size - 8) * SNAP_ADDITIONAL_MEMBER_ALLOTMENT;
}

function syncSnapCalculatorHouseholdSize() {
  if (!snapHouseholdSizeInput) return;

  const householdSize = getClampedHouseholdSize(
    currentUserInfo?.household_size || householdSizeInput?.value || onboardingHouseholdInput?.value || 1
  );
  snapHouseholdSizeInput.value = String(householdSize);
  updateSnapEstimate();
}

function updateSnapEstimate() {
  if (!snapHouseholdSizeInput || !snapIncomeInput || !snapEstimateOutput) return;

  const householdSize = getClampedHouseholdSize(snapHouseholdSizeInput.value);
  const monthlyIncome = Math.max(0, Number(snapIncomeInput.value || 0));
  const maximumAllotment = getSnapMaximumAllotment(householdSize);
  const expectedContribution = monthlyIncome * 0.3;
  const estimate = Math.max(0, Math.round(maximumAllotment - expectedContribution));
  snapHouseholdSizeInput.value = String(householdSize);
  snapEstimateOutput.textContent = estimate === 0
    ? t("snap.calculator.not_eligible")
    : t("copy.arg0.estimated.monthly.food.budget", {arg0: (currencyFormatter.format(estimate))});
  snapEstimateOutput.setAttribute(
    "aria-label",
    estimate === 0 ? t("snap.calculator.not_eligible") : t("copy.arg0.maximum.allotment.minus.arg1.estimated.contribution", {arg0: (currencyFormatter.format(maximumAllotment)), arg1: (currencyFormatter.format(expectedContribution))})
  );
  if (snapIncomeInput.value !== "") {
    budgetInput.value = String(estimate);
    renderBudget();
    queueSettingsSave();
  }
}

function updatePlateBalanceGame() {
  if (!plateBalanceSlider || !plateBalanceScore || !plateBalanceMessage || !plateProduceFill || !plateGrainFill) return;

  const producePercent = Number(plateBalanceSlider.value);
  const grainPercent = Math.max(24, 100 - producePercent - 25);
  plateBalanceScore.textContent = t("copy.arg0", {arg0: (producePercent)});
  plateProduceFill.style.width = `${producePercent}%`;
  plateGrainFill.style.width = `${grainPercent}%`;

  if (producePercent < 42) {
    plateBalanceMessage.textContent = t("copy.add.color.first.produce.makes.the.plate.feel.bigger", {});
  } else if (producePercent > 58) {
    plateBalanceMessage.textContent = t("copy.great.color.keep.space.for.protein.and.grains.too", {});
  } else {
    plateBalanceMessage.textContent = t("copy.balanced.about.half.produce.plus.protein.and.grains", {});
  }
}

function updateSnackGame() {
  if (!snackScore || !snackMeterFill || !snackMessage) return;

  const points = Array.from(snackOptionButtons).reduce((total, button) => {
    return button.classList.contains("active")
      ? total + Number(button.dataset.snackPoints || 0)
      : total;
  }, 0);
  const cappedPoints = Math.min(4, points);
  snackScore.textContent = t("copy.arg0.4", {arg0: (cappedPoints)});
  snackMeterFill.style.width = `${Math.max(18, cappedPoints * 25)}%`;

  if (points <= 1) {
    snackMessage.textContent = t("copy.quick.energy.but.it.may.not.last.long", {});
  } else if (points <= 3) {
    snackMessage.textContent = t("copy.better.pair.carbs.or.fruit.with.protein.or.fat", {});
  } else {
    snackMessage.textContent = t("copy.strong.snack.fiber.plus.protein.supports.fullness", {});
  }
}

function updateWaterGame() {
  if (!waterCount || !waterFill || !waterMessage) return;

  const cappedTaps = Math.min(6, Math.max(0, hydrationTaps));
  waterCount.textContent = t("copy.arg0.6", {arg0: (cappedTaps)});
  waterFill.style.height = `${Math.max(8, cappedTaps * 15)}%`;

  if (cappedTaps < 3) {
    waterMessage.textContent = t("copy.start.small.a.few.sips.still.count", {});
  } else if (cappedTaps < 6) {
    waterMessage.textContent = t("copy.steady.pace.add.water.between.meals", {});
  } else {
    waterMessage.textContent = t("copy.full.set.spread.drinks.across.the.day", {});
  }
}

function setOnboardingHouseholdSize(value) {
  const householdSize = getClampedHouseholdSize(value);
  onboardingHouseholdInput.value = String(householdSize);
  onboardingHouseholdOutput.textContent = String(householdSize);
  onboardingHouseholdMinusButton.disabled = householdSize <= HOUSEHOLD_MIN;
  onboardingHouseholdPlusButton.disabled = householdSize >= HOUSEHOLD_MAX;
}

function syncOnboardingFromUserInfo(userInfo) {
  const info = userInfo || {};
  onboardingZipCodeInput.value = info.zip_code || profileZipCodeInput.value || "";
  setOnboardingHouseholdSize(info.household_size || householdSizeInput.value || HOUSEHOLD_MIN);
  setDietaryPreferences(getDietaryPreferencesFromInfo(info), {
    syncTextarea: !info.dietary_restrictions,
  });
  onboardingStepIndex = 0;
  setOnboardingStatus("");
  renderOnboardingStep();
}

function renderOnboardingStep() {
  if (!onboardingForm) return;

  const steps = Array.from(onboardingForm.querySelectorAll(".onboarding-step"));
  steps.forEach((step, index) => {
    const isActive = index === onboardingStepIndex;
    step.hidden = !isActive;
    step.classList.toggle("active", isActive);
  });

  const progressValue = ((onboardingStepIndex + 1) / ONBOARDING_TOTAL_STEPS) * 100;
  onboardingProgressLabel.textContent = t("copy.arg0.of.arg1", {arg0: (onboardingStepIndex + 1), arg1: (ONBOARDING_TOTAL_STEPS)});
  onboardingProgressBar.style.width = `${progressValue}%`;
  document.querySelectorAll(".onboarding-step-label").forEach((label, index) => {
    label.classList.toggle("is-current", index === onboardingStepIndex);
    label.classList.toggle("is-complete", index < onboardingStepIndex);
    if (index === onboardingStepIndex) label.setAttribute("aria-current", "step");
    else label.removeAttribute("aria-current");
  });
  document.getElementById("onboarding-summary-zip").textContent = onboardingZipCodeInput.value.trim() || t("copy.not.set", {});
  const people = getClampedHouseholdSize(onboardingHouseholdInput.value);
  document.getElementById("onboarding-summary-household").textContent = t("copy.arg0.arg1", {arg0: (people), arg1: (people === 1 ? "person" : "people")});
  document.getElementById("onboarding-summary-preferences").textContent = selectedDietaryPreferences.length ? selectedDietaryPreferences.join(", ") : t("copy.open.to.everything", {});
  onboardingBackButton.hidden = onboardingStepIndex === 0;
  onboardingContinueButton.textContent =
    onboardingStepIndex === ONBOARDING_TOTAL_STEPS - 1 ? t("copy.start.finding.meals", {}) : t("copy.continue", {});
  setOnboardingHouseholdSize(onboardingHouseholdInput.value);

  const focusTarget = steps[onboardingStepIndex]?.querySelector(
    "input:not([hidden]), button:not([hidden])"
  );
  window.setTimeout(() => focusTarget?.focus(), 0);
}

function getOnboardingStepError() {
  if (onboardingStepIndex === 0 && !/^\d{5}$/.test(onboardingZipCodeInput.value.trim())) {
    return "Enter a valid 5-digit US ZIP code.";
  }

  if (onboardingStepIndex === 1) {
    const householdSize = getClampedHouseholdSize(onboardingHouseholdInput.value);
    if (householdSize < HOUSEHOLD_MIN || householdSize > HOUSEHOLD_MAX) {
      return "Household size must be between 1 and 20.";
    }
  }

  return "";
}

async function saveOnboardingToUser() {
  if (!supabaseClient || !currentUser) return false;

  const zipCode = onboardingZipCodeInput.value.trim();
  const householdSize = getClampedHouseholdSize(onboardingHouseholdInput.value);

  if (!/^\d{5}$/.test(zipCode)) {
    setOnboardingStatus(t("copy.enter.a.valid.5.digit.us.zip.code", {}), "error");
    onboardingStepIndex = 0;
    renderOnboardingStep();
    return false;
  }

  setOnboardingStatus(t("copy.saving.your.setup", {}));
  onboardingContinueButton.disabled = true;
  onboardingBackButton.disabled = true;

  const dietaryRestrictions = selectedDietaryPreferences.join(", ");
  const { data, error } = await supabaseClient
    .from("user_info")
    .upsert({
      id: currentUser.id,
      username: getDisplayUsername(currentUser),
      zip_code: zipCode,
      household_size: householdSize,
      dietary_preferences: selectedDietaryPreferences,
      dietary_restrictions: dietaryRestrictions,
      onboarding_completed: true,
      budget: budgetInput.value ? Number(budgetInput.value) : currentUserInfo?.budget ?? null,
      dietary_preference: currentUserInfo?.dietary_preference || dietSelect.value || "balanced",
      notifications_enabled: notificationsToggle.checked,
    })
    .select()
    .single();

  onboardingContinueButton.disabled = false;
  onboardingBackButton.disabled = false;

  if (error) {
    setOnboardingStatus(error.message, "error");
    return false;
  }

  currentUserInfo = data;
  rememberOnboardingCompleted(currentUser);
  onboardingForNewAccount = false;
  syncSettingsFromUserInfo(currentUser, currentUserInfo);
  setOnboardingStatus(t("copy.setup.saved", {}), "success");
  return true;
}

function setPantryStatus(message, type = "neutral") {
  pantryStatus.textContent = message;
  pantryStatus.dataset.type = type;
}

function populatePantrySpiceSuggestions() {
  if (!pantrySpiceSuggestions) return;
  pantrySpiceSuggestions.replaceChildren(
    ...TRADITIONAL_SPICES.map((spice) => {
      const option = document.createElement("option");
      option.value = spice;
      return option;
    })
  );
}

function updatePantryQuantityVisibility() {
  const spiceName = canonicalSpiceName(pantryNameInput.value);
  const isSpice = Boolean(spiceName);
  pantryForm.classList.toggle("spice-selected", isSpice);
  if (pantryQuantityLabel) pantryQuantityLabel.hidden = isSpice;
  pantryQuantityInput.required = !isSpice;
  pantryQuantityInput.disabled = isSpice;
  if (isSpice) {
    pantryQuantityInput.value = "";
    pantryNameInput.value = spiceName;
  }
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

function safeExternalUrl(value) {
  try {
    const url = new URL(String(value));
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
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

function getStoreNumberErrorMessage(error) {
  const message = error?.message || "";
  if (message.includes("user_info") && message.includes("schema cache")) {
    return "Store number setup is missing. Add the store_number columns to user_info in Supabase, then refresh.";
  }

  if (message.includes("store_number") && message.includes("schema cache")) {
    return "Store number setup is missing. Add the store_number columns to user_info in Supabase, then refresh.";
  }

  if (message.includes("permission denied")) {
    return "Store number permissions are missing for user_info in Supabase.";
  }

  return message || "Store number request failed.";
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
  myStoreStatus.textContent = t("copy.arg0.saved.to.my.stores", {arg0: (data.name)});
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
  myStoreStatus.textContent = t("copy.store.removed.from.my.stores", {});
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
    emptyItem.textContent = t("copy.your.pantry.starts.here.add.your.first.staple.above", {});
    pantryList.appendChild(emptyItem);
    return;
  }

  pantryItems.forEach((item) => {
    const listItem = document.createElement("li");
    const itemText = document.createElement("span");
    const removeButton = document.createElement("button");

    itemText.className = "pantry-item-details";
    const name = document.createElement("strong");
    name.textContent = isTraditionalSpice(item.name) ? canonicalSpiceName(item.name) : item.name;
    const quantity = document.createElement("small");
    quantity.textContent = isTraditionalSpice(item.name) ? t("copy.pantry.spice", {}) : item.quantity;
    itemText.append(name, quantity);
    removeButton.type = "button";
    removeButton.textContent = t("copy.remove", {});
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

  setPantryStatus(t("copy.adding.pantry.item", {}));
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
  setPantryStatus(t("copy.pantry.item.added", {}), "success");
  return true;
}

async function addPantryItems(items) {
  if (!supabaseClient || !currentUser || !items.length) return false;

  setPantryStatus(t("copy.adding.arg0.pantry.item.arg1", {arg0: (items.length), arg1: (items.length === 1 ? "" : "s")}));
  const rows = items.map((item) => ({
    user_id: currentUser.id,
    name: item.name,
    quantity: item.quantity,
  }));
  const { data, error } = await supabaseClient
    .from("user_pantry_items")
    .insert(rows)
    .select("id,name,quantity,created_at");

  if (error) {
    setPantryStatus(getPantryErrorMessage(error), "error");
    return false;
  }

  pantryItems = [...(data || []), ...pantryItems];
  renderPantryItems();
  setPantryStatus(t("copy.arg0.pantry.item.arg1.added", {arg0: (items.length), arg1: (items.length === 1 ? "" : "s")}), "success");
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
  setPantryStatus(t("copy.pantry.item.removed", {}), "success");
}

function showAuthMode(mode) {
  if (currentUser) {
    renderAccountForAuthState();
    return;
  }

  const isSignUp = mode === "sign-up";
  authTabs.hidden = false;
  signInForm.hidden = isSignUp;
  signUpForm.hidden = !isSignUp;
  if (signedInAccountPanel) {
    signedInAccountPanel.hidden = true;
  }
  showSignInButton.classList.toggle("active", !isSignUp);
  showSignUpButton.classList.toggle("active", isSignUp);
  setAuthStatus("");
}

async function renderAuthState(user) {
  const renderId = ++authRenderSequence;
  const wasSignedIn = Boolean(currentUser);
  const nextUserId = user?.id || null;
  if (activeAuthUserId !== nextUserId) {
    clearUserScopedTransientState();
  }
  activeAuthUserId = nextUserId;
  currentUser = user;
  currentUserInfo = null;
  document.body.classList.toggle("signed-in", Boolean(user));
  renderNavigationForAuthState();
  renderAccountForAuthState();
  syncSettingsFromUserInfo(user, null);
  syncSnapCalculatorHouseholdSize();
  renderHomeForAuthState();

  if (user) {
    currentUserInfo = await ensureUserInfo(user);
    currentUserInfo = await repairOnboardingCompletionIfNeeded(user, currentUserInfo);
    if (renderId !== authRenderSequence) return;
  }

  renderAccountForAuthState();
  syncSettingsFromUserInfo(user, currentUserInfo);
  syncSnapCalculatorHouseholdSize();
  if (user && currentUserInfo && isOnboardingRequired() && (authLandingPending || !wasSignedIn)) {
    syncOnboardingFromUserInfo(currentUserInfo);
  }
  renderHomeForAuthState();
  await Promise.allSettled([
    loadSavedStores(),
    loadPantryItems(),
    loadFavoriteRecipes(),
    loadScheduledMeals(),
  ]);
  if (renderId !== authRenderSequence) return;

  if (user) {
    renderAccountForAuthState();
    setAuthStatus(t("copy.signed.in.as.arg0", {arg0: (getDisplayUsername(user))}), "success");
    if (authLandingPending || !wasSignedIn) {
      authLandingPending = false;
      showPanel(isOnboardingRequired() ? ONBOARDING_PANEL_ID : SIGNED_IN_DEFAULT_PANEL_ID);
    } else if (activeAppMode === "snapp" && isOnboardingRequired()) {
      showPanel(ONBOARDING_PANEL_ID);
    } else if (activeAppMode === "snapp" && document.querySelector(".panel.visible")?.id === ONBOARDING_PANEL_ID) {
      showPanel(SIGNED_IN_DEFAULT_PANEL_ID);
    }
    return;
  }

  if (wasSignedIn) {
    onboardingForNewAccount = false;
    authLandingPending = false;
    pendingNewAccountUsername = "";
    showAuthMode("sign-in");
    setAuthStatus(t("copy.signed.out.05d2a7", {}), "success");
  }
  if (activeAppMode === "snapp") {
    showPanel(SIGNED_OUT_DEFAULT_PANEL_ID);
  }
}

async function handleSignOut() {
  if (!supabaseClient) return;

  const signOutButtons = [signOutButton, accountPanelSignOutButton].filter(Boolean);
  signOutButtons.forEach((button) => {
    button.disabled = true;
  });
  const { error } = await supabaseClient.auth.signOut();
  if (error) {
    setAuthStatus(error.message, "error");
  }
  signOutButtons.forEach((button) => {
    button.disabled = false;
  });
}

// Display source prices at their full value.
function displayPrice(value) {
  return Number(value || 0);
}

function getScheduledMealTotal() {
  const basket = window.SNAPP_ACTIVE_STORE?.result;
  return basket?.complete ? basket.basket_total : null;
}

function getHouseholdSize() {
  const householdSize = Number.parseInt(householdSizeInput.value, 10);
  return Number.isFinite(householdSize) && householdSize > 0 ? householdSize : 1;
}

function renderBudget() {
  const editor = document.getElementById("budget-monthly-input");
  if (editor && document.activeElement !== editor) editor.value = budgetInput.value;
  const hasBudget = budgetInput.value !== "";
  const budget = hasBudget ? Number(budgetInput.value || 0) : 0;
  const scheduledTotal = getScheduledMealTotal();
  const remaining = budget - scheduledTotal;

  if (budgetEmptyMessage) {
    budgetEmptyMessage.hidden = hasBudget;
  }
  currentBudget.textContent = currencyFormatter.format(budget);
  remainingBudget.textContent = scheduledTotal == null ? "Awaiting store pricing" : currencyFormatter.format(remaining);
  remainingBudget.classList.toggle("over-budget", remaining < 0);
  budgetMealCount.textContent = scheduledMeals.length;
  scheduledMealCost.textContent = scheduledTotal == null ? "See Shopping for partial or pending prices" : currencyFormatter.format(scheduledTotal);
}

function getPortionMacroValue(meal, macroKey) {
  const perPersonNutrition = meal?.nutrition_per_person || {};
  const perPersonValue = Number(perPersonNutrition[macroKey]);
  if (perPersonNutrition[macroKey] !== null && perPersonNutrition[macroKey] !== undefined && Number.isFinite(perPersonValue) && perPersonValue >= 0) {
    return perPersonValue;
  }

  const totalNutrition = meal?.nutrition_total || {};
  const totalValue = Number(totalNutrition[macroKey]);
  if (!Number.isFinite(totalValue) || totalValue <= 0) {
    return 0;
  }

  return totalValue / getServingCount(meal);
}

function getScheduledMacroTotals() {
  return scheduledMeals.reduce(
    (totals, meal) => {
      totals.protein += getPortionMacroValue(meal, "protein_g");
      totals.carbs += getPortionMacroValue(meal, "carbohydrates_g");
      totals.fat += getPortionMacroValue(meal, "fat_g");
      return totals;
    },
    { protein: 0, carbs: 0, fat: 0 }
  );
}

function setMacroBar(totalElement, goalElement, fillElement, total, goal) {
  if (!totalElement || !goalElement || !fillElement) return;
  const percent = goal > 0 ? Math.min(100, (total / goal) * 100) : 0;
  totalElement.textContent = t("copy.arg0.g", {arg0: (gramFormatter.format(total))});
  goalElement.textContent = t("copy.arg0.g", {arg0: (gramFormatter.format(goal))});
  fillElement.style.width = `${percent}%`;
}

function renderMacroTracker() {
  const totals = getScheduledMacroTotals();
  const coverage = document.getElementById("weekly-nutrition-status");
  if (coverage) {
    const missing = scheduledMeals.filter((meal) => ["protein_g", "carbohydrates_g", "fat_g"].every((key) => !getPortionMacroValue(meal, key))).length;
    const partial = scheduledMeals.filter((meal) => meal.nutrition_status === "partial").length;
    coverage.textContent = missing ? t("copy.arg0.meal.arg1.no.nutrition.data.yet.totals.include", {arg0: (missing), arg1: (missing === 1 ? " has" : "s have")})
      : partial ? t("nutrition.weekly.partial", { count: partial })
      : scheduledMeals.length ? t("nutrition.weekly.ready") : t("copy.add.meals.to.build.your.weekly.totals.these.sample", {});
    if (scheduledMeals.some((meal) => meal.nutrition_servings_source === "household")) {
      coverage.textContent += " " + t("nutrition.weekly.household");
    }
  }
  if (macroTrackerMealCount) {
    const mealCount = scheduledMeals.length;
    macroTrackerMealCount.textContent = t("copy.arg0.meal.arg1", {arg0: (mealCount), arg1: (mealCount === 1 ? "" : "s")});
  }
  setMacroBar(macroProteinTotal, macroProteinGoal, macroProteinFill, totals.protein, WEEKLY_MACRO_GOALS.protein);
  setMacroBar(macroCarbsTotal, macroCarbsGoal, macroCarbsFill, totals.carbs, WEEKLY_MACRO_GOALS.carbs);
  setMacroBar(macroFatTotal, macroFatGoal, macroFatFill, totals.fat, WEEKLY_MACRO_GOALS.fat);
}

function scheduledMealStorageKey() {
  return currentUser ? `snapp:scheduled-meals:${currentUser.id}` : null;
}

function loadScheduledMealsFromStorage() {
  const storageKey = scheduledMealStorageKey();
  if (!storageKey) {
    scheduledMeals.splice(0, scheduledMeals.length);
    return;
  }

  try {
    const storedMeals = JSON.parse(
      window.localStorage.getItem(storageKey) || "[]"
    );
    scheduledMeals.splice(
      0,
      scheduledMeals.length,
      ...storedMeals.map(normalizeScheduledMeal)
    );
  } catch {
    scheduledMeals.splice(0, scheduledMeals.length);
  }
}

function saveScheduledMealsToStorage() {
  const storageKey = scheduledMealStorageKey();
  if (!storageKey) return;

  window.localStorage.setItem(
    storageKey,
    JSON.stringify(scheduledMeals)
  );
}

function getFavoriteRecipeKey(dish) {
  return String(
    dish?.recipe_id ||
      dish?.recipe?.id ||
      dish?.recipe?.source ||
      dish?.recipe?.youtube ||
      dish?.name ||
      ""
  ).trim();
}

function normalizeFavoriteRecipe(record) {
  const recipeData = record.recipe_data || record.dish || record;
  return {
    id: record.id || null,
    recipe_key: record.recipe_key || getFavoriteRecipeKey(recipeData),
    recipe_name: record.recipe_name || recipeData.name || "Favorite recipe",
    recipe_data: recipeData,
    created_at: record.created_at || null,
  };
}

function isFavoriteRecipe(dish) {
  const recipeKey = getFavoriteRecipeKey(dish);
  return Boolean(recipeKey && favoriteRecipes.some((favorite) => favorite.recipe_key === recipeKey));
}

function setFavoriteRecipesStatus(message, type = "neutral") {
  if (!favoriteRecipesStatus) return;
  favoriteRecipesStatus.textContent = message;
  if (type === "neutral") {
    delete favoriteRecipesStatus.dataset.type;
  } else {
    favoriteRecipesStatus.dataset.type = type;
  }
}

function favoriteRecipeRecordForSave(dish) {
  const recipeKey = getFavoriteRecipeKey(dish);
  return {
    user_id: currentUser.id,
    recipe_key: recipeKey,
    recipe_name: dish.name || "Favorite recipe",
    recipe_data: dish,
  };
}

function getFavoriteRecipeErrorMessage(error) {
  const message = error?.message || "";
  if (message.includes("user_favorite_recipes") && message.includes("schema cache")) {
    return "Favorite recipe setup is missing. Run the user_favorite_recipes SQL setup in Supabase, then refresh.";
  }
  if (message.includes("permission denied")) {
    return "Favorite recipe permissions are missing. Run the user_favorite_recipes policy SQL in Supabase, then refresh.";
  }
  return message || "Favorite recipe request failed.";
}

async function loadFavoriteRecipes() {
  if (!supabaseClient || !currentUser) {
    favoriteRecipes = [];
    renderFavoriteRecipesPanel();
    return;
  }

  const { data, error } = await supabaseClient
    .from("user_favorite_recipes")
    .select("id,recipe_key,recipe_name,recipe_data,created_at")
    .eq("user_id", currentUser.id)
    .order("created_at", { ascending: false });

  if (error) {
    favoriteRecipes = [];
    renderFavoriteRecipesPanel();
    if (favoriteRecipesStatus) {
      favoriteRecipesStatus.textContent = getFavoriteRecipeErrorMessage(error);
      favoriteRecipesStatus.dataset.type = "error";
    }
    return;
  }

  favoriteRecipes = (data || []).map(normalizeFavoriteRecipe);
  renderFavoriteRecipesPanel();
}

async function addFavoriteRecipe(dish) {
  const recipeKey = getFavoriteRecipeKey(dish);
  if (!supabaseClient || !currentUser || !recipeKey) return false;

  const { data, error } = await supabaseClient
    .from("user_favorite_recipes")
    .upsert(favoriteRecipeRecordForSave(dish), { onConflict: "user_id,recipe_key" })
    .select("id,recipe_key,recipe_name,recipe_data,created_at")
    .single();

  if (error) {
    setFavoriteRecipesStatus(getFavoriteRecipeErrorMessage(error), "error");
    return false;
  }

  const favorite = normalizeFavoriteRecipe(data);
  favoriteRecipes = [
    favorite,
    ...favoriteRecipes.filter((item) => item.recipe_key !== favorite.recipe_key),
  ];
  renderFavoriteRecipesPanel();
  updateFavoriteRecipeButtons(favorite.recipe_key);
  return true;
}

async function removeFavoriteRecipe(dish) {
  const recipeKey = getFavoriteRecipeKey(dish);
  if (!supabaseClient || !currentUser || !recipeKey) return false;

  const { error } = await supabaseClient
    .from("user_favorite_recipes")
    .delete()
    .eq("user_id", currentUser.id)
    .eq("recipe_key", recipeKey);

  if (error) {
    setFavoriteRecipesStatus(getFavoriteRecipeErrorMessage(error), "error");
    return false;
  }

  favoriteRecipes = favoriteRecipes.filter((item) => item.recipe_key !== recipeKey);
  renderFavoriteRecipesPanel();
  updateFavoriteRecipeButtons(recipeKey);
  return true;
}

async function toggleFavoriteRecipe(dish, button) {
  const recipeKey = getFavoriteRecipeKey(dish);
  if (!recipeKey) return;
  if (!currentUser || !supabaseClient) {
    setFavoriteRecipesStatus(t("copy.sign.in.and.configure.supabase.to.save.favorite.recipes", {}), "error");
    return;
  }
  const wasFavorite = isFavoriteRecipe(dish);
  button.disabled = true;
  if (!wasFavorite) {
    favoriteRecipes = [
      normalizeFavoriteRecipe({
        recipe_key: recipeKey,
        recipe_name: dish.name || "Favorite recipe",
        recipe_data: dish,
      }),
      ...favoriteRecipes.filter((favorite) => favorite.recipe_key !== recipeKey),
    ];
  } else {
    favoriteRecipes = favoriteRecipes.filter((favorite) => favorite.recipe_key !== recipeKey);
  }
  renderFavoriteRecipesPanel();
  updateFavoriteRecipeButtons(recipeKey);
  const didSave = wasFavorite
    ? await removeFavoriteRecipe(dish)
    : await addFavoriteRecipe(dish);
  button.disabled = false;
  if (!didSave) {
    if (wasFavorite) {
      favoriteRecipes = [
        normalizeFavoriteRecipe({
          recipe_key: recipeKey,
          recipe_name: dish.name || "Favorite recipe",
          recipe_data: dish,
        }),
        ...favoriteRecipes.filter((favorite) => favorite.recipe_key !== recipeKey),
      ];
    } else {
      favoriteRecipes = favoriteRecipes.filter((favorite) => favorite.recipe_key !== recipeKey);
    }
    renderFavoriteRecipesPanel();
    updateFavoriteRecipeButtons(recipeKey);
    return;
  }
  renderSchedule();
}

function renderFavoriteButton(button, dish) {
  const isFavorite = isFavoriteRecipe(dish);
  button.type = "button";
  button.className = "favorite-recipe-button";
  button.textContent = isFavorite ? "♥" : "♡";
  button.title = isFavorite ? "Remove from favorite recipes" : "Add to favorite recipes";
  button.setAttribute("aria-label", button.title);
  button.dataset.recipeKey = getFavoriteRecipeKey(dish);
  button.classList.toggle("active", isFavorite);
  button.disabled = !currentUser || !supabaseClient;
}

function updateFavoriteRecipeButtons(recipeKey) {
  if (!recipeKey) return;
  document.querySelectorAll(".favorite-recipe-button").forEach((button) => {
    if (button.dataset.recipeKey !== recipeKey) return;
    const isFavorite = favoriteRecipes.some((favorite) => favorite.recipe_key === recipeKey);
    button.textContent = isFavorite ? "♥" : "♡";
    button.title = isFavorite ? "Remove from favorite recipes" : "Add to favorite recipes";
    button.setAttribute("aria-label", button.title);
    button.classList.toggle("active", isFavorite);
    button.disabled = !currentUser || !supabaseClient;
  });
}

function createFavoriteRecipeButton(dish) {
  const button = document.createElement("button");
  renderFavoriteButton(button, dish);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleFavoriteRecipe(dish, button);
  });
  return button;
}

function renderFavoriteRecipesPanel() {
  if (!favoriteRecipesList || !favoriteRecipesStatus) return;

  favoriteRecipesList.replaceChildren();

  if (!currentUser) {
    setFavoriteRecipesStatus("");
    return;
  }

  if (!favoriteRecipes.length) {
    setFavoriteRecipesStatus(t("copy.no.favorite.recipes.yet", {}));
    return;
  }

  setFavoriteRecipesStatus(t("copy.arg0.favorite.recipe.arg1", {arg0: (favoriteRecipes.length), arg1: (favoriteRecipes.length === 1 ? "" : "s")}));
  favoriteRecipes.forEach((favorite) => {
    const dish = favorite.recipe_data;
    const item = document.createElement("article");
    const title = document.createElement("h4");
    const meta = document.createElement("p");
    const actions = document.createElement("div");
    const queueButton = document.createElement("button");
    const removeButton = document.createElement("button");
    const isQueued = scheduledMeals.some(
      (meal) => (meal.recipe_id || meal.name) === (dish.recipe_id || dish.name)
    );

    item.className = "favorite-recipe-item";
    title.textContent = favorite.recipe_name || dish.name || t("copy.favorite.recipe", {});
    meta.textContent = [
      formatServings(dish),
      "See active store prices in Shopping",
    ].filter(Boolean).join(" | ");
    actions.className = "favorite-recipe-actions";

    queueButton.type = "button";
    queueButton.textContent = isQueued ? t("copy.in.queue", {}) : t("copy.add.to.queue", {});
    queueButton.disabled = isQueued;
    queueButton.addEventListener("click", () => addMealToSchedule(dish));

    removeButton.type = "button";
    removeButton.textContent = t("copy.remove", {});
    removeButton.addEventListener("click", () => removeFavoriteRecipe(dish));

    actions.append(queueButton, removeButton);
    item.append(title, meta, actions);
    favoriteRecipesList.appendChild(item);
  });
}

function normalizeScheduledMeal(record) {
  const mealData = record.meal_data || record.dish || record;
  const scheduledDay = record.scheduled_day || mealData.scheduled_day || "";
  const scheduledSlot = mealData.scheduled_slot || mealData.meal_slot || "";
  return {
    ...mealData,
    schedule_id: String(record.id || mealData.schedule_id || mealData.recipe_id || mealData.name),
    scheduled_day: SCHEDULE_DAYS.includes(scheduledDay) ? scheduledDay : null,
    scheduled_slot: MEAL_SLOTS.includes(scheduledSlot)
      ? scheduledSlot
      : SCHEDULE_DAYS.includes(scheduledDay)
        ? "Dinner"
        : null,
  };
}

function getIngredientName(ingredient) {
  if (typeof ingredient === "string") return ingredient;
  if (!ingredient) return "Ingredient";

  return (
    ingredient.product_name ||
    ingredient.recipe_ingredient ||
    ingredient.name ||
    ingredient.ingredient ||
    ingredient.display ||
    ingredient.measure ||
    "Ingredient"
  );
}

function getIngredientQuantity(ingredient) {
  if (typeof ingredient === "string" || !ingredient) return "1 item";

  return (
    ingredient.purchase_quantity_display ||
    formatPurchaseQuantity(ingredient) ||
    ingredient.package_size ||
    ingredient.quantity ||
    ingredient.amount ||
    ingredient.measure ||
    ingredient.display ||
    "1 item"
  );
}

function formatCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return "";
  return Number.isInteger(number) ? String(number) : String(Number(number.toFixed(2)));
}

function formatPurchaseQuantity(ingredient) {
  if (!ingredient || typeof ingredient !== "object") return "";
  const count = formatCount(ingredient.packages_purchased);
  const packageSize = String(ingredient.package_size || "").trim();
  if (!count) return packageSize;
  const normalizedPackage = packageSize.toLowerCase();
  if (["lb", "lbs", "pound", "pounds", "per lb", "per pound", "1 lb", "1 pound"].includes(normalizedPackage)) {
    return `${count} lb`;
  }
  if (["oz", "ounce", "ounces", "per oz", "per ounce", "1 oz", "1 ounce"].includes(normalizedPackage)) {
    return `${count} oz`;
  }
  if (["each", "ea", "ct", "count", "1 count"].includes(normalizedPackage)) {
    return Number(count) === 1 ? "1 item" : `${count} items`;
  }
  if (packageSize) return `${count} x ${packageSize}`;
  return Number(count) === 1 ? "1 package" : `${count} packages`;
}

function shoppingCategoryFromText(value) {
  const text = String(value || "").toLowerCase();
  if (!text) return "";

  const categoryMatchers = [
    ["Produce", /\b(apple|apples|avocado|banana|berries|berry|broccoli|cabbage|carrot|celery|cilantro|corn|cucumber|fruit|garlic|greens?|herbs?|kale|lettuce|lime|lemon|mushrooms?|onions?|orange|parsley|pepper|peppers|potato|potatoes|produce|salad|spinach|tomato|tomatoes|vegetable|zucchini)\b/],
    ["Bakery & Bread", /\b(bagels?|bakery|bread|brioche|buns?|croissants?|muffins?|pita|rolls?|sourdough|tortillas?)\b/],
    ["Deli & Prepared Foods", /\b(deli|prepared|rotisserie|salad bar|sandwich|sliced turkey|sliced ham)\b/],
    ["Meat", /\b(beef|bacon|brisket|chuck|ground beef|ham|lamb|meat|pork|sausage|steak|veal)\b/],
    ["Poultry", /\b(chicken|duck|poultry|turkey)\b/],
    ["Seafood", /\b(clams?|cod|crab|fish|salmon|scallops?|seafood|shrimp|tuna)\b/],
    ["Dairy & Eggs", /\b(butter|cheese|cream|dairy|eggs?|feta|half and half|milk|mozzarella|parmesan|sour cream|yogurt)\b/],
    ["Refrigerated", /\b(refrigerated|fresh pasta|hummus|tofu|tempeh)\b/],
    ["Frozen", /\b(frozen|ice cream|sorbet)\b/],
    ["Canned & Jarred Goods", /\b(canned|jarred|broth|stock|tomato paste|tomato sauce|diced tomatoes|crushed tomatoes|olives?|pickles?)\b/],
    ["Pasta, Rice & Grains", /\b(pasta|spaghetti|noodles?|rice|grains?|quinoa|couscous|barley|oats?)\b/],
    ["Beans & Legumes", /\b(beans?|black beans|chickpeas?|garbanzo|kidney beans|lentils?|legumes?|peas?)\b/],
    ["Baking", /\b(baking|baking powder|baking soda|brown sugar|cake|cocoa|cornstarch|flour|sugar|vanilla|yeast)\b/],
    ["Spices & Seasonings", /\b(spices?|seasonings?|salt|pepper|paprika|cumin|cinnamon|oregano|basil|thyme|rosemary|sage|turmeric|chili powder|cayenne)\b/],
    ["Oils, Vinegars & Condiments", /\b(oil|olive oil|vinegar|mustard|ketchup|mayonnaise|mayo|relish|condiment)\b/],
    ["Sauces & Dressings", /\b(sauce|salsa|dressing|marinade|pesto|teriyaki|soy sauce|hot sauce|bbq)\b/],
    ["Breakfast & Cereal", /\b(cereal|granola|pancake|waffle|breakfast)\b/],
    ["Snacks", /\b(chips?|crackers?|cookies?|popcorn|pretzels?|snacks?)\b/],
    ["Beverages", /\b(beverage|coffee|drink|juice|seltzer|soda|tea|water)\b/],
    ["International Foods", /\b(curry|miso|tahini|tortilla|sriracha|ramen|naan|coconut milk)\b/],
    ["Household", /\b(foil|paper towels?|soap|detergent|trash bags?|household)\b/],
  ];

  return categoryMatchers.find(([_category, pattern]) => pattern.test(text))?.[0] || "";
}

function getShoppingCategory(ingredient) {
  const categoryText = typeof ingredient === "object" && ingredient
    ? [
        ingredient.category,
        ingredient.product_category,
        ingredient.store_category,
        ingredient.department,
        ingredient.aisle,
      ].filter(Boolean).join(" ")
    : "";
  const directCategory = SHOPPING_CATEGORY_ORDER.find(
    (category) => category.toLowerCase() === String(categoryText).trim().toLowerCase()
  );
  if (directCategory) return directCategory;

  const text = typeof ingredient === "object" && ingredient
    ? [
        categoryText,
        ingredient.product_name,
        ingredient.recipe_ingredient,
        ingredient.name,
        ingredient.ingredient,
        ingredient.display,
        ingredient.measure,
      ].filter(Boolean).join(" ")
    : ingredient;

  return shoppingCategoryFromText(text) || "Other";
}

function getSortedShoppingCategories(items) {
  const categories = new Map(SHOPPING_CATEGORY_ORDER.map((category) => [category, []]));
  items.forEach((item) => {
    const category = SHOPPING_CATEGORY_ORDER.includes(item.category) ? item.category : "Other";
    categories.get(category).push(item);
  });
  return SHOPPING_CATEGORY_ORDER
    .map((category) => [category, categories.get(category)])
    .filter(([_category, categoryItems]) => categoryItems.length);
}

function getShoppingIngredients() {
  if (typeof window !== "undefined" && window.SNAPP_ACTIVE_STORE) return window.SNAPP_ACTIVE_STORE.items();
  return scheduledMeals.flatMap((meal) => {
    const ingredients =
      meal.ingredients_to_buy?.length
        ? meal.ingredients_to_buy
        : meal.ingredients?.length
          ? meal.ingredients
          : meal.recipe?.ingredients || [];

    return ingredients.filter((ingredient) => !(
      ingredient &&
      typeof ingredient === "object" &&
      (ingredient.unavailable || ingredient.availability_status === "unavailable")
    )).map((ingredient, index) => ({
      id: `${meal.schedule_id}:${index}`,
      dishName: meal.name || "Scheduled dish",
      name: getIngredientName(ingredient),
      quantity: getIngredientQuantity(ingredient),
      productName: ingredient?.product_name,
      requestedIngredient: ingredient?.recipe_ingredient,
      requestedMeasure: ingredient?.recipe_measure,
      deal: ingredient?.deal,
      category: getShoppingCategory(ingredient),
      unavailable:
        Boolean(
          ingredient &&
            typeof ingredient === "object" &&
            (ingredient.unavailable ||
              ingredient.availability_status === "unavailable")
        ),
    })).filter((item) => !pantryHandledShoppingIngredientIds.has(item.id));
  });
}

function updateShoppingAddButton(items = getShoppingIngredients()) {
  const selectedCount = selectedShoppingIngredientIds.size;
  shoppingAddPantryButton.textContent = selectedCount
    ? t("copy.add.selected.to.pantry", {})
    : t("copy.add.all.to.pantry", {});
  shoppingAddPantryButton.disabled = !items.length;
}

function appendShoppingDeal(container, item) {
  if (!item.productName) return;
  const selected = document.createElement("small");
  selected.textContent = t("shopping.selectedProduct", { product: item.productName });
  container.append(selected);
  if (item.requestedMeasure) {
    const requested = document.createElement("small");
    requested.textContent = t("shopping.requestedQuantity", { quantity: item.requestedMeasure });
    container.append(requested);
  }
  const deal = item.deal;
  if (!deal || typeof deal !== "object") return;
  const labelKey = deal.match_type === "SUBSTITUTE" ? "shopping.substitute"
    : deal.quality_tier === "A" ? "shopping.excellentMatch"
    : deal.quality_tier === "B" ? "shopping.strongMatch"
    : deal.quality_tier === "C" ? "shopping.goodMatch" : null;
  if (labelKey) {
    const label = document.createElement("small");
    label.textContent = t(labelKey, {});
    container.append(label);
  }
  const reliable = deal.deal_confidence === "high" && Number.isFinite(deal.effective_cost) && deal.effective_cost >= 0;
  if (reliable) {
    const cost = document.createElement("small");
    const amount = new Intl.NumberFormat(getLanguage(), { style: "currency", currency: "USD" }).format(deal.effective_cost);
    cost.textContent = t("shopping.totalForRecipe", { amount });
    container.append(cost);
  }
  if (Number.isInteger(deal.packages_needed) && deal.packages_needed > 1) {
    const packages = document.createElement("small");
    packages.textContent = t("shopping.packagesNeeded", { count: deal.packages_needed });
    container.append(packages);
  }
  const compared = reliable && deal.comparable_candidate_count >= 2;
  if (deal.best_deal === true && compared) {
    const badge = document.createElement("small");
    badge.className = "shopping-deal-badge";
    badge.textContent = t("shopping.bestDeal", {});
    container.append(badge);
  }
  if (compared && Number.isFinite(deal.savings_vs_closest_match) && deal.savings_vs_closest_match >= .50) {
    const savings = document.createElement("small");
    savings.className = "shopping-deal-savings";
    savings.textContent = t("shopping.saveAmount", { amount: new Intl.NumberFormat(getLanguage(), { style: "currency", currency: "USD" }).format(deal.savings_vs_closest_match) });
    container.append(savings);
  }
  const explanation = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = t("shopping.whyThisOne", {});
  const reason = document.createElement("small");
  reason.textContent = t(deal.best_deal === true && compared ? "shopping.closestQualityLowestCost" : "shopping.bestAvailableSafeMatch", {});
  explanation.className = "shopping-deal-explanation";
  explanation.append(summary, reason);
  container.append(explanation);
}

function renderShoppingList(priceRefresh = false) {
  if (!priceRefresh && document.dispatchEvent && typeof CustomEvent === "function") document.dispatchEvent(new CustomEvent("snapp:shopping-changed"));
  const items = getShoppingIngredients();
  const validIds = new Set(items.map((item) => item.id));
  selectedShoppingIngredientIds.forEach((id) => {
    if (!validIds.has(id)) selectedShoppingIngredientIds.delete(id);
  });

  shoppingList.replaceChildren();

  if (!currentUser) {
    shoppingStatus.textContent = "";
    updateShoppingAddButton(items);
    return;
  }

  if (!items.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "shopping-empty";
    emptyItem.textContent = t("copy.your.next.shop.starts.with.a.meal.add.recipes", {});
    shoppingList.appendChild(emptyItem);
    shoppingStatus.textContent = "";
    updateShoppingAddButton(items);
    return;
  }

  getSortedShoppingCategories(items).forEach(([category, categoryItems]) => {
    const section = document.createElement("li");
    const heading = document.createElement("h3");
    const categoryList = document.createElement("ul");

    section.className = "shopping-category-section";
    heading.textContent = category;
    categoryList.className = "shopping-category-list";

    categoryItems.forEach((item) => {
      const listItem = document.createElement("li");
      const checkbox = document.createElement("input");
      const details = document.createElement("span");
      const addButton = document.createElement("button");

      listItem.className = "shopping-list-item";
      listItem.classList.toggle("selected", selectedShoppingIngredientIds.has(item.id));

      checkbox.type = "checkbox";
      checkbox.checked = selectedShoppingIngredientIds.has(item.id);
      checkbox.setAttribute("aria-label", t("copy.select.arg0", {arg0: (item.name)}));
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedShoppingIngredientIds.add(item.id);
        } else {
          selectedShoppingIngredientIds.delete(item.id);
        }
        listItem.classList.toggle("selected", checkbox.checked);
        updateShoppingAddButton(items);
      });

      details.className = "shopping-item-details";
      const name = document.createElement("strong");
      name.textContent = item.requestedIngredient || item.name;
      const note = document.createElement("small");
      note.textContent = t("copy.get.arg0.arg1.arg2", {arg0: (item.quantity), arg1: (item.dishName), arg2: (item.unavailable ? " · Unavailable" : "")});
      details.append(name, note);
      if (item.store_id) {
        const packageText = [item.productName, item.package_size].filter(Boolean).join(" · ");
        details.append(document.createTextNode(packageText));
        const cost = document.createElement("small");
        cost.className = "shopping-package-cost";
        cost.textContent = item.checkout_cost == null ? "Package cost unverified" : `${item.packages_needed == null ? "" : item.packages_needed + " package(s) × "}${item.package_price == null ? "" : currencyFormatter.format(item.package_price)} · ${currencyFormatter.format(item.checkout_cost)} checkout`;
        details.append(cost);
      } else appendShoppingDeal(details, item);

      addButton.type = "button";
      addButton.textContent = t("copy.add.to.pantry", {});
      addButton.addEventListener("click", async () => {
        addButton.disabled = true;
        shoppingStatus.textContent = t("copy.adding.arg0.to.pantry", {arg0: (item.name)});
        const wasAdded = await addPantryItem(item.name, item.quantity);
        if (wasAdded) {
          pantryHandledShoppingIngredientIds.add(item.id);
          selectedShoppingIngredientIds.delete(item.id);
          shoppingStatus.textContent = t("copy.arg0.added.to.pantry", {arg0: (item.name)});
          renderShoppingList();
          return;
        }
        shoppingStatus.textContent = t("copy.could.not.add.ingredient.to.pantry", {});
        addButton.disabled = false;
      });

      listItem.append(checkbox, details, addButton);
      categoryList.appendChild(listItem);
    });

    section.append(heading, categoryList);
    shoppingList.appendChild(section);
  });

  updateShoppingAddButton(items);
}

async function refreshScheduledNutrition() {
  const userId = currentUser?.id;
  for (const meal of [...scheduledMeals]) {
    if (meal.nutrition_source === "USDA FoodData Central" || !meal.recipe?.ingredients?.length) continue;
    try {
      const nutrition = await recipeChat.nutritionFor(meal);
      if (currentUser?.id !== userId || !scheduledMeals.includes(meal)) continue;
      Object.assign(meal, nutrition);
      saveScheduledMealsToStorage();
      renderMacroTracker();
    } catch { meal.nutrition_status = "unavailable"; renderMacroTracker(); }
  }
}

async function loadScheduledMeals() {
  scheduledMeals.splice(0, scheduledMeals.length);

  if (!currentUser) {
    renderSchedule();
    return;
  }

  if (!supabaseClient) {
    loadScheduledMealsFromStorage();
    renderSchedule();
    void refreshScheduledNutrition();
    return;
  }

  const { data, error } = await supabaseClient
    .from("user_scheduled_meals")
    .select("id,scheduled_day,meal_data,created_at")
    .eq("user_id", currentUser.id)
    .order("created_at", { ascending: true });

  if (error) {
    loadScheduledMealsFromStorage();
    renderSchedule();
    void refreshScheduledNutrition();
    return;
  }

  scheduledMeals.splice(
    0,
    scheduledMeals.length,
    ...(data || []).map(normalizeScheduledMeal)
  );
  saveScheduledMealsToStorage();
  renderSchedule();
  void refreshScheduledNutrition();
}

function renderSchedule() {
  scheduleCalendar.replaceChildren();
  scheduleRecipeList.replaceChildren();

  renderMacroTracker();
  renderScheduleRecipeTray();
  renderFavoriteRecipesPanel();

  SCHEDULE_DAYS.forEach((day) => {
    const dayColumn = document.createElement("section");
    const title = document.createElement("h3");
    const slots = document.createElement("div");

    dayColumn.className = "schedule-day";
    title.textContent = day;
    slots.className = "schedule-day-slots";

    MEAL_SLOTS.forEach((slot) => {
      const slotElement = createScheduleSlot(day, slot);
      slots.appendChild(slotElement);
    });

    dayColumn.append(title, slots);
    scheduleCalendar.appendChild(dayColumn);
  });

  renderBudget();
  renderShoppingList();
}

function renderScheduleRecipeTray() {
  const unplacedMeals = scheduledMeals.filter(
    (meal) => !meal.scheduled_day || !meal.scheduled_slot
  );

  if (!unplacedMeals.length) {
    const empty = document.createElement("p");
    empty.className = "schedule-empty";
    empty.textContent = t("copy.added.recipes.will.appear.here", {});
    scheduleRecipeList.appendChild(empty);
    return;
  }

  unplacedMeals.forEach((meal) => {
    scheduleRecipeList.appendChild(createScheduleMealCard(meal));
  });
}

function createScheduleSlot(day, slot) {
  const slotElement = document.createElement("div");
  const label = document.createElement("span");
  const assignedMeal = scheduledMeals.find(
    (meal) => meal.scheduled_day === day && meal.scheduled_slot === slot
  );

  slotElement.className = "schedule-slot";
  slotElement.dataset.day = day;
  slotElement.dataset.slot = slot;
  label.className = "schedule-slot-label";
  label.textContent = slot;
  slotElement.appendChild(label);

  if (assignedMeal) {
    slotElement.appendChild(createScheduleMealCard(assignedMeal));
  } else {
    const empty = document.createElement("p");
    empty.className = "schedule-empty";
    empty.textContent = t("copy.drop.recipe", {});
    slotElement.appendChild(empty);
  }

  slotElement.addEventListener("dragover", handleScheduleDragOver);
  slotElement.addEventListener("dragleave", handleScheduleDragLeave);
  slotElement.addEventListener("drop", handleScheduleSlotDrop);
  return slotElement;
}

function createScheduleMealCard(meal) {
  const card = document.createElement("div");
  const openButton = document.createElement("button");
  const actions = document.createElement("div");
  const favoriteButton = createFavoriteRecipeButton(meal);
  const removeButton = document.createElement("button");
  const price = document.createElement("span");

  card.className = "schedule-meal";
  card.draggable = true;
  card.dataset.scheduleId = meal.schedule_id;

  openButton.type = "button";
  openButton.className = "schedule-meal-open";
  openButton.textContent = meal.name;
  price.textContent = t("stores.viewBasket");
  openButton.appendChild(price);
  openButton.addEventListener("click", () => openDishModal(meal));

  removeButton.type = "button";
  removeButton.className = "schedule-meal-remove";
  removeButton.textContent = t("copy.remove", {});
  removeButton.addEventListener("click", (event) => {
    event.stopPropagation();
    removeScheduledMeal(meal.schedule_id);
  });

  actions.className = "schedule-meal-actions";
  actions.append(favoriteButton, removeButton);
  card.append(openButton, actions);
  card.addEventListener("dragstart", (event) => {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", meal.schedule_id);
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => {
    card.classList.remove("dragging");
  });
  return card;
}

async function removeScheduledMeal(scheduleId) {
  const normalizedId = String(scheduleId || "");
  const index = scheduledMeals.findIndex((meal) => String(meal.schedule_id) === normalizedId);
  if (index === -1) return;

  scheduledMeals.splice(index, 1);
  selectedShoppingIngredientIds.forEach((id) => {
    if (id.startsWith(`${normalizedId}:`)) selectedShoppingIngredientIds.delete(id);
  });
  pantryHandledShoppingIngredientIds.forEach((id) => {
    if (id.startsWith(`${normalizedId}:`)) pantryHandledShoppingIngredientIds.delete(id);
  });
  saveScheduledMealsToStorage();
  renderSchedule();

  if (supabaseClient && currentUser && normalizedId) {
    const { error } = await supabaseClient
      .from("user_scheduled_meals")
      .delete()
      .eq("user_id", currentUser.id)
      .eq("id", normalizedId);
    if (error) {
      console.warn("Scheduled meal removal sync failed:", error.message);
    }
  }
}

function handleScheduleDragOver(event) {
  event.preventDefault();
  event.currentTarget.classList.add("drag-over");
}

function handleScheduleDragLeave(event) {
  event.currentTarget.classList.remove("drag-over");
}

function handleScheduleSlotDrop(event) {
  event.preventDefault();
  event.currentTarget.classList.remove("drag-over");
  const scheduleId = event.dataTransfer.getData("text/plain");
  updateScheduledMealPlacement(
    scheduleId,
    event.currentTarget.dataset.day,
    event.currentTarget.dataset.slot
  );
}

function handleScheduleTrayDrop(event) {
  event.preventDefault();
  scheduleRecipeTray.classList.remove("drag-over");
  const scheduleId = event.dataTransfer.getData("text/plain");
  updateScheduledMealPlacement(scheduleId, null, null);
}

scheduleRecipeTray.addEventListener("dragover", handleScheduleDragOver);
scheduleRecipeTray.addEventListener("dragleave", handleScheduleDragLeave);
scheduleRecipeTray.addEventListener("drop", handleScheduleTrayDrop);

scheduleFavoriteRecipesButton?.addEventListener("click", () => {
  const isHidden = scheduleFavoriteRecipesPanel.hidden;
  scheduleFavoriteRecipesPanel.hidden = !isHidden;
  scheduleFavoriteRecipesButton.classList.toggle("active", isHidden);
  if (isHidden) renderFavoriteRecipesPanel();
});

async function updateScheduledMealPlacement(scheduleId, day, slot) {
  const meal = scheduledMeals.find((item) => String(item.schedule_id) === scheduleId);
  if (!meal) return;

  const replacedMeal = scheduledMeals.find(
    (item) =>
      String(item.schedule_id) !== scheduleId &&
      item.scheduled_day === day &&
      item.scheduled_slot === slot
  );

  meal.scheduled_day = day;
  meal.scheduled_slot = slot;

  if (replacedMeal && day && slot) {
    replacedMeal.scheduled_day = null;
    replacedMeal.scheduled_slot = null;
  }

  saveScheduledMealsToStorage();
  renderSchedule();

  if (supabaseClient && currentUser && scheduleId) {
    const payload = { ...meal };
    const { error } = await supabaseClient
      .from("user_scheduled_meals")
      .update({
        scheduled_day: day || "Unscheduled",
        meal_data: payload,
      })
      .eq("id", scheduleId)
      .eq("user_id", currentUser.id);
    if (error) {
      console.warn("Schedule placement sync failed:", error.message);
    }

    if (replacedMeal?.schedule_id) {
      await supabaseClient
        .from("user_scheduled_meals")
        .update({
          scheduled_day: "Unscheduled",
          meal_data: { ...replacedMeal },
        })
        .eq("id", replacedMeal.schedule_id)
        .eq("user_id", currentUser.id);
    }
  }
}

function textIncludesTraditionalSpice(value) {
  const normalized = normalizeSpiceText(value);
  if (!normalized) return false;
  return TRADITIONAL_SPICES.some((spice) => {
    const spiceText = normalizeSpiceText(spice);
    return normalized === spiceText || normalized.includes(spiceText);
  }) || [...SPICE_ALIASES.keys()].some((alias) => {
    const aliasText = normalizeSpiceText(alias);
    return normalized === aliasText || normalized.includes(aliasText);
  });
}

function normalizePantryText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\b(chopped|minced|sliced|diced|fresh|dried|ground|large|medium|small|cloves?|cups?|cup|tbsp|tablespoons?|tsp|teaspoons?|oz|ounce|ounces|lb|lbs|pound|pounds|grams?|g|kg|ml|l)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function pantryItemMatchesIngredient(pantryItem, ingredient) {
  const pantryName = normalizePantryText(pantryItem.name);
  const ingredientText = normalizePantryText(
    [
      ingredient?.recipe_ingredient,
      ingredient?.recipe_measure,
      ingredient?.display,
      ingredient?.measure,
      ingredient?.name,
    ].filter(Boolean).join(" ")
  );
  return Boolean(
    pantryName &&
      ingredientText &&
      (ingredientText.includes(pantryName) || pantryName.includes(ingredientText))
  );
}

function parseSimpleQuantity(value) {
  const text = String(value || "").toLowerCase();
  const match = text.match(/(\d+(?:\.\d+)?)\s*(cups?|tbsp|tablespoons?|tsp|teaspoons?|oz|ounces?|lb|lbs|pounds?|g|grams?|kg|ml|l|count|ct|items?)?\b/);
  if (!match) return null;
  const unit = (match[2] || "count")
    .replace(/^tablespoons?$/, "tbsp")
    .replace(/^teaspoons?$/, "tsp")
    .replace(/^ounces?$/, "oz")
    .replace(/^pounds?$|^lbs?$/, "lb")
    .replace(/^grams?$/, "g")
    .replace(/^items?$/, "count");
  return { amount: Number(match[1]), unit };
}

function recipeIngredientQuantity(ingredient) {
  return parseSimpleQuantity(
    ingredient?.recipe_measure ||
      ingredient?.display ||
      ingredient?.measure ||
      ingredient?.quantity ||
      ingredient?.name ||
      ""
  );
}

async function persistPantryItemsAfterConsumption(consumedItems) {
  if (!consumedItems.length) return;
  if (!supabaseClient || !currentUser) {
    pantryItems = pantryItems.filter(
      (item) => !consumedItems.some((consumed) => consumed.id === item.id && consumed.remove)
    ).map((item) => {
      const consumed = consumedItems.find((entry) => entry.id === item.id);
      return consumed?.quantity ? { ...item, quantity: consumed.quantity } : item;
    });
    renderPantryItems();
    return;
  }

  await Promise.all(consumedItems.map(async (item) => {
    if (item.remove) {
      return supabaseClient
        .from("user_pantry_items")
        .delete()
        .eq("user_id", currentUser.id)
        .eq("id", item.id);
    }
    return supabaseClient
      .from("user_pantry_items")
      .update({ quantity: item.quantity })
      .eq("user_id", currentUser.id)
      .eq("id", item.id);
  }));
  await loadPantryItems();
}

async function consumePantryForScheduledDish(dish) {
  const recipeIngredients = dish.recipe?.ingredients || dish.ingredients || [];
  if (!recipeIngredients.length || !pantryItems.length) return;
  const consumed = [];
  const consumedIds = new Set();

  recipeIngredients.forEach((ingredient) => {
    const ingredientText = [
      ingredient?.recipe_ingredient,
      ingredient?.recipe_measure,
      ingredient?.display,
      ingredient?.measure,
      ingredient?.name,
    ].filter(Boolean).join(" ");
    if (textIncludesTraditionalSpice(ingredientText)) return;

    const pantryItem = pantryItems.find(
      (item) => !consumedIds.has(item.id) && !textIncludesTraditionalSpice(item.name) && pantryItemMatchesIngredient(item, ingredient)
    );
    if (!pantryItem) return;

    consumedIds.add(pantryItem.id);
    const pantryQuantity = parseSimpleQuantity(pantryItem.quantity);
    const requiredQuantity = recipeIngredientQuantity(ingredient);
    if (
      pantryQuantity &&
      requiredQuantity &&
      pantryQuantity.unit === requiredQuantity.unit &&
      pantryQuantity.amount > requiredQuantity.amount
    ) {
      consumed.push({
        id: pantryItem.id,
        quantity: `${Number((pantryQuantity.amount - requiredQuantity.amount).toFixed(2))} ${pantryQuantity.unit}`,
      });
    } else {
      consumed.push({ id: pantryItem.id, remove: true });
    }
  });

  await persistPantryItemsAfterConsumption(consumed);
}

async function addMealToSchedule(dish) {
  const identity = dish.recipe_id || dish.name;
  const isAlreadyScheduled = scheduledMeals.some(
    (meal) => (meal.recipe_id || meal.name) === identity
  );
  if (isAlreadyScheduled) {
    showPanel("schedule");
    return;
  }
  if (dish.nutrition_source !== "USDA FoodData Central" && dish.recipe?.ingredients?.length) {
    try { dish = { ...dish, ...await recipeChat.nutritionFor(dish) }; }
    catch { dish = { ...dish, nutrition_status: "unavailable" }; }
  }

  const scheduledMeal = {
    ...dish,
    ...(dish.recipe?.servings ? {target_servings: dish.target_servings || getHouseholdSize()} : {}),
    schedule_id: String(dish.recipe_id || dish.name),
    scheduled_day: null,
    scheduled_slot: null,
  };

  if (supabaseClient && currentUser) {
    const { data, error } = await supabaseClient
      .from("user_scheduled_meals")
      .insert({
        user_id: currentUser.id,
        meal_name: dish.name,
        scheduled_day: "Unscheduled",
        meal_data: scheduledMeal,
      })
      .select("id,scheduled_day,meal_data,created_at")
      .single();

    if (!error && data) {
      scheduledMeals.push(normalizeScheduledMeal(data));
      saveScheduledMealsToStorage();
      // Active-store baskets allocate pantry quantities together on the server.
      if (!window.SNAPP_ACTIVE_STORE) await consumePantryForScheduledDish(dish);
      renderSchedule();
      showPanel("schedule");
      return;
    }
  }

  scheduledMeals.push(scheduledMeal);
  saveScheduledMealsToStorage();
  // Active-store baskets allocate pantry quantities together on the server.
  if (!window.SNAPP_ACTIVE_STORE) await consumePantryForScheduledDish(dish);
  renderSchedule();
  showPanel("schedule");
}

function openDishModal(dish) {
  const recipe = dish.localized_recipe || dish.recipe || {};
  dishModalTitle.textContent = recipe.name || recipe.title || dish.name || t("copy.recipe", {});
  dishModalContent.replaceChildren();

  const summary = document.createElement("p");
  summary.className = "dish-modal-summary";
  summary.textContent = [
    formatServings(dish),
    "See active store prices in Shopping",
  ].filter(Boolean).join(" | ");
  dishModalContent.appendChild(summary);

  appendModalSection("Recipe ingredients", recipe.ingredients || [], (ingredient) =>
    ingredient.display || ingredient.measure || ingredient.name
  );
  appendModalSection("Ingredients to buy", (dish.ingredients_to_buy || dish.ingredients || []).filter(
    (ingredient) => !(ingredient.unavailable || ingredient.availability_status === "unavailable")
  ), (ingredient) => {
    return cleanIngredientRequirementText(ingredient.recipe_measure || ingredient.required_quantity_display) || ingredient.name || ingredient.recipe_ingredient;

  });

  const instructionsHeading = document.createElement("h4");
  const instructions = document.createElement("p");
  instructionsHeading.textContent = t("copy.instructions", {});
  instructions.textContent =
    recipe.instructions || dish.method || t("copy.open.the.source.recipe.for.cooking.instructions", {});
  dishModalContent.append(instructionsHeading, instructions);

  if (recipe.source || recipe.youtube) {
    const links = document.createElement("p");
    links.className = "dish-recipe-links";
    if (recipe.source) {
      const sourceLink = document.createElement("a");
      sourceLink.href = safeExternalUrl(recipe.source);
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
      sourceLink.textContent = t("copy.recipe.source", {});
      links.appendChild(sourceLink);
    }
    if (recipe.youtube) {
      if (links.childNodes.length) links.append(" | ");
      const youtubeLink = document.createElement("a");
      youtubeLink.href = safeExternalUrl(recipe.youtube);
      youtubeLink.target = "_blank";
      youtubeLink.rel = "noopener noreferrer";
      youtubeLink.textContent = t("copy.video", {});
      links.appendChild(youtubeLink);
    }
    dishModalContent.appendChild(links);
  }

  if (typeof dishModal.showModal === "function") {
    dishModal.showModal();
  } else {
    dishModal.setAttribute("open", "");
  }
}

function cleanIngredientRequirementText(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .replace(/\b(cups?|tablespoons?|teaspoons?|ounces?|pounds?|lbs?|jars?|cans?|packages?|containers?)\s+\1\b/gi, "$1")
    .trim();
}

function recipeItemList(items, formatter, ordered = false) {
  const list = document.createElement(ordered ? "ol" : "ul");
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = formatter(value);
    if (!ordered && value?.is_on_sale === true) {
      const badge = document.createElement("span");
      badge.className = "recipe-sale-badge";
      badge.textContent = t("copy.on.sale", {});
      item.appendChild(badge);
    }
    list.appendChild(item);
  });
  return list;
}

function appendModalSection(title, items, formatter) {
  const heading = document.createElement("h4");
  heading.textContent = title;
  const list = recipeItemList(items.length ? items : [null],
    (value) => value === null ? "None available." : formatter(value));
  list.className = "dish-modal-list";
  dishModalContent.append(heading, list);
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

async function fetchStores(zipCode, options = {}) {
  let lastError = API_BASE_URL
    ? "Unable to reach the grocery store backend."
    : "Backend URL is not configured.";

  for (const endpoint of getApiEndpoints("/grocery-stores")) {
    try {
      const params = new URLSearchParams({ zip: zipCode });
      params.set("snap_only", options.snapOnly === true ? "1" : "0");
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

async function fetchTraderJoesStore(zipCode) {
  let lastError = API_BASE_URL
    ? "Unable to reach the Trader Joe's store backend."
    : "Backend URL is not configured.";

  for (const endpoint of getApiEndpoints("/trader-joes-store")) {
    try {
      const params = new URLSearchParams({ zip: zipCode });
      const response = await fetch(`${endpoint}?${params.toString()}`);
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        lastError = data.error || `Trader Joe's store lookup failed (${response.status}).`;
        continue;
      }
      return data;
    } catch (error) {
      lastError = error.message || "Network error while finding Trader Joe's store.";
    }
  }

  throw new Error(lastError);
}

async function saveTraderJoesStoreNumber(storeLookup) {
  if (!supabaseClient || !currentUser || !storeLookup?.store) return false;

  const store = storeLookup.store;
  const { data, error } = await supabaseClient
    .from("user_info")
    .update({
      store_number: store.store_number,
      store_name: store.name,
      store_address: store.address,
      store_website: store.website,
      store_distance_miles:
        store.distance_miles != null ? Number(store.distance_miles) : null,
    })
    .eq("id", currentUser.id)
    .select()
    .single();

  if (error) {
    myStoreStatus.textContent = getStoreNumberErrorMessage(error);
    return false;
  }

  currentUserInfo = data;
  return true;
}

function getStoreId(store) {
  return store.id || getStoreKey(store);
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

function createStoreIdentity(store) {
  const identity = document.createElement("span");
  identity.className = "store-identity";
  const tile = document.createElement("span");
  tile.className = "store-brand-tile";
  tile.setAttribute("aria-hidden", "true");
  const chains = [
    [/whole foods/i, "WF", "whole-foods"],
    [/trader joe/i, "TJ", "trader-joes"],
    [/morton williams/i, "MW", "morton-williams"],
    [/\baldi\b/i, "A", "aldi"],
    [/key food/i, "KF", "key-food"],
    [/c[ -]?town/i, "CT", "ctown"],
    [/stop\s*(?:&|and)\s*shop/i, "S&S", "stop-shop"],
  ];
  const chain = chains.find(([pattern]) => pattern.test(store.name || ""));
  tile.textContent = chain ? chain[1] : (store.name || t("copy.store", {})).split(/\s+/).slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  if (chain) tile.dataset.chain = chain[2];
  const details = document.createElement("span");
  details.className = "store-identity-details";
  const name = document.createElement("strong");
  name.className = "store-identity-name";
  name.textContent = store.name || t("copy.grocery.store", {});
  const distance = document.createElement("span");
  distance.className = "store-distance";
  const miles = store.distance_miles == null || store.distance_miles === "" ? NaN : Number(store.distance_miles);
  distance.textContent = Number.isFinite(miles) && miles >= 0
    ? t("copy.arg0.mi.away", {arg0: (new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(miles))})
    : t("copy.distance.unavailable", {});
  details.append(name, distance);
  identity.append(tile, details);
  return identity;
}

function renderSelectedMyStores() {
  if (window.SNAPP_RENDER_SELECTED_STORES) { window.SNAPP_RENDER_SELECTED_STORES(); return; }
  selectedStoreList.replaceChildren();

  if (!savedMyStores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = translateText(t("copy.no.stores.selected", {}));
    selectedStoreList.appendChild(emptyItem);
    return;
  }

  savedMyStores.forEach((store) => {
    const item = document.createElement("li");
    const itemText = createStoreIdentity(store);
    const removeButton = document.createElement("button");

    removeButton.type = "button";
    removeButton.textContent = "×";
    removeButton.setAttribute("aria-label", t("copy.remove.arg0", {arg0: (store.name)}));
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

  document.getElementById("my-store-start").hidden = true;
  myStoreMapElement.hidden = false;
  const map = ensureMyStoreMap(data.center);
  if (!window.L || !map) {
    myStoreStatus.textContent = translateText(t("copy.map.library.could.not.load.store.list.is.still", {}));
  }

  if (!stores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = translateText(t("copy.no.stores.found.for.this.search", {}));
    myStoreResults.appendChild(emptyItem);
  }

  stores.forEach((store) => {
    const item = document.createElement("li");
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    const text = createStoreIdentity(store);

    checkbox.type = "checkbox";
    checkbox.value = store.id;
    checkbox.setAttribute("aria-label", t("copy.select.arg0", {arg0: (store.name)}));
    label.append(text, checkbox);
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
      popupAddress.textContent = text.querySelector(t("copy.store.distance", {})).textContent;
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

async function fetchDishes(mealPrompt, options = {}) {
  let lastError = API_BASE_URL
    ? "Unable to reach the dishes backend."
    : "Backend URL is not configured.";
  const householdSize = getHouseholdSize();
  const dietaryRestrictions =
    currentUserInfo?.dietary_restrictions ?? dietaryRestrictionsInput.value.trim();
  const maxBudget =
    currentUserInfo?.budget != null
      ? Number(currentUserInfo.budget)
      : budgetInput.value
        ? Number(budgetInput.value)
        : null;
  const dietaryPreference = currentUserInfo?.dietary_preference || dietSelect.value;

  for (const endpoint of getApiEndpoints("/dishes")) {
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meal_prompt: mealPrompt,
          locale: getLanguage(),
          sale_ingredient_id: options.saleIngredientId || null,
          household_size: householdSize,
          dietary_restrictions: dietaryRestrictions,
          max_budget: maxBudget,
          servings: householdSize,
          dietary_preference: dietaryPreference,
          include_ingredients: "",
          avoid_ingredients: dietaryRestrictions,
          max_cook_time: null,
          pantry_items: pantryItems.map((item) => ({
            name: item.name,
            quantity: item.quantity,
          })),
          store_number: currentUserInfo?.store_number || DEFAULT_TRADER_JOES_STORE_NUMBER,
        }),
      });
      const responseText = await response.text();
      let data = {};
      try {
        data = responseText ? JSON.parse(responseText) : {};
      } catch {
        data = {};
      }
      if (!response.ok) {
        lastError =
          data.details ||
          data.error ||
          `Dish request failed (${response.status}${response.statusText ? ` ${response.statusText}` : ""}).`;
        continue;
      }
      return data;
    } catch (error) {
      lastError =
        error instanceof TypeError && /fetch/i.test(error.message || "")
          ? "Unable to reach the dishes API. The backend may still be starting or temporarily unavailable."
          : error.message || "Network error while finding dishes.";
    }
  }

  throw new Error(lastError);
}

async function fetchSaleIngredients() {
  let lastError = API_BASE_URL
    ? "Unable to reach the sale ingredient backend."
    : "Backend URL is not configured.";
  for (const endpoint of getApiEndpoints("/sale-ingredients")) {
    try {
      const response = await fetch(endpoint);
      const responseText = await response.text();
      let data = {};
      try {
        data = responseText ? JSON.parse(responseText) : {};
      } catch {
        data = {};
      }
      if (!response.ok) {
        lastError = data.error || `Sale request failed (${response.status}).`;
        continue;
      }
      return data;
    } catch (error) {
      lastError = error.message || "Network error while loading sale ingredients.";
    }
  }
  throw new Error(lastError);
}

function formatSaleMoney(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return "";
  return currencyFormatter.format(number);
}

function renderSaleIngredients(items) {
  saleIngredientsGrid.replaceChildren();
  if (!items.length) {
    saleIngredientsStatus.textContent = t("copy.no.recipe.ready.sale.ingredients.found", {});
    return;
  }
  saleIngredientsStatus.textContent = t("copy.arg0.shown.from.today.s.ranked.pool", {arg0: (items.length)});
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "sale-ingredient-card";

    const category = document.createElement("span");
    category.className = "sale-category";
    category.textContent = item.category || t("copy.grocery", {});

    const title = document.createElement("h3");
    title.textContent = item.ingredient_name || item.product_name;

    const product = document.createElement("p");
    product.className = "sale-product-name";
    product.textContent = item.product_name;

    const priceRow = document.createElement("div");
    priceRow.className = "sale-price-row";
    if (item.original_price && item.discount_percent) {
      const original = document.createElement("span");
      original.className = "sale-original-price";
      original.textContent = formatSaleMoney(item.original_price);
      priceRow.appendChild(original);
    }
    const sale = document.createElement("strong");
    sale.className = "sale-price";
    sale.textContent = formatSaleMoney(item.sale_price) || item.price_display || t("copy.sale.price.available", {});
    priceRow.appendChild(sale);

    const meta = document.createElement("p");
    meta.className = "sale-meta";
    const details = [];
    if (item.discount_percent) details.push(`${Math.round(item.discount_percent * 100)}% off`);
    if (item.absolute_savings) details.push(`Save ${formatSaleMoney(item.absolute_savings)}`);
    if (item.recipe_count) details.push(`${item.recipe_count} matching recipes`);
    meta.textContent = details.join(" · ");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "sale-recipe-button";
    button.textContent = t("copy.generate.recipes.with.this.ingredient", {});
    button.addEventListener("click", () => generateRecipesForSaleIngredient(item));

    card.append(category, title, product, priceRow, meta, button);
    saleIngredientsGrid.appendChild(card);
  });
}

async function loadSaleIngredients() {
  if (!saleIngredientsGrid || !saleIngredientsStatus) return;
  saleIngredientsStatus.textContent = t("copy.loading.sales", {});
  try {
    const data = await fetchSaleIngredients();
    renderSaleIngredients(data.sale_ingredients || []);
  } catch (error) {
    saleIngredientsGrid.replaceChildren();
    saleIngredientsStatus.textContent = error.message;
  }
}

async function generateRecipesForSaleIngredient(item) {
  const ingredientId = item.ingredient_id;
  if (!ingredientId) return;
  const prompt = item.ingredient_name || ingredientId;
  const params = new URLSearchParams(window.location.search);
  params.set("panel", "recipe-chat");
  params.set("sale_ingredient", ingredientId);
  window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
  showPanel("recipe-chat");
  recipeChat.searchIngredient(prompt);
}

async function handleInitialUrlState() {
  const params = new URLSearchParams(window.location.search);
  const panel = params.get("panel");
  const appMode = params.get("app");
  const saleIngredient = params.get("sale_ingredient");
  if (!panel && appMode === "snap101") {
    showPanel(SNAP101_DEFAULT_PANEL_ID);
  }
  if (panel) {
    showPanel(panel);
  }
  if (saleIngredient) {
    await generateRecipesForSaleIngredient({
      ingredient_id: saleIngredient,
      ingredient_name: saleIngredient.replace(/\b\w/g, (letter) => letter.toUpperCase()),
      product_name: saleIngredient,
    });
  }
}

function renderStores(stores) {
  if (!storeResults) return;
  storeResults.replaceChildren();
  if (!stores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = translateText(t("copy.no.stores.found.for.this.search", {}));
    storeResults.appendChild(emptyItem);
    return;
  }

  stores.forEach((store) => {
    const item = document.createElement("li");
    const name = document.createElement("h3");
    const address = document.createElement("p");
    name.textContent = store.name;
    address.textContent = store.address;
    item.append(name, address);
    if (store.accepts_snap) {
      const snapNote = document.createElement("p");
      snapNote.textContent = t("copy.arg0.arg1.c2a27c", {arg0: (translateText("SNAP accepted")), arg1: (store.snap_source ? ` (${store.snap_source})` : "")});
      item.appendChild(snapNote);
    } else {
      const snapNote = document.createElement("p");
      snapNote.textContent = translateText(t("copy.snap.acceptance.not.verified", {}));
      item.appendChild(snapNote);
    }

    const links = document.createElement("div");
    links.className = "store-links";
    if (store.latitude != null && store.longitude != null) {
      const mapLink = document.createElement("a");
      mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(store.latitude)}&mlon=${encodeURIComponent(store.longitude)}#map=17/${encodeURIComponent(store.latitude)}/${encodeURIComponent(store.longitude)}`;
      mapLink.target = "_blank";
      mapLink.rel = "noopener noreferrer";
      mapLink.textContent = translateText(t("copy.view.on.map", {}));
      links.appendChild(mapLink);
    }

    if (store.website) {
      const websiteLink = document.createElement("a");
      websiteLink.href = safeExternalUrl(store.website);
      websiteLink.target = "_blank";
      websiteLink.rel = "noopener noreferrer";
      websiteLink.textContent = translateText(t("copy.visit.website", {}));
      links.appendChild(websiteLink);
    }

    item.appendChild(links);
    storeResults.appendChild(item);
  });
}

function renderDishes(data) {
  dishEmptyState.hidden = true;
  const botMessage = document.createElement("li");
  const intro = document.createElement("p");
  const cards = document.createElement("div");
  botMessage.className = "dish-message bot";
  intro.textContent = data.dishes.length
    ? data.sale_ingredient_id
      ? t("copy.here.are.three.recipe.matches.using.arg0", {arg0: (data.meal_prompt)})
      : t("copy.here.are.three.recipe.matches.i.found", {})
    : t("copy.i.could.not.find.recipe.matches.for.that.request", {});
  cards.className = "dish-card-grid";
  botMessage.append(intro, cards);

  data.dishes.slice(0, 3).forEach((dish) => {
    cards.appendChild(createDishCard(dish));
  });

  if (data.used_relaxed_matches) {
    const relaxed = document.createElement("p");
    relaxed.className = "dish-missing";
    relaxed.textContent = t("copy.no.exact.match.was.found.so.snapp.is.showing", {});
    botMessage.appendChild(relaxed);
  }

  if (data.missing_ingredients?.length) {
    const missing = document.createElement("p");
    missing.className = "dish-missing";
    missing.textContent = t("copy.no.usda.match.found.for.arg0", {arg0: (data.missing_ingredients.join(", "))});
    botMessage.appendChild(missing);
  }

  dishResults.appendChild(botMessage);
  dishResults.scrollTop = dishResults.scrollHeight;
  requestAnimationFrame(() => {
    botMessage.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function appendDishMessage(type, text) {
  const item = document.createElement("li");
  item.className = `dish-message ${type}`;
  item.textContent = text;
  dishResults.appendChild(item);
  dishResults.scrollTop = dishResults.scrollHeight;
  dishEmptyState.hidden = true;
  return item;
}

function createDishCard(dish) {
    const nutritionTotal = dish.nutrition_total || {};
    const card = document.createElement("article");
    const header = document.createElement("div");
    const title = document.createElement("h3");
    const favoriteButton = createFavoriteRecipeButton(dish);
    const price = document.createElement("p");
    const metadata = document.createElement("p");
    const totalNutrition = document.createElement("div");
    const restrictionWarnings = getRestrictionWarnings(dish);
    const scheduleButton = document.createElement("button");

    card.className = "dish-card";
    card.tabIndex = 0;
    card.addEventListener("click", () => openDishModal(dish));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDishModal(dish);
      }
    });
    header.className = "dish-card-header";
    title.textContent = dish.localized_recipe?.name || dish.name;
    header.append(title, favoriteButton);
    price.className = "dish-price";
    price.textContent = t("stores.viewBasket");
    metadata.className = "dish-metadata";
    metadata.textContent = [
      formatServings(dish),
      dish.cook_time_minutes ? t("copy.arg0.min", {arg0: (dish.cook_time_minutes)}) : "",
      ...(dish.dietary_tags || []),
    ].filter(Boolean).join(" | ");
    totalNutrition.className = "dish-nutrition";
    totalNutrition.textContent = [
      t("copy.arg0.protein", {arg0: (nutritionTotal.protein_g || "x g")}),
      t("copy.arg0.carbs", {arg0: (nutritionTotal.carbohydrates_g || "x g")}),
      t("copy.arg0.fat", {arg0: (nutritionTotal.fat_g || "x g")}),
      t("copy.arg0.fiber", {arg0: (nutritionTotal.fiber_g || "x g")}),
    ].join(" | ");
    scheduleButton.type = "button";
    scheduleButton.className = "add-to-schedule-button";
    scheduleButton.textContent = t("copy.add.to.schedule", {});
    scheduleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      addMealToSchedule(dish);
    });

    card.appendChild(header);

    card.append(
      price,
      metadata,
      totalNutrition,
      scheduleButton
    );

    if (dish.exact_match === false) {
      const relaxedMessage = document.createElement("p");
      relaxedMessage.className = "dish-warning";
      relaxedMessage.textContent = t("copy.closest.affordable.match.some.filters.were.relaxed", {});
      card.appendChild(relaxedMessage);
    }

    restrictionWarnings.forEach((warning) => {
      const warningMessage = document.createElement("p");
      warningMessage.className = "dish-warning";
      warningMessage.textContent = warning;
      card.appendChild(warningMessage);
    });

  return card;
}

async function initializeAuth() {
  if (!supabaseClient) {
    setAuthStatus(t("copy.supabase.is.not.configured.check.the.project.url.and", {}), "error");
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

// SNAP center locations from the official HRA directory (checked October 2026).
const SNAP_HRA_CENTERS = [
  ["Manhattan", "East End", "2322 Third Avenue, 3rd floor, NY 10035"],
  ["Manhattan", "Washington Heights", "4055 10th Avenue, lower level, NY 10034"],
  ["Manhattan", "Lower Manhattan Benefits Access Center", "109 East 16th Street, NY 10003"],
  ["Manhattan", "St. Nicholas Benefits Access Center", "132 West 125th Street, NY 10027"],
  ["Bronx", "Crotona", "1910 Monterey Avenue, 5th floor, Bronx, NY 10457"],
  ["Bronx", "Hunts Point", "845 Barretto Street, B-level, Bronx, NY 10474"],
  ["Brooklyn", "Coney Island", "1912 Mermaid Avenue, 1st & 2nd floors, Brooklyn, NY 11224"],
  ["Brooklyn", "East New York", "2400 Fulton Street, 3rd & 4th floors, Brooklyn, NY 11233"],
  ["Brooklyn", "Williamsburg", "2 George Street, 1st floor, Brooklyn, NY 11206"],
  ["Queens", "Jamaica", "165-08 88th Avenue, 3rd floor, Jamaica, NY 11432"],
  ["Queens", "Queens", "32-20 Northern Boulevard, 2nd floor, LIC, NY 11101 (entrance: One Honeywell Street)"],
  ["Queens", "Rockaway", "219 Beach 59th Street, 1st floor, Rockaway, NY 11692"],
  ["Staten Island", "Richmond", "201 Bay Street, 2nd floor, Staten Island, NY 10301"],
];
let snapCentersZip = "";
let snapCentersReturnButton = "snap101-signup-centers";

function snapCenterBorough(zip) {
  if (/^10[0-2]\d{2}$/.test(zip)) return "Manhattan";
  if (/^103\d{2}$/.test(zip)) return "Staten Island";
  if (/^104\d{2}$/.test(zip)) return "Bronx";
  if (/^112\d{2}$/.test(zip)) return "Brooklyn";
  if (/^(111|113|114|116)\d{2}$/.test(zip)) return "Queens";
  return "";
}

function renderSnapSignupCenters() {
  const input = document.getElementById("snap101-centers-zip");
  const zip = snapCentersZip || [currentUserInfo?.zip_code || "", profileZipCodeInput?.value || "", myZipCodeInput?.value || "", zipCodeInput?.value || ""].find(value => /^\d{5}$/.test(value.trim()))?.trim() || "";
  input.value = zip;
  const borough = snapCenterBorough(zip);
  document.getElementById("snap101-centers-location").textContent = zip
    ? t("copy.your.zip.code.arg0.arg1", {arg0: (zip), arg1: (borough ? `Showing ${borough} HRA centers first, followed by other NYC centers.` : "These centers serve New York City. Use the organizations’ directories to confirm assistance for your area.")})
    : t("copy.enter.your.zip.code.to.see.local.support.options.c68452", {});
  document.getElementById("snap101-hra-location-note").textContent = borough
    ? t("copy.arg0.centers.are.listed.first.check.the.official.directory", {arg0: (borough)})
    : t("copy.explore.centers.across.all.five.boroughs.below", {});
  const centers = [...SNAP_HRA_CENTERS].sort((a, b) => Number(b[0] === borough) - Number(a[0] === borough));
  document.getElementById("snap101-hra-centers").replaceChildren(...centers.map(([area, name, address]) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = t("copy.arg0.arg1.9c2551", {arg0: (name), arg1: (area)});
    const location = document.createElement("span");
    location.textContent = address;
    item.append(title, location);
    if (name === "Hunts Point") {
      const note = document.createElement("small");
      note.textContent = t("copy.work.requirements.services.8.30.9.a.m.only", {});
      item.append(note);
    }
    return item;
  }));
}

["snap101-signup-centers", "snap101-signup-help"].forEach(id => {
  document.getElementById(id).addEventListener("click", () => {
    snapCentersReturnButton = id;
    showPanel("snap101-centers");
    document.getElementById("snap101-centers-heading").focus();
  });
});
document.getElementById("snap101-centers-back").addEventListener("click", () => {
  showPanel(snapCentersReturnButton === "snap101-signup-help" ? "snap101-signup-options" : "snap101-signup");
  document.getElementById(snapCentersReturnButton).focus();
});
document.getElementById("snap101-centers-zip-form").addEventListener("submit", event => {
  event.preventDefault();
  const input = document.getElementById("snap101-centers-zip");
  if (!input.reportValidity()) return;
  snapCentersZip = input.value.trim();
  renderSnapSignupCenters();
});

document.getElementById("snap101-signup-how").addEventListener("click", () => {
  showPanel("snap101-signup-options");
  document.getElementById("snap101-signup-options-heading").focus();
});

document.getElementById("snap101-signup-back").addEventListener("click", () => {
  showPanel("snap101-signup");
  document.getElementById("snap101-signup-how").focus();
});

appSwitchButtons.forEach((button) =>
  button.addEventListener("click", () => {
    if (button.dataset.appMode === "snap101") {
      showPanel(SNAP101_DEFAULT_PANEL_ID);
      return;
    }
    showPanel(SIGNED_IN_DEFAULT_PANEL_ID);
  })
);

showSignInButton.addEventListener("click", () => showAuthMode("sign-in"));
showSignUpButton.addEventListener("click", () => showAuthMode("sign-up"));

snapHouseholdSizeInput?.addEventListener("input", updateSnapEstimate);
snapIncomeInput?.addEventListener("input", updateSnapEstimate);

onboardingZipCodeInput.addEventListener("input", () => {
  onboardingZipCodeInput.value = onboardingZipCodeInput.value.replace(/\D/g, "").slice(0, 5);
  setOnboardingStatus("");
});

onboardingHouseholdMinusButton.addEventListener("click", () => {
  setOnboardingHouseholdSize(Number(onboardingHouseholdInput.value) - 1);
  setOnboardingStatus("");
});

onboardingHouseholdPlusButton.addEventListener("click", () => {
  setOnboardingHouseholdSize(Number(onboardingHouseholdInput.value) + 1);
  setOnboardingStatus("");
});

function handleCustomPreferenceAdd(input) {
  const didAdd = addDietaryPreference(input.value);
  input.value = "";
  if (didAdd) {
    queueSettingsSave();
  }
}

onboardingAddPreferenceButton.addEventListener("click", () => {
  handleCustomPreferenceAdd(onboardingCustomPreferenceInput);
  onboardingCustomPreferenceInput.focus();
});

onboardingCustomPreferenceInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  handleCustomPreferenceAdd(onboardingCustomPreferenceInput);
});

settingsAddPreferenceButton.addEventListener("click", () => {
  handleCustomPreferenceAdd(settingsCustomPreferenceInput);
  settingsCustomPreferenceInput.focus();
});

settingsCustomPreferenceInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  handleCustomPreferenceAdd(settingsCustomPreferenceInput);
});

onboardingBackButton.addEventListener("click", () => {
  onboardingStepIndex = Math.max(0, onboardingStepIndex - 1);
  setOnboardingStatus("");
  renderOnboardingStep();
});

onboardingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const stepError = getOnboardingStepError();
  if (stepError) {
    setOnboardingStatus(stepError, "error");
    return;
  }

  if (onboardingStepIndex < ONBOARDING_TOTAL_STEPS - 1) {
    onboardingStepIndex += 1;
    setOnboardingStatus("");
    renderOnboardingStep();
    return;
  }

  const wasSaved = await saveOnboardingToUser();
  if (wasSaved) {
    showPanel(SIGNED_IN_DEFAULT_PANEL_ID);
  }
});

signInForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabaseClient) return;

  const submitButton = signInForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setAuthStatus(t("copy.signing.in", {}));
  const username = normalizeUsername(signInUsernameInput.value);
  const usernameError = getUsernameError(username);

  if (usernameError) {
    setAuthStatus(usernameError, "error");
    submitButton.disabled = false;
    return;
  }

  onboardingForNewAccount = pendingNewAccountUsername === username;
  authLandingPending = true;
  const { error } = await supabaseClient.auth.signInWithPassword({
    email: usernameToEmail(username),
    password: signInPasswordInput.value,
  });

  if (error) {
    authLandingPending = false;
    onboardingForNewAccount = false;
    setAuthStatus(t("security.signInFailed", {}), "error");
  } else {
    pendingNewAccountUsername = "";
    signInForm.reset();
    setAuthStatus(t("copy.signed.in.aeca5e", {}), "success");
  }

  submitButton.disabled = false;
});

signUpForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabaseClient) return;

  const submitButton = signUpForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setAuthStatus(t("copy.creating.account", {}));
  const username = normalizeUsername(signUpUsernameInput.value);
  const usernameError = getUsernameError(username);

  if (usernameError) {
    setAuthStatus(usernameError, "error");
    submitButton.disabled = false;
    return;
  }

  onboardingForNewAccount = true;
  authLandingPending = true;
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
    onboardingForNewAccount = false;
    authLandingPending = false;
    setAuthStatus(t("security.signUpFailed", {}), "error");
  } else if (data.session) {
    signUpForm.reset();
    setAuthStatus(t("copy.account.created.you.are.signed.in", {}), "success");
  } else {
    pendingNewAccountUsername = username;
    authLandingPending = false;
    signUpForm.reset();
    showAuthMode("sign-in");
    setAuthStatus(t("copy.account.created.sign.in.with.your.username.and.password", {}), "success");
  }

  submitButton.disabled = false;
});

signOutButton.addEventListener("click", handleSignOut);
accountPanelSignOutButton?.addEventListener("click", handleSignOut);

storeSearchForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = zipCodeInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    storeSearchStatus.textContent = translateText(t("copy.enter.a.valid.5.digit.us.zip.code", {}));
    storeResults.replaceChildren();
    storeSource.hidden = true;
    return;
  }

  const submitButton = storeSearchForm.querySelector("button");
  submitButton.disabled = true;
  storeSearchStatus.textContent = translateText(t("copy.searching.for.grocery.stores", {}));
  storeResults.replaceChildren();
  storeSource.hidden = true;

  try {
    const data = await fetchStores(zipCode, { snapOnly: false });
    const stores = data.stores || [];
    renderStores(stores);
    storeSearchStatus.textContent =
      stores.length
          ? t("copy.arg0.grocery.store.arg1.found.near.arg2", {arg0: (stores.length), arg1: (stores.length === 1 ? "" : "s"), arg2: (data.location)})
          : t("copy.no.grocery.stores.were.found.in.arg0", {arg0: (data.location)});
    storeSource.hidden = false;
  } catch (error) {
    storeSearchStatus.textContent = t("copy.arg0.arg1", {arg0: (translateText("Store search error:")), arg1: (error.message)});
  } finally {
    submitButton.disabled = false;
  }
});


pantryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const spiceName = canonicalSpiceName(pantryNameInput.value);
  const name = spiceName || pantryNameInput.value.trim();
  const quantity = spiceName ? "pantry staple" : pantryQuantityInput.value.trim();

  if (!name || (!spiceName && !quantity)) {
    setPantryStatus(t("copy.enter.both.a.food.name.and.quantity", {}), "error");
    return;
  }

  const submitButton = pantryForm.querySelector("button");
  submitButton.disabled = true;

  try {
    const wasAdded = await addPantryItem(name, quantity);
    if (wasAdded) {
      pantryForm.reset();
      updatePantryQuantityVisibility();
    }
  } finally {
    submitButton.disabled = false;
  }
});

pantryNameInput.addEventListener("input", updatePantryQuantityVisibility);
pantryNameInput.addEventListener("change", updatePantryQuantityVisibility);

shoppingAddPantryButton.addEventListener("click", async () => {
  const items = getShoppingIngredients();
  const itemsToAdd = selectedShoppingIngredientIds.size
    ? items.filter((item) => selectedShoppingIngredientIds.has(item.id))
    : items;

  if (!itemsToAdd.length) return;

  shoppingAddPantryButton.disabled = true;
  shoppingStatus.textContent = t("copy.adding.arg0.ingredient.arg1.to.pantry", {arg0: (itemsToAdd.length), arg1: (itemsToAdd.length === 1 ? "" : "s")});

  const wasAdded = await addPantryItems(itemsToAdd);
  if (wasAdded) {
    itemsToAdd.forEach((item) => pantryHandledShoppingIngredientIds.add(item.id));
    selectedShoppingIngredientIds.clear();
    shoppingStatus.textContent = t("copy.arg0.ingredient.arg1.added.to.pantry", {arg0: (itemsToAdd.length), arg1: (itemsToAdd.length === 1 ? "" : "s")});
    renderShoppingList();
  } else {
    shoppingStatus.textContent = t("copy.could.not.add.ingredients.to.pantry", {});
    updateShoppingAddButton(items);
  }
});

dishForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mealPrompt = dishInput.value.trim();
  if (!mealPrompt) return;

  const submitButton = dishForm.querySelector("button");
  submitButton.disabled = true;
  appendDishMessage("user", mealPrompt);
  dishInput.value = "";
  startDishProgress();
  dishSource.hidden = true;

  try {
    const data = await fetchDishes(mealPrompt);
    renderDishes(data);
    setDishStatus(t("copy.found.arg0.recipe.arg1.with.grocery.price.estimates", {arg0: (Math.min(data.dishes.length, 3)), arg1: (data.dishes.length === 1 ? "match" : "matches")}));
    dishSource.hidden = false;
  } catch (error) {
    appendDishMessage("bot", `Dish search error: ${error.message}`);
    setDishStatus(t("copy.dish.search.error.arg0", {arg0: (error.message)}));
  } finally {
    submitButton.disabled = false;
    dishInput.focus();
  }
});

dishModalClose.addEventListener("click", () => dishModal.close());
dishModal.addEventListener("click", (event) => {
  if (event.target === dishModal) {
    dishModal.close();
  }
});

householdSizeInput.addEventListener("input", () => {
  renderBudget();
  syncSnapCalculatorHouseholdSize();
  queueSettingsSave();
});

profileZipCodeInput.addEventListener("input", queueSettingsSave);

dietaryRestrictionsInput.addEventListener("input", queueSettingsSave);
dietaryRestrictionsInput.addEventListener("change", () => {
  setDietaryPreferences(
    dietaryRestrictionsInput.value.split(",").map(normalizeDietaryPreference),
    { syncTextarea: false }
  );
  queueSettingsSave();
});

budgetInput.addEventListener("input", () => {
  renderBudget();
  queueSettingsSave();
});

document.getElementById("budget-editor-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const input = document.getElementById("budget-monthly-input");
  const status = document.getElementById("budget-editor-status");
  const amount = Number(input.value);
  if (!form.reportValidity() || !input.value.trim() || !Number.isFinite(amount) || amount < 0) return;
  const button = form.querySelector("button");
  button.disabled = true;
  window.clearTimeout(settingsSaveTimer);
  budgetInput.value = amount.toFixed(2);
  renderBudget();
  status.textContent = t("copy.saving.budget", {});
  try {
    const saved = await saveSettingsToUser();
    status.textContent = saved ? t("copy.monthly.budget.saved", {}) : t("copy.couldn.t.save.your.budget.please.try.again", {});
  } catch {
    status.textContent = t("copy.couldn.t.save.your.budget.please.try.again", {});
  } finally {
    button.disabled = false;
  }
});

budgetOpenSnap101Button?.addEventListener("click", () => showPanel(SNAP101_DEFAULT_PANEL_ID));

plateBalanceSlider?.addEventListener("input", updatePlateBalanceGame);

snackOptionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    button.classList.toggle("active");
    updateSnackGame();
  });
});

waterTapButton?.addEventListener("click", () => {
  hydrationTaps = hydrationTaps >= 6 ? 0 : hydrationTaps + 1;
  updateWaterGame();
});

waterResetButton?.addEventListener("click", () => {
  hydrationTaps = 0;
  updateWaterGame();
});

themeSelect.addEventListener("change", () => {
  document.body.classList.toggle("dark-theme", themeSelect.value === "dark");
});

if (languageSelect) {
  languageSelect.value = getLanguage();
  languageSelect.addEventListener("change", () => window.SNAPP_I18N.setLocale(languageSelect.value));
}

notificationsToggle.addEventListener("change", () => {
  const status = notificationsToggle.checked ? "enabled" : "disabled";
  setSettingsStatus(t("copy.daily.reminders.arg0", {arg0: (status)}));
  queueSettingsSave();
});

dietSelect.addEventListener("change", () => {
  setSettingsStatus(t("copy.dietary.preference.set.to.arg0", {arg0: (dietSelect.value)}));
  queueSettingsSave();
});

// Recipe Chat. State and rendering stay separate from Dishes.
const recipeChat = (() => {
  const panel = document.getElementById("recipe-chat");
  const form = document.getElementById("recipe-chat-form");
  const input = document.getElementById("recipe-chat-input");
  const sendButton = document.getElementById("recipe-chat-send");
  const history = document.getElementById("recipe-chat-history");
  const empty = document.getElementById("recipe-chat-empty");
  const status = document.getElementById("recipe-chat-status");
  const error = document.getElementById("recipe-chat-error");
  const prompts = [...panel.querySelectorAll(".recipe-chat-prompts button")];
  let currentState = null;
  let activeRequest = null;
  let detailRequest = null;
  let detailVersion = 0;
  let detailRecipe = null;
  const detailView = document.createElement("section");
  detailView.className = "recipe-chat-card recipe-chat-detail";
  detailView.hidden = true;
  history.after(detailView);

  function backToResults() {
    detailRecipe = null;
    detailVersion += 1;
    detailRequest?.abort();
    detailRequest = null;
    detailView.hidden = true;
    history.hidden = !history.childElementCount;
    empty.hidden = Boolean(history.childElementCount);
  }

  async function fetchDetail(recipeId, forSchedule = false) {
    const controller = new AbortController();
    detailRequest?.abort();
    detailRequest = controller;
    const timeout = window.setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(endpoint().replace(/chat$/, "detail"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipe_id: recipeId, for_schedule: forSchedule, include_sale_matches: !forSchedule,
          include_price_estimate: true, locale: getLanguage(),
          household_size: householdSizeInput.value,
          pantry_items: pantryItems.map(({ name, quantity }) => ({ name, quantity })),
        }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Recipe load failed");
      const data = await response.json();
      if (data.dish?.recipe_id !== recipeId || !data.dish.recipe) throw new Error("Invalid recipe");
      return data.dish;
    } finally {
      window.clearTimeout(timeout);
      if (detailRequest === controller) detailRequest = null;
    }
  }

  async function openRecipeDetail(recipe) {
    backToResults();
    detailRecipe = recipe;
    const version = detailVersion;
    history.hidden = true;
    empty.hidden = true;
    detailView.hidden = false;
    detailView.replaceChildren();
    const back = textElement("button", "", t("copy.back.to.results", {}));
    back.type = "button";
    back.addEventListener("click", backToResults);
    const feedback = textElement("p", "recipe-chat-text", t("copy.loading.recipe", {}));
    feedback.setAttribute("role", "status");
    detailView.append(back, feedback);
    try {
      const dish = await fetchDetail(recipe.id);
      if (version !== detailVersion) return;
      const canonical = dish.recipe;
      const full = dish.localized_recipe || canonical;
      const card = recipeCard({
        ...full, pricing_recipe: canonical, title: full.name || full.title || dish.name, sale_ingredients: dish.sale_ingredients,
        grocery_estimate: dish.grocery_estimate,
        canonical_ingredients_text: (canonical.ingredients || []).map((item) => item.display || item.measure || item.name),
        ingredients_text: (full.ingredients || []).map((item) => item.display || item.measure || item.name),
      }, 0, true);
      detailView.append(card);
      if (full._translation_status && full._translation_status !== "translated") {
        card.append(textElement("p", "recipe-chat-hint", t("copy.recipe.translation.unavailable.showing.original.english")));
      }
      if (dish.sale_metadata_unavailable) card.append(textElement("p", "recipe-chat-hint", t("copy.sale.information.is.temporarily.unavailable", {})));
      const servings = formatServings(dish);
      if (servings) card.append(textElement("p", "", servings));
      const equipment = stringList(full.equipment);
      if (equipment.length) card.append(textElement("p", "", t("copy.equipment.arg0", {arg0: (equipment.join(", "))})));
      if (!full.instructions) card.append(textElement("p", "", t("copy.cooking.instructions.are.unavailable.for.this.recipe", {})));
      feedback.textContent = "";
      const schedule = textElement("button", "", t("copy.add.to.schedule.d2fc00", {}));
      schedule.type = "button";
      schedule.addEventListener("click", async () => {
        schedule.disabled = true;
        feedback.textContent = t("copy.preparing.recipe.for.your.schedule", {});
        try {
          const scheduledDish = scheduledMeals.find((meal) => meal.recipe_id === recipe.id)
            || await fetchDetail(recipe.id, true);
          if (version !== detailVersion) return;
          await addMealToSchedule(scheduledDish);
          feedback.textContent = t("copy.recipe.is.in.your.schedule", {});
        } catch {
          if (version === detailVersion) feedback.textContent = t("copy.couldn.t.add.this.recipe.to.your.schedule.try", {});
        } finally {
          schedule.disabled = false;
        }
      });
      detailView.append(schedule);
    } catch {
      if (version === detailVersion) feedback.textContent = t("copy.couldn.t.load.this.recipe.return.to.results.and", {});
    }
  }

  function setPending(pending) {
    input.disabled = pending;
    sendButton.disabled = pending;
    prompts.forEach((button) => { button.disabled = pending; });
    sendButton.textContent = pending ? t("copy.searching", {}) : t("chat.send", {});
    status.textContent = pending ? t("copy.snapp.is.checking.recipes", {}) : "";
    history.setAttribute("aria-busy", String(pending));
  }

  function reset(focus = true) {
    activeRequest?.abort();
    activeRequest = null;
    currentState = null;
    backToResults();
    history.replaceChildren();
    history.hidden = true;
    empty.hidden = false;
    input.value = "";
    error.hidden = true;
    error.textContent = "";
    setPending(false);
    if (focus) input.focus();
  }

  function textElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = text;
    return element;
  }

  function stringList(value) {
    return Array.isArray(value) ? value.filter((item) => typeof item === "string" && item.trim()) : [];
  }

  const cardRecipes = new WeakMap();
  function appendPrice(card, recipe) {
    if (window.SNAPP_RECIPE_PRICES) window.SNAPP_RECIPE_PRICES.register(card, recipe.pricing_recipe || recipe);
  }

  function recipeCard(recipe, index, selected = false) {
    const card = document.createElement("article");
    cardRecipes.set(card, { recipe, index, selected });
    card.className = `recipe-chat-card${selected ? " recipe-chat-card-selected" : ""}`;
    card.append(textElement("p", "recipe-chat-card-label", selected ? t("copy.selected.recipe", {}) : t("copy.result.arg0", {arg0: (index + 1)})));
    if (typeof recipe.title === "string") card.append(textElement("h3", "", recipe.title));
    appendPrice(card, recipe);
    const total = recipe.total_time_minutes;
    const cook = recipe.cook_time_minutes;
    if (typeof total === "number" && Number.isFinite(total)) {
      card.append(textElement("p", "recipe-chat-card-time", t("copy.arg0.minutes.total", {arg0: (total)})));
    } else if (typeof cook === "number" && Number.isFinite(cook)) {
      card.append(textElement("p", "recipe-chat-card-time", t("copy.arg0.minutes.cooking", {arg0: (cook)})));
    }
    const categories = stringList(recipe.categories);
    if (categories.length) {
      card.append(textElement("p", "recipe-chat-card-categories", categories.map((value) => t(`recipe.category.${value}`) || value.replace(/_/g, " ")).join(" · ")));
    }
    const ingredients = selected
      ? stringList(recipe.ingredients_text).length ? stringList(recipe.ingredients_text) : stringList(recipe.ingredient_names)
      : stringList(recipe.key_ingredients).length ? stringList(recipe.key_ingredients) : stringList(recipe.ingredient_names);
    if (ingredients.length) {
      card.append(textElement("p", "recipe-chat-card-label", selected ? t("copy.stored.ingredients", {}) : t("copy.ingredients.include", {})));
      if (selected) {
        const list = recipeItemList(ingredients, (ingredient) => ingredient);
        ingredients.forEach((ingredient, index) => {
          const offer = (recipe.sale_ingredients || []).find((item) => (item.recipe_display === (recipe.canonical_ingredients_text?.[index] || ingredient) || item.recipe_measure === ingredient) && item.is_on_sale === true);
          if (!offer) return;
          const badge = textElement("span", "recipe-sale-badge", t("copy.on.sale", {}));
          list.children[index].append(badge);
          list.children[index].append(textElement("small", "recipe-sale-offer", t("copy.arg0.arg1.c2a27c", {arg0: (offer.product_name || "Matched product"), arg1: (offer.sale_offer ? ` · ${offer.sale_offer}` : "")})));
        });
        card.append(list);
      } else {
        card.append(textElement("p", "", ingredients.slice(0, 8).join(", ")));
      }
    }
    if (selected) {
      const steps = stringList(recipe.instructions);
      if (steps.length || typeof recipe.instructions === "string" && recipe.instructions.trim()) {
        card.append(textElement("p", "recipe-chat-card-label", t("copy.stored.instructions", {})));
        if (steps.length) {
          card.append(recipeItemList(steps, (step) => step, true));
        } else {
          card.append(textElement("p", "recipe-chat-text", recipe.instructions));
        }
      }
    }
    if (!selected) {
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", t("copy.view.recipe.arg0", {arg0: (recipe.title || "Recipe")}));
      card.addEventListener("click", () => openRecipeDetail(recipe));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openRecipeDetail(recipe);
        }
      });
    }
    return card;
  }

  function messageElement(speaker, message) {
    const article = document.createElement("article");
    article.className = `recipe-chat-message recipe-chat-message-${speaker === t("chat.you") ? "user" : "snapp"}`;
    article.append(textElement("p", "recipe-chat-speaker", speaker), textElement("p", "recipe-chat-text", message));
    return article;
  }

  function endpoint() {
    // Only Recipe Chat targets Flask locally. Shared API routing is unchanged.
    const override = document.querySelector('meta[name="snapp-recipe-chat-api-base-url"]')?.content?.trim().replace(/\/+$/, "");
    if (override) return `${override}/api/recipes/chat`;
    if (["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
      return "http://127.0.0.1:5002/api/recipes/chat";
    }
    return getApiEndpoints("/api/recipes/chat")[0];
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (activeRequest || !message || !form.reportValidity()) return;
    backToResults();
    const controller = new AbortController();
    activeRequest = controller;
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    error.hidden = true;
    error.textContent = "";
    empty.hidden = true;
    history.hidden = false;
    setPending(true);
    const userMessage = messageElement(t("chat.you"), message);
    history.append(userMessage);
    history.scrollTop = history.scrollHeight;
    try {
      const url = endpoint();
      if (!url) throw new Error("Recipe Chat endpoint is not configured");
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, state: currentState, locale: getLanguage(), household_size: getHouseholdSize(), pantry_items: pantryItems.map(({name, quantity}) => ({name, quantity})) }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Recipe Chat request failed");
      const data = await response.json();
      if (activeRequest !== controller) return;
      if (typeof data.message !== "string" || !data.state || typeof data.state !== "object" || Array.isArray(data.state) || !Array.isArray(data.results)) {
        throw new Error("Invalid Recipe Chat response");
      }
      const reply = messageElement("SNAPP", data.message);
      if (data.results.length) {
        const results = document.createElement("div");
        results.className = "recipe-chat-results";
        results.setAttribute("aria-label", t("copy.recipes.in.result.order", {}));
        (data.localized_results || data.results).forEach((recipe, index) => results.append(recipeCard({...recipe, pricing_recipe: data.results[index]}, index)));
        reply.append(results);
      }
      if (data.selected_recipe) reply.append(recipeCard({...data.localized_selected_recipe || data.selected_recipe, pricing_recipe:data.selected_recipe}, 0));
      history.append(reply);
      currentState = data.state;
      input.value = "";
      // Bring the start of this response into view, without scrolling the entire page.
      history.scrollTop = reply.offsetTop;
      if (panel.classList.contains("visible")) {
        requestAnimationFrame(() => {
          const recipes = reply.querySelector(".recipe-chat-results") || reply;
          recipes.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
        });
      }
    } catch {
      if (activeRequest !== controller) return;
      userMessage.remove();
      empty.hidden = history.childElementCount > 0;
      history.hidden = !empty.hidden;
      error.textContent = t("copy.snapp.couldn.t.search.recipes.right.now.try.again", {});
      error.hidden = false;
    } finally {
      window.clearTimeout(timeout);
      if (activeRequest === controller) {
        activeRequest = null;
        setPending(false);
        if (panel.classList.contains("visible")) input.focus({ preventScroll: true });
      }
    }
  });

  document.addEventListener("snapp:localechange", (event) => {
    if (currentState) currentState.conversation_language = event.detail.locale;
    if (!detailView.hidden && detailRecipe) openRecipeDetail(detailRecipe);
    const locale = event.detail.locale;
    history.querySelectorAll(".recipe-chat-card").forEach(async (card) => {
      const binding = cardRecipes.get(card);
      if (!binding?.recipe.id) return;
      try {
        const response = await fetch(endpoint().replace(/chat$/, "detail"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ recipe_id: binding.recipe.id, locale }),
        });
        if (!response.ok || getLanguage() !== locale || !card.isConnected) return;
        const { dish } = await response.json();
        const full = dish.localized_recipe || dish.recipe;
        const recipe = {
          ...binding.recipe, ...full, id: binding.recipe.id,
          title: full.name || full.title || dish.name,
          key_ingredients: (full.ingredients || []).map((item) => item.display || item.measure || item.name),
        };
        card.replaceWith(recipeCard(recipe, binding.index, binding.selected));
      } catch {
        error.textContent = t("copy.recipe.translation.unavailable.showing.original.english");
        error.hidden = false;
      }
    });
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  prompts.forEach((button) => button.addEventListener("click", () => {
    input.value = button.textContent;
    form.requestSubmit();
  }));
  document.getElementById("recipe-chat-new").addEventListener("click", () => reset());
  function searchIngredient(ingredient) {
    reset(false);
    input.value = `Recipes with ${ingredient}`;
    form.requestSubmit();
  }
  async function nutritionFor(dish) {
    const response = await fetch(endpoint().replace(/chat$/, "nutrition"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipe: dish.recipe, household_size: getHouseholdSize() }),
    });
    if (!response.ok) throw new Error("Nutrition unavailable");
    const data = await response.json();
    if (data.nutrition_source !== "USDA FoodData Central") throw new Error("Invalid nutrition");
    return data;
  }
  return { reset, searchIngredient, nutritionFor };
})();
// End Recipe Chat.

populatePantrySpiceSuggestions();
updatePantryQuantityVisibility();
updatePlateBalanceGame();
updateSnackGame();
updateWaterGame();
applyLanguage();
renderSchedule();
showAuthMode("sign-in");
initializeAuth();
handleInitialUrlState();
