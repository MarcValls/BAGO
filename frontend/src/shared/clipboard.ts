export interface ClipboardPayload {
  text: string;
  imageDataUrl: string;
  imageMimeType: string;
  imageBytes: number;
  error: string;
}

export const MAX_CLIPBOARD_IMAGE_BYTES = 8 * 1024 * 1024;
export const EMPTY_CLIPBOARD: ClipboardPayload = { text: '', imageDataUrl: '', imageMimeType: '', imageBytes: 0, error: '' };

function estimatedDataUrlBytes(value: string): number {
  const payload = value.split(',', 2)[1] || '';
  return Math.floor(payload.length * 3 / 4);
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('No se pudo leer la imagen del portapapeles'));
    reader.readAsDataURL(blob);
  });
}

export async function readClipboardPayload(): Promise<ClipboardPayload> {
  const electron = typeof window === 'undefined' ? undefined : window.bagoElectron;
  if (electron?.readClipboardPayload) {
    const payload = await electron.readClipboardPayload();
    const imageDataUrl = String(payload?.imageDataUrl || '');
    const imageBytes = Number(payload?.imageBytes || estimatedDataUrlBytes(imageDataUrl));
    const tooLarge = imageBytes > MAX_CLIPBOARD_IMAGE_BYTES;
    return {
      text: String(payload?.text || ''),
      imageDataUrl: tooLarge ? '' : imageDataUrl,
      imageMimeType: tooLarge ? '' : String(payload?.imageMimeType || ''),
      imageBytes,
      error: tooLarge ? 'La imagen supera el límite seguro de 8 MB' : String(payload?.error || ''),
    };
  }
  const clipboard = typeof navigator === 'undefined' ? undefined : navigator.clipboard;
  if (!clipboard) return EMPTY_CLIPBOARD;
  let text = '';
  let imageDataUrl = '';
  let imageMimeType = '';
  try {
    if (clipboard.read) {
      const items = await clipboard.read();
      for (const item of items) {
        if (!text && item.types.includes('text/plain')) text = await (await item.getType('text/plain')).text();
        const imageType = item.types.find((type) => type.startsWith('image/'));
        if (!imageDataUrl && imageType) {
          imageMimeType = imageType;
          const blob = await item.getType(imageType);
          if (blob.size > MAX_CLIPBOARD_IMAGE_BYTES) {
            return { text, imageDataUrl: '', imageMimeType: '', imageBytes: blob.size, error: 'La imagen supera el límite seguro de 8 MB' };
          }
          imageDataUrl = await blobToDataUrl(blob);
        }
      }
    } else if (clipboard.readText) {
      text = await clipboard.readText();
    }
  } catch {
    try { text = await clipboard.readText(); } catch { return EMPTY_CLIPBOARD; }
  }
  return { text, imageDataUrl, imageMimeType, imageBytes: estimatedDataUrlBytes(imageDataUrl), error: '' };
}

export function clipboardHasContent(payload: ClipboardPayload): boolean {
  return Boolean(payload.text || payload.imageDataUrl);
}

export function clipboardLabel(payload: ClipboardPayload): string {
  if (payload.error && !payload.text && !payload.imageDataUrl) return 'No se puede pegar: imagen demasiado grande';
  if (payload.text && payload.imageDataUrl) return 'Pegar texto e imagen';
  if (payload.imageDataUrl) return 'Pegar captura o imagen';
  return 'Pegar texto';
}
