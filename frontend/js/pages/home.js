import { escapeHTML, empty, lessonCard, subjectFor } from '../ui.js';

export const homePage = state => {
  const interests = state.preferences?.subjects || [];
  const finished = new Set(state.progress?.completed?.map(item => item.id) || []);
  const recommendations = state.lessons.filter(item => interests.includes(item.subject));
  const featured = recommendations.find(item => !finished.has(item.id));
  const subjectNames = interests
    .map(id => subjectFor(state.subjects, id).name)
    .filter(Boolean);

  return `<div class="welcome-row"><div><p class="eyebrow">${new Intl.DateTimeFormat(undefined,{month:'long',day:'numeric'}).format(new Date())}</p><h1>Learn one useful thing.</h1><p class="muted">Turn a question into a focused lesson, whenever you are ready.</p></div><button class="button-secondary" data-route="profile">Settings</button></div>
  <section class="generation-hero">
    <div class="generation-copy">
      <p class="lesson-kicker">CREATE A LESSON</p>
      <h2>What do you want to understand?</h2>
      <p>Ask about anything. Crumb will shape it into a clear, practical lesson with a short quiz.</p>
      <form data-form="generate" class="generation-form">
        <label class="sr-only" for="lesson-prompt">Topic or question</label>
        <textarea id="lesson-prompt" name="prompt" rows="3" maxlength="240" placeholder="How do eclipses happen?" required></textarea>
        <div class="generation-actions"><button class="button-primary" type="submit">Generate lesson <span aria-hidden="true">→</span></button><button class="button-secondary" type="button" data-action="generate-random-topic">Surprise me</button></div>
      </form>
      ${subjectNames.length ? `<p class="generation-context">Personalized across ${escapeHTML(subjectNames.slice(0, 3).join(', '))}${subjectNames.length > 3 ? ` and ${subjectNames.length - 3} more` : ''}.</p>` : `<p class="generation-context">Choose subjects to make surprise topics more personal.</p>`}
    </div>
    <div class="generation-art" aria-hidden="true"><span class="generation-orbit"></span><span class="generation-spark spark-one">✦</span><span class="generation-spark spark-two">✦</span><span class="generation-c">c<span>.</span></span></div>
  </section>
  <div class="home-secondary">
    <section>
      <div class="section-heading"><h2>Keep learning</h2>${featured ? '' : '<button class="text-button" data-route="explore">Browse library</button>'}</div>
      ${featured ? `<div class="continue-card"><div><p class="lesson-kicker">${escapeHTML(subjectFor(state.subjects,featured.subject).name)} · ${Number(featured.minutes)||4} MIN</p><h3>${escapeHTML(featured.title)}</h3><p>${escapeHTML(featured.lead)}</p></div><button class="button-secondary" data-action="open-lesson" data-id="${escapeHTML(featured.id)}">Open lesson</button></div>` : empty('Your library is ready when you are','Generated lessons and curated material will appear here.')}
    </section>
    <aside class="home-quick-links">
      <div class="section-heading"><h2>Your subjects</h2><button class="text-button" data-route="subjects">Edit</button></div>
      <div class="subject-chips">${interests.slice(0, 5).map(id => { const s = subjectFor(state.subjects, id); return `<button class="subject-chip" data-action="filter-subject" data-id="${escapeHTML(id)}"><span>${escapeHTML(s.icon)}</span>${escapeHTML(s.name)}</button>`; }).join('') || '<button class="subject-chip subject-chip-empty" data-route="subjects">＋ Select subjects</button>'}</div>
      <div class="quick-link-row"><span><strong>${state.progress?.lessonsCompleted || 0}</strong> lessons completed</span><button class="text-button" data-route="progress">View progress</button></div>
    </aside>
  </div>
  ${recommendations.length > 1 ? `<section class="home-library-preview"><div class="section-heading"><h2>From your library</h2><button class="text-button" data-route="explore">View all lessons</button></div><div class="lesson-list">${recommendations.filter(x=>x.id!==featured?.id).slice(0,2).map(l=>lessonCard(l,subjectFor(state.subjects,l.subject))).join('')}</div></section>` : ''}`;
};
