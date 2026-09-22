/** Wait for the exact report assets. Do not silently export a substituted typeface. */
export async function prepareAccountReport(): Promise<void> {
  const report = document.querySelector<HTMLElement>('.client-pdf-report')
  if (!report) throw new Error('The account report has not loaded yet.')
  const loaded = await Promise.all([400, 500, 600, 700, 800].map(weight => document.fonts.load(`${weight} 12px TowerSignalReportInter`)))
  if (loaded.some(fonts => fonts.length === 0)) throw new Error('The report font could not be loaded. Please retry the export.')
  await Promise.all([...report.querySelectorAll('img')].map(async image => {
    await image.decode()
    if (!image.naturalWidth) throw new Error('The report logo could not be loaded.')
  }))
  report.dataset.assetsReady = 'true'
}
