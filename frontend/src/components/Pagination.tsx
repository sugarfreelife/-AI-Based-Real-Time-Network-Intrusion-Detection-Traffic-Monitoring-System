import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Pagination({ page, pageSize, total, onPage, onPageSize }: {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  onPageSize: (size: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  return <div className="pagination-row">
    <span className="range-label">{first}–{last} <span>of</span> {total}</span>
    <div className="pagination-controls">
      <label htmlFor="page-size">Rows <select id="page-size" value={pageSize} onChange={(event) => onPageSize(Number(event.target.value))}><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label>
      <span className="page-number">Page {Math.min(page, pages)} of {pages}</span>
      <button className="icon-button pagination-button" type="button" aria-label="Previous page" title="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={17} /></button>
      <button className="icon-button pagination-button" type="button" aria-label="Next page" title="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight size={17} /></button>
    </div>
  </div>
}
