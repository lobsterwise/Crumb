import { escapeHTML, subjectFor } from '../ui.js';

export const lessonPage = (state, lesson) => {
  const sections = Array.isArray(lesson.sections) && lesson.sections.length
    ? `<div class="lesson-sections">${lesson.sections.map((section, index) => `<section class="lesson-section"><h2><span>${String(index + 1).padStart(2, '0')}</span>${escapeHTML(section.heading)}</h2><p>${escapeHTML(section.body)}</p></section>`).join('')}</div>`
    : `<div class="lesson-body">${escapeHTML(lesson.body || '')}</div>`;
  const questions = Array.isArray(lesson.questions) && lesson.questions.length
    ? lesson.questions
    : lesson.question ? [{question:lesson.question,options:lesson.options,answerIndex:lesson.answerIndex}] : [];
  const quizzes = questions.map((question, questionIndex) => {
    const selected = state.selectedAnswers?.[questionIndex];
    const options = (question.options || []).map((option, index) => {
      const resultClass = selected === index ? (index === question.answerIndex ? 'correct' : 'wrong') : '';
      return `<button class="quiz-option ${resultClass}" data-action="answer" data-question-index="${questionIndex}" data-answer="${index}" ${selected !== undefined ? 'disabled' : ''}>${String.fromCharCode(65 + index)}. ${escapeHTML(option)}</button>`;
    }).join('');
    const feedback = selected !== undefined
      ? `<p class="quiz-feedback">${selected === question.answerIndex ? 'Correct.' : `Answer: ${escapeHTML(question.options?.[question.answerIndex] || '')}`}${question.explanation ? ` ${escapeHTML(question.explanation)}` : ''}</p>`
      : '';
    return `<section class="quiz-box"><p class="eyebrow">CHECK ${String(questionIndex + 1).padStart(2, '0')}</p><h2>${escapeHTML(question.question)}</h2><div class="quiz-options">${options}</div>${feedback}</section>`;
  }).join('');

  return `<button class="back-link" data-route="${state.backRoute || 'home'}">← Back</button>
    <article class="lesson-panel">
      <p class="eyebrow">${escapeHTML(subjectFor(state.subjects, lesson.subject).name)} · ${Number(lesson.minutes) || 4} MIN · ${escapeHTML(lesson.tag || 'LESSON')}</p>
      <h1>${escapeHTML(lesson.title)}</h1>
      <p class="lesson-lead">${escapeHTML(lesson.lead)}</p>
      ${sections}
      ${lesson.takeaway ? `<aside class="lesson-callout">${escapeHTML(lesson.takeaway)}</aside>` : ''}
      ${quizzes ? `<div class="quiz-list"><h2>Review what you learned</h2>${quizzes}</div>` : ''}
      <div class="lesson-footer"><span>${escapeHTML(lesson.source || 'Lesson')}</span><button class="button-primary" data-action="complete" data-id="${escapeHTML(lesson.id)}">Mark complete</button></div>
    </article>`;
};
