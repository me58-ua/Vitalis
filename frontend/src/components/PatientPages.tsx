export function PatientPages({ page, size, total, onPage }: { page: number; size: number; total: number; onPage: (page: number) => void }) {
  return <nav className="patients-pagination" aria-label="Paginación"><button disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(total / size))}</span><button disabled={page * size >= total} onClick={() => onPage(page + 1)}>Siguiente</button></nav>;
}
