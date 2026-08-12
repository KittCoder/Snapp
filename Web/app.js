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
const budgetMealCount = document.getElementById("budget-meal-count");
const scheduledMealCost = document.getElementById("scheduled-meal-cost");
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

const scheduledMeals = [];
let favoriteRecipes = [];
let currentUser = null;
let currentUserInfo = null;
let settingsSaveTimer = null;
let onboardingStepIndex = 0;
let selectedDietaryPreferences = [];
let myStoreMap = null;
let myStoreMarkers = [];
let pantryItems = [];
let savedMyStores = [];
let activeAuthUserId = null;
let dishProgressTimer = null;
let authRenderSequence = 0;
let activeAppMode = "snapp";
const selectedMyStoreIds = new Set();
const selectedShoppingIngredientIds = new Set();
const pantryHandledShoppingIngredientIds = new Set();
const LANGUAGE_STORAGE_KEY = "snapp-language";
const originalTextNodes = new WeakMap();
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

const SPANISH_TEXT = {
  "Home": "Inicio",
  "Account": "Cuenta",
  "Dishes": "Platillos",
  "My stores": "Mis tiendas",
  "My pantry": "Mi despensa",
  "Schedule": "Horario",
  "Shopping list": "Lista de compras",
  "Budget": "Presupuesto",
  "Information": "Informacion",
  "Settings": "Configuracion",
  "Signed out": "Sesion cerrada",
  "Sign out": "Cerrar sesion",
  "SNAPP Account": "Cuenta de SNAPP",
  "Save your planning session with Supabase.": "Guarda tu sesion de planificacion con Supabase.",
  "Create an account or sign in to use SNAPP. This prototype uses a username and password while Supabase keeps you signed in on this browser.": "Crea una cuenta o inicia sesion para usar SNAPP. Este prototipo usa un nombre de usuario y una contrasena mientras Supabase mantiene tu sesion abierta en este navegador.",
  "Account actions": "Acciones de cuenta",
  "Sign in": "Iniciar sesion",
  "Create account": "Crear cuenta",
  "Username": "Nombre de usuario",
  "Password": "Contrasena",
  "Nourishment Made Practical": "Nutricion practica",
  "Welcome to SNAPP": "Bienvenido a SNAPP",
  "Build balanced meals with clarity. SNAPP helps you plan your week, understand nutrition foundations, and turn food choices into habits that are realistic for your schedule.": "Crea comidas balanceadas con claridad. SNAPP te ayuda a planificar la semana, entender bases de nutricion y convertir tus decisiones de comida en habitos realistas para tu horario.",
  "Today's Store Plan": "Plan de tiendas de hoy",
  "Hello": "Hola",
  "Start with sale ingredients that already have recipe matches and Morton Williams price estimates.": "Empieza con ingredientes en oferta que ya tienen recetas compatibles y estimados de precio de Morton Williams.",
  "Best sale ingredients today": "Mejores ingredientes en oferta hoy",
  "Ranked from current Morton Williams sale data and matched to recipes SNAPP can price.": "Clasificados con datos actuales de ofertas de Morton Williams y recetas que SNAPP puede estimar.",
  "Saved local store support is coming soon. These placeholders show where selected stores will appear.": "La compatibilidad con tiendas locales guardadas llegara pronto. Estos espacios muestran donde apareceran tus tiendas seleccionadas.",
  "Placeholder active source": "Fuente activa temporal",
  "Local grocery placeholder": "Tienda local temporal",
  "Coming soon": "Proximamente",
  "Core Food Groups": "Grupos principales de alimentos",
  "Simple Plate Method": "Metodo simple del plato",
  "Weekly Nutrition Focus": "Enfoque semanal de nutricion",
  "Use SNAPP Throughout Your Day": "Usa SNAPP durante el dia",
  "Ask for a meal idea. SNAPP uses your saved profile, pantry, budget, diet, and store settings automatically.": "Pide una idea de comida. SNAPP usa automaticamente tu perfil, despensa, presupuesto, dieta y tiendas guardadas.",
  "Ask for a meal idea to get started.": "Pide una idea de comida para empezar.",
  "What meal do you want?": "Que comida quieres?",
  "Send": "Enviar",
  "Weekly Meal Schedule": "Horario semanal de comidas",
  "Meals you select from Dishes appear here. Click a meal to view its recipe and ingredients.": "Las comidas que selecciones en Platillos aparecen aqui. Haz clic en una comida para ver su receta e ingredientes.",
  "Recipes": "Recetas",
  "Drag recipes into a breakfast, lunch, or dinner slot.": "Arrastra recetas a desayuno, almuerzo o cena.",
  "Ingredients from dishes you added to your schedule appear here.": "Los ingredientes de los platillos agregados a tu horario aparecen aqui.",
  "Add all to pantry": "Agregar todo a la despensa",
  "Enter a 5-digit US ZIP code to find nearby grocery stores, then select the stores you want to use.": "Ingresa un codigo postal de EE. UU. de 5 digitos para encontrar tiendas cercanas y seleccionar las que quieres usar.",
  "ZIP code": "Codigo postal",
  "Find nearby stores": "Buscar tiendas cercanas",
  "Nearby grocery store map": "Mapa de tiendas cercanas",
  "Selected stores": "Tiendas seleccionadas",
  "Store data and map tiles ©": "Datos de tiendas y mosaicos de mapa ©",
  "OpenStreetMap contributors": "Colaboradores de OpenStreetMap",
  "Add foods you already have so SNAPP can consider them when suggesting dishes.": "Agrega alimentos que ya tienes para que SNAPP los considere al sugerir platillos.",
  "Food": "Alimento",
  "Quantity": "Cantidad",
  "Add item": "Agregar articulo",
  "Set your meal budget in Settings, and SNAPP will subtract the estimated price of each scheduled meal.": "Define tu presupuesto de comidas en Configuracion y SNAPP restara el precio estimado de cada comida programada.",
  "Remaining budget": "Presupuesto restante",
  "Meal budget:": "Presupuesto de comidas:",
  "Scheduled meals:": "Comidas programadas:",
  "Scheduled cost:": "Costo programado:",
  "Grocery Store Information": "Informacion de tiendas",
  "Enter a 5-digit US ZIP code to find grocery stores in that area.": "Ingresa un codigo postal de EE. UU. de 5 digitos para encontrar tiendas en esa area.",
  "Find stores": "Buscar tiendas",
  "Store data ©": "Datos de tiendas ©",
  "Account and Nutritional Information": "Cuenta e informacion nutricional",
  "How many people are you cooking for?": "Para cuantas personas cocinas?",
  "Dietary Restrictions": "Restricciones alimentarias",
  "Restrictions for dish recommendations": "Restricciones para recomendaciones de platillos",
  "Preferences": "Preferencias",
  "Theme": "Tema",
  "Light": "Claro",
  "Dark": "Oscuro",
  "Language": "Idioma",
  "English": "Ingles",
  "Español": "Espanol",
  "Dietary Preference": "Preferencia alimentaria",
  "Balanced": "Balanceada",
  "Vegetarian": "Vegetariana",
  "Vegan": "Vegana",
  "Keto": "Keto",
  "Enable daily reminders": "Activar recordatorios diarios",
  "Close recipe": "Cerrar receta",
  "Remove": "Quitar",
  "No stores selected.": "No hay tiendas seleccionadas.",
  "SNAP accepted": "Acepta SNAP",
  "SNAP acceptance not verified": "Aceptacion de SNAP no verificada",
  "View on map": "Ver en el mapa",
  "Visit website": "Visitar sitio web",
  "No stores found for this search.": "No se encontraron tiendas para esta busqueda.",
  "Map library could not load. Store list is still available.": "No se pudo cargar el mapa. La lista de tiendas sigue disponible.",
  "Enter a valid 5-digit US ZIP code.": "Ingresa un codigo postal valido de EE. UU. de 5 digitos.",
  "Searching for grocery stores...": "Buscando tiendas...",
  "Searching nearby stores...": "Buscando tiendas cercanas...",
  "Store search error:": "Error al buscar tiendas:",
};

