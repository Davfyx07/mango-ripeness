import { evaluated, percent } from "../utils/data";
export default function Models() {
  return (
    <main className="wrap page">
      <h1>Modelos de IA</h1>
      <p className="intro">
        Cinco arquitecturas evaluadas para interpretar la maduración del mango.
      </p>
      <section className="model-table">
        <h2>Rendimiento de los modelos</h2>
        <p>
          Resultados obtenidos durante la evaluación de 114 fotografías de prueba.
          El rendimiento puede variar según las condiciones de captura de la imagen
        </p>
        {evaluated.map((m) => (
          <article key={m.id} className={m.familia === "CNN" ? "cnn" : "transformer"}>
            <div>
              <small className="family-tag">{m.familia}</small>
              <h3>{m.nombre}</h3>
            </div>
            <div>
              <strong className="score">{percent(m.accuracy_test)}</strong>
              <div className="track">
                <i style={{ width: m.accuracy_test * 100 + "%" }} />
              </div>
            </div>
          </article>
        ))}
      </section>
      <div className="family-grid">
        <section>
          <h2>Redes convolucionales</h2>
          <p>
            ResNet50, EfficientNet-B0 y ConvNeXt-Tiny combinan rasgos locales de
            la imagen para reconocer patrones de color, textura y forma.
          </p>
        </section>
        <section>
          <h2>Transformers visuales</h2>
          <p>
            ViT-Small y Swin-Tiny usan atención para relacionar regiones del
            mango. La confianza de una predicción individual aparece al analizar
            tu imagen.
          </p>
        </section>
      </div>
    </main>
  );
}
