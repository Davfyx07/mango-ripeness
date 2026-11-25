import { LoaderCircle, ArrowRight } from "lucide-react";
import { classes, type PredictionResponse, type ModelInfo } from "../types/api";
import { labels, percent } from "../utils/data";
export default function Results({
  result,
  model,
  busy,
  reset,
  cancel,
  hasImage,
}: {
  result: PredictionResponse | null;
  model?: ModelInfo;
  busy: boolean;
  reset: () => void;
  cancel: () => void;
  hasImage: boolean;
}) {
  return (
    <section className="panel results" aria-live="polite">
      <h2>Resultado del análisis</h2>
      {busy ? (
        <div className="empty">
          <LoaderCircle className="spin" />
          <h2>Analizando la imagen</h2>
          <p>El modelo está evaluando la fotografía.</p>
          <button onClick={cancel}>Cancelar espera</button>
        </div>
      ) : result ? (
        <>
          <h2 className={result.label}>{labels[result.label]}</h2>
          <div className="confidence">{percent(result.confidence)} <small>Confianza</small></div>
          <p>
            Confianza del modelo para esta fotografía. El resultado puede ser
            incorrecto.
          </p>
          <h3>Distribución de probabilidades</h3>
          {classes.map((c) => (
            <div className="measure" key={c}>
              <div className="row">
                <span>{labels[c]}</span>
                <b>{percent(result.probabilities[c])}</b>
              </div>
              <div className="track">
                <i
                  className={c}
                  style={{ width: 100 * result.probabilities[c] + "%" }}
                />
              </div>
            </div>
          ))}
          <dl>
            <dt>Modelo utilizado</dt>
            <dd>{model?.nombre ?? result.model}</dd>
            <dt>Arquitectura</dt>
            <dd>{model?.familia}</dd>
            <dt>Tiempo de inferencia</dt>
            <dd>{result.inference_ms} ms</dd>
            <dt>Precisión experimental</dt>
            <dd>{model && percent(model.accuracy_test)}</dd>
          </dl>
          <button onClick={reset}>
            Analizar otra imagen <ArrowRight />
          </button>
        </>
      ) : (
        <div className="empty">
          <h2>{hasImage ? "Fotografía preparada" : "A la espera de una fotografía"}</h2>
          <p>
            {hasImage ? "Selecciona un modelo disponible y pulsa Analizar mango para ver las tres probabilidades." : "Fotografía un solo mango, con buena luz y enfocado, o elige una imagen de ejemplo."}
          </p>
        </div>
      )}
    </section>
  );
}
