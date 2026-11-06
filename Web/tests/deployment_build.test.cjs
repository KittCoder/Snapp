const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const env={...process.env,SNAPP_BUILD_MODE:'production',SNAPP_API_BASE_URL:'https://snapp-a64d.onrender.com',SUPABASE_URL:'https://wmagmsatawlwvcobtkxh.supabase.co',SUPABASE_ANON_KEY:'sb_publishable_fixture',TYPESENSE_API_KEY:'should-not-ship'};
test('release build emits public config and i18n, excluding backend credentials',()=>{
 cp.execFileSync(process.execPath,['scripts/build_frontend.cjs'],{cwd:root,env});
 const html=fs.readFileSync(path.join(root,'dist/index.html'),'utf8');assert.match(html,/sb_publishable_fixture/);assert.match(html,/<base href="\/"/);assert.doesNotMatch(html,/should-not-ship/);assert.ok(fs.existsSync(path.join(root,'dist/i18n/es.json')));
});
test('release build rejects privileged Supabase credentials and localhost production APIs',()=>{
 for(const change of [{SUPABASE_ANON_KEY:'sb_secret_fixture'},{SNAPP_API_BASE_URL:'http://localhost:5000'}])assert.notEqual(cp.spawnSync(process.execPath,['scripts/build_frontend.cjs'],{cwd:root,env:{...env,...change}}).status,0);
});
test('release HTML versions local assets by content and omits store onboarding',()=>{
 cp.execFileSync(process.execPath,['scripts/build_frontend.cjs'],{cwd:root,env});
 const html=fs.readFileSync(path.join(root,'dist/index.html'),'utf8');
 const hash=require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'dist/app.js'))).digest('hex').slice(0,12);
 assert.ok(html.includes(`src="app.js?v=${hash}"`));
 assert.doesNotMatch(html,/onboarding_store\.js|id="onboarding-store"|id="home-change-store"/);
 assert.match(html,/href="looks\.css\?v=[a-f0-9]{12}"/);
 assert.match(html,/Morton Williams/);
 const config=JSON.parse(fs.readFileSync(path.join(root,'vercel.json'),'utf8'));
 assert.ok(config.headers.some(rule=>rule.headers.some(header=>header.key==='Cache-Control'&&header.value.includes('must-revalidate'))));
});
