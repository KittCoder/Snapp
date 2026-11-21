/* Presentation only: preserve full precision in requests, pantry transfers and costing. */
(() => {
 'use strict';
 const units={teaspoon:['teaspoon','teaspoons'],tablespoon:['tablespoon','tablespoons'],cup:['cup','cups'],ounce:['ounce','ounces'],pound:['pound','pounds'],gram:['gram','grams'],milliliter:['mL','mL'],liter:['liter','liters'],egg:['egg','eggs'],onion:['onion','onions'],tomato:['tomato','tomatoes'],slice:['slice','slices'],leaf:['leaf','leaves'],roll:['roll','rolls'],count:['item','items'],each:['item','items']};
 const number=n=>{
  if(n>0&&n<.01)return '< 0.01';
  const whole=Math.floor(n),part=n-whole;
  for(const [a,b] of [[1,8],[1,4],[1,3],[1,2],[2,3],[3,4]])if(Math.abs(part-a/b)<.002)return (whole?whole+' ':'')+a+'/'+b;
  return new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(n);
 };
 window.SNAPP_FORMAT_QUANTITY=q=>{
  let n=Number(q.quantity??q.base_quantity),unit=q.unit||q.base_unit;
  if(!Number.isFinite(n))return 'Quantity unverified';
  if(unit==='milliliter'){
   if(n>=59&&Math.abs(n/236.588*8-Math.round(n/236.588*8))<.01){n/=236.588;unit='cup';}
   else if(n>=14&&Math.abs(n/(236.588/16)*4-Math.round(n/(236.588/16)*4))<.01){n/=236.588/16;unit='tablespoon';}
   else if(n<15){n/=236.588/48;unit='teaspoon';}
  }else if(unit==='gram'){
   if(n>=1000){n/=1000;unit='kilogram';}
   else if(n>=28&&Math.abs(n/28.3495*4-Math.round(n/28.3495*4))<.01){n/=28.3495;unit='ounce';}
  }
  const names=units[unit]||[unit||'',unit||''];return `${number(n)} ${names[n>0&&n<=1+1e-6?0:1]}`.trim();
 };
})();
