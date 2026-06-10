export interface ClassroomLessonDisplayInput {
  lesson_kind?: string
  lesson_index?: number
}

export function classroomUnitLabel(item: ClassroomLessonDisplayInput): string {
  if (item.lesson_kind === 'practice') return '补强练习'
  if (item.lesson_kind === 'challenge_practice') return '挑战练习'
  return `第 ${item.lesson_index || 1} 课`
}

export function classroomUnitCountLabel(count: number): string {
  return `${count} 个学习单元`
}
