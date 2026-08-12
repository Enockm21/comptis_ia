import type { Conflict } from '../lib/reconciliation'

interface Props {
  conflict: Conflict
  index: number
  total: number
  onDecide: (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => void
  deciding: boolean
}

export default function ConflictReview({ conflict, index, total, onDecide, deciding }: Props) {
  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <p>Conflit {index} / {total}</p>
      <p>Raison : {conflict.raison} (score {conflict.composite_score.toFixed(2)})</p>
      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
          <h3>Transaction</h3>
          <p>Montant : {conflict.transaction.montant}</p>
          <p>Date : {conflict.transaction.date}</p>
          <p>Libellé : {conflict.transaction.libelle}</p>
        </div>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
          <h3>Facture candidate</h3>
          {conflict.facture ? (
            <>
              <p>Montant : {conflict.facture.montant}</p>
              <p>Date : {conflict.facture.date}</p>
              <p>Fournisseur : {conflict.facture.fournisseur}</p>
            </>
          ) : (
            <p>Aucune facture candidate</p>
          )}
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <button disabled={deciding} onClick={() => onDecide('confirmer')}>Confirmer</button>
        <button disabled={deciding} onClick={() => onDecide('ecart_accepte')} style={{ marginLeft: 8 }}>
          Écart accepté
        </button>
        <button disabled={deciding} onClick={() => onDecide('rejeter')} style={{ marginLeft: 8, color: 'red' }}>
          Rejeter
        </button>
      </div>
    </div>
  )
}
