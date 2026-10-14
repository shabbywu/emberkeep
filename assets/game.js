/* Presentation only. Python decides movement, AI, combat, targeting, growth and saves. */
(() => {
  'use strict';
  let language='en', translations={};
  function t(key,params={}){
    return (translations[key]||key).replace(/\{(\w+)\}/g,(_,name)=>String(params[name]??'{'+name+'}'));
  }
  function applyLanguage(next){
    const changed=next.language!==language||!Object.keys(translations).length;
    if(next.catalog&&changed)translations=next.catalog;
    if(next.language)language=next.language;
    return changed;
  }
  const $ = id => document.getElementById(id);
  const canvas=$('board'), ctx=canvas.getContext('2d'), card=$('card');
  const T=16, COLS=23, ROWS=17, CW=COLS*T, CH=ROWS*T;
  const atlas=new Image(); atlas.src='atlas.png';
  const sprites={floor:0,moss:1,wall:2,wall_dark:3,stairs:4,torch:5,hero:6,hero_step:7,
    slime:8,skeleton:10,cultist:12,warden:14,potion:16,chest:17,sword:19,bolt:20,whirl:21,
    shield:22,heart:23,coin:24,skull:25,spark:26,rune:27,banner:28,lamp:30};
  let state={phase:'menu',events:[]}, visible=new Set(), busy=false, error='', calls=0, ms=0;
  let liveHero=null, initialized=false, helpOpen=false, helpWasPaused=false, pauseRequested=false;
  let camera={x:0,y:0}, hover=null, tween=null, enemyTweens={}, effects=[], particles=[];
  let shakeUntil=0, toastUntil=0, moveAfter=0, fps=60, lastFrame=0, frameCount=0;
  const icon=(name,extra='')=>{const i=sprites[name]??27;return '<span class="sprite '+extra+'" style="background-position:-'+(i%8*32)+'px -'+(Math.floor(i/8)*32)+'px"></span>'};
  const ui=EmberHTML.ui;
  const text=(id,value)=>{ui.text[id]=String(value)};
  function showError(value){
    error=String(value?.message||value);
    ui.error=error;
  }
  function toast(value){ui.toast=value;ui.toastVisible=true;toastUntil=performance.now()+1900}
  $('dismissError').onclick=()=>{ui.error='';error=''};

  async function invoke(name,args=[]){
    if(busy)return;
    busy=true;
    const feedbackTimer=setTimeout(()=>{ui.working=name;},200);
    const started=performance.now();
    try{
      const fn=window.host?(name.startsWith('game.')?host.game[name.slice(5)]:host[name]):null;
      if(typeof fn!=='function')throw new Error(t('ui.native_required'));
      // Returned dict/list values are live Python proxies, not JS containers.
      const next=Python.to_value(await fn(...args));
      calls++;ms=performance.now()-started;
      if(next&&next.phase){
        const noTurn=['move','whirl','cast_bolt','heal','wait_turn','interact'].includes(name.replace('game.',''))&&next.revision===state.revision&&next.phase==='playing';
        const message=next.messages?.[next.messages.length-1];
        const changedMessage=message&&message!==state.messages?.[state.messages.length-1];
        if(name==='set_language'&&state.phase==='menu')next.phase='menu';
        error='';ui.error='';setState(next,{preserveHelp:name==='set_language'});
        if(noTurn&&changedMessage)toast(message);
      }
      if(name==='save_game')toast(t('ui.saved_toast'));
      return next;
    }catch(err){
      showError(err);
      if(name==='save_game'){state.saved=false;state.save_error=error;ui.s.saved=false;ui.s.save_error=error;}
      return null;
    }
    finally{
      clearTimeout(feedbackTimer);ui.working='';
      await EmberHTML.nextTick();
      busy=false;
      if(pauseRequested){pauseRequested=false;if(state.player&&!state.paused&&['playing','upgrade'].includes(state.phase))invoke('set_paused',[true]);}
    }
  }

  function setState(next,{preserveHelp=false}={}){
    const languageChanged=applyLanguage(next);
    if(languageChanged)ui.text.inspect='';
    const previous=state;
    state=next;
    EmberHTML.update(next,liveHero);
    visible=new Set(state.visible||[]);
    if(next.player){
      const p=next.player;
      camera={x:Math.max(0,Math.min(next.width-COLS,p.x-Math.floor(COLS/2))),
              y:Math.max(0,Math.min(next.height-ROWS,p.y-Math.floor(ROWS/2)))};
      if(previous.floor!==next.floor){tween=null;enemyTweens={};effects=[];particles=[];}
      if(next.revision!==previous.revision){
        const now=performance.now();
        for(const ev of next.events||[]){
          if(ev.kind==='move')tween={...ev,time:now};
          else if(ev.kind==='enemy_move')enemyTweens[ev.id]={...ev,time:now};
          else if(['hit','hurt','heal','death','melee','enemy_melee','bolt','whirl','enemy_spell','pickup','rage'].includes(ev.kind)){
            effects.push({...ev,time:now});
            if(['hit','hurt','death','pickup','heal','rage'].includes(ev.kind))burst(ev.x+.5,ev.y+.5,ev.kind==='heal'?'#9ebc86':ev.kind==='hurt'?'#e49272':'#dfb875',ev.kind==='death'?16:8,now);
            if(ev.kind==='hurt')shakeUntil=now+210;
          }
        }
      }
      if(next.save_error)showError(next.save_error);
    }
    const dialogChanged=languageChanged||previous.phase!==next.phase||previous.paused!==next.paused||
      (helpOpen&&!preserveHelp)||(next.phase==='menu'&&previous.has_save!==next.has_save)||
      (next.phase==='upgrade'&&JSON.stringify(previous.upgrades)!==JSON.stringify(next.upgrades));
    if(!preserveHelp)helpOpen=false;
    if(helpOpen){if(languageChanged)renderHelp();}
    else if(dialogChanged){
      if(next.phase==='menu')showMenu();
      else if(next.paused)showPause();
      else if(next.phase==='upgrade')showUpgrades();
      else if(next.phase==='won'||next.phase==='dead')showEnding();
      else ui.dialogVisible=false;
    }
    if(!ui.dialogVisible&&document.activeElement!==canvas)canvas.focus({preventScroll:true});
  }

  function afterDialog(bind){EmberHTML.nextTick().then(bind);}
  function dialog(className=''){ui.dialogVisible=true;ui.dialogClass='dialog '+className;}
  function showMenu(){
    dialog('menu-card');
    ui.dialogHTML='<div class="menu-story"><div class="overline">THE LAST LIGHT IN THE DARK</div><h1>'+t('ui.menu_title_top')+'<br>'+t('ui.menu_title_bottom')+'</h1><div class="english-title">EMBERKEEP</div><p>'+t('ui.menu_story_one')+'<br>'+t('ui.menu_story_two')+'</p><div class="menu-rune"><i></i>'+t('ui.menu_motto')+'<i></i></div></div>'+
      '<div class="menu-actions"><div class="overline">'+t('ui.menu_start_caption')+'</div><div class="button-stack"><button id="startBtn" class="primary">'+t('ui.start')+'</button><button id="continueBtn" class="secondary" '+(!state.has_save?'disabled':'')+'>'+t('ui.continue')+'</button></div><label class="seed-input">'+t('ui.seed')+'<input id="seedInput" type="text" inputmode="numeric" placeholder="'+t('ui.random')+'" maxlength="10" aria-label="'+t('ui.seed_label')+'"></label><button id="guideBtn" class="text-button">'+t('ui.menu_guide')+'</button><div class="menu-divider"></div><div class="menu-badge">FOUR FLOORS · ONE FLAME</div><p class="under-note">'+t('ui.menu_note')+'<br>'+t('ui.menu_death_note')+'</p><button id="quitBtn" class="text-button">'+t('ui.quit')+'</button></div>';
    afterDialog(()=>{
      $('startBtn').onclick=()=>{const value=$('seedInput').value.trim();if(value&&!/^\d+$/.test(value)){showError(t('error.seed'));return}invoke('new_run',[value?Number(value):null]);};
      $('continueBtn').onclick=()=>invoke('load_game');$('guideBtn').onclick=showHelp;
      $('quitBtn').onclick=()=>{if(!busy)host.quit_game().catch(showError)};
      $('startBtn').focus();
    });
  }
  function showUpgrades(){
    dialog();
    ui.dialogHTML='<div class="overline">A GIFT FROM THE EMBERS</div><h1>'+t('ui.upgrade_title')+'</h1><p class="description">'+t('ui.level')+state.player.level+' → '+(state.player.level+1)+'<br>'+t('ui.upgrade_note')+'</p><div class="upgrade-grid">'+state.upgrades.map((u,i)=>'<button class="upgrade-card" id="choice'+i+'" data-upgrade="'+u.id+'"><span class="choice-number">0'+(i+1)+'</span>'+icon(u.icon)+'<small>'+u.tag+'</small><strong>'+u.name+'</strong><p>'+u.desc+'</p><kbd>'+(i+1)+'</kbd></button>').join('')+'</div><div class="under-note">'+t('ui.upgrade_keys')+'</div>';
    afterDialog(()=>{
      card.querySelectorAll('[data-upgrade]').forEach(node=>node.onclick=()=>invoke('choose_upgrade',[node.dataset.upgrade]));
      $('choice0').focus();
    });
  }
  function showPause(){
    dialog();ui.dialogHTML='<div class="overline">KEEP THE FLAME ALIVE</div><h1>'+t('ui.pause_title')+'</h1><p class="description">'+t('ui.pause_note')+'<br>'+t('ui.pause_saved')+'</p><div class="button-stack"><button id="resumeBtn" class="primary">'+t('ui.resume')+'</button><button id="saveMenuBtn" class="secondary">'+t('ui.save_menu')+'</button><button id="pauseGuideBtn" class="text-button">'+t('ui.guide')+'</button></div><div class="under-note">'+t('ui.pause_keys')+'</div>';
    afterDialog(()=>{
      $('resumeBtn').onclick=()=>invoke('set_paused',[false]);
      $('saveMenuBtn').onclick=async()=>{const saved=await invoke('save_game');if(saved)await invoke('boot');};
      $('pauseGuideBtn').onclick=showHelp;$('resumeBtn').focus();
    });
  }
  function showEnding(){
    dialog();const won=state.phase==='won';
    ui.dialogHTML='<div class="overline">'+(won?'THE DAWN REMEMBERS YOU':'ANOTHER FLAME, ANOTHER NIGHT')+'</div>'+icon(won?'lamp':'skull','result-emblem')+'<h1>'+(won?t('ui.win_title'):t('ui.lose_title'))+'</h1><p class="description">'+(won?t('ui.win_note'):t('ui.lose_note'))+'</p><div class="result-grid"><span>'+t('ui.score')+'<strong>'+state.score+'</strong></span><span>'+t('ui.floor_reached')+'<strong>'+state.floor+' / 4</strong></span><span>'+t('ui.kills')+'<strong>'+state.kills+'</strong></span><span>'+t('ui.turns')+'<strong>'+state.turn+'</strong></span></div><p class="result-message">'+t('ui.level')+state.player.level+t('ui.gold_prefix')+state.gold+t('ui.seed_prefix')+state.seed+'</p><div class="button-stack"><button id="restartBtn" class="primary">'+t('ui.restart')+'</button><button id="endingMenuBtn" class="secondary">'+t('ui.main_menu')+'</button></div>';
    afterDialog(()=>{
      $('restartBtn').onclick=()=>invoke('new_run');$('endingMenuBtn').onclick=()=>invoke('boot');$('restartBtn').focus();
    });
  }
  async function showHelp(){
    if(busy)return;
    helpWasPaused=!!state.paused;
    if(state.player&&['playing','upgrade'].includes(state.phase)&&!state.paused)await invoke('set_paused',[true]);
    renderHelp();
  }
  function renderHelp(){
    helpOpen=true;dialog();
    ui.dialogHTML='<div class="overline">THE WAY OF THE LANTERN</div><h1>'+t('ui.guide')+'</h1><p class="description">'+t('ui.guide_intro')+'</p><div class="guide-grid"><div><b>'+t('ui.guide_move_title')+'</b><br><kbd>WASD</kbd>'+t('ui.guide_move_keys')+'<br>'+t('ui.guide_mouse')+'</div><div><b>'+t('ui.guide_skill_title')+'</b><br><kbd>Q</kbd>'+t('ui.guide_whirl')+'<br><kbd>E</kbd>'+t('ui.guide_bolt')+'</div><div><b>'+t('ui.guide_survive_title')+'</b><br><kbd>R</kbd>'+t('ui.guide_heal')+'<br><kbd>Space</kbd>'+t('ui.guide_wait')+'</div><div><b>'+t('ui.guide_save_title')+'</b><br><kbd>Esc</kbd>'+t('ui.guide_pause')+'<kbd>F5</kbd>'+t('ui.guide_save')+'<br>'+t('ui.guide_focus')+'</div><div><b>'+t('ui.guide_enemy_title')+'</b><br>'+t('ui.guide_enemy_one')+'<br>'+t('ui.guide_enemy_two')+'</div><div><b>'+t('ui.guide_goal_title')+'</b><br>'+t('ui.guide_growth')+'<br>'+t('ui.guide_goal')+'</div></div><p class="description">'+t('ui.guide_warning')+'</p><div class="button-stack"><button id="closeGuideBtn" class="primary">'+t('ui.guide_close')+'</button></div>';
    afterDialog(()=>{
      $('closeGuideBtn').onclick=closeHelp;$('closeGuideBtn').focus();
    });
  }
  function closeHelp(){
    helpOpen=false;
    if(state.phase==='menu')showMenu();
    else if(!helpWasPaused&&state.paused)invoke('set_paused',[false]);
    else if(state.paused)showPause();else setState(state);
  }
  async function changeLanguage(value){
    if(busy)return;
    const seed=$('seedInput')?.value;
    const focused=document.activeElement?.id;
    const next=await invoke('set_language',[value]);
    if(!next)return;
    if(seed!==undefined&&$('seedInput'))$('seedInput').value=seed;
    if(focused&&$(focused))$(focused).focus();
    try{localStorage.setItem('emberkeep.language',language);}catch(_){}
    text('inspect',t('ui.inspect'));
  }
  ['languageEn','languageZh'].forEach(id=>$(id).onmousedown=event=>event.preventDefault());
  $('languageEn').onclick=()=>{if(language!=='en')changeLanguage('en')};
  $('languageZh').onclick=()=>{if(language!=='zh-CN')changeLanguage('zh-CN')};
  $('pauseBtn').onclick=()=>{if(helpOpen){closeHelp();return}if(state.player&&['playing','upgrade'].includes(state.phase))invoke('set_paused',[!state.paused]);};
  $('helpBtn').onclick=showHelp;
  // HUD and mouse use Python instance methods; keyboard uses registered functions.
  [['whirlBtn','whirl'],['boltBtn','cast_bolt'],['healBtn','heal'],['waitBtn','wait_turn']].forEach(([id,method])=>$(id).onclick=()=>invoke('game.'+method));

  function normalizeKey(event){
    const key=event.key&&event.key!=='Unidentified'?event.key.toLowerCase():'';
    const names={w:'KeyW',a:'KeyA',s:'KeyS',d:'KeyD',q:'KeyQ',e:'KeyE',r:'KeyR',
      ' ':'Space',escape:'Escape',arrowup:'ArrowUp',arrowdown:'ArrowDown',arrowleft:'ArrowLeft',arrowright:'ArrowRight',
      '1':'Digit1','2':'Digit2','3':'Digit3',enter:'Enter',f3:'F3',f5:'F5'};
    const codes={87:'KeyW',65:'KeyA',83:'KeyS',68:'KeyD',81:'KeyQ',69:'KeyE',82:'KeyR',
      32:'Space',27:'Escape',38:'ArrowUp',40:'ArrowDown',37:'ArrowLeft',39:'ArrowRight',49:'Digit1',50:'Digit2',51:'Digit3',13:'Enter',114:'F3',116:'F5'};
    return (event.code&&event.code!=='Unidentified'?event.code:'')||names[key]||codes[event.keyCode]||key;
  }
  const keys={KeyW:'up',ArrowUp:'up',KeyD:'right',ArrowRight:'right',KeyS:'down',ArrowDown:'down',KeyA:'left',ArrowLeft:'left',KeyQ:'whirl',KeyE:'bolt',KeyR:'heal',Space:'wait'};
  window.addEventListener('keydown',event=>{
    const key=normalizeKey(event);
    if(event.target.matches?.('input,textarea,select,[contenteditable=true]'))return;
    if(keys[key]||['Escape','Enter','F3','F5','Digit1','Digit2','Digit3'].includes(key))event.preventDefault();
    if(key==='F3'){if(!event.repeat)ui.debugVisible=!ui.debugVisible;return;}
    if(key==='Escape'){if(!event.repeat)$('pauseBtn').click();return;}
    if(busy)return;
    if(key==='F5'&&state.player){if(!event.repeat)invoke('save_game');return;}
    if(helpOpen)return;
    if(state.phase==='menu'&&key==='Enter'){if(!event.repeat)$('startBtn').click();return;}
    if(state.phase==='upgrade'&&!state.paused&&/^Digit[123]$/.test(key)){if(!event.repeat)invoke('choose_upgrade',[state.upgrades[Number(key.slice(-1))-1].id]);return;}
    if(state.phase!=='playing'||state.paused||!keys[key])return;
    const moving=['up','right','down','left'].includes(keys[key]);
    if(event.repeat&&(!moving||performance.now()<moveAfter))return;
    moveAfter=performance.now()+140;
    if(moving)invoke('move',[keys[key]]);
    else invoke({whirl:'whirl',bolt:'cast_bolt',heal:'heal',wait:'wait_turn'}[keys[key]]);
  });
  function pauseOnBlur(){moveAfter=0;hover=null;if(state.player&&!state.paused&&['playing','upgrade'].includes(state.phase)){if(busy)pauseRequested=true;else invoke('set_paused',[true]);}}
  window.addEventListener('blur',pauseOnBlur);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pauseOnBlur()});
  canvas.addEventListener('mousedown',event=>{event.preventDefault();canvas.focus();if(event.button!==0||busy||state.phase!=='playing'||state.paused)return;const tile=mouseTile(event);invoke('game.interact',[tile.x,tile.y]);});
  canvas.addEventListener('mousemove',event=>{
    hover=mouseTile(event);
    const enemy=(state.enemies||[]).find(e=>e.x===hover.x&&e.y===hover.y);
    const item=(state.items||[]).find(i=>i.x===hover.x&&i.y===hover.y);
    text('inspect',enemy?enemy.name+t('ui.hp_prefix')+enemy.hp+'/'+enemy.max_hp:item?(item.kind==='potion'?t('ui.inspect_potion'):t('ui.inspect_chest')):t('ui.inspect'));
  });
  canvas.addEventListener('mouseleave',()=>{hover=null});
  function mouseTile(event){const r=canvas.getBoundingClientRect();return{x:Math.floor((event.clientX-r.left)/r.width*COLS)+camera.x,y:Math.floor((event.clientY-r.top)/r.height*ROWS)+camera.y};}
  function resize(){const r=$('viewport').getBoundingClientRect();const fit=Math.min((r.width-6)/CW,(r.height-6)/CH);const scale=fit>=1?Math.floor(fit):Math.max(.1,fit);const width=Math.floor(CW*scale)+'px',height=Math.floor(CH*scale)+'px';if(canvas.style.width!==width)canvas.style.width=width;if(canvas.style.height!==height)canvas.style.height=height;}
  window.addEventListener('resize',resize);
  if(window.ResizeObserver)new ResizeObserver(resize).observe($('viewport'));

  function sprite(name,x,y,alpha=1,size=16){
    if(!atlas.complete||!atlas.naturalWidth)return;
    const i=typeof name==='number'?name:sprites[name];ctx.globalAlpha=alpha;
    ctx.drawImage(atlas,(i%8)*16,Math.floor(i/8)*16,16,16,Math.round(x),Math.round(y),size,size);ctx.globalAlpha=1;
  }
  function burst(x,y,color,count,time){
    for(let i=0;i<count;i++)particles.push({x:x*T,y:y*T,vx:(Math.random()-.5)*35,vy:-10-Math.random()*28,life:450+Math.random()*250,color,time});
    if(particles.length>220)particles=particles.slice(-220);
  }
  function worldXY(x,y){return[(x-camera.x)*T,(y-camera.y)*T]}
  function renderMenu(ts){
    ctx.fillStyle='#1e1c28';ctx.fillRect(0,0,CW,CH);
    for(let y=0;y<ROWS;y++)for(let x=0;x<COLS;x++){
      if(y<4||x<2||x>COLS-3)sprite((y+x)%3===0?'wall_dark':'wall',x*T,y*T,.75);
      else sprite((x*7+y)%11===0?'moss':'floor',x*T,y*T,.6);
    }
    for(const x of [3,8,14,19]){for(let y=3;y<11;y++)sprite('wall',x*T,y*T);sprite('torch',x*T,5*T+Math.sin(ts*.003+x));
      const light=ctx.createRadialGradient(x*T+8,5*T+8,0,x*T+8,5*T+8,58);light.addColorStop(0,'#d88f332e');light.addColorStop(1,'#d88f3300');ctx.fillStyle=light;ctx.fillRect(x*T-50,5*T-50,116,116);}
    for(let x=9;x<=13;x++)sprite('stairs',x*T,12*T);
    sprite('hero',11*T,11*T+Math.sin(ts*.002));
    sprite('banner',5*T,6*T);sprite('banner',17*T,6*T);
  }
  function render(ts){
    const dt=lastFrame?Math.min(100,ts-lastFrame):16;lastFrame=ts;fps=fps*.96+(1000/Math.max(1,dt))*.04;frameCount++;
    ctx.imageSmoothingEnabled=false;ctx.globalAlpha=1;ctx.fillStyle='#14141e';ctx.fillRect(0,0,CW,CH);
    ctx.save();
    if(ts<shakeUntil)ctx.translate(Math.round(Math.sin(ts*.06)*2),Math.round(Math.cos(ts*.09)*1));
    if(state.phase==='menu'||!state.rows)renderMenu(ts);
    else{
      const warnings=new Set((state.warnings||[]).map(t=>t[1]*state.width+t[0]));
      for(let y=0;y<ROWS;y++)for(let x=0;x<COLS;x++){
        const wx=x+camera.x,wy=y+camera.y,cell=state.rows[wy]?.[wx];
        if(!cell||cell===' ')continue;
        const lit=visible.has(wy*state.width+wx),px=x*T,py=y*T;
        sprite(cell==='#'?(state.rows[wy+1]?.[wx]!=='#'?'wall':'wall_dark'):((wx*7+wy*11)%17===0?'moss':'floor'),px,py);
        if(cell==='>'){sprite('stairs',px,py);ctx.fillStyle='#eec783';ctx.globalAlpha=.2+.13*Math.sin(ts*.004);ctx.fillRect(px+3,py+2,10,2);ctx.globalAlpha=1;}
        if(cell==='#'&&lit&&state.rows[wy+1]?.[wx]&&state.rows[wy+1][wx]!=='#'&&(wx+wy*3)%7===0){sprite('torch',px,py);ctx.fillStyle='#ffd98b';ctx.globalAlpha=.6+.2*Math.sin(ts*.01+wx);ctx.fillRect(px+7,py+3,2,2);ctx.globalAlpha=1;}
        if(!lit){ctx.fillStyle='#12101fc0';ctx.fillRect(px,py,T,T);}
        if(lit&&warnings.has(wy*state.width+wx)){ctx.fillStyle='#b84b48';ctx.globalAlpha=.34+.12*Math.sin(ts*.009);ctx.fillRect(px,py,T,T);ctx.globalAlpha=1;ctx.strokeStyle='#f29b72';ctx.strokeRect(px+1.5,py+1.5,13,13);ctx.fillStyle='#efbb93';ctx.fillRect(px+7,py+4,2,5);ctx.fillRect(px+7,py+11,2,1);}
      }
      for(const item of state.items||[]){const [x,y]=worldXY(item.x,item.y);sprite(item.kind,x,y+Math.sin(ts*.003+item.x)*.5);}
      for(const enemy of state.enemies||[]){
        let ex=enemy.x,ey=enemy.y;const tw=enemyTweens[enemy.id];
        if(tw){const a=Math.min(1,(ts-tw.time)/120);ex=tw.x+(tw.tx-tw.x)*a;ey=tw.y+(tw.ty-tw.y)*a;if(a>=1)delete enemyTweens[enemy.id];}
        const [x,y]=worldXY(ex,ey);ctx.fillStyle='#0d101955';ctx.fillRect(x+3,y+13,10,2);
        let frame=sprites[enemy.kind];if(enemy.kind==='warden'&&enemy.rage)frame++;
        else if(enemy.kind==='cultist'&&enemy.intent.length)frame++;
        else if(['slime','skeleton'].includes(enemy.kind)&&Math.floor(ts/450)%2)frame++;
        const hit=effects.some(e=>e.kind==='hit'&&e.target===enemy.id&&ts-e.time<110);
        if(hit)ctx.globalCompositeOperation='lighter';sprite(frame,x,y);ctx.globalCompositeOperation='source-over';
        if(enemy.hp<enemy.max_hp){ctx.fillStyle='#251e28';ctx.fillRect(x+2,y-2,12,2);ctx.fillStyle=enemy.kind==='warden'?'#da875b':'#b8846c';ctx.fillRect(x+2,y-2,Math.ceil(12*enemy.hp/enemy.max_hp),1);}
      }
      const p=state.player;let hx=p.x,hy=p.y;
      if(tween){const a=Math.min(1,(ts-tween.time)/120),ease=1-(1-a)**3;hx=tween.x+(tween.tx-tween.x)*ease;hy=tween.y+(tween.ty-tween.y)*ease;if(a>=1)tween=null;}
      const [px,py]=worldXY(hx,hy);
      const light=ctx.createRadialGradient(px+8,py+8,7,px+8,py+8,45);light.addColorStop(0,'#eab65e1c');light.addColorStop(1,'#eab65e00');ctx.fillStyle=light;ctx.fillRect(px-38,py-38,92,92);
      ctx.fillStyle='#11101b88';ctx.fillRect(px+3,py+14,10,2);
      const hurt=effects.some(e=>e.kind==='hurt'&&ts-e.time<170);
      if(hurt&&Math.floor(ts/40)%2===0)ctx.globalCompositeOperation='lighter';
      sprite(tween&&Math.floor(ts/60)%2?'hero_step':'hero',px,py,state.phase==='dead'?.4:1);ctx.globalCompositeOperation='source-over';
      if(hover&&state.phase==='playing'&&visible.has(hover.y*state.width+hover.x)){const [x,y]=worldXY(hover.x,hover.y);ctx.strokeStyle='#d2b18199';ctx.strokeRect(x+.5,y+.5,15,15);}
      effects=effects.filter(e=>ts-e.time<820);
      for(const ev of effects){
        const elapsed=ts-ev.time,a=elapsed/820;const [x,y]=worldXY(ev.x??0,ev.y??0);
        if(['hit','hurt','heal'].includes(ev.kind)){
          ctx.globalAlpha=1-a;ctx.font='bold 7px monospace';ctx.textAlign='center';ctx.fillStyle='#17151d';ctx.fillText((ev.kind==='heal'?'+':'−')+ev.amount,x+9,y-2-a*12);
          ctx.fillStyle=ev.kind==='heal'?'#bad69c':ev.kind==='hurt'?'#efa083':'#f2dbab';ctx.fillText((ev.kind==='heal'?'+':'−')+ev.amount,x+8,y-3-a*12);ctx.globalAlpha=1;
        }else if(['melee','enemy_melee'].includes(ev.kind)&&elapsed<170){
          const [tx,ty]=worldXY(ev.tx,ev.ty);ctx.strokeStyle=ev.kind==='melee'?'#f2d3a1':'#b76165';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x+8,y+8);ctx.lineTo(tx+8,ty+8);ctx.stroke();ctx.lineWidth=1;
        }else if(ev.kind==='bolt'&&elapsed<260){
          const [tx,ty]=worldXY(ev.tx,ev.ty);const b=Math.min(1,elapsed/200);sprite('spark',x+(tx-x)*b,y+(ty-y)*b);ctx.fillStyle='#f2c07766';ctx.fillRect(x+(tx-x)*b+6,y+(ty-y)*b+3,4,5);
        }else if(ev.kind==='whirl'&&elapsed<330){ctx.strokeStyle='#e7c392';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x+8,y+8,6+elapsed/18,elapsed*.015,elapsed*.015+4.5);ctx.stroke();ctx.lineWidth=1;}
        else if(ev.kind==='enemy_spell'&&elapsed<270){ctx.fillStyle='#f3a66c';ctx.globalAlpha=.6*(1-elapsed/270);for(const tile of ev.tiles){const [tx,ty]=worldXY(tile[0],tile[1]);ctx.fillRect(tx+2,ty+2,12,12);}ctx.globalAlpha=1;}
      }
      particles=particles.filter(p=>ts-p.time<p.life);
      for(const part of particles){const elapsed=(ts-part.time)/1000;ctx.fillStyle=part.color;ctx.globalAlpha=1-(ts-part.time)/part.life;ctx.fillRect(Math.round(part.x+part.vx*elapsed-camera.x*T),Math.round(part.y+part.vy*elapsed+25*elapsed*elapsed-camera.y*T),1+(part.life%2),1);}
      ctx.globalAlpha=1;
    }
    ctx.restore();
    if(ui.toastVisible&&ts>toastUntil)ui.toastVisible=false;
    if(ui.debugVisible)text('debug','ULTRALIGHT-PY 0.5.0 / APPCORE\nTyped Python API  ·  '+calls+' calls\nLast roundtrip    '+ms.toFixed(1)+' ms\nPresentation      '+Math.round(fps)+' fps\nLive hero proxy   hp='+ (liveHero?liveHero.hp:'—')+'\nLive game proxy   turn='+(window.host?host.game.turn:'—')+'\nPython.to_value   detached render snapshot\nasyncio Promise   atomic save / load');
    requestAnimationFrame(render);
  }
  window.EmberUI={invoke,diagnostics:()=>({phase:state.phase,turn:state.turn||0,busy,error,initialized,
    calls,frames:frameCount,paused:!!state.paused,proxyHP:liveHero?liveHero.hp:null,
    canvas:{width:canvas.width,height:canvas.height,rect:JSON.parse(JSON.stringify(canvas.getBoundingClientRect()))}}),
    snapshot:()=>state};
  window.addEventListener('error',ev=>showError(ev.message));
  window.addEventListener('unhandledrejection',ev=>{showError(ev.reason);ev.preventDefault()});
  resize();requestAnimationFrame(render);
  async function initialize(){
    try{
      await new Promise((resolve,reject)=>{if(atlas.complete&&atlas.naturalWidth)resolve();else{atlas.onload=resolve;atlas.onerror=()=>reject(new Error(t('ui.atlas_error')))}});
      if(document.fonts)await document.fonts.ready;
      if(!window.host)throw new Error(t('ui.engine_error'));
      liveHero=host.game.hero;
      const result=await invoke('boot');
      if(result&&!result.language_override){
        let preferred;try{preferred=localStorage.getItem('emberkeep.language');}catch(_){}
        if(!['en','zh-CN'].includes(preferred))preferred=/^zh/i.test(navigator.language||'')?'zh-CN':'en';
        if(preferred!==language)await changeLanguage(preferred);
      }
      if(!result)throw new Error(error||t('ui.init_error'));
      initialized=true;window.EMBER_READY=true;
    }catch(err){showError(err)}
  }
  initialize();
})();
