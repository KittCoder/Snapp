const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('Web/app.js','utf8');
function setup(){
 let finish;const saved=new Promise(resolve=>finish=resolve),deletes=[];
 const c=vm.createContext({window:{SNAPP_ACTIVE_STORE:{}},currentUser:{id:'u'},scheduledMeals:[],getHouseholdSize:()=>2,hasNutritionIngredients:()=>false,
  saveScheduledMealsToStorage(){},renderSchedule(){c.paints=(c.paints||0)+1;},showPanel(){},
  normalizeScheduledMeal:data=>({...data.meal_data,schedule_record_id:data.id}),
  supabaseClient:{from:()=>({insert:()=>({select:()=>({single:()=>saved})}),delete:()=>({eq(k,v){deletes.push([k,v]);return this;}})})}});
 vm.runInContext(source.slice(source.indexOf('async function addMealToSchedule('),source.indexOf('function openDishModal(')),c);
 return {c,deletes,finish};
}
test('schedule and budget can update before the cloud save completes, without duplicate meals',async()=>{
 const s=setup(),dish={recipe_id:'r',name:'Rice',recipe:{servings:4,ingredients:['1 cup rice']}};
 const pending=s.c.addMealToSchedule(dish);assert.equal(s.c.scheduledMeals.length,1);assert.equal(s.c.paints,1);
 await s.c.addMealToSchedule(dish);assert.equal(s.c.scheduledMeals.length,1);
 s.finish({data:{id:7,meal_data:s.c.scheduledMeals[0]},error:null});await pending;
 assert.equal(s.c.scheduledMeals[0].schedule_record_id,7);assert.equal(s.c.scheduledMeals.length,1);
});
test('removing a meal during its save does not restore it or leave an unwanted cloud record',async()=>{
 const s=setup(),pending=s.c.addMealToSchedule({recipe_id:'r',name:'Rice'}),meal=s.c.scheduledMeals.pop();
 s.finish({data:{id:7,meal_data:meal},error:null});await pending;
 assert.equal(s.c.scheduledMeals.length,0);assert.deepEqual(s.deletes,[['id',7],['user_id','u']]);
});
