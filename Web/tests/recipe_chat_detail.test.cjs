const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../app.js'), 'utf8');
class Element {
  constructor(tag = 'div') { this.tag = tag; this.children = []; this.listeners = {}; this.value = ''; this.hidden = false; this.classList = { contains: () => false }; }
  append(...nodes) { nodes.forEach(n => { n.parent = this; this.children.push(n); }); }
  appendChild(node) { this.append(node); }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  after(node) { this.afterNode = node; }
  setAttribute(k, v) { this[k] = v; }
  addEventListener(k, fn) { this.listeners[k] = fn; }
  querySelectorAll() { return []; }
  reportValidity() { return true; }
  focus() {}
  remove() { this.parent.children = this.parent.children.filter(n => n !== this); }
  get childElementCount() { return this.children.length; }
}
function text(node) { return [node.textContent || '', ...node.children.map(text)].join(' '); }
function setup() {
  const elements = new Map();
  const listeners = {};
  const document = { getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); }, createElement: tag => new Element(tag), querySelector: () => null, addEventListener: (event, callback) => { listeners[event] = callback; } };
  const calls = []; let scheduledMeals = [];
  const context = vm.createContext({ document, AbortController, console,
    window: { location: { hostname: 'localhost' }, setTimeout, clearTimeout },
    t: (key, values = {}) => { const catalog = JSON.parse(fs.readFileSync(require('node:path').join(__dirname, '../i18n/en.json'), 'utf8')); return (catalog[key] || '').replace(/\{(\w+)\}/g, (m,k) => values[k] == null ? m : String(values[k])); },
    getLanguage: () => 'en', getHouseholdSize: () => 2,
    householdSizeInput: { value: '2' }, pantryItems: [],
    getApiEndpoints: () => [],
    formatServings: dish => dish.recipe.servings ? `${dish.recipe.servings} servings` : '',
    fetch: async (url, options) => {
      const body = JSON.parse(options.body); calls.push({ url, body });
      if (url.endsWith('/chat')) return { ok: true, json: async () => ({ message: 'Recipes', state: { last_result_ids: ['r1', 'r2'] }, results: [{ id: 'r1', title: 'First' }, { id: 'r2', title: 'Second' }] }) };
      return { ok: true, json: async () => ({ dish: { recipe_id: body.recipe_id, name: 'Full second', recipe: { ingredients: [{ display: '2 eggs' }, { display: '1 cup rice' }], instructions: ['Beat eggs', 'Cook rice'] } } }) };
    },
    scheduledMeals, supabaseClient: null, currentUser: null,
    saveScheduledMealsToStorage: () => {}, consumePantryForScheduledDish: async () => {}, renderSchedule: () => {}, showPanel: () => {},
    pantryHandledShoppingIngredientIds: new Set(), getIngredientQuantity: i => i.display,
    getShoppingCategory: () => 'Other',
  });
  for (const [start, end] of [
    ['function demoPrice(', 'function getHouseholdSize('],
    ['function recipeItemList(', 'function appendModalSection('],
    ['async function addMealToSchedule(', 'function openDishModal('],
    ['function getIngredientName(', 'function getIngredientQuantity('],
    ['function getShoppingIngredients(', 'function updateShoppingSelectionControls('],
  ]) {
    let a = source.indexOf(start), b = source.indexOf(end, a);
    if (b < 0) b = source.indexOf('\nfunction ', a + 10);
    vm.runInContext(source.slice(a, b), context);
  }
  vm.runInContext(source.slice(source.indexOf('const recipeChat = (() =>'), source.indexOf('// End experimental Recipe Chat.')), context);
  return { context, elements, calls, scheduledMeals, listeners };
}
test('click opens full recipe; back preserves draft, history and follow-up state; schedule feeds shared shopping list', async () => {
  const { context, elements, calls, scheduledMeals } = setup();
  const form = elements.get('recipe-chat-form'); const input = elements.get('recipe-chat-input'); const history = elements.get('recipe-chat-history');
  input.value = 'breakfast with eggs'; await form.listeners.submit({ preventDefault() {} });
  const reply = history.children[1]; const card = reply.children[2].children[1];
  input.value = 'my draft';
  await card.listeners.click();
  const detail = history.afterNode;
  assert.match(text(detail), /2 eggs/); assert.match(text(detail), /1 cup rice/); assert.match(text(detail), /Beat eggs/);
  assert.equal(calls.find(call => call.body.include_sale_matches).body.recipe_id, 'r2');
  assert.doesNotMatch(text(detail), /servings|nutrition|rating|estimated/);
  await detail.children.at(-1).listeners.click();
  assert.equal(scheduledMeals.length, 1); assert.equal(scheduledMeals[0].recipe_id, 'r2'); assert.equal(scheduledMeals[0].name, 'Full second');
  assert.equal(vm.runInContext('getShoppingIngredients().length', context), 2);
  detail.children[0].listeners.click();
  assert.equal(history.hidden, false); assert.equal(history.children[1], reply); assert.equal(input.value, 'my draft');
  input.value = 'something quicker'; await form.listeners.submit({ preventDefault() {} });
  assert.deepEqual(calls.filter(call => call.url.endsWith('/chat')).at(-1).body.state, { last_result_ids: ['r1', 'r2'] });
  await vm.runInContext('addMealToSchedule({recipe_id:"r2",name:"Duplicate"})', context);
  assert.equal(scheduledMeals.length, 1);
  await vm.runInContext('addMealToSchedule({recipe_id:"dishes-id",name:"Dishes meal",recipe:{ingredients:[{name:"salt"}]}})', context);
  assert.equal(scheduledMeals.length, 2);
  assert.equal(vm.runInContext('getShoppingIngredients().length', context), 3);
});
test('Dishes and Chat share authenticated persistence', async () => {
  const { context, scheduledMeals } = setup();
  let saved;
  context.currentUser = { id: 'user-1' };
  context.supabaseClient = { from: table => { assert.equal(table, 'user_scheduled_meals'); return { insert(record) { saved = record; return { select: () => ({ single: async () => ({ data: { id: 'saved-id', meal_data: record.meal_data } }) }) }; } }; } };
  context.normalizeScheduledMeal = record => ({ ...record.meal_data, schedule_id: record.id });
  await vm.runInContext('addMealToSchedule({recipe_id:"r2",name:"Second"})', context);
  assert.equal(saved.user_id, 'user-1'); assert.equal(saved.meal_data.recipe_id, 'r2'); assert.equal(scheduledMeals[0].schedule_id, 'saved-id');
});
test('detail network failure preserves results and draft', async () => {
  const { context, elements } = setup();
  const form = elements.get('recipe-chat-form'); const input = elements.get('recipe-chat-input'); const history = elements.get('recipe-chat-history');
  input.value = 'chicken dinner'; await form.listeners.submit({ preventDefault() {} });
  const reply = history.children[1]; input.value = 'draft';
  context.fetch = async () => { throw Error('private failure'); };
  await reply.children[2].children[0].listeners.click();
  assert.match(text(history.afterNode), /Couldn't load this recipe/);
  assert.doesNotMatch(text(history.afterNode), /private failure/);
  history.afterNode.children[0].listeners.click();
  assert.equal(input.value, 'draft'); assert.equal(history.children[1], reply);
});
test('missing optional fields render safely and keyboard opens recipe', async () => {
  const { context, elements } = setup();
  const input = elements.get('recipe-chat-input'); const history = elements.get('recipe-chat-history');
  input.value = 'eggs'; await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  context.fetch = async () => ({ ok: true, json: async () => ({ dish: { recipe_id: 'r1', name: 'Eggs', recipe: {} } }) });
  const card = history.children[1].children[2].children[0];
  card.listeners.keydown({ key: 'Enter', preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(text(history.afterNode), /Cooking instructions are unavailable/);
  assert.doesNotMatch(text(history.afterNode), /servings|Equipment|minutes|nutrition|rating/);
});
test('schedule failure leaves detail and chat available', async () => {
  const { context, elements, scheduledMeals } = setup();
  const input = elements.get('recipe-chat-input'); const history = elements.get('recipe-chat-history');
  input.value = 'chicken'; await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  const reply = history.children[1]; await reply.children[2].children[0].listeners.click();
  context.fetch = async () => ({ ok: false });
  const button = history.afterNode.children.at(-1);
  await button.listeners.click();
  assert.equal(button.disabled, false); assert.equal(scheduledMeals.length, 0);
  assert.match(text(history.afterNode), /Couldn't add this recipe/);
  assert.equal(history.children[1], reply);
});
test('shared list renderer preserves Dishes ingredient text', () => {
  const { context } = setup();
  context.dishModalContent = new Element();
  vm.runInContext(source.slice(source.indexOf('function appendModalSection('), source.indexOf('function dishIngredientText(')), context);
  vm.runInContext('appendModalSection("Recipe ingredients", [{display:"2 eggs"}], item => item.display)', context);
  assert.match(text(context.dishModalContent), /Recipe ingredients.*2 eggs/);
  vm.runInContext('appendModalSection("Ingredients to buy", [], item => item.display)', context);
  assert.match(text(context.dishModalContent), /None available/);
});

test('recipe sale badges require verified offers and preserve original ingredient text', async () => {
  const { context, elements } = setup();
  const form = elements.get('recipe-chat-form');
  elements.get('recipe-chat-input').value = 'eggs';
  await form.listeners.submit({ preventDefault() {} });
  context.fetch = async () => ({ ok: true, json: async () => ({ dish: {
    recipe_id: 'r1', name: 'Eggs', recipe: { ingredients: [{ display: '2 eggs' }, { display: 'rice' }] },
    sale_ingredients: [
      { recipe_display: '2 eggs', is_on_sale: true, product_name: 'Farm eggs', sale_offer: '2 for $5' },
      { recipe_display: 'rice', is_on_sale: false, product_name: 'Rice' },
    ],
  } }) });
  await elements.get('recipe-chat-history').children[1].children[2].children[0].listeners.click();
  const detailText = text(elements.get('recipe-chat-history').afterNode);
  assert.match(detailText, /2 eggs On sale Farm eggs · 2 for \$5/);
  assert.equal((detailText.match(/On sale/g) || []).length, 1);
});

test('weekly nutrition sums one portion, handles totals and excludes missing data', () => {
  const meals = [
    { nutrition_per_person: { protein_g: 20, carbohydrates_g: 30, fat_g: 10 } },
    { servings: 2, nutrition_total: { protein_g: 60, carbohydrates_g: 80, fat_g: 30 } },
    { nutrition_per_person: { protein_g: 'x g', carbohydrates_g: 'x g', fat_g: 'x g' } },
  ];
  const context = vm.createContext({ scheduledMeals: meals, getServingCount: meal => meal.servings || 1 });
  vm.runInContext(source.slice(source.indexOf('function getPortionMacroValue('), source.indexOf('function setMacroBar(')), context);
  assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(getScheduledMacroTotals())', context)), { protein: 50, carbs: 70, fat: 25 });
  meals.splice(0, 1);
  assert.equal(vm.runInContext('getScheduledMacroTotals().protein', context), 30);
});

test('populated pantry renders food names and quantities without store data', () => {
  const { context } = setup();
  const pantryList = new Element('ul');
  Object.assign(context, { pantryList, currentUser: { id: 'user' },
    pantryItems: [{ id: 'rice', name: 'Rice', quantity: '2 cups' }],
    isTraditionalSpice: () => false, canonicalSpiceName: value => value,
    setPantryStatus: () => {}, deletePantryItem: () => {},
  });
  vm.runInContext(source.slice(source.indexOf('function renderPantryItems('), source.indexOf('async function loadPantryItems(')), context);
  vm.runInContext('renderPantryItems()', context);
  assert.match(text(pantryList), /Rice 2 cups Remove/);
});
test('recipe cards and detail use translated titles and every translated recipe line', async () => {
  const { context, elements } = setup();
  context.getLanguage = () => 'es';
  context.fetch = async (url) => ({ ok: true, json: async () => url.endsWith('/chat') ? {
    message: 'Recetas', state: { last_result_ids: ['translated'] },
    results: [{ id: 'translated', title: 'Chicken dinner', ingredient_names: ['chicken'] }],
    localized_results: [{ id: 'translated', title: 'Cena de pollo', ingredient_names: ['pollo'] }],
  } : { dish: {
    recipe_id: 'translated', name: 'Chicken dinner',
    recipe: { name: 'Chicken dinner', ingredients: [{ display: '2 eggs' }], instructions: ['Beat eggs.'] },
    localized_recipe: { name: 'Cena de pollo', ingredients: [{ display: '2 huevos' }],
      instructions: ['Bate los huevos.'], _translation_status: 'translated' },
  } } });
  const input = elements.get('recipe-chat-input'); input.value = 'pollo';
  await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  const history = elements.get('recipe-chat-history');
  assert.match(text(history), /Cena de pollo/);
  assert.doesNotMatch(text(history), /Chicken dinner/);
  await history.children[1].children[2].children[0].listeners.click();
  assert.match(text(history.afterNode), /Cena de pollo/);
  assert.match(text(history.afterNode), /2 huevos/);
  assert.match(text(history.afterNode), /Bate los huevos/);
  assert.doesNotMatch(text(history.afterNode), /Chicken dinner|2 eggs|Beat eggs/);
});
test('switching language reloads existing recipe cards in the chosen language', async () => {
  const { context, elements, listeners } = setup();
  elements.get('recipe-chat-input').value = 'dinner';
  await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  const history = elements.get('recipe-chat-history');
  const resultList = history.children[1].children[2];
  const card = resultList.children[0];
  card.isConnected = true;
  card.replaceWith = replacement => { resultList.children[0] = replacement; };
  history.querySelectorAll = () => [card];
  history.afterNode.hidden = true;
  context.getLanguage = () => 'fr';
  context.fetch = async () => ({ ok: true, json: async () => ({ dish: {
    recipe_id: 'r1', name: 'First', recipe: { name: 'First' },
    localized_recipe: { name: 'Premier plat', ingredients: [{ display: '2 œufs' }] },
  } }) });
  listeners['snapp:localechange']({ detail: { locale: 'fr' } });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(text(resultList.children[0]), /Premier plat/);
  assert.match(text(resultList.children[0]), /2 œufs/);
  assert.doesNotMatch(text(resultList.children[0]), /First/);
});
test('legacy default-store estimates are hidden until active-store basket pricing', async () => {
  const { context, elements, calls, scheduledMeals } = setup();
  const originalFetch = context.fetch;
  context.fetch = async (url, options) => {
    const response = await originalFetch(url, options);
    const data = await response.json();
    if (data.dish) data.dish.grocery_estimate = { total: 12.5, status: 'complete', currency: 'USD' };
    return { ok: true, json: async () => data };
  };
  elements.get('recipe-chat-input').value = 'dinner';
  await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  const history = elements.get('recipe-chat-history');
  assert.doesNotMatch(text(history), /\$12\.50/);
  assert.doesNotMatch(text(history), /estimated groceries/);

  assert.equal(scheduledMeals.length, 0);
  assert.ok(!calls.some(call => call.body.include_price_estimate));
  await history.children[1].children[2].children[0].listeners.click();
  assert.doesNotMatch(text(history.afterNode), /\$12\.50/);
  assert.equal(scheduledMeals.length, 0);
});
test('partial estimates are labeled as subtotals and never look like a complete price', async () => {
  const { context, elements } = setup();
  const originalFetch = context.fetch;
  context.fetch = async (url, options) => {
    const data = await (await originalFetch(url, options)).json();
    if (data.dish) data.dish.grocery_estimate = { total: 8.25, status: 'partial' };
    return { ok: true, json: async () => data };
  };
  elements.get('recipe-chat-input').value = 'dinner';
  await elements.get('recipe-chat-form').listeners.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  const history = elements.get('recipe-chat-history');
  assert.doesNotMatch(text(history), /\$8\.25/);
  assert.doesNotMatch(text(history), /estimated groceries/);
});
test('sale ingredient action routes to Recipe Chat and starts an ingredient search', async () => {
  const { context, elements } = setup();
  context.URLSearchParams = URLSearchParams;
  context.window.location.search = ''; context.window.location.pathname = '/';
  let panel, destination, submissions = 0;
  context.showPanel = value => { panel = value; };
  context.window.history = { replaceState: (state, title, url) => { destination = url; } };
  elements.get('recipe-chat-form').requestSubmit = () => { submissions++; };
  vm.runInContext(source.slice(source.indexOf('async function generateRecipesForSaleIngredient('), source.indexOf('async function handleInitialUrlState(')), context);
  await vm.runInContext('generateRecipesForSaleIngredient({ingredient_id:"chicken",ingredient_name:"Chicken"})', context);
  assert.equal(panel, 'recipe-chat');
  assert.match(destination, /panel=recipe-chat/);
  assert.equal(elements.get('recipe-chat-input').value, 'Recipes with Chicken');
  assert.equal(submissions, 1);
});
test('adding a saved dish calculates USDA nutrition before persisting it', async () => {
  const { context, scheduledMeals } = setup();
  context.fetch = async (url, options) => {
    assert.ok(url.endsWith('/nutrition'));
    const data = JSON.parse(options.body);
    assert.equal(data.recipe.ingredients[0].display, '2 eggs');
    return { ok: true, json: async () => ({
      nutrition_source: 'USDA FoodData Central', nutrition_status: 'complete', nutrition_servings: 2,
      nutrition_total: { protein_g: 12, carbohydrates_g: 2, fat_g: 10 },
      nutrition_per_person: { protein_g: 6, carbohydrates_g: 1, fat_g: 5 },
    }) };
  };
  await vm.runInContext('addMealToSchedule({recipe_id:"saved-eggs",name:"Eggs",recipe:{servings:2,ingredients:[{display:"2 eggs"}]}})', context);
  assert.equal(scheduledMeals.length, 1);
  assert.equal(scheduledMeals[0].nutrition_source, 'USDA FoodData Central');
  assert.equal(scheduledMeals[0].nutrition_per_person.protein_g, 6);
});
test('actual Recipe Chat response renders cards before one canonical store-price batch finishes',async()=>{
  const {context,elements}=setup();
  context.window.SNAPP_ACTIVE_STORE={id:'ctown:PS41_311'};
  context.window.SNAPP_STORES={stores:[{id:'ctown:PS41_311',retailer:'ctown',address:'330 Graham Avenue'}]};
  context.getApiEndpoints=p=>[p];
  const create=context.document.createElement;context.document.createElement=tag=>{const e=create(tag);e.dataset={};e.isConnected=true;return e;};
  const requests=[];let finish;
  context.fetch=async(url,options)=>{
    const body=JSON.parse(options.body);requests.push({url,body});
    if(url.endsWith('/chat'))return {ok:true,json:async()=>({message:'Recipes',state:{},results:Array.from({length:5},(_,i)=>({id:'r'+i,title:'Rice '+i,servings:4,ingredients_text:['8 oz rice','2 oz butter']}))})};
    return new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({store_id:body.store_id,prices:body.recipes.map(r=>({id:body.store_id,recipe_id:r.id,inventory_version:'v1',complete:true,basket_total:6.92,checkout_total_known:6.92,unknown_cost_items:[]}))})});});
  };
  for(const file of ['recipe_requirements.js','recipe_store_prices.js'])vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../',file),'utf8'),context);
  elements.get('recipe-chat-input').value='rice';
  await elements.get('recipe-chat-form').listeners.submit({preventDefault(){}});
  assert.match(text(elements.get('recipe-chat-history')),/Rice 4/);
  assert.equal(requests.filter(r=>r.url.endsWith('/store-prices')).length,1);
  assert.deepEqual(requests[1].body.recipes[0].ingredients,['8 oz rice','2 oz butter']);
  assert.doesNotMatch(text(elements.get('recipe-chat-history')),/\$6.92/);
  finish();await new Promise(resolve=>setImmediate(resolve));
  assert.match(text(elements.get('recipe-chat-history')),/C-Town — 330 Graham Avenue/);
  assert.match(text(elements.get('recipe-chat-history')),/\$6.92 total/);
});
test('scheduling preserves source quantities and serving intent without consuming pantry before basket allocation',async()=>{
 const {context,scheduledMeals}=setup();let consumed=0;
 context.window.SNAPP_ACTIVE_STORE={id:'ctown:PS41_311'};
 context.consumePantryForScheduledDish=async()=>{consumed++;};
 const dish={recipe_id:'r-quantity',name:'Beef',recipe:{servings:4,ingredients:[{name:'ground beef',display:'1 lb ground beef',measure:'1 pound ground beef'}]}};
 await context.addMealToSchedule(dish);
 assert.equal(consumed,0);assert.equal(scheduledMeals[0].target_servings,2);
 const saved=JSON.parse(JSON.stringify(scheduledMeals[0]));
 assert.equal(saved.recipe.ingredients[0].display,'1 lb ground beef');assert.equal(saved.recipe.servings,4);
});
