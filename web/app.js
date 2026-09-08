const token=document.querySelector('meta[name="coach-token"]').content;
const state={catalog:[],draft:null,strava:null};
const days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const $=id=>document.getElementById(id);
const value=id=>$(id).value;
const number=id=>Number(value(id));
const persistedFields=['race-search','race-name','race-date','start-date','goal-hours','goal-minutes','benchmark-distance','benchmark-date','benchmark-hours','benchmark-minutes','benchmark-seconds','weekly-km','runs-week','long-run','long-day','context'];

async function api(path,body){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Coach-Token':token},body:JSON.stringify(body||{})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Request failed');
  return data;
}
function showStep(id){
  document.querySelector('.hero').classList.add('hidden');$('wizard').classList.remove('hidden');
  document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===id));
  document.querySelectorAll('.step').forEach(x=>x.classList.toggle('active',x.dataset.step===id));
  window.scrollTo({top:0,behavior:'smooth'});
}
function seconds(hours,minutes,extra=0){return Math.round((Number(hours)*60+Number(minutes))*60+Number(extra))}
function clock(total){total=Math.round(total);const h=Math.floor(total/3600),m=Math.floor(total%3600/60),s=total%60;return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}
function escapeText(text){const span=document.createElement('span');span.textContent=String(text);return span.innerHTML}

document.querySelectorAll('[data-go],[data-next],[data-back]').forEach(button=>button.addEventListener('click',()=>showStep(button.dataset.go||button.dataset.next||button.dataset.back)));
document.querySelectorAll('.step').forEach(button=>button.addEventListener('click',()=>showStep(button.dataset.step)));

