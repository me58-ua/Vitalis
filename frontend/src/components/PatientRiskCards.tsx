import type { PatientRiskItem } from '../types/api';

export const riskNames: Record<string, string> = {
  bmi: 'Índice de masa corporal', audit_c: 'Consumo de alcohol', tobacco: 'Tabaco', sedentary: 'Sedentarismo',
  family_diabetes: 'Antecedentes de diabetes', family_cancer: 'Antecedentes de cáncer', family_cardiovascular: 'Antecedentes cardiovasculares',
  family_huntington: 'Antecedentes de Huntington', family_other: 'Otros antecedentes familiares',
  family_hypertension: 'Antecedentes de hipertensión', family_high_cholesterol: 'Antecedentes de colesterol alto',
  family_stroke: 'Antecedentes de ictus', family_osteoporosis: 'Antecedentes de osteoporosis',
  family_cystic_fibrosis: 'Antecedentes de fibrosis quística', family_sickle_cell_disease: 'Antecedentes de enfermedad de células falciformes',
  family_familial_hypercholesterolemia: 'Antecedentes de hipercolesterolemia familiar',
};
const categories: Record<string, string> = {
  underweight: 'Bajo peso', healthy: 'Intervalo saludable', overweight: 'Sobrepeso', obesity: 'Obesidad',
  positive_screen: 'Cribado positivo', lower_screen: 'Por debajo del umbral de cribado', none: 'Sin consumo registrado',
  low: 'Consumo bajo', moderate: 'Consumo moderado', high: 'Consumo alto', active: 'Actividad suficiente',
  low_activity: 'Actividad baja', very_low_activity: 'Actividad muy baja', inactive: 'Sin actividad registrada', family_history: 'Antecedentes registrados',
};
export const trendNames: Record<string, string> = { improving: 'Mejora', worsening: 'Empeoramiento', stable: 'Estable', insufficient_history: 'Historial insuficiente' };
const missingNames: Record<string, string> = {
  height_cm: 'altura', weight_kg: 'peso', birth_date: 'fecha de nacimiento', adult_age: 'edad adulta', valid_measurements: 'medidas válidas',
  frequency: 'frecuencia de consumo', quantity: 'cantidad consumida', binge: 'consumo intensivo', sex_at_birth: 'sexo al nacer', valid_scores: 'respuestas válidas de AUDIT-C',
  tobacco_logs: 'registros recientes de tabaco', three_exercise_logs: 'al menos tres registros recientes de ejercicio',
};
export function riskValue(model: string, value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return 'Valor no disponible';
  const unit = model === 'bmi' ? 'kg/m²' : model === 'audit_c' ? 'puntos AUDIT-C' : model === 'tobacco' ? 'cigarrillos/día' : model === 'sedentary' ? 'min/semana' : value === 1 ? 'antecedente' : 'antecedentes';
  return `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(value)} ${unit}`;
}
export function PatientRiskCards({ results, onHistory }: { results: PatientRiskItem[]; onHistory: (model: string) => void }) {
  const primary = ['bmi', 'audit_c', 'tobacco', 'sedentary'];
  const models = [...primary, ...results.map(item => item.model).filter(model => !primary.includes(model))];
  return <div className="patient-risk-grid">{[...new Set(models)].map(model => {
    const item = results.find(result => result.model === model);
    return <article className={`patient-risk-card ${item?.status === 'ok' ? `risk-${item.alert_level}` : ''}`} key={model}>
      <h3>{riskNames[model] ?? 'Evaluación adicional'}</h3>
      {!item ? <p>Evaluación no disponible.</p> : item.status === 'insufficient_data' ? <><p>Datos insuficientes</p>{model === 'bmi' && <p>No se puede calcular el BMI porque faltan datos.</p>}<p className="field-help">Falta información: {(item.missing ?? []).map(field => missingNames[field] ?? 'dato requerido por el servidor').join(', ') || 'completa tus datos de salud'}.</p></>
        : item.status === 'error' ? <p role="alert">No se ha podido completar esta evaluación.</p>
          : <><p className="patient-risk-value">{riskValue(model, item.metric_value)}</p><p>{item.category ? categories[item.category] ?? 'Clasificación no disponible' : 'Sin clasificación'}</p>
            <p className="patient-risk-explanation">{item.explanation}</p>
            {item.source.startsWith('https://') && <p><a href={item.source} target="_blank" rel="noreferrer">Consultar fuente de salud</a></p>}
            <span className="patient-trend">{trendNames[item.trend] ?? 'Tendencia no disponible'}</span></>}
      <button className="text-button" onClick={() => onHistory(model)}>Ver historial</button>
      <p className="patient-disclaimer">Evaluación orientativa; no sustituye una consulta médica.</p>
    </article>;
  })}</div>;
}
