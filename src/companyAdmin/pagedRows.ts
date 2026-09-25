type Row = Record<string, unknown>
type Page = { data: Row[] | null; count: number | null; error: unknown }

// Keep each response small even when the complete private directory exceeds
// the Data API response limit. A short server page is not the end of the table.
export async function readAllPages(
  fetchPage: (from: number, to: number) => PromiseLike<Page>,
  key: string,
): Promise<Row[]> {
  const rows: Row[] = []
  const ids = new Set<string>()
  let expected: number | undefined
  do {
    const page = await fetchPage(rows.length, rows.length + 99)
    if (page.error) {
      const message = typeof page.error === 'object' && 'message' in page.error ? String(page.error.message) : String(page.error)
      throw new Error(message)
    }
    if (!Array.isArray(page.data) || !Number.isSafeInteger(page.count) || page.count! < 0) {
      throw new Error('Company records returned an incomplete page. Please retry.')
    }
    expected ??= page.count!
    if (page.count !== expected || rows.length + page.data.length > expected || (!page.data.length && rows.length < expected)) {
      throw new Error('Company records changed or could not be loaded completely. Please retry.')
    }
    for (const row of page.data) {
      const id = row[key]
      if (typeof id !== 'string' || !id || ids.has(id)) {
        throw new Error('Company records returned missing or duplicate identifiers. Please retry.')
      }
      ids.add(id)
      rows.push(row)
    }
  } while (rows.length < expected)
  return rows
}
