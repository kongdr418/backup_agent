import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api/studyTools'
import type {
  FlashcardItem,
  ListFlashcardsParams,
  ListMistakesParams,
  MistakeCollection,
  MistakeItem,
  StatsResult,
} from '@/api/studyTools'

export const useStudyToolsStore = defineStore('studyTools', () => {
  const mistakes = ref<MistakeItem[]>([])
  const mistakesTotal = ref(0)
  const mistakesLoading = ref(false)

  const flashcards = ref<FlashcardItem[]>([])
  const flashcardsTotal = ref(0)
  const flashcardsLoading = ref(false)

  const dueCards = ref<FlashcardItem[]>([])
  const dueLoading = ref(false)

  const stats = ref<StatsResult | null>(null)
  const statsLoading = ref(false)

  const collections = ref<MistakeCollection[]>([])
  const collectionsLoading = ref(false)

  async function fetchMistakes(params: ListMistakesParams = {}) {
    mistakesLoading.value = true
    try {
      const r = await api.listMistakes(params)
      mistakes.value = r.items
      mistakesTotal.value = r.total
    } finally {
      mistakesLoading.value = false
    }
  }

  async function addMistake(payload: Partial<MistakeItem>, files?: File[]) {
    const item = files && files.length
      ? await api.addMistakeWithFiles(payload, files)
      : await api.addMistake(payload)
    mistakes.value = [item, ...mistakes.value]
    mistakesTotal.value += 1
    return item
  }

  async function addAttachments(mistakeId: string, files: File[]) {
    if (!files.length) return { saved: [], rejected: [], item: null as MistakeItem | null }
    const result = await api.uploadMistakeAttachments(mistakeId, files)
    if (result.item) {
      const i = mistakes.value.findIndex((m) => m.id === mistakeId)
      if (i !== -1) mistakes.value[i] = result.item
    }
    return { saved: result.saved, rejected: result.rejected, item: result.item }
  }

  async function removeAttachment(mistakeId: string, attachmentId: string) {
    const item = await api.deleteMistakeAttachment(mistakeId, attachmentId)
    const i = mistakes.value.findIndex((m) => m.id === mistakeId)
    if (i !== -1) mistakes.value[i] = item
    return item
  }

  async function updateMistake(id: string, patch: Partial<MistakeItem>) {
    const item = await api.updateMistake(id, patch)
    const i = mistakes.value.findIndex((m) => m.id === id)
    if (i !== -1) mistakes.value[i] = item
    return item
  }

  async function deleteMistake(id: string) {
    await api.deleteMistake(id)
    mistakes.value = mistakes.value.filter((m) => m.id !== id)
    mistakesTotal.value = Math.max(0, mistakesTotal.value - 1)
  }

  async function mistakeToFlashcard(id: string) {
    const card = await api.mistakeToFlashcard(id)
    flashcards.value = [card, ...flashcards.value]
    flashcardsTotal.value += 1
    return card
  }

  async function fetchFlashcards(params: ListFlashcardsParams = {}) {
    flashcardsLoading.value = true
    try {
      const r = await api.listFlashcards(params)
      flashcards.value = r.items
      flashcardsTotal.value = r.total
    } finally {
      flashcardsLoading.value = false
    }
  }

  async function addFlashcard(payload: Partial<FlashcardItem>) {
    const item = await api.addFlashcard(payload)
    flashcards.value = [item, ...flashcards.value]
    flashcardsTotal.value += 1
    return item
  }

  async function deleteFlashcard(id: string) {
    await api.deleteFlashcard(id)
    flashcards.value = flashcards.value.filter((c) => c.id !== id)
    flashcardsTotal.value = Math.max(0, flashcardsTotal.value - 1)
    dueCards.value = dueCards.value.filter((c) => c.id !== id)
  }

  async function fetchDueCards(limit = 50) {
    dueLoading.value = true
    try {
      dueCards.value = await api.listDueFlashcards(limit)
    } finally {
      dueLoading.value = false
    }
  }

  async function reviewFlashcard(id: string, grade: number) {
    const item = await api.reviewFlashcard(id, grade)
    const i = flashcards.value.findIndex((c) => c.id === id)
    if (i !== -1) flashcards.value[i] = item
    // 不在此处乐观移除 dueCards:统一在 closeReview / refreshAll 里 refetch
    // 否则会与后端 SRS 算法"评分后 due_date=tomorrow"产生 UI 假死,
    // 表现为"还有未复习的却不能点今日复习,必须刷新"(Bug 7)
    return item
  }

  async function fetchStats() {
    statsLoading.value = true
    try {
      stats.value = await api.getStats()
    } finally {
      statsLoading.value = false
    }
  }

  async function fetchCollections() {
    collectionsLoading.value = true
    try {
      collections.value = await api.listCollections()
    } finally {
      collectionsLoading.value = false
    }
  }

  async function createCollection(name: string, mistakeIds: string[] = []) {
    const item = await api.createCollection(name, mistakeIds)
    collections.value = [item, ...collections.value]
    // 若初始带入错题,刷新列表项的 collection_ids
    if (mistakeIds.length) {
      const idset = new Set(mistakeIds)
      mistakes.value = mistakes.value.map((m) =>
        idset.has(m.id) && !m.collection_ids.includes(item.id)
          ? { ...m, collection_ids: [item.id, ...m.collection_ids] }
          : m,
      )
    }
    return item
  }

  async function renameCollection(id: string, name: string) {
    const item = await api.renameCollection(id, name)
    const i = collections.value.findIndex((c) => c.id === id)
    if (i !== -1) collections.value[i] = item
    return item
  }

  async function deleteCollection(id: string) {
    await api.deleteCollection(id)
    collections.value = collections.value.filter((c) => c.id !== id)
    // 同步从所有错题中移除该 id
    mistakes.value = mistakes.value.map((m) =>
      m.collection_ids.includes(id)
        ? { ...m, collection_ids: m.collection_ids.filter((c) => c !== id) }
        : m,
    )
  }

  async function addMistakesToCollection(collectionId: string, mistakeIds: string[]) {
    const result = await api.addMistakesToCollection(collectionId, mistakeIds)
    const idset = new Set(mistakeIds)
    mistakes.value = mistakes.value.map((m) =>
      idset.has(m.id) && !m.collection_ids.includes(collectionId)
        ? { ...m, collection_ids: [collectionId, ...m.collection_ids] }
        : m,
    )
    // 刷新该集合的 count
    await fetchCollections()
    return result
  }

  async function removeMistakeFromCollection(collectionId: string, mistakeId: string) {
    await api.removeMistakeFromCollection(collectionId, mistakeId)
    const i = mistakes.value.findIndex((m) => m.id === mistakeId)
    if (i !== -1) {
      mistakes.value[i] = {
        ...mistakes.value[i],
        collection_ids: mistakes.value[i].collection_ids.filter((c) => c !== collectionId),
      }
    }
    await fetchCollections()
  }

  return {
    mistakes,
    mistakesTotal,
    mistakesLoading,
    flashcards,
    flashcardsTotal,
    flashcardsLoading,
    dueCards,
    dueLoading,
    stats,
    statsLoading,
    collections,
    collectionsLoading,
    fetchMistakes,
    addMistake,
    addAttachments,
    removeAttachment,
    updateMistake,
    deleteMistake,
    mistakeToFlashcard,
    fetchFlashcards,
    addFlashcard,
    deleteFlashcard,
    fetchDueCards,
    reviewFlashcard,
    fetchStats,
    fetchCollections,
    createCollection,
    renameCollection,
    deleteCollection,
    addMistakesToCollection,
    removeMistakeFromCollection,
  }
})
