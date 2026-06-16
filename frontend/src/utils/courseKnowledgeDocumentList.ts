export function toggleExpandedKnowledgeDocument(
  currentDocumentId: string | null,
  documentId: string,
): string | null {
  return currentDocumentId === documentId ? null : documentId
}
