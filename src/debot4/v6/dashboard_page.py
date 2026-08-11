"""Single-file dashboard UI; data always comes from /api/snapshot."""


def page() -> bytes:
    return _HTML.encode("utf-8")


_HTML = r"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DeBot v6</title>
<style>
:root{color-scheme:dark;--bg:#080b10;--card:#111722;--line:#263043;--muted:#8c9aaf;--good:#29d391;--bad:#ff6577;--warn:#f3bd4f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#eef3fb;font:14px system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:16px;align-items:end}h1{margin:0;font-size:24px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:10px;margin:18px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px}.value{font-size:25px;font-weight:750;margin-top:5px}.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}h2{font-size:16px;margin:24px 0 9px}table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line)}th,td{padding:9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}th{color:var(--muted);font-size:12px}td.reason{white-space:normal;min-width:260px}.scroll{overflow:auto;border-radius:10px}.pill{padding:3px 7px;border-radius:12px;background:#202a3a}.buy{background:#12382d;color:var(--good)}.reject{background:#3a1d26;color:#ff9baa}.empty{padding:22px;color:var(--muted)}a{color:#80b7ff}@media(max-width:700px){main{padding:12px}.top{display:block}}
</style></head><body><main><div class="top"><div><h1>DeBot v6 · 实盘模拟基线</h1><div class="muted">DeBot → 历史 KOL → 叙事 → 同区块 MC/安全复核 → BUY → 逐块追踪 1h</div></div><div id="health" class="muted">连接中…</div></div>
<div id="cards" class="grid"></div><h2>模拟 BUY 与 1h 结果</h2><div id="buys" class="scroll"></div><h2>最近决策</h2><div id="decisions" class="scroll"></div><h2>最近 DeBot 信号</h2><div id="signals" class="scroll"></div></main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const short=v=>v?esc(String(v).slice(0,10)+'…'+String(v).slice(-6)):'—';
const money=v=>v==null?'—':'$'+Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
const time=v=>v?new Date(v).toLocaleTimeString():'—';
function table(rows,cols){if(!rows.length)return'<div class="card empty">暂无数据</div>';return'<table><thead><tr>'+cols.map(c=>'<th>'+c[0]+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td class="'+(c[2]||'')+'">'+c[1](r)+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
function render(x){const s=x.ledger.summary||{},r=x.runtime||{};document.querySelector('#health').textContent=`${r.status||'unknown'} · DeBot ${r.last_debot_latency_ms??'—'}ms · Block ${r.last_block_number??'—'} · ${new Date().toLocaleTimeString()}`;
const cards=[['DeBot 信号',s.signals||0],['历史 KOL',s.historical_kol||0],['决策',s.decisions||0],['BUY',s.buys||0],['逐块观察',s.observations||0],['完整 1h',s.outcomes_complete||0],['1h 盈利',s.profitable_1h||0],['平均 1h PnL',s.mean_final_pnl_usd==null?'—':money(s.mean_final_pnl_usd)]];document.querySelector('#cards').innerHTML=cards.map(c=>`<div class="card"><div class="muted">${c[0]}</div><div class="value">${c[1]}</div></div>`).join('');
document.querySelector('#buys').innerHTML=table(x.ledger.buys||[],[['时间',r=>time(r.executed_at)],['Token',r=>short(r.token_address)],['BUY MC',r=>money(r.entry_fdv_usd)],['最新 MC',r=>money(r.latest_fdv_usd)],['1h 最高 MC',r=>money(r.peak_fdv_usd)],['最终 MC',r=>money(r.final_fdv_usd)],['峰值倍数',r=>r.peak_multiple?Number(r.peak_multiple).toFixed(2)+'x':'—'],['最终 PnL',r=>money(r.final_pnl_usd)],['状态',r=>esc(r.outcome_status||'追踪中')]]);
document.querySelector('#decisions').innerHTML=table(x.ledger.decisions||[],[['时间',r=>time(r.decided_at)],['信号',r=>esc(r.signal_kind)],['Token',r=>short(r.token_address)],['结果',r=>`<span class="pill ${esc(r.status)}">${esc(r.status)}</span>`],['原因',r=>esc(r.reason),'reason']]);
document.querySelector('#signals').innerHTML=table(x.ledger.signals||[],[['事件时间',r=>time(r.event_at)],['类型',r=>esc(r.signal_kind)],['Token',r=>short(r.token_address)],['ID',r=>short(r.signal_id)]]);}
async function tick(){try{const q=await fetch('/api/snapshot',{cache:'no-store'});if(!q.ok)throw Error(q.status);render(await q.json())}catch(e){document.querySelector('#health').textContent='看板数据读取失败: '+e}finally{setTimeout(tick,1000)}}tick();
</script></body></html>"""
