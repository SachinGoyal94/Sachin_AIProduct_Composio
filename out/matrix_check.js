
(function(){
  var DATA = JSON.parse(document.getElementById('report-data').textContent).rows;
  var GATE_C = {"Open self-serve":"#16a34a","Paid self-serve":"#2563eb",
    "Admin approval":"#d97706","Contact sales / partner":"#dc2626",
    "N/A (no auth)":"#9ca3af"};
  var GATE_T = {"Open self-serve":"Open self-serve","Paid self-serve":"Paid self-serve",
    "Admin approval":"Admin approval","Contact sales / partner":"Sales/partner",
    "N/A (no auth)":"No auth"};
  var V_C = {"Ready":"#16a34a","Ready with caveats":"#d97706","Blocked":"#dc2626"};
  var A_C = {"OAuth2":"#ea580c","API key":"#2563eb","Basic":"#7c3aed","Token":"#0891b2",
    "HMAC":"#be185d","None":"#6b7280","Other":"#a16207"};
  var T_C = {"S":"#ea580c","A":"#2563eb","B":"#7c3aed","C":"#9ca3af"};
  var M_C = {"Yes (official)":"#ea580c","Yes (community)":"#d97706","No":"#d6d3d1",
    "Unclear":"#f5f5f4"};
  var state = {q:"",cat:"",verdict:"",mcp:"",tier:"",k:"id",dir:1};
  var cats = []; DATA.forEach(function(r){if(cats.indexOf(r.category)<0)cats.push(r.category);});
  var chipbox = document.getElementById('cats');
  cats.forEach(function(c){
    var b=document.createElement('span'); b.className='chip'; b.textContent=c; b.dataset.v=c;
    b.onclick=function(){state.cat=(state.cat===c?'':c);
      chipbox.querySelectorAll('.chip').forEach(function(x){x.classList.toggle('on',
        x.dataset.v===state.cat||(state.cat===''&&x.dataset.v===''));}); render();};
    chipbox.appendChild(b);
  });
  function chip(v){return '<span class="b" style="background:'+v.c+'">'+esc(v.t)+'</span>';}
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function conf(n){var s='';for(var i=1;i<=5;i++)s+='<span class="'+(i<=n?'':'off')+'">&#9679;</span>';return s;}
  function ev(r){
    var urls=(r.evidence||'').split(',').filter(Boolean);
    if(!urls.length) return '<span style="color:#d6d3d1">—</span>';
    return urls.slice(0,2).map(function(u,i){
      var st=(r.ev_status&&r.ev_status[i])||0;
      var ok=st>=200&&st<300;
      return '<a href="'+esc(u)+'" target="_blank" rel="noopener">docs ↗'+
        '<span class="st" style="color:'+(ok?'#16a34a':'#dc2626')+'">'+(st||'?')+'</span></a>';
    }).join(' ');
  }
  function rowHtml(r){
    var mcpTxt=r.mcp==='Yes (official)'?'MCP':(r.mcp==='Yes (community)'?'mcp':'—');
    return '<td class="num">'+r.id+'</td>'+
    '<td><span class="app-nm">'+esc(r.name)+'</span><br><span class="app-ct">'+
      esc(r.category)+'</span></td>'+
    '<td class="does">'+esc(r.does)+'</td>'+
    '<td>'+chip({t:r.auth,c:A_C[r.auth]||'#999'})+'</td>'+
    '<td>'+chip({t:GATE_T[r.gate]||r.gate,c:GATE_C[r.gate]||'#999'})+'</td>'+
    '<td>'+esc(r.surface)+'<div class="breadth">'+esc(r.breadth)+'</div></td>'+
    '<td>'+(r.mcp==='No'?'<span class="b ghost">none</span>':
      chip({t:mcpTxt,c:M_C[r.mcp]||'#999'}))+'</td>'+
    '<td>'+chip({t:r.tier,c:T_C[r.tier]||'#999'})+'</td>'+
    '<td>'+chip({t:r.verdict,c:V_C[r.verdict]||'#999'})+
      (r.blocker?'<div class="breadth">'+esc(r.blocker)+'</div>':'')+'</td>'+
    '<td class="ev">'+ev(r)+'</td>'+
    '<td class="conf" title="confidence '+r.confidence+'/5">'+conf(r.confidence)+'</td>';
  }
  function detailHtml(r){
    function cell(k,v){return v?'<div><b>'+k+'</b>'+esc(v)+'</div>':'';}
    return '<td colspan="11"><div class="dgrid">'+
      cell('Auth detail',r.auth_detail)+cell('Gating detail',r.gate_detail)+
      cell('API breadth',r.breadth)+cell('Blocker',r.blocker)+
      '<div><b>Evidence</b><span class="evlinks">'+((r.evidence||'').split(',').
        filter(Boolean).map(function(u){return '<a href="'+esc(u)+'" target="_blank">'+
        esc(u)+'</a>';}).join('')||'—')+
        ((r.mcp_evidence)?'<a href="'+esc(r.mcp_evidence)+'" target="_blank">MCP: '+
        esc(r.mcp_evidence)+'</a>':'')+'</span></div>'+
      (r.notes?'<div><b>Notes</b><span class="note">'+esc(r.notes)+'</span></div>':'')+
      (r.quotes?'<div><b>Quotes from the docs (verbatim)</b><span class="note">'+
        esc(r.quotes.split(' || ').map(function(q){return '\u201c'+q+'\u201d';}).join(' '))+
        '</span></div>':'')+
      '</div></td>';
  }
  var open=null;
  function render(){
    var q=state.q.toLowerCase();
    var rows=DATA.filter(function(r){
      if(state.cat&&r.category!==state.cat)return false;
      if(state.verdict&&r.verdict!==state.verdict)return false;
      if(state.mcp&&r.mcp!==state.mcp)return false;
      if(state.tier&&r.tier!==state.tier)return false;
      if(q){var hay=(r.name+' '+r.does+' '+r.auth+' '+r.auth_detail+' '+r.gate+' '+
        r.blocker+' '+r.surface+' '+r.category).toLowerCase();
        if(hay.indexOf(q)<0)return false;}
      return true;});
    rows.sort(function(a,b){var va=a[state.k],vb=b[state.k];
      if(typeof va==='number')return (va-vb)*state.dir;
      return String(va).localeCompare(String(vb))*state.dir;});
    var tb=document.getElementById('tbody'); tb.innerHTML='';
    rows.forEach(function(r){
      var tr=document.createElement('tr'); tr.className='row';
      tr.setAttribute('data-id', r.id);
      tr.innerHTML=rowHtml(r);
      tr.onclick=function(){var id=r.id;
        if(open){var prev=tb.querySelector('tr.detail');if(prev&&prev.dataset.for==id){
          prev.remove();open=null;return;}prev&&prev.remove();}
        var d=document.createElement('tr');d.className='detail';
        d.setAttribute('data-for', id);
        d.innerHTML=detailHtml(r);tr.after(d);open=id;};
      tb.appendChild(tr);});
    document.getElementById('count').textContent='showing '+rows.length+' of '+DATA.length;
  }
  document.getElementById('q').oninput=function(e){state.q=e.target.value;render();};
  ['fVerdict','fMcp','fTier'].forEach(function(id){
    document.getElementById(id).onchange=function(e){
      state[{fVerdict:'verdict',fMcp:'mcp',fTier:'tier'}[id]]=e.target.value;render();};});
  document.querySelectorAll('th[data-k]').forEach(function(th){
    th.onclick=function(){var k=th.dataset.k;
      state.dir=(state.k===k)?-state.dir:1;state.k=k;render();};});
  document.getElementById('csvBtn').onclick=function(){
    var cols=['id','name','category','does','auth','auth_detail','gate','gate_detail',
      'surface','breadth','mcp','verdict','blocker','evidence','tier','confidence'];
    var csv=[cols.join(',')].concat(DATA.map(function(r){
      return cols.map(function(c){return '"'+String(r[c]==null?'':r[c]).
        replace(/"/g,'""')+'"';}).join(',');})).join('\n');
    var a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
    a.download='apps_verified.csv';a.click();};
  window.jumpTo=function(id){state.q='';document.getElementById('q').value='';
    var r=DATA.filter(function(x){return x.id===id;})[0];
    document.getElementById('fVerdict').value='';document.getElementById('fMcp').value='';
    document.getElementById('fTier').value='';state.verdict='';state.mcp='';state.tier='';
    state.cat='';
    document.querySelectorAll('#cats .chip').forEach(function(x){
      x.classList.toggle('on',x.dataset.v==='');});
    document.getElementById('tbl').scrollIntoView({behavior:'smooth'});
    setTimeout(function(){
      var tr=document.querySelector('tr.row[data-id="'+id+'"]');
      if(tr){tr.click();tr.scrollIntoView({behavior:'smooth',block:'center'});}},150);};
  render();
})();
