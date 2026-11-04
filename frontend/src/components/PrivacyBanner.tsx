import lock from '../assets/figma/imgContainer11.svg';
import shield from '../assets/figma/imgContainer16.svg';
import access from '../assets/figma/imgContainer15.svg';

export function PrivacyBanner() {
  return <section id="privacidad" className="privacy-section section-container" aria-labelledby="privacy-heading">
    <div className="privacy-banner"><div className="privacy-copy">
      <span className="privacy-eyebrow"><img src={lock} alt="" />PRIVACIDAD Y CONTROL</span>
      <h2 id="privacy-heading">Tu salud, mejor comprendida. Tus datos, protegidos.</h2>
      <p>Conoce mejor tu salud e identifica posibles riesgos a partir de tu información y tus hábitos, con la tranquilidad de que tus datos se tratan de forma segura y confidencial.</p>
      <div className="privacy-facts"><span><img src={access} alt="" />Acceso autenticado</span><span><img src={lock} alt="" />Controles de consentimiento</span></div>
    </div><div className="privacy-visual" aria-hidden="true"><div className="shield-circle"><img src={shield} alt="" /></div>
      <span className="privacy-tag tag-top">Control de acceso</span><span className="privacy-tag tag-bottom">Tú decides qué compartes</span>
    </div></div>
  </section>;
}