days.forEach((day,index)=>{
  const label=document.createElement('label');label.innerHTML=`<input type="checkbox" value="${index}" ${[1,3,5,6].includes(index)?'checked':''}><span>${day}</span>`;$('days').append(label);
  const option=document.createElement('option');option.value=index;option.textContent=day;if(index===6)option.selected=true;$('long-day').append(option);
});
function localISODate(){const now=new Date();return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`}
$('start-date').value=localISODate();$('start-date').min=localISODate();

function rememberInputs(){
  const fields=Object.fromEntries(persistedFields.map(id=>[id,value(id)]));
  const risk=document.querySelector('input[name="risk"]:checked').value;
  const runDays=[...document.querySelectorAll('#days input:checked')].map(x=>x.value);
  sessionStorage.setItem('coach-onboarding',JSON.stringify({fields,risk,runDays}));
}
function restoreInputs(){
  try{
    const saved=JSON.parse(sessionStorage.getItem('coach-onboarding')||'null');if(!saved)return;
    Object.entries(saved.fields||{}).forEach(([id,v])=>{if($(id))$(id).value=v});
    const risk=[...document.querySelectorAll('input[name="risk"]')].find(x=>x.value===saved.risk);if(risk)risk.checked=true;
    document.querySelectorAll('#days input').forEach(x=>x.checked=(saved.runDays||[]).includes(x.value));
  }catch(_error){sessionStorage.removeItem('coach-onboarding')}
}

fetch('/api/catalog').then(r=>r.json()).then(data=>state.catalog=data.races);
$('race-search').addEventListener('input',()=>{
  const query=value('race-search').toLowerCase().trim();const box=$('race-results');box.textContent='';
  if(query.length<2){box.classList.add('hidden');return}
  state.catalog.filter(r=>`${r.name} ${r.city} ${r.country}`.toLowerCase().includes(query)).slice(0,8).forEach(race=>{
    const button=document.createElement('button');button.className='result';
    const title=document.createElement('strong');title.textContent=race.name;
    const detail=document.createElement('small');detail.textContent=`${race.city}, ${race.country}${race.next_date?' · '+race.next_date:' · date not confirmed'}`;
    button.append(title,detail);button.addEventListener('click',()=>{
      $('race-name').value=race.name;$('race-search').value=race.name;
      if(race.next_date)$('race-date').value=race.next_date;
      $('race-source').textContent='';const link=document.createElement('a');link.href=race.url;link.target='_blank';link.rel='noreferrer';
      link.textContent=race.next_date?`Official date · verified ${race.verified_at} ↗`:'Check the date on the official race site ↗';$('race-source').append(link);
      box.classList.add('hidden');
    });box.append(button);
  });box.classList.toggle('hidden',!box.children.length);
});

$('show-strava').addEventListener('click',()=>$('strava-box').classList.toggle('hidden'));
$('connect-strava').addEventListener('click',async()=>{
  try{rememberInputs();const data=await api('/api/strava/start',{client_id:value('client-id'),client_secret:value('client-secret'),read_private:$('read-private').checked});location.href=data.url}
  catch(error){$('strava-data').className='error';$('strava-data').textContent=error.message}
});

async function loadStrava(){
  $('strava-data').className='race-list';$('strava-data').textContent='Reading your recent Strava training…';
  try{
    const data=await api('/api/strava/analyse',{timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'});state.strava=data;
    $('weekly-km').value=data.baseline.median_weekly_km;$('runs-week').value=data.baseline.runs_per_week;$('long-run').value=data.baseline.longest_run_km;
    $('strava-data').textContent='';const title=document.createElement('strong');title.textContent=`Connected · ${data.race_candidates.length} possible recent race${data.race_candidates.length===1?'':'s'}`;$('strava-data').append(title);
    const explanation=document.createElement('p');explanation.textContent='From the last 12 months: activities marked or named as races appear first. If those labels are missing, the fastest run within 5% of each standard distance appears once as a fallback. Confirm the correct result below.';$('strava-data').append(explanation);
    if(!data.race_candidates.length){const copy=document.createElement('p');copy.textContent='Training data was found, but no run in the last year was close to a standard race distance. Enter a result below.';$('strava-data').append(copy)}
    if(data.race_candidates.length){const header=document.createElement('div');header.className='race-row race-header';['Date','Activity','Distance','Time','Match'].forEach(x=>{const cell=document.createElement('span');cell.textContent=x;header.append(cell)});$('strava-data').append(header)}
    data.race_candidates.forEach(race=>{const button=document.createElement('button');button.className='race-row';const values=[race.date,race.name,`${race.recorded_km} km`,race.recorded_seconds?clock(race.recorded_seconds):'—',race.confidence==='likely_race'?'Race label':'Fastest match'];values.forEach(x=>{const cell=document.createElement('span');cell.textContent=x;button.append(cell)});button.addEventListener('click',()=>{document.querySelectorAll('.race-row.selected').forEach(x=>x.classList.remove('selected'));button.classList.add('selected');$('benchmark-distance').value=race.distance_km;$('benchmark-date').value=race.date;if(race.recorded_seconds){$('benchmark-hours').value=Math.floor(race.recorded_seconds/3600);$('benchmark-minutes').value=Math.floor(race.recorded_seconds%3600/60);$('benchmark-seconds').value=race.recorded_seconds%60}});$('strava-data').append(button)});
  }catch(error){$('strava-data').className='notice error';$('strava-data').textContent=error.message}
}
if(new URLSearchParams(location.search).get('strava')==='connected'){restoreInputs();showStep('fitness');loadStrava();sessionStorage.removeItem('coach-onboarding')}

function updateReadiness(){
  const gaps=[];if(number('weekly-km')<25)gaps.push('Weekly volume is below the 25 km reference.');if(number('runs-week')<3)gaps.push('Recent frequency is below three runs per week.');if(number('long-run')<12)gaps.push('The longest recent run is below 12 km.');
  $('readiness').innerHTML=`<h3>${gaps.length?'Some foundation gaps':'Standard foundation'}</h3><p>${gaps.length?gaps.map(escapeText).join('<br>')+'<br>Your plan will start conservatively from these values.':'Your recent training meets the suggested starting references.'}</p>`;
}
['weekly-km','runs-week','long-run'].forEach(id=>$(id).addEventListener('input',updateReadiness));updateReadiness();

function formData(){
  const runDays=[...document.querySelectorAll('#days input:checked')].map(x=>Number(x.value));
  return {race_name:value('race-name').trim(),race_date:value('race-date'),start_date:value('start-date'),goal_seconds:seconds(number('goal-hours'),number('goal-minutes')),
    benchmark:{name:'Confirmed race result',distance_km:number('benchmark-distance'),date:value('benchmark-date'),seconds:seconds(number('benchmark-hours'),number('benchmark-minutes'),number('benchmark-seconds'))},
    weekly_km:number('weekly-km'),runs_per_week:number('runs-week'),long_run_km:number('long-run'),history_weeks:state.strava?state.strava.baseline.active_weeks:8,
    run_days:runDays,long_run_day:number('long-day'),aggressiveness:document.querySelector('input[name="risk"]:checked').value,context:value('context'),timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'};
}
$('generate').addEventListener('click',async()=>{
  $('plan-error').textContent='';
  try{state.draft=await api('/api/plan',formData());renderDraft(state.draft);showStep('draft')}
  catch(error){$('plan-error').textContent=error.message}
});
function renderDraft(draft){
  const r=draft.readiness;$('draft-summary').innerHTML=`<div class="summary-grid"><div class="stat"><strong>${draft.vdot}</strong><span>CURRENT VDOT</span></div><div class="stat"><strong>${draft.weeks}</strong><span>WEEKS</span></div><div class="stat"><strong>${draft.peak_km} km</strong><span>PEAK WEEK</span></div><div class="stat"><strong>${clock(draft.marathon_equivalent_seconds)}</strong><span>CURRENT EQUIVALENT</span></div></div><div class="pace-grid">${Object.entries(draft.paces).map(([k,v])=>`<div class="pace"><b>${k}</b><span>${escapeText(v)}</span></div>`).join('')}</div><div class="readiness"><h3>${escapeText(r.status)}</h3><p>${r.gaps.length?r.gaps.map(escapeText).join('<br>'):'The suggested starting references are met.'}</p></div>`;
  if(draft.warnings.length){const note=document.createElement('div');note.className='readiness warning';const heading=document.createElement('h3');heading.textContent='Review before accepting';const copy=document.createElement('p');copy.textContent=draft.warnings.join(' ');note.append(heading,copy);$('draft-summary').append(note)}
  $('weeks').textContent='';draft.config.weeks.forEach(week=>{const longest=Math.max(0,...week.workouts.filter(x=>x.long_run||x.race).map(x=>x.segments.reduce((sum,s)=>sum+s.km*(s.repeats||1)+(s.recovery_km||0)*((s.repeats||1)-1),0)));const row=document.createElement('div');row.className='week';row.innerHTML=`<strong>W${week.number}</strong><span>${week.start}</span><b>${escapeText(week.phase)}</b><span>${week.training_km} km</span><strong>${longest?longest.toFixed(1)+' km':'—'}</strong>`;$('weeks').append(row)});
}
$('save').addEventListener('click',async()=>{
  try{await api('/api/save',{config:state.draft.config,anthropic_api_key:value('anthropic-key')});$('anthropic-key').value='';$('save-status').className='source success';$('save-status').textContent='Draft saved privately.';$('after-save').classList.remove('hidden');$('after-save').scrollIntoView({behavior:'smooth',block:'start'})}
  catch(error){$('save-status').className='source error';$('save-status').textContent=error.message}
});

async function dashboard(send=false){
  const status=send?$('dashboard-status'):$('home-status');status.className='form-error';status.textContent=send?'Preparing and sending your dashboard…':'Refreshing your dashboard from Strava…';
  try{const data=await api('/api/dashboard',{use_ai:$('dashboard-ai').checked,send});if(send){status.className='source success';status.textContent='Dashboard sent.'}else{location.href=data.url}}
  catch(error){status.textContent=error.message}
}
$('open-dashboard').addEventListener('click',()=>dashboard(false));
$('open-dashboard-home').addEventListener('click',()=>dashboard(false));
$('save-email').addEventListener('click',async()=>{const status=$('dashboard-status');try{await api('/api/email/save',{sender:value('email-sender'),recipient:value('email-recipient'),app_password:value('email-password')});$('email-password').value='';status.className='source success';status.textContent='Email settings saved in private local storage and macOS Keychain.'}catch(error){status.className='form-error';status.textContent=error.message}});
$('send-dashboard').addEventListener('click',()=>dashboard(true));
fetch('/api/status').then(r=>r.json()).then(data=>{if(data.plan_saved&&data.strava_connected)$('open-dashboard-home').classList.remove('hidden')});
