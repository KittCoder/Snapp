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
  const document = { getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); }, createElement: tag => new Element(tag), querySelector: () => null };
  const calls = []; let scheduledMeals = [];
  const context = vm.createContext({ document, AbortController, console,
    window: { location: { hostname: 'localhost' }, setTimeout, clearTimeout },
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
  return { context, elements, calls, scheduledMeals };
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
  assert.equal(calls[1].body.recipe_id, 'r2');
  assert.doesNotMatch(text(detail), /servings|nutrition|rating|estimated/);
  await detail.children.at(-1).listeners.click();
  assert.equal(scheduledMeals.length, 1); assert.equal(scheduledMeals[0].recipe_id, 'r2'); assert.equal(scheduledMeals[0].name, 'Full second');
  assert.equal(vm.runInContext('getShoppingIngredients().length', context), 2);
  detail.children[0].listeners.click();
  assert.equal(history.hidden, false); assert.equal(history.children[1], reply); assert.equal(input.value, 'my draft');
  input.value = 'something quicker'; await form.listeners.submit({ preventDefault() {} });
  assert.deepEqual(calls.at(-1).body.state, { last_result_ids: ['r1', 'r2'] });
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
