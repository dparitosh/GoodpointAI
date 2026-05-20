import readXlsxFile from 'read-excel-file';
import writeXlsxFile from 'write-excel-file';

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export async function readExcelArrayBufferToAoa(arrayBuffer) {
  // Backward compatible signature: (arrayBuffer) or (arrayBuffer, sheet)
  const sheet = arguments.length > 1 ? arguments[1] : undefined;
  let rows;
  try {
    rows = sheet != null ? await readXlsxFile(arrayBuffer, { sheet }) : await readXlsxFile(arrayBuffer);
  } catch (_err) {
    // Fall back to default sheet behavior if the library rejects options.
    rows = await readXlsxFile(arrayBuffer);
  }
  const aoa = Array.isArray(rows) ? rows : [];
  const maxLen = aoa.reduce((m, r) => Math.max(m, Array.isArray(r) ? r.length : 0), 0);

  return aoa.map((r) => {
    const row = Array.isArray(r) ? r : [];
    const out = row.map((v) => (v == null ? '' : String(v)));
    while (out.length < maxLen) out.push('');
    return out;
  });
}

export async function getExcelSheetNames(arrayBuffer) {
  try {
    const sheets = await readXlsxFile(arrayBuffer, { getSheets: true });
    const list = Array.isArray(sheets) ? sheets : [];
    return list
      .map((s) => (typeof s === 'string' ? s : s?.name))
      .filter((n) => typeof n === 'string' && n.trim() !== '');
  } catch (_err) {
    return [];
  }
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
  let blob;
  if (dataList.length === 1) {
    blob = await writeXlsxFile(dataList[0], { sheet: names[0] || 'Sheet1' });
  } else {
    // For multiple sheets, convert to the format required by write-excel-file
    // Each sheet needs { columns: [...], data: [...] }
    const sheetsData = dataList.map((data) => {
      if (!data.length) return { columns: [], data: [] };
      
      const headerRow = data[0]; // First row contains headers
      const columns = headerRow.map((cell, idx) => ({
        title: cell.value || `Column ${idx + 1}`,
        key: `col${idx}`
      }));
      
      const rows = data.slice(1).map((row) => {
        const obj = {};
        row.forEach((cell, idx) => {
          obj[`col${idx}`] = cell.value || '';
        });
        return obj;
      });
      
      return { columns, data: rows };
    });
    
    blob = await writeXlsxFile(sheetsData, { sheets: names });
  }

  return blob;
}