function getLanguage() {
  return languageSelect?.value || localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en";
}

function translateText(text) {
  if (getLanguage() !== "es") return text;
  return SPANISH_TEXT[text] || text;
}

function translateNodeValue(value) {
  const match = String(value).match(/^(\s*)(.*?)(\s*)$/s);
  if (!match || !match[2]) return value;
  return `${match[1]}${translateText(match[2])}${match[3]}`;
}

function applyLanguage() {
  const language = getLanguage();
  document.documentElement.lang = language === "es" ? "es" : "en";
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!originalTextNodes.has(node)) {
      originalTextNodes.set(node, node.nodeValue);
    }
    node.nodeValue = translateNodeValue(originalTextNodes.get(node));
  }
  document.querySelectorAll("[placeholder]").forEach((element) => {
    if (!element.dataset.i18nPlaceholder) {
      element.dataset.i18nPlaceholder = element.getAttribute("placeholder") || "";
    }
    element.setAttribute("placeholder", translateText(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[aria-label]").forEach((element) => {
    if (!element.dataset.i18nAriaLabel) {
      element.dataset.i18nAriaLabel = element.getAttribute("aria-label") || "";
    }
    element.setAttribute("aria-label", translateText(element.dataset.i18nAriaLabel));
  });
}

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
const SNAP101_PANEL_IDS = new Set(["snap101-snap", "snap101-nutrition"]);
const SNAP101_DEFAULT_PANEL_ID = "snap101-snap";
const SNAPP_PANEL_IDS = new Set([
  "account",
  "onboarding",
  "home",
  "dishes",
  "schedule",
  "shopping",
  "my",
  "pantry",
  "budget",
  "information",
  "settings",
]);
const SNAP_MAX_ALLOTMENTS = {
  1: 298,
  2: 546,
  3: 785,
  4: 994,
  5: 1183,
  6: 1421,
  7: 1571,
  8: 1789,
};
const SNAP_ADDITIONAL_MEMBER_ALLOTMENT = 218;
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
  navButtons.forEach((button) =>
    button.classList.toggle("active", button.dataset.target === targetId)
  );

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
  return Boolean(currentUser && currentUserInfo && !currentUserInfo.onboarding_completed);
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
      removeButton.setAttribute("aria-label", `Remove ${preference}`);
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
      dietary_preferences: selectedDietaryPreferences,
      dietary_restrictions: dietaryRestrictionsInput.value.trim(),
      onboarding_completed: Boolean(currentUserInfo?.onboarding_completed),
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
  snapEstimateOutput.textContent = `${currencyFormatter.format(estimate)} estimated monthly benefit`;
  snapEstimateOutput.setAttribute(
    "aria-label",
    `${currencyFormatter.format(maximumAllotment)} maximum allotment minus ${currencyFormatter.format(expectedContribution)} estimated contribution`
  );
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
  onboardingProgressLabel.textContent = `${onboardingStepIndex + 1} of ${ONBOARDING_TOTAL_STEPS}`;
  onboardingProgressBar.style.width = `${progressValue}%`;
  onboardingBackButton.hidden = onboardingStepIndex === 0;
  onboardingContinueButton.textContent =
    onboardingStepIndex === ONBOARDING_TOTAL_STEPS - 1 ? "Start finding meals" : "Continue";
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
    setOnboardingStatus("Enter a valid 5-digit US ZIP code.", "error");
    onboardingStepIndex = 0;
    renderOnboardingStep();
    return false;
  }

  setOnboardingStatus("Saving your setup...");
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
  syncSettingsFromUserInfo(currentUser, currentUserInfo);
  setOnboardingStatus("Setup saved.", "success");
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

    itemText.textContent = isTraditionalSpice(item.name)
      ? `${canonicalSpiceName(item.name)} - pantry spice`
      : `${item.name} - ${item.quantity}`;
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

