import { Link } from "react-router-dom";
import {
  ArrowRight,
  Camera,
  ScanLine,
  Sprout,
} from "lucide-react";
export default function Home() {
  return (
    <main className="wrap home">
      <section className="hero">
        <div>
          <h1>
            Descubre el punto de <em>maduración</em> de tu mango.
          </h1>
          <p className="intro">
            Analiza imágenes de mangos mediante inteligencia artificial y conoce
            su estado de maduración en segundos.
          </p>
          <div className="actions">
            <Link className="primary btn" to="/analizar">
              Analizar un mango <ArrowRight size={17} />
            </Link>
            <Link className="btn" to="/modelos">
              Conocer los modelos
            </Link>
          </div>
        </div>
        <img className="hero-photo" src="/maduro.jpg" alt="Mango maduro fotografiado en estudio" />
      </section>
      <section className="how">
        <h2>Cómo funciona</h2>
        <div className="steps">
          {[
            [
              Camera,
              "Captura o sube una imagen",
              "Usa la cámara o elige una fotografía de tu dispositivo.",
            ],
            [
              ScanLine,
              "Analiza con IA",
              "Selecciona un modelo y confirma el análisis.",
            ],
            [
              Sprout,
              "Consulta la maduración",
              "Explora la clase predicha y sus probabilidades.",
            ],
          ].map(([Icon, title, desc], i) => {
            const Symbol = Icon as typeof Camera;
            return (
              <article key={i}>
                <div className="step-icon">
                  <Symbol />
                </div>
                <div>
                  <h3>{String(title)}</h3>
                  <p>{String(desc)}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>
      <section className="stages">
        <h2>Estados de maduración</h2>
        <p>
          Categorías visuales del dataset. La calidad y la aptitud para el
          consumo requieren una evaluación propia.
        </p>
        <div className="stage-grid">
          {[
            ["verde", "Verde", "unripe", "Predominan los tonos verdes."],
            [
              "ambar",
              "En maduración",
              "partially_ripe",
              "Aparecen tonos amarillos junto al verde.",
            ],
            [
              "maduro",
              "Maduro",
              "ripe",
              "Predominan los tonos dorados o anaranjados.",
            ],
          ].map(([img, title, id, desc]) => (
            <article key={id}>
              <img
                loading="lazy"
                src={"/" + img + ".jpg"}
                alt={"Mango de referencia clasificado como " + title}
              />
              <h3>
                <span className={"dot " + id} />
                {title}
              </h3>
              <p>{desc}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
