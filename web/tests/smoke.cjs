// Isolated contract fixtures are never used by the web application.
const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');
const durable=new Map();let storageFails=false;let uncertain=true;
const storage={getItem:key=>durable.get(key)||null,setItem(key,value){if(storageFails)throw Error('QuotaExceededError');durable.set(key,value);}};
const response=data=>({ok:true,status:200,json:async()=>({ok:true,...data})});
async function browser(username='alice',origin='http://nas.local:7120'){
 const elements=new Map();const calls=[];
 const element=selector=>{if(!elements.has(selector))elements.set(selector,{hidden:false,value:selector==='#downloader'?'all':'',innerHTML:'',textContent:'',disabled:false,open:false,children:[],classList:{toggle(){}},setAttribute(){},addEventListener(){},querySelectorAll(){return [];},focus(){},append(){},showModal(){this.open=true;},close(){this.open=false;},querySelector(){return element('button');}});return elements.get(selector);};
 const context=vm.createContext({document:{querySelector:element,createElement:()=>element('created'),hidden:false},location:{origin},localStorage:storage,crypto:require('node:crypto').webcrypto,URLSearchParams,FileReader:class{},FormData:class{},console,setTimeout(){return 1;},clearTimeout(){},setInterval(){},confirm:()=>false,fetch:async(url,options)=>{
  calls.push({url,options});if(url.endsWith('/health'))return response({configured:false,version:'0.1.0'});
  if(url.includes('/tasks?')){const q=new URL(url,'http://local').searchParams;const offset=Number(q.get('offset')),limit=Number(q.get('limit'));return response({items:Array.from({length:Math.min(limit,251-offset)},(_,i)=>({id:String(offset+i),downloader_id:'one',name:'<unsafe & task>',total_size:1024,progress:.5,state:'downloading',download_speed:10,upload_speed:0})),total:251,summary:{download_speed:2510,upload_speed:0,downloading:251,total:251},errors:[]});}
  if(url.includes('/operations/'))return response({operation:{status:uncertain?'uncertain':'completed',message:'checked'}});
  if(url.endsWith('/action'))return response({operation:{status:'uncertain',message:'timeout'}});throw Error('Unexpected fixture request '+url);
 }});
 const run=code=>vm.runInContext(code,context);vm.runInContext(source,context);await new Promise(setImmediate);run(`initializePending(${JSON.stringify(username)})`);
 return {run,element,calls,posts:()=>calls.filter(c=>c.options.method==='POST')};
}
const action="operation('/tasks/one/id/action',{request_id:uuid(),action:'pause',delete_data:false},document.querySelector('button'))";
(async()=>{
 const first=await browser();await first.run('state.limit=300;refresh()');const taskCalls=first.calls.filter(c=>c.url.includes('/tasks?'));assert.equal(taskCalls.length,2);assert(taskCalls.every(c=>Number(new URL(c.url,'http://local').searchParams.get('limit'))<=200));assert.equal(first.run('state.tasks.length'),251);assert(first.element('#tasks').innerHTML.includes('&lt;unsafe &amp; task&gt;'));assert(first.element('#tasks').innerHTML.includes('1.0 KB'));assert(!first.element('#tasks').innerHTML.includes('style='));
 await first.run(action);await first.run(action);assert.equal(first.posts().length,1,'Identical uncertain action must never be resubmitted');const originalId=first.run('[...pendingOperations.values()][0]');assert(first.calls.every(c=>c.options.headers['X-Nas-Request']==='1'));
 const reopened=await browser();assert.equal(reopened.run('[...pendingOperations.values()][0]'),originalId,'Closing browser must preserve original UUID');await reopened.run(action);assert.equal(reopened.posts().length,0,'Reopened browser may only query original receipt');assert(reopened.calls.some(c=>c.url.endsWith('/operations/'+originalId)));
 const differentAccount=await browser('bob');assert.equal(differentAccount.run('pendingOperations.size'),0,'Accounts must not share pending receipts');
 const differentOrigin=await browser('alice','http://other-nas:7120');assert.equal(differentOrigin.run('pendingOperations.size'),0,'NAS origins must not share pending receipts');
 const blocked=await browser('blocked');storageFails=true;await blocked.run(action);assert.equal(blocked.posts().length,0,'Persistence failure must prevent all POSTs');assert(blocked.element('#toast').textContent.includes('本次操作未提交'));assert.equal(blocked.run('state.busy'),false);storageFails=false;
 uncertain=false;await reopened.run('pollOperation([...pendingOperations.values()][0])');assert.equal(reopened.run('pendingOperations.size'),0);const afterConfirmation=await browser();assert.equal(afterConfirmation.run('pendingOperations.size'),0,'Confirmed receipt removal must persist');
 console.log('PASS: pagination >200, total_size, safe escaping, CSP progress, request headers, persistent UUID across browser reopen, account/origin isolation, storage failure zero POST, read-only confirmation');
})().catch(e=>{console.error(e);process.exitCode=1;});

