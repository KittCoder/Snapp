const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const c={window:{},Intl};vm.runInNewContext(fs.readFileSync('Web/quantity_display.js','utf8'),c);const format=c.window.SNAPP_FORMAT_QUANTITY;
test('calculation units display as familiar kitchen measures without changing the source',()=>{
 for(const [q,unit,expected] of [[236.588,'milliliter','1 cup'],[118.294,'milliliter','1/2 cup'],[1.2322291666666667,'milliliter','1/4 teaspoon'],[4.928916666666667,'milliliter','1 teaspoon'],[4,'egg','4 eggs'],[1,'egg','1 egg']]){
  const original={quantity:q,unit};assert.equal(format(original),expected);assert.equal(original.quantity,q);
 }
});
