import { escapeHTML, subjectFor } from '../ui.js';

export const lessonPage = (state, lesson) => {
  const options = (lesson.options || []).map((option, index) => {
    const resultClass = state.selectedAnswer === index
      ? (index === lesson.answerIndex ? 'correct' : 'wrong')
      : '';
    return `<button class="quiz-option ${resultClass}" data-action="answer" data-answer="${index}" ${state.selectedAnswer !== null ? 'disabled' : ''}>${String.fromCharCode(65 + index)}. ${escapeHTML(option)}</button>`;
  }).join('');

  return `<button class="back-link" data-route="${state.backRoute || 'home'}">← Back</button>
    <article class="lesson-panel">
      <p class="eyebrow">${escapeHTML(subjectFor(state.subjects, lesson.subject).name)} · ${Number(lesson.minutes) || 4} MIN · ${escapeHTML(lesson.tag || 'LESSON')}</p>
      <h1>${escapeHTML(lesson.title)}</h1>
      <p class="lesson-lead">${escapeHTML(lesson.lead)}</p>
      <div class="lesson-body">${escapeHTML(lesson.body)}</div>
      ${lesson.takeaway ? `<aside class="lesson-callout">${escapeHTML(lesson.takeaway)}</aside>` : ''}
      <section class="quiz-box">
        <h2>${escapeHTML(lesson.question)}</h2>
        <div class="quiz-options">${options}</div>
        ${state.selectedAnswer !== null ? `<p class="quiz-feedback">${state.selectedAnswer === lesson.answerIndex ? 'Correct.' : `Answer: ${escapeHTML(lesson.options?.[lesson.answerIndex] || '')}`}</p>` : ''}
      </section>
      <div class="lesson-footer"><span>${escapeHTML(lesson.source || 'Lesson')}</span><button class="button-primary" data-action="complete" data-id="${escapeHTML(lesson.id)}">Mark complete</button></div>
    </article>`;
};
