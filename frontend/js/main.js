import { api } from './api.js';
import { state, clearAccount } from './state.js';
import { shell, showToast } from './ui.js';
import { authPage } from './pages/auth.js';
import { homePage } from './pages/home.js';
import { subjectsPage } from './pages/subjects.js';
import { explorePage } from './pages/explore.js';
import { progressPage } from './pages/progress.js';
import { lessonPage } from './pages/lesson.js';
import { profilePage } from './pages/profile.js';

const root=document.querySelector('#app');
let authMode='register',authError='',searchQuery='',subjectFilter='';
const showError=error=>showToast(error?.message||'Request failed.');
async function refreshAccount(){
  const [account,progress,library]=await Promise.all([api.me(),api.progress(),api.lessons()]);
  state.user=account.user;state.preferences=account.preferences;state.progress=progress;state.lessons=library.lessons;state.subjects=await api.subjects().then(x=>x.subjects);
}
function render(){
  if(!state.user){root.innerHTML=authPage(authMode,authError);return;}
  let content='';
  if(state.route==='subjects')content=subjectsPage(state);
  else if(state.route==='explore'){
    const library=state.lessons.filter(item=>(!searchQuery||item.title.toLowerCase().includes(searchQuery.toLowerCase())||item.body.toLowerCase().includes(searchQuery.toLowerCase()))&&(!subjectFilter||item.subject===subjectFilter));
    content=explorePage(state,library,searchQuery);
  } else if(state.route==='lesson'&&state.lesson)content=lessonPage(state,state.lesson);
  else if(state.route==='progress')content=progressPage(state,state.progress||{lessonsCompleted:0,streak:0,completedToday:0,completed:[]});
  else if(state.route==='profile')content=profilePage(state);
  else content=homePage(state);
  root.innerHTML=shell(state,content);
}
async function start(){
  try{state.subjects=(await api.subjects()).subjects;await refreshAccount();render();}
  catch(error){state.user=null;authError=error.message==='Sign in to continue.'?'':`Could not load Crumb data: ${error.message}`;render();}
}
async function openLesson(id){try{const back=state.route==='explore'?'explore':'home';state.lesson=(await api.lesson(id)).lesson;state.backRoute=back;state.route='lesson';state.selectedAnswers={};render();}catch(error){showError(error);}}
root.addEventListener('click',async event=>{
  const action=event.target.closest('[data-action]');const route=event.target.closest('[data-route]');
  if(route){event.preventDefault();state.route=route.dataset.route;state.lesson=null;state.selectedAnswers={};subjectFilter='';render();return;}
  if(!action)return;
  const {action:kind,id}=action.dataset;
  try{
    if(kind==='auth-mode'){authMode=action.dataset.mode;authError='';render();}
    if(kind==='open-lesson')await openLesson(id);
    if(kind==='filter-subject'){subjectFilter=id;searchQuery='';state.route='explore';render();}
    if(kind==='random'){const result=await api.randomLesson();if(!result.lesson){showToast('No lessons match your subjects yet.');return;}await openLesson(result.lesson.id);}
    if(kind==='generate-random-topic'){
      const label=action.textContent;action.disabled=true;action.textContent='Generating…';
      try{const result=await api.generateRandom();state.lesson=result.lesson;state.route='lesson';state.backRoute='home';state.selectedAnswers={};await refreshAccount();render();}
      finally{if(action.isConnected){action.disabled=false;action.textContent=label;}}
    }
    if(kind==='answer'){state.selectedAnswers={...state.selectedAnswers,[Number(action.dataset.questionIndex)]:Number(action.dataset.answer)};render();}
    if(kind==='complete'){await api.complete(id);state.progress=await api.progress();state.route='progress';state.lesson=null;render();showToast('Lesson saved.');}
    if(kind==='logout'){await api.logout();clearAccount();render();}
    if(kind==='clear-search'){searchQuery='';subjectFilter='';render();}
  }catch(error){showError(error);}
});
root.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target;const data=new FormData(form);
  try{
    if(form.dataset.form==='auth'){
      const mode=form.dataset.mode;const payload={email:data.get('email'),password:data.get('password')};if(mode==='register')payload.name=data.get('name');
      const account=await (mode==='register'?api.register(payload):api.login(payload));state.user=account.user;state.preferences=account.preferences;authError='';await refreshAccount();state.route=state.preferences.subjects.length?'home':'subjects';render();return;
    }
    if(form.dataset.form==='subjects'){
      const subjects=data.getAll('subject');const result=await api.savePreferences({...state.preferences,subjects});state.preferences=result.preferences;state.user=result.user;render();showToast('Subjects saved.');return;
    }
    if(form.dataset.form==='profile'){
      const result=await api.savePreferences({...state.preferences,name:data.get('name'),reminderEnabled:data.has('reminderEnabled'),reminderTime:data.get('reminderTime')});state.preferences=result.preferences;state.user=result.user;render();showToast('Settings saved.');return;
    }
    if(form.dataset.form==='search'){searchQuery=String(data.get('q')||'').trim();subjectFilter='';render();return;}
    if(form.dataset.form==='generate'){
      const button=form.querySelector('button[type="submit"]');button.disabled=true;button.textContent='Generating…';
      const result=await api.generate(data.get('prompt'));state.lesson=result.lesson;state.route='lesson';state.backRoute='home';state.selectedAnswers={};await refreshAccount();state.route='lesson';render();return;
    }
  }catch(error){if(form.dataset.form==='auth'){authError=error.message;render();}else{if(form.dataset.form==='generate')render();showError(error);}}
});
start();
