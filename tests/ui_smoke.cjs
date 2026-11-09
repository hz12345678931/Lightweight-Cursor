/* Real app E2E against tests/mock_provider.py. No cloud service or API key.
   npm install --no-save playwright; npx playwright install chromium
   PYPILOT_URL=http://127.0.0.1:8878 node tests/ui_smoke.cjs
   Set PYPILOT_PLAYWRIGHT to a Playwright module path if needed. */
const {chromium} = require(process.env.PYPILOT_PLAYWRIGHT || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async()=>{
  const dest = process.env.PYPILOT_QA_OUTPUT || path.resolve('test-results');
  fs.mkdirSync(dest,{recursive:true});
  const browser = await chromium.launch({headless:true,...(process.env.PYPILOT_BROWSER_CHANNEL?{channel:process.env.PYPILOT_BROWSER_CHANNEL}:{})});
  const ctx = await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror',e=>errors.push(e.message));
  try {
    await page.goto(process.env.PYPILOT_URL || 'http://127.0.0.1:8878');
    await page.waitForSelector('.tree-file');
    await page.locator('.tree-file[data-path="stats.py"]').click();
    await page.screenshot({path:path.join(dest,'01-workbench.png')});
    await page.locator('#map-button').click();
    await page.waitForSelector('.map-module');
    assert.match(await page.locator('#map-content').textContent(),/mean/);
    await page.screenshot({path:path.join(dest,'02-python-map.png')});
    await page.locator('[data-close="map-dialog"]').click();
    await page.locator('#mcp-button').click();
    await page.waitForSelector('.mcp-server');
    assert.match(await page.locator('#mcp-list').textContent(),/已连接/);
    await page.locator('#test-mcp').click();
    await page.waitForFunction(()=>document.getElementById('mcp-result').textContent.includes('JSON-RPC'));
    await page.screenshot({path:path.join(dest,'03-mcp.png')});
    await page.locator('[data-close="mcp-dialog"]').click();

    await page.locator('#settings-button').click();
    await page.locator('#setting-url').fill('http://127.0.0.1:8877/v1');
    await page.locator('#setting-model').fill('local-protocol-fixture-NOT-AI');
    await page.locator('#test-model').click();
    await page.waitForFunction(()=>document.getElementById('connection-result').textContent.includes('连接成功'));
    await page.locator('#settings-form button[type=submit]').click();
    await page.locator('#settings-dialog').waitFor({state:'hidden'});
    await page.locator('#prompt').fill('本地协议验收（固定测试响应，非真实 AI）：修复 mean，验证失败恢复、差异审阅、真实测试与 MCP。');
    assert.ok((await page.locator('#prompt').inputValue()).length>5);
    await page.locator('#send-button').click();
    await page.locator('.approval-actions .accept').last().waitFor();
    assert.match(await page.locator('#chat').textContent(),/文件不存在/);
    await page.locator('.approval-actions .accept:enabled').click();
    await page.locator('.view-diff:enabled').waitFor();
    await page.locator('.view-diff:enabled').click();
    await page.waitForSelector('.monaco-diff-editor');
    await page.screenshot({path:path.join(dest,'04-review-diff.png')});
    await page.locator('#diff-accept').click();
    await page.locator('#diff-dialog').waitFor({state:'hidden'});
    // Remaining approvals: regression test command, then external MCP call.
    for(let i=0;i<2;i++){
      await page.locator('.approval-actions .accept:enabled').waitFor();
      const approvedCard = await page.locator('.approval-actions .accept:enabled').evaluate(b=>b.closest('.approval-card').id);
      await page.locator('.approval-actions .accept:enabled').click();
      await page.waitForFunction(id=>document.getElementById(id).querySelector('.accept').disabled, approvedCard);
    }
    await page.waitForFunction(()=>!state.run, {timeout:60000});
    assert.match(await page.locator('#console-output').textContent(),/FAILED/);
    assert.match(await page.locator('#console-output').textContent(),/\bOK\b/);
    assert.match(await page.locator('#chat').textContent(),/本地协议测试完成/);
    assert.match(await page.evaluate(()=>state.editor.getValue()),/raise ValueError/);
    await page.screenshot({path:path.join(dest,'05-agent-result.png')});
    const trace = await page.evaluate(async()=>{const r=await api('/trace/'+state.session,{raw:true});return r.text();});
    fs.writeFileSync(path.join(dest,'trace.md'),'# 本地协议验收记录（非真实 AI）\n\n模型响应由 tests/mock_provider.py 固定提供；以下文件修改、命令执行和 MCP 通信是真实执行的。\n\n'+trace);

    // Completion must appear as a ghost insertion and Tab must accept it.
    await page.locator('#new-file').click();
    await page.locator('#path-input').fill('completion_demo.py');
    await page.locator('#path-form button[type=submit]').click();
    await page.waitForFunction(()=>state.current==='completion_demo.py');
    await page.locator('#autocomplete-toggle').check();
    await page.evaluate(()=>{state.editor.setValue('def add(a, b):\n    ');state.editor.setPosition({lineNumber:2,column:5});state.editor.focus();state.editor.trigger('test','editor.action.inlineSuggest.trigger',{});});
    await page.waitForSelector('.ghost-text-decoration',{timeout:30000});
    await page.keyboard.press('Tab');
    assert.match(await page.evaluate(()=>state.editor.getValue()),/return a \+ b/);
    await page.keyboard.press('Control+s');
    await page.waitForFunction(()=>!state.tabs.get(state.current).dirty);
    await page.locator('#autocomplete-toggle').uncheck();

    // Stop while the real child interpreter is sleeping.
    await page.locator('#new-chat').click();
    await page.locator('#prompt').fill('停止测试：执行等待命令，由界面中断。');
    await page.locator('#send-button').click();
    await page.locator('.approval-actions .accept:enabled').waitFor();
    await page.locator('.approval-actions .accept:enabled').click();
    await page.waitForFunction(()=>document.getElementById('run-status').textContent==='正在处理任务');
    await page.locator('#stop-button').click();
    await page.waitForFunction(()=>!state.run);
    assert.match(await page.locator('#chat').textContent(),/中断|取消/);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(dest,'ui-result.json'),JSON.stringify({passed:true,checks:['workbench','python AST map','real MCP stdio','OpenAI SSE','failure recovery','diff review','real unittest','inline completion Tab','task stop'],pageErrors:errors},null,2));
    console.log('UI PASS: 9 workflows; no page errors');
  } catch(e) {
    await page.screenshot({path:path.join(dest,'failure.png')});
    console.error('UI state:',await page.locator('#toast').textContent(),'Page errors:',errors);
    console.error(await page.evaluate(()=>({run:state.run,session:state.session,prompt:document.getElementById('prompt').value,chat:document.getElementById('chat').innerText})));
    throw e;
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
