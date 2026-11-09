/* PyPilot UI. Models, filesystem operations, and tools are owned by Python. */
'use strict';
const $ = id => document.getElementById(id);
const token = window.__PYPILOT_TOKEN__;
delete window.__PYPILOT_TOKEN__;
const icons = {
  folder:'<path d="M3 7V5a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v12H3z"/>',
  files:'<path d="M8 3h8l4 4v14H8z"/><path d="M16 3v5h4M4 7v12"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  network:'<rect x="8" y="3" width="8" height="5" rx="1"/><rect x="2" y="16" width="6" height="5" rx="1"/><rect x="16" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M5 16v-4h14v4"/>',
  settings:'<path d="m9 3-.5 3-2 1-2.5-1-2 3 2 2v2l-2 2 2 3 2.5-1 2 1 .5 3h4l.5-3 2-1 2.5 1 2-3-2-2v-2l2-2-2-3-2.5 1-2-1-.5-3z"/><circle cx="11" cy="12" r="3"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  refresh:'<path d="M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 3M4 16l2 3a8 8 0 0 0 13-3"/>',
  shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  save:'<path d="M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8"/>',
  clear:'<path d="m5 18 9-13 6 4-8 12H6zM3 21h18"/>',
  chevron:'<path d="m6 9 6 6 6-6"/>',
  play:'<path d="m8 5 11 7-11 7z"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
  history:'<path d="M3 11a9 9 0 1 1 3 8M3 5v6h6M12 7v6l4 2"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6"/>',
  code:'<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
  attach:'<path d="m9 12 6-6a4 4 0 0 1 6 6l-9 9a6 6 0 0 1-8-8l10-10a2 2 0 0 1 3 3L7 16"/>',
  arrow:'<path d="M12 20V4m-7 7 7-7 7 7"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3"/>',
};
function drawIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[el.dataset.icon]||icons.code}</svg>`;});}
drawIcons();
const state={files:[], settings:{}, tabs:new Map(), current:null, editor:null, session:null, run:null, mode:'agent', attached:new Set(), streamBody:null, toolCards:new Map(), approvals:new Map(), searchMode:'files', completion:false};
let toastTimer;
function toast(message,error=false){$('toast').textContent=message;$('toast').classList.toggle('error',error);$('toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),5000);}
function safe(fn){return async(...args)=>{try{return await fn(...args);}catch(e){toast(e.message||String(e),true);}};}
async function api(path, options={}){
  const headers={Authorization:'Bearer '+token,...options.headers};
  if(options.body && typeof options.body!=='string'){options.body=JSON.stringify(options.body);headers['Content-Type']='application/json';}
  const response=await fetch('/api'+path,{...options,headers});
  if(!response.ok){let error;try{error=await response.json();}catch{error={detail:'服务请求失败（'+response.status+'）'};}throw new Error(typeof error.detail==='string'?error.detail:JSON.stringify(error.detail));}
  return options.raw?response:response.json();
}
function el(tag, cls, text){const item=document.createElement(tag);if(cls)item.className=cls;if(text!==undefined)item.textContent=text;return item;}
function openDialog(id){if(!$(id).open)$(id).showModal();}
document.querySelectorAll('[data-close]').forEach(btn=>btn.onclick=()=>$(btn.dataset.close).close());
document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}}));

function modelConfigured(){return state.settings.has_key||/^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])[:/]/.test(state.settings.base_url||'');}
function updateModel(){
  $('model-name').textContent=modelConfigured()?state.settings.model:'配置模型后开始';
  $('model-chip').querySelector('.dot').classList.toggle('muted',!modelConfigured());
}
function setRunning(running){$('send-button').classList.toggle('hidden',running);$('stop-button').classList.toggle('hidden',!running);$('run-dot').classList.toggle('running',running);$('run-dot').classList.remove('waiting');$('run-status').textContent=running?'正在处理任务':'准备就绪';if(!running)$('step-count').textContent='';}
function renderFiles(){
  const root=$('file-tree');root.replaceChildren();
  const folders=new Set();
  state.files.forEach(file=>{
    const parts=file.path.split('/');
    parts.slice(0,-1).forEach((part,i)=>{const key=parts.slice(0,i+1).join('/');if(!folders.has(key)){folders.add(key);const row=el('div','tree-folder');row.style.paddingLeft=(15+i*13)+'px';row.append(el('span','','⌄'),el('span','','▱'),el('span','',part));root.append(row);}});
    const row=el('button','tree-file'+(state.current===file.path?' active':''));row.title=file.path;row.style.paddingLeft=(20+(parts.length-1)*13)+'px';row.dataset.path=file.path;
    row.append(el('span','file-icon'+(file.path.endsWith('.md')?' md':''),file.python?'PY':file.path.endsWith('.md')?'M↓':'◇'),el('span','',parts.at(-1)));row.onclick=safe(()=>openFile(file.path));root.append(row);
  });
  $('python-count').textContent=state.files.filter(f=>f.python).length+' 个 Python 文件';
}
async function refreshFiles(){state.files=await api('/files');renderFiles();}
function language(path){if(path.endsWith('.py'))return'python';if(path.endsWith('.md'))return'markdown';if(path.endsWith('.json'))return'json';if(path.endsWith('.toml')||path.endsWith('.yaml'))return'plaintext';return'plaintext';}
function renderTabs(){
  $('tabs').replaceChildren();
  for(const [path,tab] of state.tabs){
    const button=el('button','tab'+(state.current===path?' active':''));
    button.append(el('span','file-icon',path.endsWith('.py')?'PY':'◇'),el('span','',path.split('/').at(-1)));
    const close=el('span','tab-close'+(tab.dirty?' tab-dirty':''),tab.dirty?'●':'×');close.onclick=e=>{e.stopPropagation();if(tab.dirty&&!confirm('关闭此文件会丢弃未保存的修改，是否继续？'))return;tab.model.dispose();state.tabs.delete(path);if(state.current===path){state.current=null;const next=state.tabs.keys().next().value;if(next)activateFile(next);else{state.editor.setModel(null);$('empty-editor').classList.remove('hidden');}}renderTabs();renderFiles();};button.append(close);button.onclick=()=>activateFile(path);$('tabs').append(button);
  }
}
function activateFile(path){const tab=state.tabs.get(path);if(!tab)return;if(state.current&&state.tabs.has(state.current))state.tabs.get(state.current).view=state.editor.saveViewState();state.current=path;state.editor.setModel(tab.model);if(tab.view)state.editor.restoreViewState(tab.view);$('empty-editor').classList.add('hidden');$('file-breadcrumb').textContent=path.replaceAll('/','  /  ');$('file-modified').textContent=tab.dirty?'未保存':'';$('language-label').textContent=language(path)==='python'?'Python':language(path);renderTabs();renderFiles();state.editor.focus();}
async function openFile(path,line){
  if(!state.tabs.has(path)){
    const data=await api('/file?path='+encodeURIComponent(path));
    const model=monaco.editor.createModel(data.content,language(path),monaco.Uri.parse('file:///'+path));
    const tab={model,version:data.version,dirty:false,saved:data.content};state.tabs.set(path,tab);
    model.onDidChangeContent(()=>{tab.dirty=model.getValue()!==tab.saved;renderTabs();if(state.current===path)$('file-modified').textContent=tab.dirty?'未保存':'';});
  }
  activateFile(path);if(line){state.editor.setPosition({lineNumber:line,column:1});state.editor.revealLineInCenter(line);}
}
async function saveCurrent(){if(!state.current)return;const tab=state.tabs.get(state.current);const content=tab.model.getValue();const saved=await api('/file',{method:'PUT',body:{path:state.current,content,version:tab.version}});tab.version=saved.version;tab.saved=content;tab.dirty=tab.model.getValue()!==content;renderTabs();$('file-modified').textContent=tab.dirty?'未保存':'';toast('已保存 '+state.current);await refreshFiles();}
async function reloadChanged(path){
  if(!path)return;
  const tab=state.tabs.get(path);
  if(tab){if(tab.dirty){toast(path+' 已在磁盘改变；你的未保存内容仍保留，请手动合并。',true);return;}const fresh=await api('/file?path='+encodeURIComponent(path));tab.saved=fresh.content;tab.version=fresh.version;tab.model.setValue(fresh.content);tab.dirty=false;renderTabs();}
  await refreshFiles();
}
async function openWorkspace(){if(state.run)throw new Error('请先停止当前任务');if([...state.tabs.values()].some(t=>t.dirty)&&!confirm('切换项目会丢弃未保存的修改，是否继续？'))return;if(window.pywebview?.api){const path=await window.pywebview.api.choose_folder();if(path)await switchWorkspace(path);}else{$('path-title').textContent='打开项目';$('path-input').value=state.workspace;$('path-input').placeholder='文件夹绝对路径';state.pathAction='workspace';openDialog('path-dialog');}}
async function switchWorkspace(path){const data=await api('/workspace',{method:'POST',body:{path}});state.editor.setModel(null);for(const t of state.tabs.values())t.model.dispose();state.tabs.clear();state.current=null;state.session=null;state.attached.clear();updateBootstrap(data);resetChat();renderTabs();$('empty-editor').classList.remove('hidden');$('file-breadcrumb').textContent='选择一个文件开始';toast('已打开 '+data.name);}
function updateBootstrap(data){state.workspace=data.workspace;state.files=data.files;state.settings=data.settings;$('workspace-name').textContent=data.name;$('tree-root').textContent=data.name.toUpperCase();$('status-project').textContent=data.name;renderFiles();updateModel();}
function resetChat(){state.streamBody=null;state.toolCards.clear();state.approvals.clear();$('chat').replaceChildren(welcomeTemplate.cloneNode(true));state.attached.clear();renderChips();bindSuggestions();}
function setMode(mode){state.mode=mode;document.querySelectorAll('.mode-switch button').forEach(btn=>btn.classList.toggle('active',btn.dataset.mode===mode));}
function renderChips(){$('context-chips').replaceChildren();for(const path of state.attached){const chip=el('button','context-chip',path.split('/').at(-1)+'  ×');chip.title=path;chip.onclick=()=>{state.attached.delete(path);renderChips();};$('context-chips').append(chip);}}
function scrollChat(){const chat=$('chat');chat.scrollTop=chat.scrollHeight;}
function removeWelcome(){$('chat-welcome')?.remove();}
function richText(body,text){body.replaceChildren();const parts=text.split(/```[^\n]*\n([\s\S]*?)```/g);parts.forEach((part,i)=>{if(i%2){const pre=el('pre');const code=el('code','',part);pre.append(code);body.append(pre);}else body.append(document.createTextNode(part));});}
function message(role,text){removeWelcome();const wrap=el('div','message '+role);const head=el('div','message-header');head.append(el('span','mini-logo',role==='user'?'◦':'p›'),el('span','',role==='user'?'你':'PyPilot'));const body=el('div','message-body');richText(body,text);wrap.append(head,body);$('chat').append(wrap);scrollChat();return body;}
function notice(text,error=false){removeWelcome();const item=el('div','notice'+(error?' error':''));item.append(el('span','',error?'!':'·'),el('span','',text));$('chat').append(item);scrollChat();}
function prettyResult(result){if(result.stdout!==undefined)return`exit_code: ${result.exit_code}${result.timed_out?' · 超时':''}${result.truncated?' · 输出已截断':''}\n\n${result.stdout}${result.stderr?'\n[stderr]\n'+result.stderr:''}`;if(result.text!==undefined)return result.text+(result.remaining_lines?`\n\n还有 ${result.remaining_lines} 行，下次 offset=${result.next_offset}`:'');if(result.diff)return result.diff;return JSON.stringify(result,null,2);}
function toolStart(event){removeWelcome();const card=el('details','tool-card');const summary=el('summary');summary.append(el('span','',event.tool.startsWith('mcp_')?'◇':'⌘'),el('span','',event.tool),el('span','tool-state','执行中'));const pre=el('pre','',event.arguments||'');card.append(summary,pre);$('chat').append(card);state.toolCards.set(event.call_id,card);scrollChat();}
function toolResult(event){const card=state.toolCards.get(event.call_id);const failed=!event.ok||event.result.exit_code&&event.result.exit_code!==0;if(card){card.classList.toggle('failed',!!failed);card.querySelector('.tool-state').textContent=failed?'失败':'完成';card.querySelector('pre').textContent=prettyResult(event.result);if(failed)card.open=true;}
  if(event.tool==='bash'){$('console-panel').classList.remove('collapsed');$('console-output').textContent+='\n'+prettyResult(event.result)+'\n';$('console-output').scrollTop=$('console-output').scrollHeight;}
  if(event.result.path&&['edit','write'].includes(event.tool))safe(()=>reloadChanged(event.result.path))();
  scrollChat();
}
function approval(event){
  state.approvals.set(event.approval_id,event);$('run-dot').classList.add('waiting');$('run-status').textContent='等待你的确认';
  const card=el('div','approval-card');card.id='approval-'+event.approval_id;
  card.append(el('div','approval-title',event.preview?'审阅文件修改':event.tool.startsWith('mcp_')?'确认外部 MCP 调用':'确认运行命令'));
  card.append(el('div','approval-detail',event.preview?event.preview.path+`\n${event.preview.old_lines} 行 → ${event.preview.new_lines} 行`:event.args.command||JSON.stringify(event.args,null,2)));
  const actions=el('div','approval-actions');
  if(event.preview){const view=el('button','view-diff','查看差异');view.onclick=()=>showDiff(event);actions.append(view);}
  const reject=el('button','','拒绝');reject.onclick=safe(()=>respondApproval(event.approval_id,false));
  const accept=el('button','accept',event.preview?'接受并写入':'允许执行');accept.onclick=safe(()=>respondApproval(event.approval_id,true));actions.append(reject,accept);card.append(actions);$('chat').append(card);scrollChat();
}
async function respondApproval(id,accept){if(!state.run)throw new Error('任务已结束');await api('/runs/'+state.run+'/approve',{method:'POST',body:{id,accept}});const card=$('approval-'+id);if(card){card.querySelectorAll('button').forEach(b=>b.disabled=true);card.querySelector('.approval-title').textContent=accept?'已允许执行':'已拒绝，未执行';}state.approvals.delete(id);$('run-dot').classList.remove('waiting');$('run-status').textContent='正在处理任务';}
let diffEditor=null,diffModels=[];
function showDiff(event){$('diff-title').textContent=event.preview.path;$('diff-summary').textContent=`${event.preview.old_lines} 行 → ${event.preview.new_lines} 行 · 写入前再次校验文件版本`;openDialog('diff-dialog');if(!diffEditor)diffEditor=monaco.editor.createDiffEditor($('diff-editor'),{theme:'pypilot',automaticLayout:true,readOnly:true,renderSideBySide:true,fontSize:12,minimap:{enabled:false},originalEditable:false});diffModels.forEach(m=>m.dispose());diffModels=[monaco.editor.createModel(event.preview.before,language(event.preview.path)),monaco.editor.createModel(event.preview.after,language(event.preview.path))];diffEditor.setModel({original:diffModels[0],modified:diffModels[1]});$('diff-accept').disabled=!state.approvals.has(event.approval_id);$('diff-reject').disabled=!state.approvals.has(event.approval_id);$('diff-accept').onclick=safe(async()=>{await respondApproval(event.approval_id,true);$('diff-dialog').close();});$('diff-reject').onclick=safe(async()=>{await respondApproval(event.approval_id,false);$('diff-dialog').close();});setTimeout(()=>diffEditor.layout(),40);}
async function handleEvent(event,terminal=false){
  switch(event.type){
    case'user':if(!terminal)message('user',event.text);break;
    case'context':notice(`已读取项目地图 · ${event.python_files} 个 Python 模块`);$('console-shell').textContent=event.shell;break;
    case'step':$('step-count').textContent=`${event.step} / ${event.max_steps}`;state.streamBody=null;break;
    case'token':if(!state.streamBody){state.streamBody=message('assistant','');state.streamText='';}state.streamText+=event.delta;state.streamBody.textContent=state.streamText;scrollChat();break;
    case'assistant':if(state.streamBody)richText(state.streamBody,event.text);else if(event.text)message('assistant',event.text);state.streamBody=null;break;
    case'tool_start':toolStart(event);break;
    case'tool_result':toolResult(event);break;
    case'approval':approval(event);break;
    case'mcp':$('mcp-dot').classList.toggle('muted',!event.servers.some(s=>s.ok));for(const s of event.servers.filter(s=>!s.ok))notice('MCP '+s.name+'：'+s.error,true);break;
    case'notice':notice(event.text);break;
    case'error':notice(event.text,true);break;
    case'done':notice(event.text,event.reason==='timeout'||event.reason==='step_limit');break;
  }
}
async function readEvents(id,terminal=false){
  let after=-1,retries=0;
  while(true){
    try{
      const response=await api(`/runs/${id}/events?after=${after}`,{raw:true});const reader=response.body.getReader();const decoder=new TextDecoder();let buffer='';
      while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let split;while((split=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,split);buffer=buffer.slice(split+2);for(const line of block.split('\n')){if(line.startsWith('data: ')){const event=JSON.parse(line.slice(6));if(event.id>after){after=event.id;await handleEvent(event,terminal);}}}}}
      break;
    }catch(error){if(retries++<2){await new Promise(r=>setTimeout(r,700));continue;}notice('连接中断，任务可能仍在后端运行。点击停止结束任务，或刷新窗口恢复连接。',true);throw error;}
  }
  state.run=null;setRunning(false);for(const [aid]of state.approvals){const card=$('approval-'+aid);if(card){card.querySelectorAll('button').forEach(b=>b.disabled=true);card.querySelector('.approval-title').textContent='任务已结束，此操作未执行';}}state.approvals.clear();await refreshFiles();
}
async function sendPrompt(){
  const prompt=$('prompt').value.trim();if(!prompt)return;if(state.run)throw new Error('请等待当前任务完成或先停止');if(!modelConfigured()){showSettings();toast('先配置模型服务；本地 Ollama 可不填 Key');return;}
  if([...state.tabs.values()].some(t=>t.dirty))throw new Error('请先保存打开文件中的修改，再让 Agent 操作项目');
  const run=await api('/runs',{method:'POST',body:{prompt,mode:state.mode,session_id:state.session,attachments:[...state.attached]}});state.session=run.session_id;state.run=run.id;$('prompt').value='';setRunning(true);await readEvents(run.id);
}
async function stopRun(){if(!state.run)return;const id=state.run;$('run-status').textContent='正在终止进程…';await api('/runs/'+id+'/cancel',{method:'POST'});state.run=null;setRunning(false);toast('任务已停止');}
function bindSuggestions(){document.querySelectorAll('.suggestion').forEach(btn=>btn.onclick=()=>{setMode(btn.dataset.mode);$('prompt').value=btn.dataset.prompt;$('prompt').focus();});}
const welcomeTemplate=$('chat-welcome').cloneNode(true);
bindSuggestions();

function showSettings(){const s=state.settings;$('setting-url').value=s.base_url||'';$('setting-model').value=s.model||'';$('setting-completion').value=s.completion_model||'';$('setting-key').value='';$('setting-key').placeholder=s.has_key?'已保存密钥；留空保持不变':'粘贴 API Key（本地模型可留空）';$('setting-steps').value=s.max_steps||16;$('setting-timeout').value=s.timeout||180;$('key-note').textContent=s.has_key?'已配置 · '+s.key_storage+' · 不进入项目或前端状态':'密钥仅保存在本机，不进入项目或前端状态。';$('connection-result').textContent='';openDialog('settings-dialog');}
async function saveSettings(close=true){state.settings=await api('/settings',{method:'POST',body:{base_url:$('setting-url').value.trim(),model:$('setting-model').value.trim(),completion_model:$('setting-completion').value.trim(),api_key:$('setting-key').value,max_steps:Number($('setting-steps').value),timeout:Number($('setting-timeout').value)}});$('setting-key').value='';updateModel();if(close){$('settings-dialog').close();toast('模型配置已保存 · 密钥：'+state.settings.key_storage);}}
async function testModel(){await saveSettings(false);const result=$('connection-result');result.classList.remove('error');result.textContent='正在发送一条简短测试请求…';$('test-model').disabled=true;try{const response=await api('/model-test',{method:'POST'});result.textContent='连接成功 · '+response.text;}catch(e){result.classList.add('error');result.textContent=e.message;}finally{$('test-model').disabled=false;}}
async function showMap(){openDialog('map-dialog');$('map-content').textContent='正在分析 Python 文件…';const data=await api('/project-map');$('map-stats').replaceChildren(el('span','',data.modules.length+' 个模块'),el('span','',data.modules.reduce((n,m)=>n+m.symbols.length,0)+' 个顶层符号'),el('span','',data.errors.length+' 个解析提示'));$('map-content').replaceChildren();for(const module of data.modules){const block=el('div','map-module');const link=el('button','',module.path);link.onclick=safe(async()=>{$('map-dialog').close();await openFile(module.path);});block.append(link,el('pre','',module.summary.split('\n').slice(1).join('\n')||'暂无顶层函数或类'));$('map-content').append(block);}for(const error of data.errors)$('map-content').append(el('div','notice error',error.path+': '+error.error));if(!data.modules.length)$('map-content').textContent='当前工作区还没有可解析的 Python 文件。';}
async function showMCP(){openDialog('mcp-dialog');$('mcp-list').textContent='正在发现外部工具…';$('mcp-config').value=JSON.stringify(state.settings.mcp_servers||[],null,2);const result=await api('/mcp');$('mcp-list').replaceChildren();for(const server of result.servers){const row=el('div','mcp-server');const copy=el('div','',server.name);copy.append(el('small','',server.ok?server.tools.length+' 个工具 · '+server.transport:server.error));row.append(el('span','dot'+(server.ok?'':' error')),copy,el('span','',server.ok?'已连接':'未连接'));$('mcp-list').append(row);}$('mcp-dot').classList.toggle('muted',!result.servers.some(s=>s.ok));}
async function testMCP(){$('test-mcp').disabled=true;$('mcp-result').textContent='启动独立进程，执行 initialize / tools/list / tools/call…';try{const result=await api('/mcp-test',{method:'POST'});$('mcp-result').textContent=result.text+'\n\n'+result.transport+' · '+result.elapsed_ms+' ms';}catch(e){$('mcp-result').textContent=e.message;}finally{$('test-mcp').disabled=false;}}
async function search(mode='files'){state.searchMode=mode;$('search-title').textContent=mode==='files'?'快速打开':'搜索项目内容';$('search-input').placeholder=mode==='files'?'输入文件名…':'搜索文件内容…';$('search-input').value='';openDialog('search-dialog');await updateSearch();$('search-input').focus();}
let searchSequence=0;
async function updateSearch(){const seq=++searchSequence,q=$('search-input').value;let rows=state.searchMode==='files'?state.files.filter(f=>f.path.toLowerCase().includes(q.toLowerCase())).slice(0,60):q?await api('/search?q='+encodeURIComponent(q)):[];if(seq!==searchSequence)return;$('search-results').replaceChildren();for(const item of rows){const button=el('button','search-result');button.append(el('span','',item.path+(item.line?':'+item.line:'')));if(item.text)button.append(el('small','',item.text));button.onclick=safe(async()=>{$('search-dialog').close();await openFile(item.path,item.line);});$('search-results').append(button);}if(!rows.length)$('search-results').append(el('div','notice',q?'没有找到匹配内容':'输入要搜索的内容'));}
async function showHistory(){openDialog('history-dialog');const data=await api('/bootstrap');$('history-list').replaceChildren();for(const session of data.sessions){const button=el('button','history-item');button.append(el('span','',session.title),el('small','',new Date(session.updated*1000).toLocaleString()));button.onclick=safe(async()=>{if(state.run)throw new Error('请先结束当前任务');const data=await api('/sessions/'+session.id);state.session=session.id;resetChat();for(const event of data.events)if(['user','assistant','tool_start','tool_result','notice','error','done'].includes(event.type))await handleEvent(event);$('history-dialog').close();});$('history-list').append(button);}if(!data.sessions.length)$('history-list').append(el('div','notice','开始对话后，历史会保存在本机。'));}
async function exportTrace(){if(!state.session)throw new Error('请先完成一次对话或任务');const response=await api('/trace/'+state.session,{raw:true});const text=await response.text();if(window.pywebview?.api){const path=await window.pywebview.api.save_text(text,'trace.md');if(path)toast('已导出运行记录');}else{const link=el('a');link.href=URL.createObjectURL(new Blob([text],{type:'text/markdown'}));link.download='trace.md';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}}

$('workspace-button').onclick=safe(openWorkspace);$('welcome-open').onclick=safe(openWorkspace);$('refresh-files').onclick=safe(refreshFiles);$('save-button').onclick=safe(saveCurrent);$('settings-button').onclick=showSettings;$('model-chip').onclick=showSettings;
$('map-button').onclick=safe(showMap);$('map-action').onclick=safe(showMap);$('mcp-button').onclick=safe(showMCP);$('test-mcp').onclick=safe(testMCP);$('search-action').onclick=safe(()=>search('content'));$('history-button').onclick=safe(showHistory);$('export-trace').onclick=safe(exportTrace);
$('settings-form').onsubmit=e=>{e.preventDefault();safe(()=>saveSettings())();};$('test-model').onclick=safe(testModel);
$('save-mcp').onclick=safe(async()=>{const configs=JSON.parse($('mcp-config').value||'[]');state.settings=await api('/settings',{method:'POST',body:{mcp_servers:configs}});await showMCP();toast('MCP 配置已保存');});
$('new-chat').onclick=safe(async()=>{if(state.run)throw new Error('请先结束或停止当前任务');state.session=null;resetChat();});
$('attach-file').onclick=()=>{if(!state.current)return toast('先打开需要附加的文件');if(state.attached.size>=6&&!state.attached.has(state.current))return toast('最多附加 6 个文件');state.attached.add(state.current);renderChips();};
document.querySelectorAll('.mode-switch button').forEach(btn=>btn.onclick=()=>setMode(btn.dataset.mode));
$('chat-form').onsubmit=e=>{e.preventDefault();safe(sendPrompt)();};$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();safe(sendPrompt)();}};$('stop-button').onclick=safe(stopRun);
$('terminal-form').onsubmit=e=>{e.preventDefault();safe(async()=>{if(state.run)throw new Error('请先结束当前任务');const command=$('terminal-input').value.trim();if(!command)return;$('console-output').textContent+='\n› '+command+'\n';$('terminal-input').value='';const run=await api('/terminal',{method:'POST',body:{command}});state.run=run.id;state.session=run.session_id;setRunning(true);await readEvents(run.id,true);})()};
$('clear-console').onclick=()=>$('console-output').textContent='';$('toggle-console').onclick=()=>$('console-panel').classList.toggle('collapsed');$('status-console').onclick=()=>$('console-panel').classList.toggle('collapsed');
$('new-file').onclick=()=>{state.pathAction='file';$('path-title').textContent='新建文件';$('path-input').value='';$('path-input').placeholder='例如 src/helpers.py（工作区相对路径）';openDialog('path-dialog');};
$('path-form').onsubmit=e=>{e.preventDefault();safe(async()=>{const path=$('path-input').value.trim();if(state.pathAction==='file'){await api('/file',{method:'PUT',body:{path,content:'',version:'missing'}});await refreshFiles();await openFile(path);}else await switchWorkspace(path);$('path-dialog').close();})()};
let searchTimer;$('search-input').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(safe(updateSearch),160);};
$('autocomplete-toggle').onchange=()=>{if($('autocomplete-toggle').checked&&!modelConfigured()){$('autocomplete-toggle').checked=false;showSettings();return;}state.completion=$('autocomplete-toggle').checked;toast(state.completion?'已开启 Python AI 补全 · Tab 接受，Esc 取消':'AI 补全已关闭');};
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&!e.altKey){if(e.key.toLowerCase()==='s'){e.preventDefault();safe(saveCurrent)();}if(e.key.toLowerCase()==='p'){e.preventDefault();safe(()=>search())();}if(e.key.toLowerCase()==='l'){e.preventDefault();$('prompt').focus();}if(e.key.toLowerCase()==='f'&&e.shiftKey){e.preventDefault();safe(()=>search('content'))();}}});
window.addEventListener('beforeunload',e=>{if([...state.tabs.values()].some(t=>t.dirty)){e.preventDefault();e.returnValue='存在未保存的修改';}});

require.config({paths:{vs:'/static/vendor/vs'}});
require(['vs/editor/editor.main'],safe(async()=>{
  monaco.editor.defineTheme('pypilot',{base:'vs-dark',inherit:true,rules:[{token:'comment',foreground:'59716F'},{token:'keyword',foreground:'A5B8EF'},{token:'string',foreground:'A7C998'},{token:'number',foreground:'DBBA85'},{token:'identifier',foreground:'CAD9E5'}],colors:{'editor.background':'#111419','editor.foreground':'#C7D4E2','editorLineNumber.foreground':'#374454','editorLineNumber.activeForeground':'#8DA5B6','editor.lineHighlightBackground':'#191F27','editor.selectionBackground':'#30534688','editorCursor.foreground':'#72D7BB','editorIndentGuide.background1':'#222D36','editorIndentGuide.activeBackground1':'#3D4B57','editorGutter.background':'#111419','editorSuggestWidget.background':'#1C252E','editorSuggestWidget.border':'#3A4F57','editorSuggestWidget.selectedBackground':'#2B403C','editorGhostText.foreground':'#648B82','diffEditor.insertedTextBackground':'#365E3D55','diffEditor.removedTextBackground':'#703B4555'}});
  state.editor=monaco.editor.create($('editor-container'),{theme:'pypilot',model:null,automaticLayout:true,fontFamily:'Cascadia Code, Consolas, Microsoft YaHei, monospace',fontSize:13,lineHeight:23,minimap:{enabled:false},padding:{top:13,bottom:20},scrollBeyondLastLine:false,smoothScrolling:true,renderLineHighlight:'line',tabSize:4,wordWrap:'off',overviewRulerBorder:false,bracketPairColorization:{enabled:true},inlineSuggest:{enabled:true},quickSuggestions:{other:true,comments:false,strings:false}});
  state.editor.onDidChangeCursorPosition(e=>$('cursor-position').textContent=`Ln ${e.position.lineNumber}, Col ${e.position.column}`);
  state.editor.addAction({id:'pypilot.ask-selection',label:'解释选中的代码',contextMenuGroupId:'navigation',contextMenuOrder:1,run:()=>{const selected=state.editor.getModel()?.getValueInRange(state.editor.getSelection());if(selected){setMode('ask');$('prompt').value='解释这段 Python 代码：\n```python\n'+selected+'\n```';$('prompt').focus();}}});
  let completionAbort=null;
  monaco.languages.registerInlineCompletionsProvider('python',{
    provideInlineCompletions:async(model,position,context,cancel)=>{
      if(!state.completion||state.run||!modelConfigured())return{items:[]};
      completionAbort?.abort();const controller=new AbortController();completionAbort=controller;
      const subscription=cancel.onCancellationRequested(()=>controller.abort());
      try{
        await new Promise(r=>setTimeout(r,450));if(cancel.isCancellationRequested||controller.signal.aborted)return{items:[]};
        const version=model.getVersionId();const offset=model.getOffsetAt(position),content=model.getValue();
        const result=await api('/completion',{method:'POST',signal:controller.signal,body:{path:state.current,prefix:content.slice(Math.max(0,offset-6000),offset),suffix:content.slice(offset,offset+2000)}});
        if(cancel.isCancellationRequested||model.getVersionId()!==version||!result.text)return{items:[]};
        return{items:[{insertText:result.text,range:new monaco.Range(position.lineNumber,position.column,position.lineNumber,position.column)}]};
      }catch(error){if(error.name!=='AbortError')$('run-status').textContent='补全暂不可用 · 检查模型配置';return{items:[]};}finally{subscription.dispose();}
    },freeInlineCompletions:()=>{}
  });
  const data=await api('/bootstrap');updateBootstrap(data);if(state.files.some(f=>f.path==='stats.py'))await openFile('stats.py');
  if(data.active_run){state.run=data.active_run.id;state.session=data.active_run.session_id;setRunning(true);safe(()=>readEvents(state.run))();}
}));
