/* One quantity-preserving request representation for chat, saved meals and comparison. */
(() => {
  'use strict';
  window.SNAPP_RECIPE_REQUIREMENTS = (meal, index=0) => {
    const original=meal.pricing_recipe || meal.recipe || meal;
    const clean=item=>typeof item==='string'?item:Object.fromEntries(Object.entries(item||{}).filter(([key])=>['name','nameClean','original','originalName','amount','quantity','quantity_text','unit','raw','text','note','recipe_ingredient','recipe_measure','display','measure','type'].includes(key)));
    const source=Number(original.source_servings || original.servings);
    const requested=Number(meal.target_servings || original.target_servings || (typeof getHouseholdSize==='function'?getHouseholdSize():source));
    return {id:String(meal.recipe_id || original.id || meal.schedule_id || index),name:meal.name || original.title || original.name,
      ...(source>0?{source_servings:source,...(requested>0?{target_servings:requested}:{})}:{}),
      ...(original.extendedIngredients?.length?{extendedIngredients:original.extendedIngredients.map(clean)}:{ingredients:(original.ingredients_text?.length?original.ingredients_text:original.ingredients || meal.ingredients || []).map(clean)})};
  };
})();
