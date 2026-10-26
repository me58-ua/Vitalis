import riskIcon from '../assets/figma/imgContainer3.svg';
import videoIcon from '../assets/figma/imgContainer5.svg';
import chatIcon from '../assets/figma/imgContainer7.svg';
import arrow from '../assets/figma/imgContainer6.svg';

export function BenefitCards() {
  return <section id="servicios" className="benefits section-container" aria-labelledby="benefits-heading">
    <div className="section-intro"><h2 id="benefits-heading">Prestación de Atención Inteligente</h2>
      <p>Herramientas para conocer mejor tu salud y facilitar la comunicación entre pacientes y profesionales.</p></div>
    <div className="benefit-grid">
      <article className="benefit-card risk-card"><div className="benefit-icon"><img src={riskIcon} alt="" /></div>
        <h3>Detección de <br />Riesgos</h3><p>Comprende cómo tus hábitos y antecedentes se relacionan con tu salud. Consulta evaluaciones orientativas calculadas a partir de la información que compartes.</p>
        <div className="benefit-note">Información para acompañarte.<br /><strong>No sustituye una valoración médica.</strong></div>
      </article>
      <article className="benefit-card video-card"><div className="benefit-icon"><img src={videoIcon} alt="" /></div>
        <h3>Teleconsulta</h3><p>Comunícate con tu profesional a través de una videollamada vinculada a tu cita confirmada, dentro de su horario de acceso.</p>
        <a className="benefit-link" href="#teleconsultas">Más información <img src={arrow} alt="" /></a>
      </article>
      <article className="benefit-card chat-card"><div className="benefit-icon"><img src={chatIcon} alt="" /></div>
        <h3>Mensajería</h3><p>Comparte preguntas y actualizaciones con el profesional de tu cita. El acceso y la disponibilidad del chat dependen del estado y del horario de la consulta.</p>
        <p className="benefit-note">Conversaciones vinculadas<br />a tu atención.</p>
      </article>
    </div>
    <details id="teleconsultas" className="telehealth-info"><summary>¿Cómo funcionan las teleconsultas?</summary>
      <p>Las videollamadas se habilitan para citas de tipo vídeo confirmadas. Solo pueden acceder el paciente y el profesional de la cita, durante la ventana de acceso autorizada por el servidor.</p>
      <p>La reserva y el acceso a consultas se incorporarán en sus pantallas correspondientes.</p>
    </details>
  </section>;
}
