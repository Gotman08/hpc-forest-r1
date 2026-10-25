// Execute the offline dashboard against its real report data and minimal DOM API.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.resolve(__dirname, '../../outputs/forest-corrections-20261024/TABLEAU-DE-BORD.html'), 'utf8');
const dataText = html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const source = html.match(/<\/script><script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const [, id] of html.matchAll(/id="([^"]+)"/g)) elements.set(id, {textContent:'', innerHTML:''});
elements.get('data').textContent = dataText;
const buttons = ['sgemm', 'utf8', 'mandelbrot'].map(caseId => ({
  dataset:{case:caseId}, attributes:{}, handlers:{},
  setAttribute(k,v){this.attributes[k]=v;},
  addEventListener(k,v){this.handlers[k]=v;}
}));
const context = vm.createContext({document:{
  getElementById(id){assert(elements.has(id), id); return elements.get(id);},
  querySelectorAll(selector){assert.equal(selector,'[data-case]'); return buttons;}
}});
new vm.Script(source).runInContext(context);
const expected = {sgemm:1,utf8:1,mandelbrot:2};
for (const button of buttons){
  button.handlers.click();
  assert.equal(button.attributes['aria-pressed'], 'true');
  assert.equal(buttons.filter(b=>b.attributes['aria-pressed']==='true').length,1);
  assert.equal((elements.get('timings').innerHTML.match(/<tr>/g)||[]).length, expected[button.dataset.case]);
  assert.equal((elements.get('engines').innerHTML.match(/<tr>/g)||[]).length,3);
  assert.equal((elements.get('analysts').innerHTML.match(/<tr>/g)||[]).length,2);
  assert(elements.get('case-note').textContent.length>60);
  assert(!elements.get('timings').innerHTML.includes('NaN'));
  assert(!elements.get('timings').innerHTML.includes('undefined'));
}
assert(elements.get('tests').textContent.includes('895'));
const result={passed:true,tabs_checked:3,comparison_rows:4,method:'Real-data JavaScript/DOM-contract check; not a screenshot/layout test'};
fs.writeFileSync(path.join(__dirname,'dashboard-validation.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify(result));
