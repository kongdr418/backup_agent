import type { GeneratedFile } from '@/types'

export function getGeneratedPptJobId(file: GeneratedFile) {
  if (file.job_id) return file.job_id
  return file.id.startsWith('svg_ppt_') ? file.id.slice('svg_ppt_'.length) : ''
}

function stripPptExtension(name: string) {
  return name.trim().replace(/\.(pptx|ppt)$/i, '')
}

export function buildCoursewareClassroomSeed(params: {
  selectedPptJobId: string
  files: GeneratedFile[]
  topic: string
  course: string
}) {
  const jobId = params.selectedPptJobId
  const matched = params.files.find((file) => getGeneratedPptJobId(file) === jobId)
  const fallbackTopic = matched?.name
    ? stripPptExtension(matched.name)
    : jobId
      ? `课堂-${jobId.slice(0, 8)}`
      : ''
  const topic = params.topic.trim() || fallbackTopic

  return {
    topic,
    course: params.course.trim() || topic,
  }
}

