export const state = {
  user: null,
  preferences: null,
  subjects: [],
  progress: null,
  lessons: [],
  route: 'home',
  lesson: null,
  selectedAnswer: null,
};
export function clearAccount() {
  state.user = null;
  state.preferences = null;
  state.progress = null;
  state.lessons = [];
  state.lesson = null;
  state.route = 'home';
}
