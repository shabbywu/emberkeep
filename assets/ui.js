/* Alpine owns HTML bindings. Only detached, changed presentation fields enter its store. */
(() => {
  'use strict';
  document.addEventListener('alpine:init',()=>{
    const ui=Alpine.reactive({
      language:'en', catalog:{}, working:'', error:'', toast:'', toastVisible:false,
      dialogHTML:'', dialogClass:'dialog', dialogVisible:false, debugVisible:false,
      bossVisible:false, messages:[], text:{inspect:'',debug:''},
      s:{phase:'menu',player:false,saved:false,save_error:'',floor:0},
      p:{xp:0,xp_next:7,whirl_remaining:0,bolt_remaining:0},
      hero:{level:1,hp:42,max_hp:42,attack:6,armor:1,potions:3},
      boss:{hp:1,max_hp:1,rage:false}
    });
    const t=(key,params={})=>(ui.catalog[key]||key).replace(/&nbsp;/g,'\u00a0')
      .replace(/\{(\w+)\}/g,(_,name)=>String(params[name]??'{'+name+'}'));
    Alpine.data('emberkeep',()=>({ui,s:ui.s,p:ui.p,hero:ui.hero,boss:ui.boss,t,
      get saveStatus(){
        if(ui.working)return t(ui.working==='load_game'?'ui.loading':'ui.working');
        return t(ui.s.phase==='menu'?'ui.idle':ui.s.saved&&!ui.s.save_error?'ui.saved':'ui.unsaved');
      }
    }));
    window.EmberHTML={ui,t,nextTick:()=>Alpine.nextTick(),
      update(next,liveHero){
        if(next.catalog&&(!Object.keys(ui.catalog).length||next.language!==ui.language))ui.catalog=next.catalog;
        if(next.language!==ui.language||document.documentElement.lang!==next.language){
          ui.language=next.language;
          document.documentElement.lang=next.language;
        }
        const title=t('ui.window_title');if(document.title!==title)document.title=title;
        for(const key of ['phase','saved','save_error','floor','floors','floor_name','turn','seed','kills','gold']){
          ui.s[key]=next[key];
        }
        ui.s.player=!!next.player;
        if(next.player){
          // Materialize live Python properties as numbers; never proxy a host object with Alpine.
          for(const key of Object.keys(ui.hero))ui.hero[key]=(liveHero||next.player)[key];
          for(const key of Object.keys(ui.p))ui.p[key]=next.player[key];
        }
        const messages=next.player?(next.messages||[]).slice(-4):[t('ui.journal_intro')];
        if(JSON.stringify(messages)!==JSON.stringify(ui.messages)){
          ui.messages=messages;
          Alpine.nextTick(()=>{const log=document.getElementById('logLines');log.scrollTop=log.scrollHeight;});
        }
        const boss=(next.enemies||[]).find(enemy=>enemy.kind==='warden');
        ui.bossVisible=!!boss&&next.phase==='playing';
        if(boss)for(const key of Object.keys(ui.boss))ui.boss[key]=boss[key];
      }
    };
  });
})();
