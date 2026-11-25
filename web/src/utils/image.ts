export const accept = "image/jpeg,image/png,image/webp,.mpo";
export function checkDimensions(width: number, height: number) {
  if (width * height > 50_000_000)
    throw Error("La imagen supera los 50 millones de píxeles.");
  if (Math.max(width, height) > 8 * Math.min(width, height))
    throw Error("La proporción máxima permitida es 8:1.");
}
export async function validate(file: File) {
  if (!file.size) throw Error("El archivo está vacío.");
  if (file.size > 25 * 1024 * 1024 - 8192)
    throw Error(
      "Selecciona un archivo más pequeño. La petición completa debe caber en 25 MB.",
    );
  const bytes = new Uint8Array(await file.slice(0, 24).arrayBuffer());
  const text = String.fromCharCode(...bytes);
  const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
  const png = [137, 80, 78, 71, 13, 10, 26, 10].every((v, i) => bytes[i] === v);
  if (!(
    jpeg ||
    png ||
    (text.startsWith("RIFF") && text.slice(8, 12) === "WEBP")
  ))
    throw Error(
      "Formato incompatible. Si tu foto es HEIC, expórtala como JPEG o PNG.",
    );
  if (png && bytes.length >= 24) {
    const view = new DataView(bytes.buffer);
    checkDimensions(view.getUint32(16), view.getUint32(20));
  }
}
