import { useCallback, useEffect, useRef, useState } from "react";
import {
  Camera as CameraIcon,
  SwitchCamera,
  X,
  RotateCcw,
  Check,
} from "lucide-react";
import { useObjectUrl } from "../hooks/useObjectUrl";
interface Props {
  onClose: () => void;
  onConfirm: (f: File) => void;
}
function explain(e: unknown) {
  const name = e instanceof DOMException ? e.name : "";
  return (
    (
      {
        NotAllowedError: "Permite el acceso a la cámara desde tu navegador.",
        NotFoundError: "No encontramos una cámara conectada.",
        NotReadableError:
          "La cámara está ocupada. Cierra otras aplicaciones e inténtalo de nuevo.",
      } as Record<string, string>
    )[name] ?? "No se pudo iniciar la cámara en este dispositivo."
  );
}
export default function Camera({ onClose, onConfirm }: Props) {
  const dialog = useRef<HTMLDialogElement>(null),
    video = useRef<HTMLVideoElement>(null),
    stream = useRef<MediaStream | null>(null),
    token = useRef(0);
  const [device, setDevice] = useState(""),
    [devices, setDevices] = useState<MediaDeviceInfo[]>([]),
    [shot, setShot] = useState<File | null>(null),
    [error, setError] = useState(""),
    [ready, setReady] = useState(false),
    [attempt, setAttempt] = useState(0);
  const preview = useObjectUrl(shot);
  const stop = useCallback(() => {
    token.current++;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  useEffect(() => {
    if (shot) return;
    const version = ++token.current;
    setReady(false);
    setError("");
    async function start() {
      if (!window.isSecureContext) {
        setError(
          "La cámara en vivo requiere HTTPS o localhost. También puedes subir una imagen.",
        );
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(
          "Este navegador no admite cámara en vivo. Usa el selector del dispositivo.",
        );
        return;
      }
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: device
            ? { deviceId: { exact: device } }
            : { facingMode: { ideal: "environment" } },
        });
        if (version !== token.current) {
          media.getTracks().forEach((t) => t.stop());
          return;
        }
        stream.current = media;
        if (video.current) video.current.srcObject = media;
        const list = await navigator.mediaDevices
          .enumerateDevices()
          .catch(() => []);
        if (version === token.current)
          setDevices(list.filter((d) => d.kind === "videoinput"));
      } catch (e) {
        if (version === token.current) setError(explain(e));
      }
    }
    void start();
    return stop;
  }, [device, shot, attempt, stop]);
  function capture() {
    const v = video.current;
    if (!v?.videoWidth) return;
    const version = token.current;
    try {
      const c = document.createElement("canvas");
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      const ctx = c.getContext("2d");
      if (!ctx) throw Error();
      ctx.drawImage(v, 0, 0);
      c.toBlob(
        (blob) => {
          if (version !== token.current) return;
          if (!blob) {
            setError("No se pudo capturar la fotografía.");
            return;
          }
          stop();
          setShot(
            new File([blob], "captura-mango.jpg", { type: "image/jpeg" }),
          );
        },
        "image/jpeg",
        0.94,
      );
    } catch {
      setError("No se pudo capturar la fotografía.");
    }
  }
  return (
    <dialog ref={dialog} onCancel={onClose} aria-labelledby="camera-title">
      <div className="row">
        <h2 id="camera-title">Tomar fotografía</h2>
        <button aria-label="Cerrar cámara" className="icon" onClick={onClose}>
          <X />
        </button>
      </div>
      {shot ? (
        <img className="camera" src={preview} alt="Fotografía capturada" />
      ) : (
        <video
          className="camera"
          ref={video}
          autoPlay
          playsInline
          muted
          onLoadedData={() => setReady(true)}
        />
      )}
      {error && <p role="alert">{error}</p>}
      <p>Centra un mango y procura que tenga buena iluminación.</p>
      <div className="actions">
        {shot ? (
          <>
            <button onClick={() => setShot(null)}>
              <RotateCcw />
              Repetir
            </button>
            <button className="primary" onClick={() => onConfirm(shot)}>
              <Check />
              Usar fotografía
            </button>
          </>
        ) : (
          <>
            <button className="primary" disabled={!ready} onClick={capture}>
              <CameraIcon />
              Capturar
            </button>
            {devices.length > 1 && (
              <button
                onClick={() => {
                  const current = stream.current
                    ?.getVideoTracks()[0]
                    ?.getSettings().deviceId;
                  setDevice(
                    devices[
                      (devices.findIndex((d) => d.deviceId === current) + 1) %
                        devices.length
                    ].deviceId,
                  );
                }}
              >
                <SwitchCamera />
                Cambiar cámara
              </button>
            )}
            {error && (
              <button onClick={() => setAttempt((n) => n + 1)}>
                Reintentar
              </button>
            )}
            <label className="file-label">
              Cámara del dispositivo
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onConfirm(f);
                }}
              />
            </label>
          </>
        )}
      </div>
    </dialog>
  );
}