async function addPantryItems(items) {
  if (!supabaseClient || !currentUser || !items.length) return false;

  setPantryStatus(`Adding ${items.length} pantry item${items.length === 1 ? "" : "s"}...`);
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
  setPantryStatus(`${items.length} pantry item${items.length === 1 ? "" : "s"} added.`, "success");
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
    if (renderId !== authRenderSequence) return;
  }

  renderAccountForAuthState();
  syncSettingsFromUserInfo(user, currentUserInfo);
  syncSnapCalculatorHouseholdSize();
  if (user && currentUserInfo && !currentUserInfo.onboarding_completed) {
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
    setAuthStatus(`Signed in as ${getDisplayUsername(user)}.`, "success");
    if (activeAppMode === "snapp" && isOnboardingRequired()) {
      showPanel(ONBOARDING_PANEL_ID);
    } else if (activeAppMode === "snapp" && document.querySelector(".panel.visible")?.id === ONBOARDING_PANEL_ID) {
      showPanel(SIGNED_IN_DEFAULT_PANEL_ID);
    }
    return;
  }

  if (wasSignedIn) {
    showAuthMode("sign-in");
    setAuthStatus("Signed out.", "success");
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
    setFavoriteRecipesStatus("Sign in and configure Supabase to save favorite recipes.", "error");
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
    setFavoriteRecipesStatus("No favorite recipes yet.");
    return;
  }

  setFavoriteRecipesStatus(`${favoriteRecipes.length} favorite recipe${favoriteRecipes.length === 1 ? "" : "s"}`);
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
    title.textContent = favorite.recipe_name || dish.name || "Favorite recipe";
    meta.textContent = [
      formatServings(dish),
      dish.estimated_price_total
        ? `${currencyFormatter.format(dish.estimated_price_total)} estimated groceries`
        : "",
    ].filter(Boolean).join(" | ");
    actions.className = "favorite-recipe-actions";

    queueButton.type = "button";
    queueButton.textContent = isQueued ? "In queue" : "Add to queue";
    queueButton.disabled = isQueued;
    queueButton.addEventListener("click", () => addMealToSchedule(dish));

    removeButton.type = "button";
    removeButton.textContent = "Remove";
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
    ? "Add selected to pantry"
    : "Add all to pantry";
  shoppingAddPantryButton.disabled = !items.length;
}

