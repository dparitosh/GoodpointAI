import readXlsxFile from 'read-excel-file';
import writeXlsxFile from 'write-excel-file';

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export async function readExcelArrayBufferToAoa(arrayBuffer) {
  const rows = await readXlsxFile(arrayBuffer);
  const aoa = Array.isArray(rows) ? rows : [];
  const maxLen = aoa.reduce((m, r) => Math.max(m, Array.isArray(r) ? r.length : 0), 0);

  return aoa.map((r) => {
    const row = Array.isArray(r) ? r : [];
    const out = row.map((v) => (v == null ? '' : String(v)));
    while (out.length < maxLen) out.push('');
    return out;
  });
}

export function jsonToAoa(items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return [];

  const headers = Array.from(
    list.reduce((set, obj) => {
      Object.keys(obj || {}).forEach((k) => set.add(k));
      return set;
    }, new Set())
  );

  const rows = list.map((obj) => headers.map((h) => (obj && obj[h] != null ? String(obj[h]) : '')));
  return [headers, ...rows];
}

export function jsonToCsv(items) {
  const aoa = jsonToAoa(items);
  if (!aoa.length) return '';

  return aoa
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n');
}

export async function sheetsToXlsxBlob(sheets) {
  const safeSheets = Array.isArray(sheets) ? sheets : [];
  const names = safeSheets.map((s, idx) => s?.name || `Sheet${idx + 1}`);
  const toCellRow = (row) =>
    (Array.isArray(row) ? row : [row]).map((cell) => ({ value: cell == null ? '' : String(cell) }));
  const toData = (aoa) => (Array.isArray(aoa) ? aoa : []).map(toCellRow);

  const dataList = safeSheets.map((s) => toData(s?.aoa));
  if (!dataList.length) {
    return await writeXlsxFile([[{ value: '' }]], { sheet: 'Sheet1' });
  }

  // In browsers, writeXlsxFile returns a Blob when no fileName is provided.
  const blob =
    dataList.length === 1
      ? await writeXlsxFile(dataList[0], { sheet: names[0] || 'Sheet1' })
      : await writeXlsxFile(dataList, { sheets: names });

  return blob;
}
