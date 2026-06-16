import type { InteractiveClassroomScene } from '../api/interactiveClassroom.ts'

export interface PreviewSceneMergeResult {
  scenes: InteractiveClassroomScene[]
  currentIndex: number
}

export interface LockedPreviewScene {
  id: string
  title: string
  order: number
  locked: true
}

export function buildLockedPreviewScenes(
  readyCount: number,
  expectedTotal: number,
  expectedSlideTotal = expectedTotal,
): LockedPreviewScene[] {
  if (expectedTotal <= readyCount) return []
  const rows: LockedPreviewScene[] = []
  for (let order = readyCount + 1; order <= expectedTotal; order += 1) {
    const isMindmap = expectedTotal > expectedSlideTotal && order === expectedTotal
    const isSlide = order <= expectedSlideTotal
    rows.push({
      id: `locked_scene_${order}`,
      title: isSlide ? `第 ${order} 页生成中` : (isMindmap ? '知识结构生成中' : '随堂测验生成中'),
      order,
      locked: true,
    })
  }
  return rows
}

function previewSceneSortOrder(scene: InteractiveClassroomScene): number {
  return scene.order > 0 ? scene.order : Number.MAX_SAFE_INTEGER
}

export function mergePreviewScene(
  currentScenes: InteractiveClassroomScene[],
  incomingScene: InteractiveClassroomScene,
  currentIndex: number,
): PreviewSceneMergeResult {
  const activeSceneId = currentScenes[currentIndex]?.id || ''
  const nextScenes = [...currentScenes]
  const existingIndex = nextScenes.findIndex((item) => item.id === incomingScene.id)

  if (existingIndex >= 0) {
    nextScenes[existingIndex] = incomingScene
  } else {
    nextScenes.push(incomingScene)
  }

  nextScenes.sort((a, b) => previewSceneSortOrder(a) - previewSceneSortOrder(b))

  if (!activeSceneId) {
    return { scenes: nextScenes, currentIndex: nextScenes.length ? 0 : 0 }
  }

  const nextActiveIndex = nextScenes.findIndex((item) => item.id === activeSceneId)
  return {
    scenes: nextScenes,
    currentIndex: nextActiveIndex >= 0 ? nextActiveIndex : Math.min(currentIndex, nextScenes.length - 1),
  }
}