function renderShoppingList() {
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
    emptyItem.textContent = "Add dishes to your schedule to build a shopping list.";
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
      checkbox.setAttribute("aria-label", `Select ${item.name}`);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selectedShoppingIngredientIds.add(item.id);
        } else {
          selectedShoppingIngredientIds.delete(item.id);
        }
        listItem.classList.toggle("selected", checkbox.checked);
        updateShoppingAddButton(items);
      });

      details.textContent = `${item.name} - get ${item.quantity} (${item.dishName})`;
      if (item.unavailable) {
        details.textContent += " - unavailable";
      }

      addButton.type = "button";
      addButton.textContent = "Add to pantry";
      addButton.addEventListener("click", async () => {
        addButton.disabled = true;
        shoppingStatus.textContent = `Adding ${item.name} to pantry...`;
        const wasAdded = await addPantryItem(item.name, item.quantity);
        if (wasAdded) {
          pantryHandledShoppingIngredientIds.add(item.id);
          selectedShoppingIngredientIds.delete(item.id);
          shoppingStatus.textContent = `${item.name} added to pantry.`;
          renderShoppingList();
          return;
        }
        shoppingStatus.textContent = "Could not add ingredient to pantry.";
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

async function loadScheduledMeals() {
  scheduledMeals.splice(0, scheduledMeals.length);

  if (!currentUser) {
    renderSchedule();
    return;
  }

  if (!supabaseClient) {
    loadScheduledMealsFromStorage();
    renderSchedule();
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
    return;
  }

  scheduledMeals.splice(
    0,
    scheduledMeals.length,
    ...(data || []).map(normalizeScheduledMeal)
  );
  saveScheduledMealsToStorage();
  renderSchedule();
}

function renderSchedule() {
  scheduleCalendar.replaceChildren();
  scheduleRecipeList.replaceChildren();

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
    empty.textContent = "Added recipes will appear here.";
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
    empty.textContent = "Drop recipe";
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
  price.textContent = currencyFormatter.format(meal.estimated_price_total || 0);
  openButton.appendChild(price);
  openButton.addEventListener("click", () => openDishModal(meal));

  removeButton.type = "button";
  removeButton.className = "schedule-meal-remove";
  removeButton.textContent = "Remove";
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
      .eq("id", scheduleId);
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
        .eq("id", replacedMeal.schedule_id);
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

  const scheduledMeal = {
    ...dish,
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
      await consumePantryForScheduledDish(dish);
      renderSchedule();
      showPanel("schedule");
      return;
    }
  }

  scheduledMeals.push(scheduledMeal);
  saveScheduledMealsToStorage();
  await consumePantryForScheduledDish(dish);
  renderSchedule();
  showPanel("schedule");
}

function openDishModal(dish) {
  const recipe = dish.recipe || {};
  dishModalTitle.textContent = dish.name || "Recipe";
  dishModalContent.replaceChildren();

  const summary = document.createElement("p");
  summary.className = "dish-modal-summary";
  summary.textContent = [
    formatServings(dish),
    dish.estimated_price_total
      ? `${currencyFormatter.format(dish.estimated_price_total)} estimated groceries`
      : "",
  ].filter(Boolean).join(" | ");
  dishModalContent.appendChild(summary);

  appendModalSection("Recipe ingredients", recipe.ingredients || [], (ingredient) =>
    ingredient.display || ingredient.measure || ingredient.name
  );
	  appendModalSection("Ingredients to buy", (dish.ingredients_to_buy || dish.ingredients || []).filter(
	    (ingredient) => !(ingredient.unavailable || ingredient.availability_status === "unavailable")
	  ), (ingredient) => {
	    const storeText = ingredient.store_name ? ` at ${ingredient.store_name}` : "";
	    const priceText = ingredient.estimated_price_total
	      ? ` - ${currencyFormatter.format(ingredient.estimated_price_total)}`
	      : "";
	    const sourceText = ingredient.recipe_measure || ingredient.required_quantity_display;
	    const requirementText = sourceText ? `${sourceText} -> ` : "";
	    const purchaseText = ingredient.purchase_quantity_display || formatPurchaseQuantity(ingredient);
	    const packageText = purchaseText ? `, get ${purchaseText}` : ingredient.package_size ? ` (${ingredient.package_size})` : "";
	    return `${requirementText}${ingredient.product_name || ingredient.name}${packageText}${storeText}${priceText}`;
	  });

  const instructionsHeading = document.createElement("h4");
  const instructions = document.createElement("p");
  instructionsHeading.textContent = "Instructions";
  instructions.textContent =
    recipe.instructions || dish.method || "Open the source recipe for cooking instructions.";
  dishModalContent.append(instructionsHeading, instructions);

  if (recipe.source || recipe.youtube) {
    const links = document.createElement("p");
    links.className = "dish-recipe-links";
    if (recipe.source) {
      const sourceLink = document.createElement("a");
      sourceLink.href = recipe.source;
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
      sourceLink.textContent = "Recipe source";
      links.appendChild(sourceLink);
    }
    if (recipe.youtube) {
      if (links.childNodes.length) links.append(" | ");
      const youtubeLink = document.createElement("a");
      youtubeLink.href = recipe.youtube;
      youtubeLink.target = "_blank";
      youtubeLink.rel = "noopener noreferrer";
      youtubeLink.textContent = "Video";
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

function appendModalSection(title, items, formatter) {
  const heading = document.createElement("h4");
  const list = document.createElement("ul");
  heading.textContent = title;
  list.className = "dish-modal-list";
  if (!items.length) {
    const item = document.createElement("li");
    item.textContent = "None available.";
    list.appendChild(item);
  }
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = formatter(value);
    list.appendChild(item);
  });
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
    emptyItem.textContent = translateText("No stores selected.");
    selectedStoreList.appendChild(emptyItem);
    return;
  }

  savedMyStores.forEach((store) => {
    const item = document.createElement("li");
    const itemText = document.createElement("span");
    const removeButton = document.createElement("button");

    itemText.textContent = store.name;
    removeButton.type = "button";
    removeButton.textContent = translateText("Remove");
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
    myStoreStatus.textContent = translateText("Map library could not load. Store list is still available.");
  }

  if (!stores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = translateText("No stores found for this search.");
    myStoreResults.appendChild(emptyItem);
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
    saleIngredientsStatus.textContent = "No recipe-ready sale ingredients found.";
    return;
  }
  saleIngredientsStatus.textContent = `${items.length} shown from today's ranked pool`;
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "sale-ingredient-card";

    const category = document.createElement("span");
    category.className = "sale-category";
    category.textContent = item.category || "grocery";

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
    sale.textContent = formatSaleMoney(item.sale_price) || item.price_display || "Sale price available";
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
    button.textContent = "Generate recipes with this ingredient";
    button.addEventListener("click", () => generateRecipesForSaleIngredient(item));

    card.append(category, title, product, priceRow, meta, button);
    saleIngredientsGrid.appendChild(card);
  });
}

