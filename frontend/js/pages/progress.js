import { escapeHTML, subjectFor } from '../ui.js';

export const progressPage = (state, progress) => {
  const subjectStats = state.subjects
    .map(subject => ({ subject, count: progress.completed.filter(item => item.subject === subject.id).length }))
    .filter(item => item.count)
    .sort((a, b) => b.count - a.count);
  const maxCount = Math.max(...subjectStats.map(item => item.count), 1);
  const streakTarget = Math.min(progress.streak, 7);
  const streakPercent = Math.round((streakTarget / 7) * 100);

  return `<div class="progress-heading"><div><p class="eyebrow">LEARNING RECORD</p><h1 class="page-title">Your learning, in motion.</h1><p class="page-subtitle">Small lessons add up. Here is what you have been building.</p></div><div class="progress-badge" aria-hidden="true"><span>✦</span><strong>${progress.lessonsCompleted}</strong><small>learned</small></div></div>
  <div class="progress-layout">
    <section class="progress-main">
      <div class="stats-grid progress-stats"><div class="stat-card stat-card-primary"><small>Lessons completed</small><strong>${progress.lessonsCompleted}</strong><span>keep the momentum going</span></div><div class="stat-card"><small>Current streak</small><strong>${progress.streak}<em> days</em></strong><span>${progress.streak ? 'You are on a roll' : 'Start a new streak today'}</span></div><div class="stat-card"><small>Completed today</small><strong>${progress.completedToday}</strong><span>${progress.completedToday ? 'Nice work today' : 'There is time for one'}</span></div></div>
      <section class="streak-card"><div><p class="lesson-kicker">STREAK MOMENTUM</p><h2>${progress.streak ? `${progress.streak} day${progress.streak === 1 ? '' : 's'} in a row` : 'Make today count'}</h2><p>${progress.streak >= 7 ? 'A full week of learning. Keep going.' : `${7 - streakTarget} more ${7 - streakTarget === 1 ? 'day' : 'days'} to reach a one-week streak.`}</p></div><div class="streak-track" aria-label="${progress.streak} of 7 days toward a one-week streak"><span style="width:${streakPercent}%"></span><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></section>
      <div class="section-heading progress-section-heading"><h2>Recent lessons</h2><span class="muted">${progress.completed.length} total</span></div>
      ${progress.completed.length ? `<div class="history-list">${progress.completed.slice(0, 8).map(item => `<button class="history-item" data-action="open-lesson" data-id="${escapeHTML(item.id)}"><span class="history-emoji">${escapeHTML(subjectFor(state.subjects,item.subject).icon)}</span><span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(subjectFor(state.subjects,item.subject).name)} · ${new Date(item.date).toLocaleDateString()}</small></span><span class="history-arrow">→</span></button>`).join('')}</div>` : '<div class="progress-empty"><span>✦</span><h2>Your story starts with one lesson.</h2><p>Complete a lesson and your learning history will appear here.</p><button class="button-primary" data-route="explore">Explore lessons</button></div>'}
    </section>
    <aside class="progress-sidebar"><section class="subject-progress"><div class="section-heading"><h2>Learning by subject</h2></div>${subjectStats.length ? subjectStats.map(item => `<div class="subject-progress-row"><div><span>${escapeHTML(item.subject.icon)}</span><strong>${escapeHTML(item.subject.name)}</strong><small>${item.count} ${item.count === 1 ? 'lesson' : 'lessons'}</small></div><div class="subject-track"><span style="width:${Math.round((item.count / maxCount) * 100)}%"></span></div></div>`).join('') : '<p class="muted">Your completed subjects will show up here.</p>'}</section><section class="progress-next"><p class="lesson-kicker">NEXT UP</p><h2>Keep your curiosity moving.</h2><p>Explore a new subject or generate a lesson from a question.</p><button class="button-secondary" data-route="explore">Find a lesson →</button></section></aside>
  </div>`;
};