async function loadSaleIngredients() {
  if (!saleIngredientsGrid || !saleIngredientsStatus) return;
  saleIngredientsStatus.textContent = "Loading sales...";
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
  const prompt = item.ingredient_name || item.product_name || ingredientId;
  const params = new URLSearchParams(window.location.search);
  params.set("panel", "dishes");
  params.set("sale_ingredient", ingredientId);
  window.history.replaceState({}, "", `${window.location.pathname}?${params.toString()}`);
  showPanel("dishes");
  appendDishMessage("user", `Recipes with ${prompt}`);
  startDishProgress();
  dishSource.hidden = true;
  try {
    const data = await fetchDishes(prompt, { saleIngredientId: ingredientId });
    renderDishes(data);
    setDishStatus(`Found ${Math.min(data.dishes.length, 3)} recipe ${data.dishes.length === 1 ? "match" : "matches"} using ${prompt}.`);
    dishSource.hidden = false;
  } catch (error) {
    appendDishMessage("bot", `Dish search error: ${error.message}`);
    setDishStatus(`Dish search error: ${error.message}`);
  }
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
  storeResults.replaceChildren();
  if (!stores.length) {
    const emptyItem = document.createElement("li");
    emptyItem.textContent = translateText("No stores found for this search.");
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
      snapNote.textContent = `${translateText("SNAP accepted")}${store.snap_source ? ` (${store.snap_source})` : ""}`;
      item.appendChild(snapNote);
    } else {
      const snapNote = document.createElement("p");
      snapNote.textContent = translateText("SNAP acceptance not verified");
      item.appendChild(snapNote);
    }

    const links = document.createElement("div");
    links.className = "store-links";
    if (store.latitude != null && store.longitude != null) {
      const mapLink = document.createElement("a");
      mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(store.latitude)}&mlon=${encodeURIComponent(store.longitude)}#map=17/${encodeURIComponent(store.latitude)}/${encodeURIComponent(store.longitude)}`;
      mapLink.target = "_blank";
      mapLink.rel = "noopener noreferrer";
      mapLink.textContent = translateText("View on map");
      links.appendChild(mapLink);
    }

    if (store.website) {
      const websiteLink = document.createElement("a");
      websiteLink.href = store.website;
      websiteLink.target = "_blank";
      websiteLink.rel = "noopener noreferrer";
      websiteLink.textContent = translateText("Visit website");
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
      ? `Here are three recipe matches using ${data.meal_prompt}.`
      : "Here are three recipe matches I found."
    : "I could not find recipe matches for that request.";
  cards.className = "dish-card-grid";
  botMessage.append(intro, cards);

  data.dishes.slice(0, 3).forEach((dish) => {
    cards.appendChild(createDishCard(dish));
  });

  if (data.used_relaxed_matches) {
    const relaxed = document.createElement("p");
    relaxed.className = "dish-missing";
    relaxed.textContent = "No exact match was found, so SNAPP is showing the closest affordable real recipes.";
    botMessage.appendChild(relaxed);
  }

  if (data.missing_ingredients?.length) {
    const missing = document.createElement("p");
    missing.className = "dish-missing";
    missing.textContent = `No USDA match found for: ${data.missing_ingredients.join(", ")}.`;
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
    title.textContent = dish.name;
    header.append(title, favoriteButton);
    price.className = "dish-price";
    price.textContent = dish.estimated_price_total
      ? `${currencyFormatter.format(dish.estimated_price_total)} estimated grocery total | ${currencyFormatter.format(dish.estimated_price_per_serving)} per serving`
      : "No grocery price match";
    metadata.className = "dish-metadata";
    metadata.textContent = [
      formatServings(dish),
      dish.cook_time_minutes ? `${dish.cook_time_minutes} min` : "",
      ...(dish.dietary_tags || []),
    ].filter(Boolean).join(" | ");
    totalNutrition.className = "dish-nutrition";
    totalNutrition.textContent = [
      `${nutritionTotal.protein_g || "x g"} protein`,
      `${nutritionTotal.carbohydrates_g || "x g"} carbs`,
      `${nutritionTotal.fat_g || "x g"} fat`,
      `${nutritionTotal.fiber_g || "x g"} fiber`,
    ].join(" | ");
    scheduleButton.type = "button";
    scheduleButton.className = "add-to-schedule-button";
    scheduleButton.textContent = "Add to schedule";
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
      relaxedMessage.textContent = "Closest affordable match; some filters were relaxed.";
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

signOutButton.addEventListener("click", handleSignOut);
accountPanelSignOutButton?.addEventListener("click", handleSignOut);

storeSearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = zipCodeInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    storeSearchStatus.textContent = translateText("Enter a valid 5-digit US ZIP code.");
    storeResults.replaceChildren();
    storeSource.hidden = true;
    return;
  }

  const submitButton = storeSearchForm.querySelector("button");
  submitButton.disabled = true;
  storeSearchStatus.textContent = translateText("Searching for grocery stores...");
  storeResults.replaceChildren();
  storeSource.hidden = true;

  try {
    const data = await fetchStores(zipCode, { snapOnly: false });
    const stores = data.stores || [];
    renderStores(stores);
    storeSearchStatus.textContent =
      getLanguage() === "es"
        ? stores.length
          ? `Se encontraron ${stores.length} tienda${stores.length === 1 ? "" : "s"} cerca de ${data.location}.`
          : `No se encontraron tiendas en ${data.location}.`
        : stores.length
          ? `${stores.length} grocery store${stores.length === 1 ? "" : "s"} found near ${data.location}.`
          : `No grocery stores were found in ${data.location}.`;
    storeSource.hidden = false;
  } catch (error) {
    storeSearchStatus.textContent = `${translateText("Store search error:")} ${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

myStoreForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const zipCode = myZipCodeInput.value.trim();
  if (!/^\d{5}$/.test(zipCode)) {
    myStoreStatus.textContent = translateText("Enter a valid 5-digit US ZIP code.");
    myStoreResults.replaceChildren();
    myStoreSource.hidden = true;
    clearMyStoreMap();
    renderSelectedMyStores();
    return;
  }

  const submitButton = myStoreForm.querySelector("button");
  submitButton.disabled = true;
  myStoreStatus.textContent = translateText("Searching nearby stores...");
  myStoreResults.replaceChildren();
  myStoreSource.hidden = true;
  clearMyStoreMap();
  renderSelectedMyStores();

  try {
    const data = await fetchStores(zipCode, { snapOnly: false });
    renderMyStores(data);
    const stores = data.stores || [];
    let statusMessage =
      getLanguage() === "es"
        ? stores.length
          ? `Se encontraron ${stores.length} tienda${stores.length === 1 ? "" : "s"} cerca de ${data.location}.`
          : `No se encontraron tiendas cerca de ${data.location}.`
        : stores.length
          ? `${stores.length} grocery store${stores.length === 1 ? "" : "s"} found near ${data.location}.`
          : `No grocery stores were found near ${data.location}.`;
    try {
      const traderJoesData = await fetchTraderJoesStore(zipCode);
      const store = traderJoesData.store;
      const didSaveStoreNumber = await saveTraderJoesStoreNumber(traderJoesData);
      if (store && didSaveStoreNumber) {
        statusMessage +=
          getLanguage() === "es"
            ? ` Numero de tienda Trader Joe's ${store.store_number} guardado para ${store.name}.`
            : ` Trader Joe's store number ${store.store_number} saved for ${store.name}.`;
      }
    } catch (error) {
      statusMessage +=
        getLanguage() === "es"
          ? ` No se pudo resolver el numero de tienda Trader Joe's: ${error.message}`
          : ` Trader Joe's store number could not be resolved: ${error.message}`;
    }
    myStoreStatus.textContent = statusMessage;
  } catch (error) {
    myStoreStatus.textContent = `${translateText("Store search error:")} ${error.message}`;
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
    setPantryStatus("Enter both a food name and quantity.", "error");
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
  shoppingStatus.textContent = `Adding ${itemsToAdd.length} ingredient${itemsToAdd.length === 1 ? "" : "s"} to pantry...`;

  const wasAdded = await addPantryItems(itemsToAdd);
  if (wasAdded) {
    itemsToAdd.forEach((item) => pantryHandledShoppingIngredientIds.add(item.id));
    selectedShoppingIngredientIds.clear();
    shoppingStatus.textContent = `${itemsToAdd.length} ingredient${itemsToAdd.length === 1 ? "" : "s"} added to pantry.`;
    renderShoppingList();
  } else {
    shoppingStatus.textContent = "Could not add ingredients to pantry.";
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
    setDishStatus(`Found ${Math.min(data.dishes.length, 3)} recipe ${data.dishes.length === 1 ? "match" : "matches"} with grocery price estimates.`);
    dishSource.hidden = false;
  } catch (error) {
    appendDishMessage("bot", `Dish search error: ${error.message}`);
    setDishStatus(`Dish search error: ${error.message}`);
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

themeSelect.addEventListener("change", () => {
  document.body.classList.toggle("dark-theme", themeSelect.value === "dark");
});

if (languageSelect) {
  languageSelect.value = localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en";
  languageSelect.addEventListener("change", () => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, languageSelect.value);
    applyLanguage();
  });
}

notificationsToggle.addEventListener("change", () => {
  const status = notificationsToggle.checked ? "enabled" : "disabled";
  setSettingsStatus(`Daily reminders ${status}.`);
  queueSettingsSave();
});

dietSelect.addEventListener("change", () => {
  setSettingsStatus(`Dietary preference set to ${dietSelect.value}.`);
  queueSettingsSave();
});

populatePantrySpiceSuggestions();
updatePantryQuantityVisibility();
applyLanguage();
renderSchedule();
showAuthMode("sign-in");
initializeAuth();
handleInitialUrlState();
